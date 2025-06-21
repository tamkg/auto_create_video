# fonts.py
import os
import platform
from pathlib import Path

def find_fonts():
    system = platform.system()
    font_paths = []

    if system == 'Windows':
        font_paths = [Path("C:/Windows/Fonts")]
    elif system == 'Darwin':  # macOS
        font_paths = [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            Path.home() / "Library/Fonts"
        ]
    elif system == 'Linux':
        font_paths = [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path.home() / ".fonts",
            Path.home() / ".local/share/fonts"
        ]
    else:
        return []

    font_files = []
    for path in font_paths:
        if path.exists():
            for ext in ('*.ttf', '*.otf', '*.ttc'):
                font_files.extend(path.rglob(ext))

    return sorted(font_files)  # Trả về danh sách Path
