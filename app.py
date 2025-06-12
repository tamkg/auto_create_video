# app.py

from flask import Flask, render_template
from extensions import db, basedir
from flask_migrate import Migrate

from blueprints.trends.routes import trends_bp
from blueprints.downloads.routes import download_bp
from blueprints.urls.routes import url_manager_bp
from blueprints.create_videos.routes import video_bp
from blueprints.audio_tools.routes import audio_tools_bp
from blueprints.create_images.routes import create_images_bp
from blueprints.socials.routes import social_bp

import os
import logging

logging.basicConfig(level=logging.DEBUG)

def create_app():
    app = Flask(__name__, template_folder='templates')

    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'data.db')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'some_secret_key'

    UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    # 🔧 Thêm đoạn này để fix lỗi output_path
    DOWNLOAD_FOLDER = os.path.join(basedir, 'downloads')
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    app.config['OUTPUT_PATH'] = DOWNLOAD_FOLDER

    db.init_app(app)
    migrate = Migrate(app, db)

    @app.route("/", endpoint="index")
    def homepage():
        return render_template('index.html')

    # Đăng ký blueprint
    app.register_blueprint(trends_bp, url_prefix='/trends')
    app.register_blueprint(download_bp, url_prefix='/downloads')
    app.register_blueprint(url_manager_bp, url_prefix='/url')
    app.register_blueprint(video_bp, url_prefix='/create_video')
    app.register_blueprint(audio_tools_bp, url_prefix='/audio')
    app.register_blueprint(create_images_bp, url_prefix='/create_images')
    app.register_blueprint(social_bp, url_prefix='/social')

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", debug=True, port=5000)
