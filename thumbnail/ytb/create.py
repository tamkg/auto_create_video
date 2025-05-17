from PIL import Image

def create_youtube_thumbnail(input_image_path: str, output_image_path: str):
    target_size = (1280, 720)  # 16:9

    with Image.open(input_image_path) as img:
        # Chuyển ảnh RGBA (có alpha) sang RGB (không alpha)
        if img.mode in ("RGBA", "LA"):
            img = img.convert("RGB")

        # Tính toán tỷ lệ ảnh
        img_ratio = img.width / img.height
        target_ratio = target_size[0] / target_size[1]

        # Resize ảnh giữ tỷ lệ gốc, sau đó crop để full 16:9
        if img_ratio > target_ratio:
            # Ảnh rộng hơn 16:9, crop chiều ngang
            new_height = target_size[1]
            new_width = int(new_height * img_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            left = (new_width - target_size[0]) // 2
            img = img.crop((left, 0, left + target_size[0], target_size[1]))
        else:
            # Ảnh cao hơn 16:9, crop chiều dọc
            new_width = target_size[0]
            new_height = int(new_width / img_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            top = (new_height - target_size[1]) // 2
            img = img.crop((0, top, target_size[0], top + target_size[1]))

        # Lưu ảnh dưới dạng JPG với chất lượng cao
        img.save(output_image_path, quality=95, format="JPEG")
        print(f"✅ Thumbnail đã được tạo và lưu tại: {output_image_path}")

# Sử dụng:
create_youtube_thumbnail("00.png", "youtube_thumbnail.jpg")
