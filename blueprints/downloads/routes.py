from flask import Blueprint, render_template, request, redirect, flash, send_from_directory, current_app
import yt_dlp
import os
import json
import shutil
import re
import logging
import unicodedata
from models import DownloadUrl
from extensions import db

download_bp = Blueprint('downloads', __name__, url_prefix='', template_folder='templates')

# Cấu hình logging
logging.basicConfig(level=logging.DEBUG)

# Các tùy chọn format
FORMATS = {
    '1080p': 'bestvideo[height<=1080]+bestaudio/best',
    '720p': 'bestvideo[height<=720]+bestaudio/best',
    'audio': 'bestaudio',
    'default': 'best'
}

# Hàm làm sạch tên file
def safe_filename(filename):
    filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
    max_filename_length = 255
    if len(filename) > max_filename_length:
        filename = filename[:max_filename_length]
    logging.debug(f"Safe filename: {filename}")
    return filename


@download_bp.route('/')
def index():
    formats = FORMATS.keys()
    
    # Lấy thông số phân trang từ request
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Phân trang với truy vấn cơ sở dữ liệu
    pagination = DownloadUrl.query.order_by(DownloadUrl.created_at.desc()).paginate(page=page, per_page=per_page)
    urls = pagination.items  # Danh sách URL của trang hiện tại
    total_pages = pagination.pages

    # Tính toán start_page và end_page cho việc phân trang
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)

    return render_template(
        'downloads/downloads.html',
        formats=formats,
        urls=urls,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        start_page=start_page,
        end_page=end_page
    )

