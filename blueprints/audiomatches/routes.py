from flask import Blueprint, render_template, request, url_for, jsonify
from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException
import subprocess
import re
from gtts.lang import tts_langs
import os
import uuid
from gtts import gTTS
from pydub import AudioSegment
import tempfile
import datetime


UPLOAD_DIR = os.path.join('static', 'uploads', 'audios')
os.makedirs(UPLOAD_DIR, exist_ok=True)

audiomatch_bp = Blueprint('audiomatch', __name__, template_folder='templates')


def timestamp_to_seconds(ts):
    x = datetime.datetime.strptime(ts, "%M:%S")
    return x.minute * 60 + x.second

def get_edge_voices():
    try:
        result = subprocess.run(
            ["edge-tts", "--list-voices"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print("Lỗi khi lấy danh sách giọng đọc:", result.stderr)
            return []

        lines = result.stdout.splitlines()[2:]  # Bỏ header
        voices = []
        for line in lines:
            if not line.strip():
                continue

            m = re.match(r'^(\S+)\s+(Female|Male)\s+(.+?)\s{2,}(.+)$', line)
            if m:
                name = m.group(1)
                gender = m.group(2)
                content_categories = m.group(3)
            else:
                name = line[0:33].strip()
                gender = line[33:43].strip()
                content_categories = line[43:64].strip()

            voices.append({
                "Name": name,
                "Gender": gender,
                "ContentCategories": content_categories,
            })
        return voices
    except Exception as e:
        print("❌ Exception khi lấy Edge voices:", e)
        return []

def chunk_text(text, max_len=300):
    """Chia nhỏ đoạn text dài thành các đoạn nhỏ không vượt quá max_len ký tự, cố gắng cắt tại khoảng trắng."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_len
        if end < len(text):
            space_pos = text.rfind(' ', start, end)
            if space_pos != -1 and space_pos > start:
                end = space_pos
        chunks.append(text[start:end].strip())
        start = end
    return chunks

def parse_and_translate(content: str, target_lang='en'):
    lines = content.strip().split('\n')
    result = []

    try:
        detected_lang = detect(content)
    except LangDetectException:
        detected_lang = 'auto'

    for line in lines:
        if not line.strip():
            continue

        try:
            timestamp, text = line.split(' ', 1)
        except ValueError:
            continue

        chunks = chunk_text(text, max_len=300)
        translated_chunks = []
        for chunk in chunks:
            translated_chunk = GoogleTranslator(source=detected_lang, target=target_lang).translate(chunk)
            translated_chunks.append(translated_chunk)

        translated_text = ' '.join(translated_chunks)
        result.append(f"{timestamp} {translated_text}")

    return '\n'.join(result)

@audiomatch_bp.route('/', methods=['GET', 'POST'])
def index():
    translated = None
    content = ''
    target_lang = 'en'

    # ✅ Luôn load danh sách ngôn ngữ và giọng đọc
    translator = GoogleTranslator(source='auto', target='en')
    languages = translator.get_supported_languages(as_dict=True)
    google_tts_langs = tts_langs()
    edge_voices = get_edge_voices()  # 👉 Load luôn, không cần đợi POST

    if request.method == 'POST':
        content = request.form.get('content', '')
        target_lang = request.form.get('target_lang', 'en')

        if content.strip():
            translated = parse_and_translate(content, target_lang)

    return render_template(
        'audiomatches/index.html',
        translated=translated,
        content=content,
        target_lang=target_lang,
        languages=languages,
        google_tts_langs=google_tts_langs,
        edge_voices=edge_voices
    )


@audiomatch_bp.route('/create-audio', methods=['POST'])
def create_audio():
    tts_system = request.form.get('tts_system')
    google_voice = request.form.get('google_voice')
    edge_voice = request.form.get('edge_voice')
    translated_text = request.form.get('translated_text')

    if not translated_text:
        return "Không có nội dung để tạo audio", 400

    voice = google_voice if tts_system == "google" else edge_voice
    lines = translated_text.strip().split('\n')
    segments = []

    timestamps = []
    texts = []

    for line in lines:
        try:
            ts, txt = line.split(' ', 1)
            timestamps.append(timestamp_to_seconds(ts))
            texts.append(txt.strip())
        except ValueError:
            continue

    timestamps.append(timestamps[-1] + 3)  # giả định câu cuối dài 3s

    for i in range(len(texts)):
        duration = (timestamps[i+1] - timestamps[i]) * 1000  # millisec
        sentence = texts[i]
        temp_path = tempfile.mktemp(suffix=".mp3")

        try:
            if tts_system == "google":
                tts = gTTS(text=sentence, lang=voice, slow=False)
                tts.save(temp_path)
            else:
                cmd = [
                    "edge-tts",
                    "--voice", voice,
                    "--text", sentence,
                    "--write-media", temp_path
                ]
                subprocess.run(cmd, capture_output=True)

            audio = AudioSegment.from_file(temp_path)
            audio_duration = len(audio)

            if audio_duration < duration:
                silence = AudioSegment.silent(duration=duration - audio_duration)
                final = audio + silence
            elif audio_duration > duration:
                speedup = audio._spawn(audio.raw_data, overrides={
                    "frame_rate": int(audio.frame_rate * (audio_duration / duration))
                }).set_frame_rate(audio.frame_rate)
                final = speedup
            else:
                final = audio

            segments.append(final)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    combined = sum(segments[1:], segments[0])
    filename = f"audio_{uuid.uuid4().hex}.mp3"
    output_path = os.path.join(UPLOAD_DIR, filename)
    combined.export(output_path, format="mp3")

    audio_url = url_for('static', filename=f'uploads/audios/{filename}')
    return jsonify({'audio_url': audio_url})