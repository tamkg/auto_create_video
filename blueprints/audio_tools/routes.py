import os
import uuid
import subprocess
from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, current_app, flash

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

    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'audio_input')
    output_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'extracted_audio')
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)

    audio_files = []

    for video in uploaded_files:
        filename = f"{uuid.uuid4().hex}_{video.filename}"
        video_path = os.path.join(upload_folder, filename)
        video.save(video_path)

        base_name = os.path.splitext(filename)[0]
        audio_filename = f"{base_name}.{audio_format}"
        audio_path = os.path.join(output_folder, audio_filename)

        cmd = ['ffmpeg', '-i', video_path, '-vn', audio_path]

        try:
            subprocess.run(cmd, check=True)
            audio_files.append(audio_filename)
        except subprocess.CalledProcessError:
            flash(f"❌ Lỗi khi tách audio từ {video.filename}")
    
    return render_template('audio_tools/index.html', audio_files=audio_files)


@audio_tools_bp.route('/download_audio/<filename>')
def download_audio(filename):
    output_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'extracted_audio')
    return send_from_directory(output_folder, filename, as_attachment=True)
