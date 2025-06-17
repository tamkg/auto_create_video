from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
import os, uuid, logging, shutil, tempfile
from PIL import Image as PILImage
from gtts import gTTS
from deep_translator import GoogleTranslator
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

from extensions import db, basedir
from models import Video, Segment, Image  # Giả sử model nằm trong models.py
from gtts.lang import tts_langs
import logging
from flask import current_app
from .tts_service import get_voices, generate_audio, split_text
from langdetect import detect
import uuid
from slugify import slugify

video_bp = Blueprint('video', __name__, template_folder="templates")

@video_bp.route("/")
def index():
    videos = Video.query.all()
    languages = tts_langs()  # Trả về dict {'en': 'English', 'vi': 'Vietnamese', ...}
    edge_voices = get_voices() # Trả về các giọng mà edge-tts hỗ trợ
    print("Số giọng đọc Edge:", len(edge_voices))
    return render_template("videos/index.html", 
                           videos=videos, 
                           languages=languages,
                            edge_voices=edge_voices)

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
    # --- Lấy thông số từ query params ---
    codec = request.args.get("codec", "libx264")
    bitrate = request.args.get("bitrate", "8000k")
    preset = request.args.get("preset", "slow")
    audio_codec = request.args.get("audio_codec", "aac")
    audio_bitrate = request.args.get("audio_bitrate", "192k")
    target_lang = request.args.get("lang", "en")
    ratio = request.args.get("ratio", "horizontal")
    tts_engine = request.args.get("tts_type", "google")
    voice = request.args.get("voice")

    # --- Kiểm tra tham số ---
    if target_lang not in tts_langs():
        flash(f"Ngôn ngữ không được hỗ trợ: {target_lang}")
        return redirect(url_for('video.index'))

    if tts_engine == "google" and not target_lang:
        flash("Chưa chọn ngôn ngữ cho Google TTS.")
        return redirect(url_for('video.index'))

    if tts_engine == "edge" and not voice:
        flash("Chưa chọn giọng đọc cho Edge TTS.")
        return redirect(url_for('video.index'))

    # --- Kích thước video theo tỷ lệ ---
    target_size = {
        "vertical": (1080, 1920),
        "square": (1080, 1080),
        "horizontal": (1920, 1080)
    }.get(ratio, (1920, 1080))

    # --- Lấy video và các đoạn ---
    video = Video.query.get_or_404(video_id)
    segments = Segment.query.filter_by(video_id=video.id).order_by(Segment.order_index).all()
    if not segments:
        flash("Video chưa có đoạn nào để xuất!")
        return redirect(url_for('video.index'))

    # --- Tạo thư mục tạm ---
    with tempfile.TemporaryDirectory() as temp_dir:
        clips = []

        for i, segment in enumerate(segments):
            try:
                # --- Dịch nội dung nếu cần ---
                source_lang = detect(segment.text)
                text_chunks = split_text(segment.text, max_length=1000)

                if source_lang != target_lang:
                    translated_chunks = [
                        GoogleTranslator(source=source_lang, target=target_lang).translate(chunk)
                        for chunk in text_chunks
                    ]
                    translated_text = " ".join(translated_chunks)
                    logging.info(f"[Segment {i+1}] Dịch: {source_lang} → {target_lang}")
                else:
                    translated_text = segment.text
                    logging.info(f"[Segment {i+1}] Không cần dịch.")

                # --- Tạo file audio bằng TTS (Google hoặc Edge) ---
                audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
                try:
                    generate_audio(
                        text=translated_text,
                        lang=target_lang,
                        voice=voice,
                        output_path=audio_path,
                        engine=tts_engine
                    )
                except Exception as e:
                    flash(f"Không tạo được audio cho đoạn {i + 1}: {e}")
                    logging.error(f"[Segment {i+1}] TTS lỗi: {e}", exc_info=True)
                    continue

                if not os.path.exists(audio_path):
                    flash(f"Không tồn tại file audio đoạn {i + 1}")
                    continue

                # --- Resize ảnh ---
                img_path = os.path.join(basedir, segment.images[0].file_path) if segment.images else os.path.join(basedir, 'static/default.jpg')
                if not os.path.exists(img_path):
                    flash(f"Không tìm thấy ảnh cho đoạn {i + 1}")
                    continue

                with PILImage.open(img_path) as img:
                    img_ratio = img.width / img.height
                    target_ratio = target_size[0] / target_size[1]

                    if img_ratio > target_ratio:
                        # Cắt ngang
                        new_height = target_size[1]
                        new_width = int(new_height * img_ratio)
                        img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
                        left = (new_width - target_size[0]) // 2
                        img = img.crop((left, 0, left + target_size[0], target_size[1]))
                    else:
                        # Cắt dọc
                        new_width = target_size[0]
                        new_height = int(new_width / img_ratio)
                        img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
                        top = (new_height - target_size[1]) // 2
                        img = img.crop((0, top, target_size[0], top + target_size[1]))

                    resized_img_path = os.path.join(temp_dir, f"resized_{i}.jpg")
                    img.save(resized_img_path, quality=95)

                # --- Tạo clip hình + tiếng ---
                audio_clip = AudioFileClip(audio_path)
                image_clip = ImageClip(resized_img_path).with_duration(audio_clip.duration).with_audio(audio_clip)
                clips.append(image_clip)

            except Exception as seg_error:
                logging.error(f"[Segment {i+1}] Lỗi xử lý: {seg_error}", exc_info=True)
                flash(f"Lỗi xử lý đoạn {i + 1}: {seg_error}")
                continue

        # --- Kiểm tra nếu không tạo được đoạn nào ---
        if not clips:
            flash("Không thể tạo video vì lỗi ở tất cả các đoạn.")
            return redirect(url_for('video.index'))

        # --- Ghép video ---
        exports_dir = os.path.join(basedir, 'exports')
        os.makedirs(exports_dir, exist_ok=True)

        final_clip = concatenate_videoclips(clips, method="compose")
        output_filename = f"{slugify(video.title)}_{uuid.uuid4().hex[:8]}_{ratio}_export.mp4"
        output_path = os.path.join(exports_dir, output_filename)
        audio_temp_path = os.path.join(temp_dir, "temp_audio.m4a")

        try:
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
        except Exception as e:
            logging.error(f"Lỗi khi xuất video: {e}", exc_info=True)
            flash(f"Lỗi khi xuất video: {e}")
            return redirect(url_for('video.index'))

        return send_file(output_path, as_attachment=True)


