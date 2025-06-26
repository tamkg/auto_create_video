import os
import uuid
import srt
from datetime import timedelta

def generate_subtitles(translated_texts, durations, output_dir, fmt="srt"):
    subtitle_path = os.path.join(output_dir, f"sub_{uuid.uuid4().hex[:6]}.{fmt}")

    if fmt == "srt":
        subs = []
        start_time = 0
        for idx, (text, dur) in enumerate(zip(translated_texts, durations), start=1):
            subs.append(srt.Subtitle(
                index=idx,
                start=timedelta(seconds=start_time),
                end=timedelta(seconds=start_time + dur),
                content=text
            ))
            start_time += dur
        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write(srt.compose(subs))

    elif fmt == "lrc":
        start_time = 0
        with open(subtitle_path, "w", encoding="utf-8") as f:
            for text, dur in zip(translated_texts, durations):
                m, s = divmod(int(start_time), 60)
                ms = int((start_time - int(start_time)) * 100)
                f.write(f"[{m:02}:{s:02}.{ms:02}]{text}\n")
                start_time += dur

    elif fmt == "ass":
        def fmt_ass(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            cs = int((t - int(t)) * 100)
            return f"{h:01}:{m:02}:{s:02}.{cs:02}"

        start_time = 0
        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write("[Script Info]\nScriptType: v4.00+\n\n")
            f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, BackColour, OutlineColour, "
                    "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write("Style: Default,Arial,20,&H00FFFFFF,&H00000000,&H00000000,1,1,0,2,10,10,10,1\n\n")
            f.write("[Events]\nFormat: Layer, Start, End, Style, Text\n")

            for text, dur in zip(translated_texts, durations):
                f.write(f"Dialogue: 0,{fmt_ass(start_time)},{fmt_ass(start_time + dur)},Default,,0,0,0,,{text}\n")
                start_time += dur

    else:
        raise ValueError("Unsupported subtitle format")

    return subtitle_path
