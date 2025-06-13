# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from flask import current_app
from models import ScheduledVideo
from extensions import db
from blueprints.socials.routes import upload_video_to_youtube

def check_and_upload_scheduled_videos():
    with current_app.app_context():
        print("🔍 Kiểm tra video chờ đăng...")
        now = datetime.utcnow()
        videos = ScheduledVideo.query.filter(
            ScheduledVideo.status == "pending",
            ScheduledVideo.scheduled_time != None,
            ScheduledVideo.scheduled_time <= now
        ).all()

        for video in videos:
            print(f"⏰ Đăng video: {video.title}")
            try:
                upload_video_to_youtube(video)
            except Exception as e:
                print(f"❌ Upload thất bại: {e}")
                video.status = "failed"
                db.session.commit()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_upload_scheduled_videos, 'interval', minutes=2)
    scheduler.start()
    print("✅ APScheduler đã khởi động.")
