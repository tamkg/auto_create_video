from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import Category, VideoTemplate, AIPromptTemplate, AIModelConfig  # đảm bảo bạn import đúng
from extensions import db
import openai
import requests
import markdown2 

setup_video_prompt_bp = Blueprint('setup_video_prompt', __name__, template_folder='templates')


@setup_video_prompt_bp.route('/')
def index():
    categories = Category.query.order_by(Category.created_at.desc()).all()
    video_templates = VideoTemplate.query.order_by(VideoTemplate.created_at.desc()).all()
    ai_prompt_templates = AIPromptTemplate.query.order_by(AIPromptTemplate.created_at.desc()).all()
    model_configs = AIModelConfig.query.order_by(AIModelConfig.created_at.desc()).all()

    return render_template(
        'setup_video_prompt/index.html',
        categories=categories,
        video_templates=video_templates,
        ai_prompt_templates=ai_prompt_templates,
        model_configs=model_configs
    )


# --- TẠO DANH MỤC ---
@setup_video_prompt_bp.route('/categories/create', methods=['GET', 'POST'])
def create_category():
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Tên danh mục không được để trống.', 'danger')
        else:
            new_category = Category(name=name)
            db.session.add(new_category)
            db.session.commit()
            flash('Tạo danh mục thành công.', 'success')
            return redirect(url_for('setup_video_prompt.index'))
    return render_template('setup_video_prompt/create_category.html')


# --- SỬA DANH MỤC ---
@setup_video_prompt_bp.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
def edit_category(id):
    category = Category.query.get_or_404(id)
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Tên danh mục không được để trống.', 'danger')
        else:
            category.name = name
            db.session.commit()
            flash('Cập nhật danh mục thành công.', 'success')
            return redirect(url_for('setup_video_prompt.index'))
    return render_template('setup_video_prompt/edit_category.html', category=category)


# --- XOÁ DANH MỤC ---
@setup_video_prompt_bp.route('/categories/<int:id>/delete', methods=['POST'])
def delete_category(id):
    category = Category.query.get_or_404(id)

    if category.video_templates:
        flash('Không thể xoá danh mục vì đang có Video Template sử dụng.', 'danger')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('Xóa danh mục thành công.', 'success')

    return redirect(url_for('setup_video_prompt.index'))


@setup_video_prompt_bp.route('/video_templates/create', methods=['GET', 'POST'])
def create_video_template():
    categories = Category.query.all()
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        video_file = request.form.get('video_file')
        title_pattern = request.form.get('title_pattern')
        description_pattern = request.form.get('description_pattern')
        default_tags = request.form.get('default_tags')

        if not category_id or not video_file or not title_pattern:
            flash('Vui lòng điền đầy đủ thông tin bắt buộc.', 'danger')
        else:
            vt = VideoTemplate(
                category_id=category_id,
                video_file=video_file,
                title_pattern=title_pattern,
                description_pattern=description_pattern,
                default_tags=default_tags
            )
            db.session.add(vt)
            db.session.commit()
            flash('Tạo video template thành công.', 'success')
            return redirect(url_for('setup_video_prompt.index'))

    return render_template('setup_video_prompt/create_video_template.html', categories=categories)

@setup_video_prompt_bp.route('/prompt_templates/create', methods=['GET', 'POST'])
def create_prompt_template():
    categories = Category.query.all()
    model_configs = AIModelConfig.query.all()

    if request.method == 'POST':
        category_id = request.form.get('category_id')
        model_config_id = request.form.get('model_config_id')
        task_type = request.form.get('task_type')
        prompt_template = request.form.get('prompt_template')
        description = request.form.get('description')
        version = request.form.get('version')

        if not category_id or not model_config_id or not task_type or not prompt_template:
            flash('Thiếu thông tin bắt buộc.', 'danger')
        else:
            prompt = AIPromptTemplate(
                category_id=category_id,
                model_config_id=model_config_id,
                task_type=task_type,
                prompt_template=prompt_template,
                description=description,
                version=version
            )
            db.session.add(prompt)
            db.session.commit()
            flash('Tạo prompt template thành công.', 'success')
            return redirect(url_for('setup_video_prompt.index'))

    return render_template('setup_video_prompt/create_prompt_template.html', categories=categories, model_configs=model_configs)

@setup_video_prompt_bp.route('/model_configs/create', methods=['GET', 'POST'])
def create_model_config():
    if request.method == 'POST':
        provider = request.form.get('provider')
        model_name = request.form.get('model_name')
        endpoint = request.form.get('endpoint')
        api_key = request.form.get('api_key')

        if not provider or not model_name:
            flash('Provider và model name là bắt buộc.', 'danger')
        else:
            config = AIModelConfig(
                provider=provider,
                model_name=model_name,
                endpoint=endpoint,
                api_key=api_key
            )
            db.session.add(config)
            db.session.commit()
            flash('Tạo model config thành công.', 'success')
            return redirect(url_for('setup_video_prompt.index'))

    return render_template('setup_video_prompt/create_model_config.html')

