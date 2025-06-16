import asyncio
import edge_tts
from gtts import gTTS
import subprocess
import re
import tempfile
from pydub import AudioSegment  # pip install pydub
import os
from textwrap import wrap

# Chia văn bản dài thành nhiều đoạn nhỏ
def split_text(text, max_length=200):
    import re
    from textwrap import wrap

    # Cắt theo câu để giữ nghĩa tự nhiên
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_length:
            current_chunk += sentence + " "
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Xử lý những đoạn vẫn quá dài (do không có dấu câu)
    final_chunks = []
    for idx, chunk in enumerate(chunks):
        if len(chunk) > max_length:
            wrapped = wrap(chunk, max_length)
            print(f"[split_text] ⚠️ Đoạn {idx} ({len(chunk)} ký tự) quá dài, chia thành {len(wrapped)} phần nhỏ.")
            final_chunks.extend(wrapped)
        else:
            final_chunks.append(chunk)

    print(f"[split_text] ✅ Tổng {len(final_chunks)} đoạn sau khi chia.")
    return final_chunks

# Edge TTS (async)
async def generate_edge_audio(text: str, voice: str, output_path: str):
    if len(text) > 5000:
        raise ValueError(f"[Edge TTS] Đoạn văn bản quá dài: {len(text)} ký tự (giới hạn là 5000)")
    
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(output_path)

# Google TTS (sync)
def generate_google_audio(text: str, lang: str, output_path: str):
    tts = gTTS(text=text, lang=lang)
    tts.save(output_path)

# Hàm chính: Gọi TTS theo engine, xử lý chia đoạn & ghép file
def generate_audio(text: str, output_path: str, engine: str = "gtts", lang: str = "en", voice: str = "en-US-AriaNeural"):
    print(f"[TTS] Đang tạo audio bằng {engine}, voice={voice}, lang={lang}, text_length={len(text)}")
    chunks = split_text(text, max_length=200)

    with tempfile.TemporaryDirectory() as temp_dir:
        audio_segments = []

        for i, chunk in enumerate(chunks):
            chunk = chunk.strip()
            if not chunk:
                continue

            chunk_path = os.path.join(temp_dir, f"chunk_{i}.mp3")

            try:
                if engine == "edge":
                    asyncio.run(generate_edge_audio(chunk, voice, chunk_path))
                else:
                    generate_google_audio(chunk, lang, chunk_path)

                if os.path.exists(chunk_path):
                    audio = AudioSegment.from_file(chunk_path, format="mp3")
                    audio_segments.append(audio)
                    os.remove(chunk_path)  # Xóa file ngay sau khi dùng
            except Exception as e:
                print(f"Lỗi tạo audio cho đoạn {i}: {e}")
                continue

        if not audio_segments:
            raise Exception("Không tạo được đoạn audio nào!")

        final_audio = sum(audio_segments)
        final_audio.export(output_path, format="mp3")

# Lấy thông tin voice của edge-tts
def get_voices():
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
