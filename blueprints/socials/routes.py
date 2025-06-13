from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import YouTubeChannel, ScheduledVideo, Topic  
from extensions import db
import os
import json
import requests
from datetime import datetime
from werkzeug.utils import secure_filename
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
# from .func import upload_video_to_youtube

# ✅ Bỏ cảnh báo HTTPS
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

social_bp = Blueprint('social', __name__, template_folder='templates')

# ✅ Thư mục lưu file client_secret.json
UPLOAD_FOLDER = 'uploaded_credentials'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ Scopes OAuth
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]

# ✅ Làm mới token nếu hết hạn và cập nhật lại DB
def get_fresh_credentials_and_update_db(channel: YouTubeChannel):
    try:
        creds_data = json.loads(channel.credentials_json)
        creds = Credentials.from_authorized_user_info(creds_data)

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                channel.credentials_json = creds.to_json()
                channel.token_expiry = creds.expiry
                db.session.commit()
            else:
                print("❌ Không thể làm mới token.")
                return None
        return creds
    except Exception as e:
        print("❌ Lỗi refresh credentials:", e)
        return None

# ✅ Lấy thông tin kênh từ credentials
def get_channel_info_from_credentials(credentials_json_str):
    try:
        channel = YouTubeChannel.query.filter_by(credentials_json=credentials_json_str).first()
        if not channel:
            return None

        creds = get_fresh_credentials_and_update_db(channel)
        if not creds:
            return None

        youtube = build("youtube", "v3", credentials=creds)
        response = youtube.channels().list(part="snippet,statistics", mine=True).execute()

        if "items" not in response or not response["items"]:
            return None

        info = response["items"][0]
        snippet = info["snippet"]
        stats = info.get("statistics", {})

        return {
            "title": snippet["title"],
            "thumbnail": snippet["thumbnails"]["default"]["url"],
            "description": snippet.get("description"),
            "published_at": snippet.get("publishedAt"),
            "country": snippet.get("country", "Không rõ"),
            "subscribers": stats.get("subscriberCount", "N/A"),
            "views": stats.get("viewCount", "N/A"),
        }
    except Exception as e:
        print("❌ Lỗi lấy thông tin kênh:", e)
        return None

@social_bp.route('/')
def index():
    return render_template('socials/index.html')

@social_bp.route("/youtube/channels", endpoint="list_youtube_channels")
def list_youtube_channels():
    channels = YouTubeChannel.query.all()
    enriched_channels = []

    for channel in channels:
        info = get_channel_info_from_credentials(channel.credentials_json)
        if info:
            enriched_channels.append({
                "id": channel.id, # cột id trong db
                "title": info["title"],
                "channel_id": channel.channel_id, # id của chanel ytb
                "thumbnail_url": info["thumbnail"],
                "subscribers": info["subscribers"],
                "views": info["views"],
                "country": info["country"],
                "published_at": info["published_at"]
            })
        else:
            enriched_channels.append({
                "id": channel.id,
                "title": channel.title or "Không lấy được",
                "channel_id": channel.channel_id,
                "thumbnail_url": channel.thumbnail_url,
                "subscribers": "N/A",
                "views": "N/A",
                "country": "Không rõ",
                "published_at": None
            })

    return render_template("socials/youtube_channels.html", channels=enriched_channels)

@social_bp.route("/youtube/connect/form", methods=["POST"], endpoint="connect_youtube_form")
def connect_youtube_form():
    auth_method = request.form.get("auth_method")

    if auth_method == "manual":
        client_id = request.form.get("client_id")
        client_secret = request.form.get("client_secret")

        if not client_id or not client_secret:
            flash("Vui lòng nhập đầy đủ Client ID và Secret", "danger")
            return redirect(url_for("social.list_youtube_channels"))

        session["auth_type"] = "manual"
        session["client_config"] = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": ["http://localhost:5000/social/youtube/oauth/callback"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }

    elif auth_method == "file":
        file = request.files.get("client_file")
        if not file or file.filename == '':
            flash("Chưa chọn file JSON hợp lệ", "danger")
            return redirect(url_for("social.list_youtube_channels"))

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        with open(filepath, "r") as f:
            config = json.load(f)

        session["auth_type"] = "file"
        session["client_config"] = config

    else:
        flash("Phương thức kết nối không hợp lệ", "danger")
        return redirect(url_for("social.list_youtube_channels"))

    return redirect(url_for("social.youtube_oauth_start"))

