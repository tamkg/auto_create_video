import os
import uuid
import subprocess
from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, current_app, flash
from werkzeug.utils import secure_filename
from extensions import basedir  # basedir = os.path.abspath(os.path.dirname(__file__))

audio_tools_bp = Blueprint('audio_tools', __name__, template_folder='templates')

@audio_tools_bp.route('/')
def index():
    return render_template('audio_tools/index.html')

@audio_tools_bp.route('/extract_audio', methods=['POST'])
def extract_audio():
    uploaded_files = request.files.getlist('videos')
    audio_format = request.form.get('audio_format', 'mp3').lower()

    allowed_formats = ['mp3', 'wav', 'aac', 'flac', 'ogg']
    if audio_format not in allowed_formats:
        flash("❌ Định dạng không được hỗ trợ.")
        return redirect(url_for('audio_tools.index'))

    if not uploaded_files:
        flash("❗ Vui lòng chọn ít nhất một file video.")
        return redirect(url_for('audio_tools.index'))

    # ✅ Dùng thư mục audios/ ngang cấp app.py
    audio_dir = os.path.join(basedir, 'audios')
    os.makedirs(audio_dir, exist_ok=True)

    audio_files = []

    for video in uploaded_files:
        original_name = secure_filename(video.filename)
        unique_name = f"{uuid.uuid4().hex}_{original_name}"
        video_path = os.path.join(audio_dir, unique_name)
        video.save(video_path)

        base_name = os.path.splitext(unique_name)[0]
        audio_filename = f"{base_name}.{audio_format}"
        audio_path = os.path.join(audio_dir, audio_filename)

        cmd = ['ffmpeg', '-i', video_path, '-vn', audio_path]

        try:
            subprocess.run(cmd, check=True)
            audio_files.append(audio_filename)
            # ❌ Nếu muốn xoá file video gốc sau khi trích xuất:
            # os.remove(video_path)
        except subprocess.CalledProcessError:
            flash(f"❌ Lỗi khi tách audio từ {original_name}")

    return render_template('audio_tools/index.html', audio_files=audio_files)

@audio_tools_bp.route('/download_audio/<filename>')
def download_audio(filename):
    audio_dir = os.path.join(basedir, 'audios')
    return send_from_directory(audio_dir, filename, as_attachment=True)

@audio_tools_bp.route('/list_audios')
def list_audios():
    audio_folder = os.path.join(basedir, 'audios')
    video_folder = os.path.join(basedir, 'downloads')

    # Lấy file audio cấp 1
    audio_files = os.listdir(audio_folder) if os.path.exists(audio_folder) else []

    # Duyệt đệ quy để lấy video trong toàn bộ downloads/
    video_files = []
    if os.path.exists(video_folder):
        for root, _, files in os.walk(video_folder):
            for file in files:
                if file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                    rel_path = os.path.relpath(os.path.join(root, file), video_folder)
                    video_files.append(rel_path.replace("\\", "/"))  # Hỗ trợ Windows

    return render_template('audio_tools/list_audios.html', audio_files=audio_files, video_files=video_files)



@audio_tools_bp.route('/media/<media_type>/<path:filename>')
def serve_media(media_type, filename):
    folder_map = {
        'audio': os.path.join(basedir, 'audios'),
        'video': os.path.join(basedir, 'downloads'),
    }
    folder = folder_map.get(media_type)
    if not folder:
        flash("❌ Loại tệp không hợp lệ.")
        return redirect(url_for('audio_tools.list_audios'))

    return send_from_directory(folder, filename)