@setup_video_prompt_bp.route('/model_configs/<int:id>/edit', methods=['GET', 'POST'])
def edit_model_config(id):
    model = AIModelConfig.query.get_or_404(id)

    if request.method == 'POST':
        model.provider = request.form.get('provider')
        model.model_name = request.form.get('model_name')
        model.endpoint = request.form.get('endpoint')
        model.api_key = request.form.get('api_key')
        model.active = bool(request.form.get('active'))

        db.session.commit()
        flash('Cập nhật model config thành công.', 'success')
        return redirect(url_for('setup_video_prompt.index'))

    return render_template('setup_video_prompt/edit_model_config.html', model=model)

@setup_video_prompt_bp.route('/model_configs/<int:id>/delete', methods=['POST'])
def delete_model_config(id):
    model = AIModelConfig.query.get_or_404(id)
    db.session.delete(model)
    db.session.commit()
    flash('Xóa model config thành công.', 'success')
    return redirect(url_for('setup_video_prompt.index'))


@setup_video_prompt_bp.route('/video_templates/<int:id>/edit', methods=['GET', 'POST'])
def edit_video_template(id):
    vt = VideoTemplate.query.get_or_404(id)
    categories = Category.query.all()

    if request.method == 'POST':
        vt.category_id = request.form.get('category_id')
        vt.video_file = request.form.get('video_file')
        vt.title_pattern = request.form.get('title_pattern')
        vt.description_pattern = request.form.get('description_pattern')
        vt.default_tags = request.form.get('default_tags')

        db.session.commit()
        flash('Cập nhật video template thành công.', 'success')
        return redirect(url_for('setup_video_prompt.index'))

    return render_template('setup_video_prompt/edit_video_template.html', vt=vt, categories=categories)

@setup_video_prompt_bp.route('/video_templates/<int:id>/delete', methods=['POST'])
def delete_video_template(id):
    vt = VideoTemplate.query.get_or_404(id)
    db.session.delete(vt)
    db.session.commit()
    flash('Xóa video template thành công.', 'success')
    return redirect(url_for('setup_video_prompt.index'))


@setup_video_prompt_bp.route('/prompt_templates/<int:id>/edit', methods=['GET', 'POST'])
def edit_prompt_template(id):
    prompt = AIPromptTemplate.query.get_or_404(id)
    categories = Category.query.all()
    model_configs = AIModelConfig.query.all()

    if request.method == 'POST':
        prompt.category_id = request.form.get('category_id')
        prompt.model_config_id = request.form.get('model_config_id')
        prompt.task_type = request.form.get('task_type')
        prompt.prompt_template = request.form.get('prompt_template')
        prompt.description = request.form.get('description')
        prompt.version = request.form.get('version')

        db.session.commit()
        flash('Cập nhật prompt template thành công.', 'success')
        return redirect(url_for('setup_video_prompt.index'))

    return render_template(
        'setup_video_prompt/edit_prompt_template.html',
        prompt=prompt,
        categories=categories,
        model_configs=model_configs
    )

@setup_video_prompt_bp.route('/prompt_templates/<int:id>/delete', methods=['POST'])
def delete_prompt_template(id):
    prompt = AIPromptTemplate.query.get_or_404(id)
    db.session.delete(prompt)
    db.session.commit()
    flash('Xóa prompt template thành công.', 'success')
    return redirect(url_for('setup_video_prompt.index'))



@setup_video_prompt_bp.route('/api/test_prompt', methods=['POST'])
def test_prompt():
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    model_config_id_raw = data.get('model_config_id')

    print("👉 Dữ liệu nhận được:", data)
    print("👉 prompt:", prompt)
    print("👉 model_config_id_raw:", model_config_id_raw)

    try:
        model_config_id = int(model_config_id_raw)
        print("👉 model_config_id:", model_config_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'model_config_id không hợp lệ'}), 400

    if not prompt or not model_config_id:
        return jsonify({'error': 'Thiếu prompt hoặc model_config_id'}), 400

    model_config = AIModelConfig.query.get(model_config_id)
    if not model_config:
        return jsonify({'error': 'Không tìm thấy cấu hình model'}), 404

    provider = model_config.provider.lower()
    print(f"📩 Gửi prompt test đến {provider}: {prompt}")

    try:
        if provider == 'openai':
            openai.api_key = model_config.api_key
            response = openai.ChatCompletion.create(
                model=model_config.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            content = response['choices'][0].get('message', {}).get('content', 'Không có nội dung phản hồi')
            html_response = markdown2.markdown(content)  # 🔁 convert Markdown → HTML
            return jsonify({'response': html_response})

        elif provider == 'gemini':
            model_name = model_config.model_name or 'gemini-1.5-pro'
            endpoint = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent"
            
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            params = {"key": model_config.api_key}
            
            res = requests.post(endpoint, headers=headers, params=params, json=payload)
            res.raise_for_status()
            json_data = res.json()
            
            content = json_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "Không có nội dung phản hồi")
            html_response = markdown2.markdown(content)  # 🔁 convert Markdown → HTML
            return jsonify({'response': html_response})

        else:
            return jsonify({'error': f'Provider không hỗ trợ: {model_config.provider}'}), 400

    except Exception as e:
        import traceback
        print("❌ Lỗi khi gọi AI:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500