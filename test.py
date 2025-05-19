import os
from moviepy import VideoFileClip, concatenate_videoclips, CompositeVideoClip, TextClip

# Đường dẫn thư mục chứa các video
video_folder = "F:/00.code_all/04.auto_create_vd/auto_create_video/downloads/"

# Đường dẫn intro, outro và watermark
intro_path = "F:/00.code_all/04.auto_create_vd/auto_create_video/intro.mp4"
outro_path = "F:/00.code_all/04.auto_create_vd/auto_create_video/outro.mp4"
watermark_path = "F:/00.code_all/04.auto_create_vd/auto_create_video/watermark.png"

# Lấy danh sách file video trong thư mục (sắp xếp theo tên)
video_files = sorted(
    [f for f in os.listdir(video_folder) if f.endswith(('.mp4', '.mkv', '.mov'))]
)

# Đọc video intro, outro (nếu có)
video_clips = []

if os.path.exists(intro_path):
    intro_clip = VideoFileClip(intro_path)
    video_clips.append(intro_clip)

# Đọc và tạo danh sách các clip video chính
for f in video_files:
    video_path = os.path.join(video_folder, f)
    video_clip = VideoFileClip(video_path)

    # Thêm watermark vào mỗi video
    if os.path.exists(watermark_path):
        watermark = (VideoFileClip(watermark_path)
                     .resize(height=50)  # Đổi kích thước watermark
                     .set_position(("right", "bottom")))  # Đặt vị trí watermark
        video_clip = CompositeVideoClip([video_clip, watermark])

    video_clips.append(video_clip)

# Thêm outro nếu có
if os.path.exists(outro_path):
    outro_clip = VideoFileClip(outro_path)
    video_clips.append(outro_clip)

# Ghép các video lại
final_clip = concatenate_videoclips(video_clips, method="compose")

# Xuất video đã ghép
output_path = os.path.join(video_folder, "output_video.mp4")
final_clip.write_videofile(output_path, codec="libx264", fps=30)

print(f"Video đã ghép được lưu tại: {output_path}")
