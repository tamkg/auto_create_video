from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import os, tempfile, shutil
from PIL import Image as PILImage
from gtts import gTTS
from deep_translator import GoogleTranslator
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

from extensions import db, basedir
from models import Video, Segment, Image  # Giả sử model nằm trong models.py
from gtts.lang import tts_langs
import logging
from flask import current_app

import re
from pydub import AudioSegment

def split_text(text, max_length=1000):
    """Chia đoạn văn bản dài thành các phần nhỏ để dịch và đọc TTS."""
    sentences = re.split(r'(?<=[.!?]) +', text)
    parts = []
    current_part = ""

    for sentence in sentences:
        if len(current_part) + len(sentence) < max_length:
            current_part += " " + sentence
        else:
            parts.append(current_part.strip())
            current_part = sentence
    if current_part:
        parts.append(current_part.strip())

    return parts

video_bp = Blueprint('video', __name__, template_folder="templates")

@video_bp.route("/")
def index():
    videos = Video.query.all()
    languages = tts_langs()  # Trả về dict {'en': 'English', 'vi': 'Vietnamese', ...}
    return render_template("videos/index.html", videos=videos, languages=languages)

@video_bp.route('/video/new', methods=['GET', 'POST'])
def create_video():
    if request.method == 'POST':
        title = request.form.get('title')
        if not title:
            flash("Tiêu đề video là bắt buộc")
            return redirect(request.url)

        video = Video(title=title)
        db.session.add(video)
        db.session.commit()

        for key in request.form.keys():
            if key.startswith('segment_text_'):
                idx = key.replace('segment_text_', '')
                text = request.form.get(key)
                if text:
                    segment = Segment(video_id=video.id, text=text, order_index=int(idx))
                    db.session.add(segment)
                    db.session.flush()

                    files = request.files.getlist(f'segment_images_{idx}')
                    order_img = 0
                    for file in files:
                        if file and file.filename != '':
                            filename = secure_filename(file.filename)
                            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                            file.save(filepath)

                            order_img += 1
                            image = Image(segment_id=segment.id,
                                          file_path=f'static/uploads/{filename}',
                                          order_index=order_img)
                            db.session.add(image)

        db.session.commit()
        flash('Tạo video thành công')
        return redirect(url_for('video.index'))

    return render_template('new_video.html')

@video_bp.route('/video/<int:video_id>')
def video_detail(video_id):
    video = Video.query.get_or_404(video_id)
    return render_template('video_detail.html', video=video)

@video_bp.route('/video/<int:video_id>/edit', methods=['GET', 'POST'])
def edit_video(video_id):
    video = Video.query.get_or_404(video_id)

    if request.method == 'POST':
        title = request.form.get('title')
        if not title:
            flash("Tiêu đề video không được để trống!")
            return redirect(request.url)
        video.title = title

        # Lấy tất cả segment cũ hiện có trong DB, key = order_index
        existing_segments = {seg.order_index: seg for seg in video.segments}

        # Lấy danh sách order_index đoạn trong form (đoạn còn tồn tại)
        segment_indices_in_form = []
        for key in request.form.keys():
            if key.startswith('segment_text_'):
                idx = int(key.replace('segment_text_', ''))
                segment_indices_in_form.append(idx)

        # Xóa các đoạn trong DB mà không còn trong form (bị xóa)
        for idx in list(existing_segments.keys()):
            if idx not in segment_indices_in_form:
                seg_to_delete = existing_segments[idx]
                # Xóa luôn các ảnh trong đoạn đó
                for img in seg_to_delete.images:
                    # Xóa file ảnh trên disk nếu muốn (tuỳ bạn)
                    try:
                        os.remove(os.path.join(basedir, img.file_path))
                    except Exception:
                        pass
                    db.session.delete(img)
                db.session.delete(seg_to_delete)
                db.session.flush()

        # Cập nhật hoặc thêm mới các đoạn còn lại trong form
        for idx in segment_indices_in_form:
            text = request.form.get(f'segment_text_{idx}')

            if idx in existing_segments:
                segment = existing_segments[idx]
                segment.text = text
            else:
                segment = Segment(video_id=video.id, text=text, order_index=idx)
                db.session.add(segment)
                db.session.flush()  # để có id segment thêm ảnh

            # Xử lý ảnh mới upload (nếu có)
            files = request.files.getlist(f'segment_images_{idx}')
            if any(file and file.filename != '' for file in files):
                current_image_count = len(segment.images)
                for i, file in enumerate(files):
                    if file and file.filename != '':
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

                        file.save(filepath)
                        image = Image(
                            segment_id=segment.id,
                            file_path=f'static/uploads/{filename}',
                            order_index=current_image_count + i + 1
                        )
                        db.session.add(image)

        db.session.commit()
        flash("Cập nhật video thành công")
        return redirect(url_for('video.video_detail', video_id=video.id))

    return render_template('edit_video.html', video=video)



