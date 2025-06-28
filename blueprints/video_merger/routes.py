from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash, jsonify
import os
from werkzeug.utils import secure_filename
from moviepy import VideoFileClip
from extensions import db
from models import VideoClip, CategoryClip
from datetime import datetime
import random
import subprocess

import shutil

import re

video_merger_bp = Blueprint("video_merger", __name__, template_folder="templates")

ALLOWED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv'}

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def get_video_duration(path):
    try:
        clip = VideoFileClip(path)
        duration = round(clip.duration)
        clip.close()  # nhớ đóng file clip để tránh lỗi file lock
        return duration
    except Exception as e:
        print(f"Lỗi đọc video {path}: {e}")
        return 0


@video_merger_bp.route("/", methods=["GET", "POST"])
def index():
    categories = CategoryClip.query.order_by(CategoryClip.name).all()
    videos = []
    selected_category = None
    selected_ratio = None

    if request.method == "POST":
        category_id = request.form.get("category_id")
        selected_ratio = request.form.get("ratio")
        target_duration = int(request.form.get("duration", 0))
        selected_category = CategoryClip.query.get(category_id)

        if selected_category and selected_ratio:
            # Lọc video theo category và ratio
            all_videos = VideoClip.query.filter_by(
                category_id=selected_category.id,
                ratio=selected_ratio
            ).all()

            random.shuffle(all_videos)
            total = 0
            remaining_videos = []

            for vid in all_videos:
                if total + vid.duration <= target_duration:
                    videos.append(vid)
                    total += vid.duration
                else:
                    remaining_videos.append(vid)

            # Nếu tổng thời lượng vẫn chưa đủ → cắt 1 video còn lại
            if total < target_duration and remaining_videos:
                extra_video = random.choice(remaining_videos)
                remaining_time = round(target_duration - total, 1)
                extra_video.cut_to = remaining_time  # Gán thuộc tính tạm
                videos.append(extra_video)
                total += remaining_time  # Giờ đủ rồi

    return render_template("video_merger/index.html",
                        categories=categories,
                        videos=videos,
                        selected_category=selected_category,
                        selected_ratio=selected_ratio,
                        selected_videos=videos)  # <-- thêm dòng này

@video_merger_bp.route("/manage", methods=["GET", "POST"])
def manage_videos():
    upload_folder = os.path.join(current_app.root_path, "static", "videos")
    os.makedirs(upload_folder, exist_ok=True)

    if request.method == "POST":
        files = request.files.getlist("video_files[]")  # Lấy danh sách các file
        category_name = request.form.get("category", "").strip()

        if not files:
            flash("❌ Không có file nào được chọn!", "danger")
        else:
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    save_path = os.path.join(upload_folder, filename)
                    file.save(save_path)

                    try:
                        clip = VideoFileClip(save_path)
                        width, height = clip.size
                        duration = clip.duration
                        ratio = "16:9" if width > height else "9:16"
                        clip.close()

                        existing = VideoClip.query.filter_by(filename=filename).first()
                        if not existing:
                            category_obj = None
                            if category_name:
                                category_obj = CategoryClip.query.filter_by(name=category_name).first()
                                if not category_obj:
                                    category_obj = CategoryClip(name=category_name)
                                    db.session.add(category_obj)
                                    db.session.commit()

                            video = VideoClip(
                                filename=filename,
                                filepath=save_path,
                                category_id=category_obj.id if category_obj else None,
                                ratio=ratio,
                                duration=duration
                            )
                            db.session.add(video)
                            db.session.commit()
                            flash(f"✅ Đã thêm video '{filename}'", "success")
                        else:
                            flash(f"⚠️ Video '{filename}' đã tồn tại trong hệ thống!", "warning")
                    except Exception as e:
                        flash(f"❌ Lỗi đọc video '{filename}': {e}", "danger")
                else:
                    flash(f"❌ File '{file.filename}' không hợp lệ!", "danger")

    videos = VideoClip.query.order_by(VideoClip.created_at.desc()).all()
    categories = CategoryClip.query.order_by(CategoryClip.name).all()

    return render_template(
        "video_merger/manage.html",
        videos=videos,
        category_list=[c.name for c in categories]
    )