@social_bp.route("/youtube/oauth/start", endpoint="youtube_oauth_start")
def youtube_oauth_start():
    config = session.get("client_config")
    if not config:
        return "Chưa có cấu hình OAuth", 400

    flow = Flow.from_client_config(
        config,
        scopes=SCOPES,
        redirect_uri="http://localhost:5000/social/youtube/oauth/callback"
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )

    session["oauth_state"] = state
    return redirect(auth_url)

@social_bp.route("/youtube/oauth/callback")
def youtube_oauth_callback():
    state = session.get("oauth_state")
    config = session.get("client_config")
    auth_type = session.get("auth_type")

    if not state or not config or not auth_type:
        return "Thiếu thông tin xác thực", 400

    flow = Flow.from_client_config(
        config,
        scopes=SCOPES,
        state=state,
        redirect_uri="http://localhost:5000/social/youtube/oauth/callback"
    )

    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    headers = {"Authorization": f"Bearer {credentials.token}"}
    response = requests.get("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", headers=headers)
    data = response.json()

    if "items" not in data or not data["items"]:
        flash("Không lấy được thông tin kênh", "danger")
        return redirect(url_for("social.list_youtube_channels"))

    item = data["items"][0]
    info = item["snippet"]

    channel = YouTubeChannel.query.filter_by(channel_id=item["id"]).first()
    if not channel:
        channel = YouTubeChannel(channel_id=item["id"])

    channel.title = info["title"]
    channel.thumbnail_url = info["thumbnails"]["default"]["url"]
    channel.token_expiry = credentials.expiry
    channel.credentials_json = credentials.to_json()

    if auth_type == "manual":
        installed = config.get("installed", {})
        channel.client_id = installed.get("client_id")
        channel.client_secret = installed.get("client_secret")
    else:
        channel.client_id = None
        channel.client_secret = None

    db.session.add(channel)
    db.session.commit()

    flash(f"Kết nối thành công với kênh: {info['title']}", "success")
    return redirect(url_for("social.list_youtube_channels"))

@social_bp.route("/youtube/delete/<channel_id>", methods=["POST"], endpoint="delete_youtube_channel")
def delete_youtube_channel(channel_id):
    channel = YouTubeChannel.query.filter_by(channel_id=channel_id).first()
    if not channel:
        flash("Không tìm thấy kênh cần xoá", "danger")
        return redirect(url_for("social.list_youtube_channels"))

    db.session.delete(channel)
    db.session.commit()
    flash(f"Đã xoá kênh: {channel.title}", "success")
    return redirect(url_for("social.list_youtube_channels"))


@social_bp.route("/youtube/videos/manage", methods=["GET"], endpoint="manage_videos")
def manage_videos():
    channel_id = request.args.get("channel_id", type=int)
    if channel_id:
        channels = YouTubeChannel.query.filter_by(id=channel_id).all()
    else:
        channels = YouTubeChannel.query.all()

    video_data = []

    for channel in channels:
        creds = get_fresh_credentials_and_update_db(channel)
        if not creds:
            continue

        try:
            youtube = build("youtube", "v3", credentials=creds)

            search_response = youtube.search().list(
                part="id",
                forMine=True,
                type="video",
                maxResults=10
            ).execute()

            video_ids = [item["id"]["videoId"] for item in search_response.get("items", []) if "videoId" in item["id"]]
            if not video_ids:
                continue

            videos_response = youtube.videos().list(
                part="snippet,statistics",
                id=",".join(video_ids)
            ).execute()

            for item in videos_response.get("items", []):
                video_data.append({
                    "channel_title": channel.title,
                    "video_id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"].get("description", ""),
                    "published_at": item["snippet"]["publishedAt"],
                    "thumbnail_url": item["snippet"]["thumbnails"]["default"]["url"],
                    "views": item["statistics"].get("viewCount", "N/A"),
                    "likes": item["statistics"].get("likeCount", "N/A")
                })

        except Exception as e:
            print(f"❌ Lỗi khi lấy video của kênh {channel.title}: {e}")

    return render_template("socials/manage_videos.html", videos=video_data, channel_id=channel_id)