@download_bp.route('/download_format_id', methods=['POST'])
def download_format_id():
    url = request.form.get('url')
    format_id = request.form.get('format_id')
    merge_audio = request.form.get('merge_audio') == 'yes'

    if not url or not format_id:
        flash("❗ Thiếu URL hoặc định dạng.")
        return redirect('/')

    format_str = f"{format_id}+bestaudio/best" if merge_audio else format_id
    cookies_file = 'cookies.txt'
    output_path = current_app.config.get('OUTPUT_PATH')

    if not os.path.exists(cookies_file):
        flash("❗ Không tìm thấy file cookies.txt. Vui lòng xuất cookies từ trình duyệt.")
        return redirect('/')

    ydl_opts = {
        'format': format_str,
        'outtmpl': os.path.join(output_path, '%(title).100s.%(ext)s'),  # Giới hạn độ dài tiêu đề
        'quiet': False,
        'cookies': cookies_file,
    }

    try:
        logging.debug(f"YDL options: {ydl_opts}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        flash(f"✅ Đã tải thành công video và audio {'(đã gộp video và audio)' if merge_audio else ''}")
    except Exception as e:
        flash(f"❌ Lỗi khi tải: {e}")
        logging.error(f"Error downloading: {e}")

    return redirect('/')

@download_bp.route('/batch')
def batch_download():
    # Lấy danh sách URL chưa tải (status='pending')
    urls = DownloadUrl.query.filter_by(status='pending').all()

    cookies_file = os.path.join('configs', 'cookies.txt')
    output_path = current_app.config.get('OUTPUT_PATH')

    if not os.path.exists(cookies_file):
        flash("❗ Không tìm thấy file cookies.txt.")
        return redirect('/')

    downloaded_titles = []

    for download_url in urls:
        url = download_url.url
        try:
            logging.debug(f"Processing URL: {url}")

            with yt_dlp.YoutubeDL({'quiet': True, 'cookies': cookies_file}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                title = info.get('title', 'Không rõ tiêu đề')

            # Tìm format tốt nhất
            best_video = sorted(
                [f for f in formats if f.get('vcodec') != 'none' and f.get('ext') == 'mp4'],
                key=lambda x: x.get('height') or 0,
                reverse=True
            )
            best_audio = sorted(
                [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('ext') == 'm4a'],
                key=lambda x: x.get('abr') or 0,
                reverse=True
            )
            best_video_format = best_video[0] if best_video else None
            best_audio_format = best_audio[0] if best_audio else None

            if best_video_format and best_audio_format:
                format_str = f"{best_video_format['format_id']}+{best_audio_format['format_id']}"
                flash(f"📦 Ghép video {best_video_format['height']}p và audio {best_audio_format['abr']}kdownload_bps.")
            elif best_video_format:
                format_str = best_video_format['format_id']
                flash(f"📹 Video có sẵn audio, dùng định dạng {format_str}")
            else:
                format_str = 'best'
                flash("⚠️ Không tìm được định dạng mp4 phù hợp, dùng fallback 'best'.")

            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(output_path, '%(id)s.%(ext)s'),
                'quiet': False,
                'merge_output_format': 'mp4',
                'cookies': cookies_file,
                'postprocessors': [
                    {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}
                ],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            downloaded_titles.append(title)
            logging.debug(f"Downloaded {title}")

            # Cập nhật trạng thái thành công
            download_url.status = 'completed'
            download_url.title = title
            db.session.commit()

        except Exception as e:
            flash(f"❌ Lỗi với {url}: {e}")
            logging.error(f"Error with URL {url}: {e}")
            # Cập nhật trạng thái lỗi
            download_url.status = 'failed'
            db.session.commit()

    if downloaded_titles:
        flash("✅ Đã tải xong các video:")
        for title in downloaded_titles:
            flash(f"• {title}")
    else:
        flash("⚠️ Không có video nào được tải.")

    return redirect('/')

@download_bp.route('/downloads/<filename>')
def serve_file(filename):
    output_path = current_app.config.get('OUTPUT_PATH')
    full_path = os.path.join(output_path, filename)
    if not os.path.exists(full_path):
        logging.error(f"File not found: {full_path}")
        return f"File not found: {filename}", 404
    logging.debug(f"Serving file: {filename}")
    return send_from_directory(output_path, filename)


@download_bp.route('/formats', methods=['POST'])
def get_formats():
    url = request.form.get('url')

    if not url:
        return {'error': 'URL không được để trống'}, 400

    cookies_file = 'cookies.txt'

    if not os.path.exists(cookies_file):
        return {'error': 'File cookies.txt không tìm thấy. Vui lòng xuất cookies từ trình duyệt.'}, 400

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'cookies': cookies_file}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            format_list = []
            for f in formats:
                format_list.append({
                    'id': f.get('format_id'),
                    'ext': f.get('ext'),
                    'resolution': f.get('resolution') or f.get('height'),
                    'abr': f.get('abr'),
                    'filesize': f.get('filesize'),
                    'vcodec': f.get('vcodec'),
                    'acodec': f.get('acodec')
                })
            # Trả thêm title
            title = info.get('title', '')

            return {'formats': format_list, 'title': title}
    except Exception as e:
        logging.error(f"Error fetching formats: {e}")
        return {'error': str(e)}, 500


@download_bp.route('/batch/download', methods=['POST'])
def batch_download_selected():
    selected_ids = request.form.getlist('selected_urls')
    logging.debug(f"📝 Danh sách ID được chọn: {selected_ids}")
    print(f"📝 [DEBUG] selected_ids = {selected_ids}")

    if not selected_ids:
        flash("⚠️ Bạn chưa chọn URL nào.")
        return redirect('/downloads')

    cookies_file = 'cookies.txt'
    output_path = current_app.config.get('OUTPUT_PATH')

    if not os.path.exists(cookies_file):
        flash("❗ Không tìm thấy file cookies.txt.")
        return redirect('/downloads')

    urls = DownloadUrl.query.filter(DownloadUrl.id.in_(selected_ids)).all()
    logging.debug(f"🔍 Truy vấn {len(urls)} URL từ DB.")
    print(f"🔍 [DEBUG] Found {len(urls)} urls from DB.")

    downloaded_titles = []

    for download_url in urls:
        url = download_url.url
        print(f"🚀 [DEBUG] Bắt đầu tải: {url}")
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'cookies': cookies_file}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                title = info.get('title', 'Không rõ tiêu đề')
                print(f"📄 [DEBUG] Tên video: {title}, số định dạng: {len(formats)}")

            # Tìm định dạng tốt nhất
            best_video = sorted(
                [f for f in formats if f.get('vcodec') != 'none' and f.get('ext') == 'mp4'],
                key=lambda x: x.get('height') or 0,
                reverse=True
            )
            best_audio = sorted(
                [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('ext') == 'm4a'],
                key=lambda x: x.get('abr') or 0,
                reverse=True
            )

            best_video_format = best_video[0] if best_video else None
            best_audio_format = best_audio[0] if best_audio else None

            if best_video_format and best_audio_format:
                format_str = f"{best_video_format['format_id']}+{best_audio_format['format_id']}"
            elif best_video_format:
                format_str = best_video_format['format_id']
            else:
                format_str = 'best'

            print(f"🎯 [DEBUG] Format được chọn: {format_str}")

            ydl_opts = {
                'format': format_str,
                'outtmpl': os.path.join(output_path, '%(id)s.%(ext)s'),
                'quiet': False,
                'merge_output_format': 'mp4',
                'cookies': cookies_file,
                'postprocessors': [
                    {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}
                ],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                print(f"✅ [DEBUG] Đã tải xong: {title}")

            downloaded_titles.append(title)
            download_url.status = 'completed'
            download_url.title = title
            db.session.commit()

        except Exception as e:
            logging.error(f"❌ Lỗi khi tải {url}: {e}")
            print(f"❌ [ERROR] {url}: {e}")
            flash(f"❌ Lỗi khi tải {url}: {e}")
            download_url.status = 'failed'
            db.session.commit()

    if downloaded_titles:
        flash("✅ Đã tải các video:")
        for title in downloaded_titles:
            flash(f"• {title}")
            print(f"📦 [DONE] {title}")
    else:
        flash("⚠️ Không có video nào được tải.")
        print("⚠️ [DEBUG] Không có video nào được tải.")

    return redirect('/downloads')

@download_bp.route('/download_format_only', methods=['POST'])
def download_format_only():
    url = request.form.get('url')
    format_id = request.form.get('format_id')

    if not url or not format_id:
        flash("❗ Thiếu URL hoặc định dạng.")
        return redirect('/')

    cookies_file = 'cookies.txt'
    output_path = current_app.config.get('OUTPUT_PATH')

    if not os.path.exists(cookies_file):
        flash("❗ Không tìm thấy file cookies.txt. Vui lòng xuất cookies từ trình duyệt.")
        return redirect('/')

    ydl_opts = {
        'format': format_id,
        'outtmpl': os.path.join(output_path, '%(title).100s.%(ext)s'),
        'quiet': False,
        'cookies': cookies_file,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        flash(f"✅ Đã tải thành công định dạng {format_id}")
    except Exception as e:
        flash(f"❌ Lỗi khi tải: {e}")
        logging.error(f"Error downloading format only: {e}")

    return redirect('/')
