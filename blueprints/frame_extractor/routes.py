from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
import os
import subprocess
from werkzeug.utils import secure_filename
from datetime import datetime
import pathlib
import shutil
from concurrent.futures import ProcessPoolExecutor

frame_extractor_bp = Blueprint("frame_extractor_bp", __name__, template_folder="templates")

# ⚙️ Hàm xử lý từng video (chạy ở tiến trình riêng)
def extract_single_video(file_storage_info):
    file_content, filename, interval, upload_folder, frames_root = file_storage_info
    name_only = pathlib.Path(filename).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"{name_only}_{timestamp}"

    video_path = os.path.join(upload_folder, filename)
    with open(video_path, "wb") as f:
        f.write(file_content)

    output_dir = os.path.join(frames_root, unique_name)
    os.makedirs(output_dir, exist_ok=True)

    output_pattern = os.path.join(output_dir, f"{unique_name}_%04d.jpg")

    command = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps=1/{interval}",
        "-qscale:v", "2",
        output_pattern
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ✅ KHÔNG DÙNG url_for ở đây!
    shutil.make_archive(output_dir, 'zip', output_dir)
    zip_url = f"/static/frames/{unique_name}.zip"

    return {
        "folder": unique_name,
        "zip_url": zip_url
    }

@frame_extractor_bp.route("/")
def index():
    return render_template("frame_extractor/index.html")

@frame_extractor_bp.route("/extract", methods=["POST"])
def extract_frames():
    files = request.files.getlist("videos")
    interval = request.form.get("interval", "2").strip()

    if not files or len(files) == 0:
        flash("❌ Không có file video nào được chọn.")
        return redirect(url_for("frame_extractor_bp.index"))

    if not interval.isdigit() or int(interval) < 1:
        flash("⚠️ Khoảng thời gian không hợp lệ. Nhập số >= 1.")
        return redirect(url_for("frame_extractor_bp.index"))

    interval = int(interval)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    frames_root = os.path.join("static", "frames")

    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(frames_root, exist_ok=True)

    # Chuẩn bị data để gửi vào tiến trình
    input_data = []
    for file in files:
        if file.filename == "":
            continue
        filename = secure_filename(file.filename)
        file_bytes = file.read()
        input_data.append((file_bytes, filename, interval, upload_folder, frames_root))

    # Chạy đa tiến trình
    results = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(extract_single_video, item) for item in input_data]
        for future in futures:
            results.append(future.result())

    flash(f"✅ Đã trích ảnh từ {len(results)} video.")
    return render_template("frame_extractor/index.html", results=results)