@social_bp.route("/youtube/posts/manage", methods=["GET"], endpoint="manage_posts")
def manage_posts():
    channel_id = request.args.get("channel_id", type=int)
    if channel_id:
        channels = YouTubeChannel.query.filter_by(id=channel_id).all()
    else:
        channels = YouTubeChannel.query.all()

    posts = []

    for channel in channels:
        creds = get_fresh_credentials_and_update_db(channel)
        if not creds:
            continue

        try:
            youtube = build("youtube", "v3", credentials=creds)

            activities_response = youtube.activities().list(
                part="snippet,contentDetails",
                mine=True,
                maxResults=10
            ).execute()

            for item in activities_response.get("items", []):
                kind = item["snippet"]["type"]
                if kind == "upload":
                    video_id = item["contentDetails"]["upload"]["videoId"]
                    posts.append({
                        "channel_title": channel.title,
                        "title": item["snippet"].get("title", "[Không có tiêu đề]"),
                        "published_at": item["snippet"]["publishedAt"],
                        "description": item["snippet"].get("description", ""),
                        "video_id": video_id
                    })
        except Exception as e:
            print(f"❌ Lỗi khi lấy bài viết từ kênh {channel.title}: {e}")

    return render_template("socials/manage_posts.html", posts=posts, channel_id=channel_id)


# Func normal
def upload_video_to_youtube(video: ScheduledVideo):
    from googleapiclient.http import MediaFileUpload
    from models import YouTubeChannel
    from extensions import db
    import traceback

    channel = YouTubeChannel.query.get(video.channel_id)
    if not channel:
        print("❌ Không tìm thấy kênh.")
        return

    creds = get_fresh_credentials_and_update_db(channel)
    if not creds:
        print("❌ Không lấy được credentials.")
        return

    youtube = build("youtube", "v3", credentials=creds)

    tags_list = [tag.strip() for tag in video.tags.split(",")] if video.tags else []

    body = {
        "snippet": {
            "title": video.title,
            "description": video.description or "",
            "tags": tags_list,
            "categoryId": "22",  # Mặc định: People & Blogs
        },
        "status": {
            "privacyStatus": video.privacy_status,
        },
    }

    media = MediaFileUpload(video.video_file, resumable=True)

    try:
        insert_request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        response = insert_request.execute()

        video.youtube_video_id = response["id"]
        video.status = "uploaded"
        video.uploaded_at = datetime.utcnow()
        db.session.commit()
        print(f"✅ Đã đăng video: {video.title}")
    except Exception as e:
        print(f"❌ Upload thất bại: {e}")
        print(traceback.format_exc())
        video.status = "failed"
        db.session.commit()



@social_bp.route("/youtube/videos/upload", methods=["POST"], endpoint="upload_video")
def upload_video():
    try:
        channel_id = request.form.get("channel_id")
        topic_id = request.form.get("topic_id") or None
        title = request.form.get("title")
        description = request.form.get("description")
        tags = request.form.get("tags")
        video_type = request.form.get("video_type", "long")
        privacy_status = request.form.get("privacy_status", "private")

        scheduled_time_str = request.form.get("scheduled_time")
        scheduled_time = (
            datetime.fromisoformat(scheduled_time_str)
            if scheduled_time_str else None
        )

        video_file = request.files["video_file"]
        thumbnail_file = request.files.get("thumbnail_file")

        if not video_file:
            flash("Chưa chọn file video.", "danger")
            return redirect(url_for("social.manage_videos"))

        # Tạo thư mục lưu
        video_folder = os.path.join("uploads", "videos")
        thumb_folder = os.path.join("uploads", "thumbnails")
        os.makedirs(video_folder, exist_ok=True)
        os.makedirs(thumb_folder, exist_ok=True)

        # Lưu video
        video_filename = secure_filename(video_file.filename)
        video_path = os.path.join(video_folder, video_filename)
        video_file.save(video_path)

        thumbnail_path = None
        if thumbnail_file and thumbnail_file.filename:
            thumbnail_filename = secure_filename(thumbnail_file.filename)
            thumbnail_path = os.path.join(thumb_folder, thumbnail_filename)
            thumbnail_file.save(thumbnail_path)

        new_video = ScheduledVideo(
            channel_id=channel_id,
            topic_id=topic_id,
            title=title,
            description=description,
            tags=tags,
            video_type=video_type,
            privacy_status=privacy_status,
            video_file=video_path,
            thumbnail_file=thumbnail_path,
            scheduled_time=scheduled_time,
            status="pending"
        )

        db.session.add(new_video)
        db.session.commit()

        # ✅ Nếu không có scheduled_time thì upload luôn
        if scheduled_time is None:
            upload_video_to_youtube(new_video)

        flash("✅ Video đã được lên lịch đăng!" if scheduled_time else "✅ Video đã được đăng ngay!", "success")
    except Exception as e:
        flash(f"❌ Có lỗi xảy ra khi lên lịch: {e}", "danger")

    return redirect(url_for("social.manage_videos"))
