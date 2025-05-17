from flask import Blueprint, request, jsonify, redirect, flash, render_template
from models import DownloadUrl
from extensions import db
import re
import yt_dlp

url_manager_bp = Blueprint('url_manager', __name__, url_prefix='/url', template_folder='templates')

def json_response(success, message=None, data=None, status=200):
    return jsonify({'success': success, 'message': message, 'data': data}), status

def is_valid_url(url):
    regex = re.compile(r'^(http|https)://[^\s/$.?#].[^\s]*$')
    return re.match(regex, url) is not None

@url_manager_bp.route('/manage', methods=['GET'])
def manage_urls():
    urls = DownloadUrl.query.all()
    return render_template('urls/urls.html', urls=urls)


def is_playlist(info):
    return info.get('_type') == 'playlist'

def extract_video_info(entry):
    video_url = entry.get('url') or entry.get('id')
    if video_url and not video_url.startswith('http'):
        video_url = f"https://www.youtube.com/watch?v={video_url}"
    title = entry.get('title', 'Không tìm thấy tiêu đề')
    return video_url, title


# Lấy title tự động từ yt_dlp
@url_manager_bp.route('/fetch_title', methods=['POST'])
def fetch_title():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url or not is_valid_url(url):
        return json_response(False, "❌ URL không hợp lệ.", status=400)

    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'extract_flat': True,  # quan trọng để lấy danh sách playlist nhanh
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Kiểm tra nếu là playlist
            if info.get('_type') == 'playlist':
                # Lấy danh sách video URLs trong playlist
                entries = info.get('entries', [])
                playlist_urls = []
                for entry in entries:
                    # entry có thể là dict hoặc id, lấy id hoặc url
                    video_url = entry.get('url') or entry.get('id')
                    if video_url:
                        # Xây dựng url đầy đủ nếu chỉ có id
                        if not video_url.startswith('http'):
                            # mặc định YouTube
                            video_url = f"https://www.youtube.com/watch?v={video_url}"
                        playlist_urls.append(video_url)

                return json_response(True, "✅ Đây là playlist.", data={
                    'is_playlist': True,
                    'playlist_title': info.get('title', 'Playlist không có tên'),
                    'playlist_urls': playlist_urls
                })

            # Nếu không phải playlist, trả title video
            title = info.get('title', 'Không tìm thấy tiêu đề')
    except Exception as e:
        return json_response(False, f"❌ Không thể lấy tiêu đề. Lỗi: {str(e)}", status=500)

    return json_response(True, "✅ Đã lấy tiêu đề thành công.", data={
        'is_playlist': False,
        'title': title
    })


@url_manager_bp.route('/add', methods=['POST'])
def add_url():
    url = request.form.get('url', '').strip()
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'None').strip()
    fetch_playlist = request.form.get('fetch_playlist') == 'on'

    print(f"[DEBUG] Thêm URL mới: url={url}, title={title}, category={category}, fetch_playlist={fetch_playlist}")

    if not url or not is_valid_url(url):
        flash("❌ URL không hợp lệ.")
        return redirect('/url/manage')

    try:
        ydl_opts = {'quiet': True, 'skip_download': True, 'extract_flat': True}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if is_playlist(info):
                if not fetch_playlist:
                    flash("❌ Đây là playlist. Hãy chọn tùy chọn 'Lấy playlist' nếu muốn thêm toàn bộ video.")
                    return redirect('/url/manage')

                count_added = 0
                for entry in info.get('entries', []):
                    video_url, video_title = extract_video_info(entry)
                    if not video_url:
                        continue
                    
                    # Kiểm tra URL đã tồn tại chưa
                    if not DownloadUrl.query.filter_by(url=video_url).first():
                        new_url = DownloadUrl(
                            url=video_url,
                            title=video_title,
                            category=category,
                            status='pending',
                            ratio="Không xác định"
                        )
                        db.session.add(new_url)
                        count_added += 1

                db.session.commit()
                flash(f"✅ Đã thêm {count_added} video từ playlist.")
                return redirect('/url/manage')

            # Nếu không phải playlist (URL đơn lẻ)
            if DownloadUrl.query.filter_by(url=url).first():
                flash("❌ URL đã tồn tại trong danh sách.")
                return redirect('/url/manage')

            title = title or info.get('title', 'Không tìm thấy tiêu đề')
            width = info.get('width')
            height = info.get('height')
            ratio = f"{width}:{height}" if width and height else "Không xác định"

            new_url = DownloadUrl(
                url=url,
                title=title,
                category=category,
                status='pending',
                ratio=ratio
            )
            db.session.add(new_url)
            db.session.commit()

            flash(f"✅ Đã thêm URL thành công với tỉ lệ: {ratio}")
    except yt_dlp.utils.DownloadError:
        flash("❌ Không thể lấy thông tin từ URL. URL không hợp lệ hoặc không được hỗ trợ.")
    except Exception as e:
        print(f"[ERROR] Lỗi khi thêm URL: {e}")
        flash(f"❌ Lỗi khi thêm URL: {e}")

    return redirect('/url/manage')




# Sửa URL
@url_manager_bp.route('/edit', methods=['POST'])
def edit_url():
    data = request.get_json()
    if not data:
        return json_response(False, "Dữ liệu không hợp lệ", 400)

    url_id = data.get('id')
    new_url = data.get('new_url', '').strip()
    new_title = data.get('new_title', '').strip()
    new_category = data.get('new_category', 'None').strip()  # Thêm category mới

    if not url_id or not new_url:
        return json_response(False, "Thiếu id hoặc URL mới", 400)

    try:
        url_id = int(url_id)
    except ValueError:
        return json_response(False, "ID không hợp lệ", 400)

    url_obj = DownloadUrl.query.get(url_id)
    if not url_obj:
        return json_response(False, "Không tìm thấy URL cần sửa", 404)

    url_obj.url = new_url
    if new_title:
        url_obj.title = new_title
    url_obj.category = new_category  # Cập nhật category
    url_obj.status = 'pending'  # reset trạng thái nếu muốn
    db.session.commit()
    return json_response(True, "✅ Đã sửa URL thành công.")


# Xóa URL
@url_manager_bp.route('/delete', methods=['POST'])
def delete_url():
    data = request.get_json()
    if not data:
        return json_response(False, "Dữ liệu không hợp lệ", 400)

    url_id = data.get('id')
    if not url_id:
        return json_response(False, "Thiếu id URL cần xóa", 400)

    try:
        url_id = int(url_id)
    except ValueError:
        return json_response(False, "ID không hợp lệ", 400)

    url_obj = DownloadUrl.query.get(url_id)
    if not url_obj:
        return json_response(False, "Không tìm thấy URL cần xóa", 404)

    db.session.delete(url_obj)
    db.session.commit()
    return json_response(True, "✅ Đã xóa URL thành công.")


