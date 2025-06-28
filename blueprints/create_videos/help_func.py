from datetime import timedelta
import srt, pysubs2
import os

def generate_subtitles(translated_texts, durations, output_dir, fmt="srt"):
    subs = []
    current = timedelta()
    for i, (text, duration) in enumerate(zip(translated_texts, durations), 1):
        start = current
        end = current + timedelta(seconds=duration)
        subs.append(srt.Subtitle(index=i, start=start, end=end, content=text.strip()))
        current = end

    path = os.path.join(output_dir, f"subtitle.{fmt}")

    if fmt == "srt":
        with open(path, "w", encoding="utf-8") as f:
            f.write(srt.compose(subs))
    elif fmt == "lrc":
        with open(path, "w", encoding="utf-8") as f:
            for sub in subs:
                total_sec = int(sub.start.total_seconds())
                minutes = total_sec // 60
                seconds = sub.start.total_seconds() % 60
                f.write(f"[{int(minutes):02}:{seconds:05.2f}]{sub.content}\n")
    elif fmt == "ass":
        subs2 = pysubs2.SSAFile()
        for sub in subs:
            start_ms = int(sub.start.total_seconds() * 1000)
            end_ms = int(sub.end.total_seconds() * 1000)
            subs2.append(pysubs2.SSAEvent(start=start_ms, end=end_ms, text=sub.content))
        subs2.save(path)

    return path