@video_bp.route('/video/<int:video_id>/delete', methods=['POST'])
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    db.session.delete(video)
    db.session.commit()
    flash("Xóa video thành công")
    return redirect(url_for('video.index'))

@video_bp.route('/image/<int:image_id>/delete', methods=['GET', 'POST'])
def delete_image(image_id):
    image = Image.query.get_or_404(image_id)
    segment_id = image.segment_id
    db.session.delete(image)
    db.session.commit()
    flash("Xóa ảnh thành công")
    # Quay lại trang sửa video của segment này
    segment = Segment.query.get(segment_id)
    if segment:
        return redirect(url_for('video.edit_video', video_id=segment.video_id))
    else:
        return redirect(url_for('video.index'))

@video_bp.route('/video/<int:video_id>/export')
def export_video(video_id):
    codec = request.args.get("codec", "libx264")
    bitrate = request.args.get("bitrate", "8000k")
    preset = request.args.get("preset", "slow")
    audio_codec = request.args.get("audio_codec", "aac")
    audio_bitrate = request.args.get("audio_bitrate", "192k")
    target_lang = request.args.get("lang", "en")
    ratio = request.args.get("ratio", "horizontal")

    video = Video.query.get_or_404(video_id)
    segments = Segment.query.filter_by(video_id=video.id).order_by(Segment.order_index).all()
    if not segments:
        flash("Video chưa có đoạn nào để xuất!")
        return redirect(url_for('video.index'))

    from gtts.lang import tts_langs
    if target_lang not in tts_langs():
        flash(f"Ngôn ngữ không được hỗ trợ: {target_lang}")
        return redirect(url_for('video.index'))

    target_size = {
        "vertical": (1080, 1920),
        "square": (1080, 1080),
        "horizontal": (1920, 1080)
    }.get(ratio, (1920, 1080))

    temp_dir = tempfile.mkdtemp()
    clips = []

    try:
        for i, segment in enumerate(segments):
            try:
                text_chunks = split_text(segment.text, max_length=1000)
                translated_chunks = []
                for chunk in text_chunks:
                    translated = GoogleTranslator(source='vi', target=target_lang).translate(chunk)
                    translated_chunks.append(translated)

                audio = AudioSegment.empty()
                for j, part in enumerate(translated_chunks):
                    part_path = os.path.join(temp_dir, f"audio_{i}_{j}.mp3")
                    gTTS(part, lang=target_lang).save(part_path)
                    audio += AudioSegment.from_mp3(part_path)

                audio_path = os.path.join(temp_dir, f"full_audio_{i}.mp3")
                audio.export(audio_path, format="mp3")

                if segment.images:
                    img_path = os.path.join(basedir, segment.images[0].file_path)
                else:
                    img_path = os.path.join(basedir, 'static/default.jpg')

                with PILImage.open(img_path) as img:
                    img_ratio = img.width / img.height
                    target_ratio = target_size[0] / target_size[1]

                    if img_ratio > target_ratio:
                        new_height = target_size[1]
                        new_width = int(new_height * img_ratio)
                        img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
                        left = (new_width - target_size[0]) // 2
                        img = img.crop((left, 0, left + target_size[0], target_size[1]))
                    else:
                        new_width = target_size[0]
                        new_height = int(new_width / img_ratio)
                        img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
                        top = (new_height - target_size[1]) // 2
                        img = img.crop((0, top, target_size[0], top + target_size[1]))

                    resized_img_path = os.path.join(temp_dir, f"resized_{i}.jpg")
                    img.save(resized_img_path, quality=95)

                audio_clip = AudioFileClip(audio_path)
                duration = audio_clip.duration
                image_clip = ImageClip(resized_img_path).with_duration(duration).with_audio(audio_clip)
                clips.append(image_clip)

            except Exception as seg_err:
                flash(f"Lỗi xử lý đoạn {i+1}: {seg_err}")
                continue

        if not clips:
            flash("Không thể tạo video vì lỗi ở tất cả các đoạn.")
            return redirect(url_for('video.index'))

        exports_dir = os.path.join(basedir, 'exports')
        os.makedirs(exports_dir, exist_ok=True)
        output_path = os.path.join(exports_dir, f"{video.title}_{ratio}_export.mp4")
        audio_temp_path = os.path.join(temp_dir, "temp_audio.m4a")

        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip.write_videofile(
            output_path,
            fps=30,
            codec=codec,
            bitrate=bitrate,
            preset=preset,
            audio_codec=audio_codec,
            audio_bitrate=audio_bitrate,
            temp_audiofile=audio_temp_path,
            remove_temp=True
        )

        return send_file(output_path, as_attachment=True)

    except Exception as e:
        logging.error(f"Lỗi khi xuất video: {e}", exc_info=True)
        flash(f"Lỗi khi xuất video: {e}")
        return redirect(url_for('video.index'))

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)