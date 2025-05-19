import os
from moviepy import VideoFileClip, concatenate_videoclips, CompositeVideoClip, TextClip


# Đường dẫn thư mục chứa các video
video_folder = "F:/00.code_all/04.auto_create_vd/auto_create_video/downloads/"
output_path = os.path.join(video_folder, "output_video_with_watermark.mp4")

# Lấy danh sách file video trong thư mục (sắp xếp theo tên)
video_files = sorted(
    [f for f in os.listdir(video_folder) if f.endswith(('.mp4', '.mkv', '.mov'))]
)

# Đọc và tạo danh sách các clip video
video_clips = []

for f in video_files:
    video_path = os.path.join(video_folder, f)
    video_clip = VideoFileClip(video_path)

    # Thêm watermark dạng text vào mỗi video
    watermark_text = "Mania Girl"  # Thay bằng nội dung watermark của bạn
    watermark = (TextClip(watermark_text, fontsize=24, color='white')  # Bỏ `font="Arial-Bold"`
                 .set_duration(video_clip.duration)
                 .set_position(("right", "bottom"))  # Vị trí watermark
                 .set_opacity(0.7))  # Độ trong suốt của watermark

    # Ghép watermark vào video
    watermarked_clip = CompositeVideoClip([video_clip, watermark])
    video_clips.append(watermarked_clip)

# Ghép các video lại
final_clip = concatenate_videoclips(video_clips, method="compose")

# Xuất video đã ghép
final_clip.write_videofile(output_path, codec="libx264", fps=30)

print(f"Video đã ghép được lưu tại: {output_path}")