@video_bp.route('/api/test-voice', methods=['POST'])
def test_voice():
    text = request.form.get('text', '')
    engine = request.form.get('engine', 'google')
    lang = request.form.get('lang', 'en')
    voice = request.form.get('voice')

    if not text.strip():
        return {"error": "Missing text"}, 400

    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, "test_voice.mp3")

    try:
        generate_audio(
            text=text,
            lang=lang,
            voice=voice,
            output_path=output_path,
            engine=engine
        )
        return send_file(output_path, mimetype='audio/mpeg', as_attachment=False)
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        pass  # Không xóa temp_dir ở đây để tránh xóa file trước khi gửi        



@video_bp.route('/create_audio', methods=['POST'])
def create_audio():
    translated_text = request.form.get("translated_text", "")
    tts_system = request.form.get("tts_system", "google")
    google_voice = request.form.get("google_voice")
    edge_voice = request.form.get("edge_voice")

    if not translated_text.strip():
        flash("Không có nội dung để tạo audio.")
        return redirect(url_for("video.index"))

    try:
        # Chọn voice phù hợp theo engine
        voice = google_voice if tts_system == "google" else edge_voice

        # Tạo thư mục tạm để chứa file .mp3
        temp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(temp_dir, f"audio_output.mp3")

        # Gọi hàm tạo audio (đã có trong tts_service.py của bạn)
        generate_audio(
            text=translated_text,
            lang=voice,  # Google: mã ngôn ngữ; Edge: tên voice
            voice=voice,
            output_path=audio_path,
            engine=tts_system
        )

        if not os.path.exists(audio_path):
            raise Exception("Không tìm thấy file âm thanh được tạo.")

        return send_file(audio_path, mimetype="audio/mpeg", as_attachment=True, download_name="output_audio.mp3")

    except Exception as e:
        logging.error(f"Lỗi tạo audio: {e}", exc_info=True)
        flash(f"Lỗi tạo audio: {e}")
        return redirect(url_for("video.index"))
