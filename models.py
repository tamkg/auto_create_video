from extensions import db

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
