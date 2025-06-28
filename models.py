from extensions import db
from datetime import datetime

class Video(db.Model):
    __tablename__ = 'videos'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    segments = db.relationship('Segment', backref='video', cascade="all, delete-orphan")

class Segment(db.Model):
    __tablename__ = 'segments'
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    order_index = db.Column(db.Integer, nullable=False)
    images = db.relationship('Image', backref='segment', cascade="all, delete-orphan")

class Image(db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    segment_id = db.Column(db.Integer, db.ForeignKey('segments.id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)

class DownloadUrl(db.Model):
    __tablename__ = 'download_urls'
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1024), unique=True, nullable=False)
    category = db.Column(db.String(50), default='none', nullable=False)  
    status = db.Column(db.String(20), default='pending', nullable=False)
    title = db.Column(db.String(255))
    ratio = db.Column(db.String(20), nullable=True)  # Thêm cột tỷ lệ khung hình
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class YouTubeChannel(db.Model):
    __tablename__ = 'youtube_channels'
    id = db.Column(db.Integer, primary_key=True)

    channel_id = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    thumbnail_url = db.Column(db.String(1024))

    client_id = db.Column(db.String(255), nullable=True)
    client_secret = db.Column(db.String(255), nullable=True)

    credentials_json = db.Column(db.Text, nullable=True)
    credentials_path = db.Column(db.String(255), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    videos = db.relationship('ScheduledVideo', backref='channel', cascade="all, delete-orphan")
    posts = db.relationship('ScheduledPost', backref='channel', cascade="all, delete-orphan")


class Topic(db.Model):
    __tablename__ = 'topics'
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), unique=True, nullable=False)

    videos = db.relationship('ScheduledVideo', backref='topic_ref', cascade="all, delete-orphan")
    posts = db.relationship('ScheduledPost', backref='topic_ref', cascade="all, delete-orphan")


class ScheduledVideo(db.Model):
    __tablename__ = 'scheduled_videos'
    id = db.Column(db.Integer, primary_key=True)

    channel_id = db.Column(db.Integer, db.ForeignKey('youtube_channels.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    tags = db.Column(db.Text)

    video_type = db.Column(db.String(20), default='long')  # 'short' or 'long'
    privacy_status = db.Column(db.String(20), default='private')

    video_file = db.Column(db.String(1024), nullable=False)
    thumbnail_file = db.Column(db.String(1024), nullable=True)

    scheduled_time = db.Column(db.DateTime, nullable=True)
    uploaded_video_id = db.Column(db.String(64), nullable=True)

    status = db.Column(db.String(20), default='pending')  # pending | uploading | done | failed

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScheduledPost(db.Model):
    __tablename__ = 'scheduled_posts'
    id = db.Column(db.Integer, primary_key=True)

    channel_id = db.Column(db.Integer, db.ForeignKey('youtube_channels.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=True)

    content = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(1024), nullable=True)

    scheduled_time = db.Column(db.DateTime, nullable=True)
    post_id = db.Column(db.String(64), nullable=True)  # post ID nếu đã đăng

    status = db.Column(db.String(20), default='pending')  # pending | posted | failed

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    video_templates = db.relationship('VideoTemplate', backref='category', lazy=True)
    ai_prompt_templates = db.relationship('AIPromptTemplate', backref='category', lazy=True)

class VideoTemplate(db.Model):
    __tablename__ = 'video_templates'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    video_file = db.Column(db.String(1024), nullable=False)
    title_pattern = db.Column(db.Text, nullable=False)
    description_pattern = db.Column(db.Text, nullable=True)
    default_tags = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_uploaded_at = db.Column(db.DateTime, nullable=True)
    upload_count = db.Column(db.Integer, default=0)

class AIPromptTemplate(db.Model):
    __tablename__ = 'ai_prompt_templates'
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    prompt_template = db.Column(db.Text, nullable=False)
    model_config_id = db.Column(db.Integer, db.ForeignKey('ai_model_configs.id'), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(255), nullable=True)
    version = db.Column(db.String(20), nullable=True)

class AIModelConfig(db.Model):
    __tablename__ = 'ai_model_configs'
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    endpoint = db.Column(db.String(255), nullable=True)
    api_key = db.Column(db.String(255), nullable=True)  # consider encrypting
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    prompt_templates = db.relationship('AIPromptTemplate', backref='model_config', lazy=True)    



class CategoryClip(db.Model):
    __tablename__ = 'category_clips'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    videos = db.relationship('VideoClip', backref='category_clip', lazy=True)

class VideoClip(db.Model):
    __tablename__ = 'video_clips'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    filepath = db.Column(db.String(512), nullable=False)

    # FK → CategoryClip
    category_id = db.Column(db.Integer, db.ForeignKey('category_clips.id'), nullable=True)

    ratio = db.Column(db.String(10), nullable=True)
    duration = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
