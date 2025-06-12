from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import YouTubeChannel
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
                "title": info["title"],
                "channel_id": channel.channel_id,
                "thumbnail_url": info["thumbnail"],
                "subscribers": info["subscribers"],
                "views": info["views"],
                "country": info["country"],
                "published_at": info["published_at"]
            })
        else:
            enriched_channels.append({
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
