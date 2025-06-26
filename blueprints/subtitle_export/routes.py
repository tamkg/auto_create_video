from flask import Blueprint, render_template, request, redirect, flash, url_for
import os
import uuid
import srt
import pysubs2
import re
import zipfile
from datetime import timedelta, datetime
from werkzeug.utils import secure_filename
from concurrent.futures import ProcessPoolExecutor

subtitle_export_bp = Blueprint('subtitle_export', __name__, template_folder="templates")

UPLOAD_FOLDER = 'static/uploads'
SUBTITLE_FOLDER = os.path.join(UPLOAD_FOLDER, 'sub_title')
os.makedirs(SUBTITLE_FOLDER, exist_ok=True)


def clean_filename(name):
    return re.sub(r"[^\w\-]", "", name)[:50]


def generate_subtitles_process(args):
    import whisper
    video_path, fmt, mode, clean_name, subtitle_folder = args

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{clean_name}_{timestamp}"
    output_dir = os.path.join(subtitle_folder, folder_name)
    os.makedirs(output_dir, exist_ok=True)

    model = whisper.load_model("base")
    result = model.transcribe(video_path, word_timestamps=(mode == "word"))
    segments = result["segments"]

    subs = []
    if mode == "word" and "words" in segments[0]:
        idx = 1
        for segment in segments:
            for word_info in segment["words"]:
                start = timedelta(seconds=word_info['start'])
                end = timedelta(seconds=word_info['end'])
                content = word_info['word'].strip()
                if content:
                    subs.append(srt.Subtitle(index=idx, start=start, end=end, content=content))
                    idx += 1
    else:
        for i, seg in enumerate(segments):
            start = timedelta(seconds=seg["start"])
            end = timedelta(seconds=seg["end"])
            content = seg["text"].strip()
            subs.append(srt.Subtitle(index=i + 1, start=start, end=end, content=content))

    out_path = os.path.join(output_dir, f"{clean_name}.{fmt}")
    if fmt == "srt":
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(srt.compose(subs))
    elif fmt == "lrc":
        with open(out_path, "w", encoding="utf-8") as f:
            for sub in subs:
                total_sec = int(sub.start.total_seconds())
                minutes = total_sec // 60
                seconds = sub.start.total_seconds() % 60
                f.write(f"[{int(minutes):02}:{seconds:05.2f}]{sub.content}\n")
    elif fmt == "ass":
        subs2 = pysubs2.SSAFile()
        for sub in subs:
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            subs2.append(pysubs2.SSAEvent(start=start_ms, end=end_ms, text=sub.content))
        subs2.save(out_path)

    return output_dir


def zip_subtitle_folders(folders: list, zip_name: str) -> str:
    zip_path = os.path.join(SUBTITLE_FOLDER, f"{zip_name}.zip")
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for folder in folders:
            for root, _, files in os.walk(folder):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, os.path.dirname(folder))
                    zipf.write(full_path, arcname)
    return zip_path


@subtitle_export_bp.route("/subtitle-export", methods=["GET"])
def index():
    return render_template("subtitle_export/index.html")


@subtitle_export_bp.route("/subtitle-export", methods=["POST"])
def process():
    video_files = request.files.getlist('video_files[]')
    formats = request.form.getlist('formats[]')
    modes = request.form.getlist('modes[]')  # 👈 Thêm dòng này

    if not video_files or not formats or not modes or \
       len(video_files) != len(formats) or len(formats) != len(modes):
        flash("Vui lòng chọn đầy đủ thông tin cho từng video!", "danger")
        return redirect(url_for("subtitle_export.index"))

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    sub_tasks = []

    for video_file, fmt, mode in zip(video_files, formats, modes):
        filename = secure_filename(video_file.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        save_path = os.path.join(UPLOAD_FOLDER, unique_name)
        video_file.save(save_path)

        clean_name = clean_filename(os.path.splitext(filename)[0])
        sub_tasks.append((save_path, fmt, mode, clean_name, SUBTITLE_FOLDER))  # 👈 Thêm `mode`

    sub_folders = []
    with ProcessPoolExecutor() as executor:
        for result in executor.map(generate_subtitles_process, sub_tasks):
            sub_folders.append(result)

    zip_name = f"subs_{len(sub_folders)}files_{datetime.now().strftime('%H%M%S')}"
    zip_path = zip_subtitle_folders(sub_folders, zip_name)
    zip_rel_path = os.path.relpath(zip_path, "static").replace(os.path.sep, "/")

    flash("Tạo phụ đề thành công!", "success")
    return render_template("subtitle_export/index.html", zip_path=zip_rel_path)
