# blueprints/subtitle_downloader/routes.py

from flask import Blueprint, request, render_template, redirect, flash, current_app, send_file, url_for
import os
import yt_dlp

LANGUAGE_MAP = {
    "vi": "Tiếng Việt",
    "en": "English",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
    "ja": "日本語",
    "ko": "한국어",
    "zh-Hans": "中文 (Giản Thể)",
    "zh-Hant": "中文 (Phồn Thể)",
}

subtitle_downloader_bp = Blueprint("subtitle_downloader", __name__, template_folder="templates")

@subtitle_downloader_bp.route("/", methods=["GET", "POST"])
def index():
    available_subs = None
    video_url = ""
    video_title = ""
    downloaded_file = None

    if request.method == "POST":
        video_url = request.form.get("video_url")

        if not video_url:
            flash("❌ Vui lòng nhập URL video!", "danger")
            return redirect(request.url)

        try:
            with yt_dlp.YoutubeDL({}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                video_title = info.get("title", "video")

                subtitles = info.get("subtitles", {})
                auto_captions = info.get("automatic_captions", {})

                all_subs = subtitles.copy()
                for lang, tracks in auto_captions.items():
                    if lang not in all_subs:
                        all_subs[lang] = tracks

                available_subs = {
                    lang: {
                        "name": LANGUAGE_MAP.get(lang, lang),
                        "formats": [track["ext"] for track in tracks]
                    }
                    for lang, tracks in all_subs.items()
                }

        except Exception as e:
            flash(f"❌ Lỗi khi lấy phụ đề: {str(e)}", "danger")

    return render_template("subtitle_downloader/index.html",
                           available_subs=available_subs,
                           video_url=video_url,
                           video_title=video_title,
                           downloaded_file=request.args.get("file"))


@subtitle_downloader_bp.route("/download_sub", methods=["POST"])
def download_sub():
    video_url = request.form.get("video_url")
    lang_code = request.form.get("lang_code")
    subtitle_format = request.form.get("subtitle_format")
    video_title = request.form.get("video_title")

    if not (video_url and lang_code and subtitle_format):
        flash("❌ Thiếu thông tin!", "danger")
        return redirect("/subtitle_downloader")

    output_dir = os.path.join(current_app.static_folder, "get_sub_title")
    os.makedirs(output_dir, exist_ok=True)

    # Lấy thông tin video để kiểm tra phụ đề tồn tại
    try:
        with yt_dlp.YoutubeDL({}) as ydl:
            info = ydl.extract_info(video_url, download=False)

        subtitles = info.get("subtitles", {})
        auto_captions = info.get("automatic_captions", {})
        all_subs = subtitles.copy()
        for lang, tracks in auto_captions.items():
            if lang not in all_subs:
                all_subs[lang] = tracks

        if lang_code not in all_subs:
            flash("❌ Ngôn ngữ phụ đề không có trong video!", "danger")
            return redirect("/subtitle_downloader")

        available_formats = [track["ext"] for track in all_subs[lang_code]]
        if subtitle_format not in available_formats:
            flash(f"❌ Định dạng phụ đề .{subtitle_format} không khả dụng cho ngôn ngữ này!", "danger")
            return redirect("/subtitle_downloader")

    except Exception as e:
        flash(f"❌ Lỗi khi kiểm tra phụ đề: {str(e)}", "danger")
        return redirect("/subtitle_downloader")

    base_filename = f"{video_title}.{lang_code}"
    outtmpl_path = os.path.join(output_dir, base_filename)

    ydl_opts = {
        'subtitleslangs': [lang_code],
        'subtitlesformat': subtitle_format,
        'skip_download': True,
        'writeautomaticsub': True,
        'outtmpl': outtmpl_path,  # yt-dlp sẽ thêm phần đuôi tương ứng
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        downloaded_path = f"{outtmpl_path}.{subtitle_format}"
        if not os.path.exists(downloaded_path):
            flash("❌ Phụ đề không thể tải về hoặc không tồn tại.", "danger")
            return redirect("/subtitle_downloader")

        flash(f"✅ Đã tải phụ đề [{lang_code}] định dạng .{subtitle_format}", "success")
        return redirect(url_for("subtitle_downloader.index", file=os.path.basename(downloaded_path)))

    except Exception as e:
        flash(f"❌ Lỗi khi tải phụ đề: {str(e)}", "danger")
        return redirect("/subtitle_downloader")


@subtitle_downloader_bp.route("/get_sub_title/<filename>")
def serve_subtitle(filename):
    file_path = os.path.join(current_app.static_folder, "get_sub_title", filename)
    return send_file(file_path, as_attachment=True)
