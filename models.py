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


from datetime import datetime

class YouTubeChannel(db.Model):
    __tablename__ = 'youtube_channels'
    id = db.Column(db.Integer, primary_key=True)

    channel_id = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    thumbnail_url = db.Column(db.String(1024))

    # ➕ Thêm client_id & secret nếu dùng kiểu nhập tay
    client_id = db.Column(db.String(255), nullable=True)
    client_secret = db.Column(db.String(255), nullable=True)

    # Giữ lại để track token
    credentials_json = db.Column(db.Text, nullable=True)  # Lưu toàn bộ token JSON

    credentials_path = db.Column(db.String(255), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    videos = db.relationship('ScheduledVideo', backref='channel', cascade="all, delete-orphan")



class ScheduledVideo(db.Model):
    __tablename__ = 'scheduled_videos'
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('youtube_channels.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    tags = db.Column(db.Text)
    privacy_status = db.Column(db.String(20), default='private')
    video_file = db.Column(db.String(1024), nullable=False)
    thumbnail_file = db.Column(db.String(1024))
    scheduled_time = db.Column(db.DateTime, nullable=True)
    uploaded_video_id = db.Column(db.String(64))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)