@video_merger_bp.route("/manage/category/add", methods=["POST"])
def add_category():
    name = request.form.get("new_category", "").strip()
    if not name:
        flash("⚠️ Tên danh mục không được để trống.", "danger")
    else:
        existing = CategoryClip.query.filter_by(name=name).first()
        if existing:
            flash("⚠️ Danh mục đã tồn tại!", "warning")
        else:
            new_cat = CategoryClip(name=name)
            db.session.add(new_cat)
            db.session.commit()
            flash(f"✅ Đã thêm danh mục '{name}'", "success")
    return redirect(url_for("video_merger.manage_videos"))

@video_merger_bp.route("/manage/category/delete/<string:category_name>", methods=["POST"])
def delete_video_category(category_name):
    category = CategoryClip.query.filter_by(name=category_name).first()
    if category:
        # Xóa tham chiếu category_id của video sang None trước khi xóa category
        VideoClip.query.filter_by(category_id=category.id).update({"category_id": None})
        db.session.delete(category)
        db.session.commit()
        flash(f"🗑 Đã xoá danh mục '{category_name}' và cập nhật video liên quan", "warning")
    else:
        flash("⚠️ Danh mục không tồn tại!", "danger")
    return redirect(url_for("video_merger.manage_videos"))

@video_merger_bp.route('/manage/video/delete/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    video = VideoClip.query.get_or_404(video_id)
    # Xóa file trên ổ cứng
    try:
        if os.path.exists(video.filepath):
            os.remove(video.filepath)
    except Exception as e:
        flash(f"⚠️ Lỗi khi xóa file video: {e}", "warning")

    # Xóa record db
    db.session.delete(video)
    db.session.commit()
    flash(f"🗑 Đã xóa video {video.filename}", "warning")
    return redirect(url_for('video_merger.manage_videos'))


@video_merger_bp.route("/generate", methods=["POST"])
def generate_video():
    print("=== BẮT ĐẦU XỬ LÝ ===")

    video_ids = request.form.getlist("video_ids")
    print(f"[INFO] Danh sách video ID: {video_ids}")

    raw_output_name = request.form.get("output_name", "merged_output.mp4")
    raw_output_name = re.sub(r"[^\w\-_.]", "_", raw_output_name)
    if not raw_output_name.lower().endswith(".mp4"):
        raw_output_name += ".mp4"

    fps = int(request.form.get("fps", 30))
    preset = request.form.get("preset", "fast")
    codec = request.form.get("codec", "libx264")
    resolution_input = request.form.get("resolution", "keep")
    aspect_ratio = request.form.get("aspect_ratio", "keep")

    print(f"[INFO] Output: {raw_output_name} | FPS: {fps} | Codec: {codec} | Preset: {preset}")
    print(f"[INFO] Resolution input: {resolution_input}, Aspect ratio: {aspect_ratio}")

    if resolution_input != "keep":
        resolution = resolution_input
    elif aspect_ratio != "keep":
        resolution = {
            "16:9": "1920x1080",
            "9:16": "1080x1920",
            "1:1": "1080x1080"
        }.get(aspect_ratio)
    else:
        resolution = None

    print(f"[INFO] Sử dụng độ phân giải: {resolution}")

    temp_dir = os.path.join(current_app.root_path, "static", "temp")
    output_dir = os.path.join(current_app.root_path, "static", "outputs")
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    base_name, ext = os.path.splitext(raw_output_name)
    output_name = raw_output_name
    output_path = os.path.join(output_dir, output_name)
    if os.path.exists(output_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{base_name}_{timestamp}{ext}"
        output_path = os.path.join(output_dir, output_name)

    print(f"[INFO] Đường dẫn output: {output_path}")

    clips = []
    total_duration = 0

    for vid_id in video_ids:
        print(f"\n--- ĐANG XỬ LÝ VIDEO ID: {vid_id} ---")
        video = VideoClip.query.get(int(vid_id))
        if not video:
            print(f"[⚠️] Không tìm thấy video ID: {vid_id}")
            continue

        cut_key = f"cut_to_{vid_id}"
        cut_to = request.form.get(cut_key)
        print(f"[DEBUG] cut_to = {cut_to}")

        input_path = (
            video.filepath if os.path.isabs(video.filepath)
            else os.path.join(current_app.root_path, video.filepath)
        )
        print(f"[DEBUG] input_path = {input_path}")

        if not os.path.exists(input_path):
            print(f"[⚠️] File không tồn tại: {input_path}")
            continue

        output_clip_path = os.path.join(temp_dir, f"clip_{vid_id}.mp4")

        cmd = ["ffmpeg", "-y"]
        if cut_to:
            try:
                cut_duration = float(cut_to)
                total_duration += cut_duration
                cmd += ["-ss", "0", "-i", input_path, "-t", str(cut_duration)]
            except ValueError:
                flash(f"⚠️ cut_to không hợp lệ cho video ID {vid_id}", "warning")
                continue
        else:
            cmd += ["-i", input_path]
            total_duration += video.duration or 0

        vf_filters = []
        if resolution:
            try:
                w, h = map(int, resolution.split("x"))
                w, h = w // 2 * 2, h // 2 * 2
                vf_filters.append(f"scale={w}:{h}")
            except Exception as e:
                flash(f"❌ Lỗi scale: {e}", "danger")

        vf_filters.append(f"fps={fps}")
        vf_filter = ",".join(vf_filters)

        if codec in ["h264_qsv", "hevc_qsv"]:
            cmd += [
                "-vf", vf_filter,
                "-c:v", codec,
                "-preset", preset,
                "-look_ahead", "0",
                "-global_quality", "23",
                "-c:a", "aac",
                "-movflags", "+faststart",
                output_clip_path
            ]
        else:
            cmd += [
                "-vf", vf_filter,
                "-r", str(fps),
                "-pix_fmt", "yuv420p",
                "-c:v", codec,
                "-preset", preset,
                "-crf", "23",
                "-c:a", "aac",
                "-movflags", "+faststart",
                output_clip_path
            ]

        print(f"[FFMPEG] CMD: {' '.join(cmd)}")

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stderr_output = result.stderr.decode(errors='ignore')
        if result.returncode != 0:
            print(f"[❌] FFmpeg lỗi cho video ID {vid_id}:\n{stderr_output}")
            continue

        if os.path.exists(output_clip_path):
            size = os.path.getsize(output_clip_path)
            print(f"[OK] Clip tạo thành công: {output_clip_path} | Size: {size}")
            if size > 1000:
                clips.append(output_clip_path)
            else:
                print(f"[⚠️] Clip quá nhỏ, bị bỏ qua.")
        else:
            print(f"[⚠️] Clip không tồn tại sau khi xử lý.")

    if not clips:
        print("[❌] Không có clip nào được xử lý thành công.")
        flash("❌ Không có clip nào được xử lý thành công", "danger")
        return redirect(url_for("video_merger.index"))

    file_list_path = os.path.join(temp_dir, "file_list.txt")
    with open(file_list_path, "w", encoding="utf-8") as f:
        for clip in clips:
            abs_path = os.path.abspath(clip)
            f.write(f"file '{abs_path}'\n")
            print(f"[LIST] Thêm vào file_list.txt: {abs_path}")

    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", file_list_path,
        "-c:v", codec if codec in ["libx264", "h264_qsv", "hevc_qsv"] else "libx264",
        "-preset", preset,
        "-crf", "23",
        "-c:a", "aac",
        "-movflags", "+faststart",
        output_path
    ]

    print(f"[FFMPEG] CONCAT CMD: {' '.join(concat_cmd)}")

    concat_result = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    concat_stderr = concat_result.stderr.decode(errors='ignore')
    if concat_result.returncode != 0:
        print(f"[❌] Lỗi khi concat các clip:\n{concat_stderr}")
        flash("❌ Lỗi khi ghép các clip", "danger")
    else:
        print(f"[✅] Ghép video thành công: {output_path}")

    shutil.rmtree(temp_dir, ignore_errors=True)
    print("=== HOÀN TẤT ===")

    return render_template(
        "video_merger/result.html",
        video_url=f"/static/outputs/{output_name}",
        duration=round(total_duration, 1)
    )
