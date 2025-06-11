from flask import Blueprint, render_template, request, url_for, current_app, redirect, flash
import os
import uuid
from deep_translator import GoogleTranslator
import httpx

create_images_bp = Blueprint('create_images', __name__, template_folder='templates')

STABILITY_API_KEY = "sk-P1nE5JNtWG8stmitbjMTuMwQT3niQt1w9EJn9kCaekoCDKID"

def translate_to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except Exception as e:
        print(f"[Translation Error] {e}")
        return text  # fallback nếu dịch lỗi

@create_images_bp.route('/', methods=['GET', 'POST'])
def index():
    generated_image_url = None
    description = ''
    selected_tool = ''

    if request.method == 'POST':
        selected_tool = request.form.get('tool')
        description = request.form.get('description', '').strip()

        if not description:
            flash("Mô tả không được để trống.", "warning")
            return redirect(request.url)

        if selected_tool == 'stability':
            translated_prompt = translate_to_english(description)
            image_bytes = generate_image_with_stability(translated_prompt)

            if image_bytes:
                filename = f"{uuid.uuid4().hex}.png"
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, filename)

                with open(file_path, 'wb') as f:
                    f.write(image_bytes)

                generated_image_url = url_for('static', filename=f'uploads/{filename}')
        else:
            filename = f"{uuid.uuid4().hex}.png"
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'static/uploads')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)

            from PIL import Image, ImageDraw
            img = Image.new('RGB', (400, 300), color='white')
            d = ImageDraw.Draw(img)
            text = f"Công cụ: {selected_tool}\nMô tả: {description}"
            d.text((10, 10), text, fill='black')
            img.save(file_path)
            generated_image_url = url_for('static', filename=f'uploads/{filename}')

    return render_template('create_images/index.html',
                           generated_image_url=generated_image_url,
                           description=description,
                           selected_tool=selected_tool)


def generate_image_with_stability(prompt: str):
    url = "https://api.stability.ai/v2beta/stable-image/generate/core"

    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Accept": "image/*",  # <-- Đây là giá trị đúng
    }

    files = {
        "prompt": (None, prompt),
        "model": (None, "stable-diffusion-xl-beta-v2-2-2"),
        "output_format": (None, "png")
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, files=files)

        if response.status_code == 200:
            return response.content  # Ảnh trả về dạng bytes
        else:
            print(f"[Stability API Error {response.status_code}] {response.text}")
    except httpx.RequestError as e:
        print(f"[HTTPX Error] {e}")

    return None
