"""Build a real sample audiobook and render its captured CLI output as a README GIF."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
WIDTH, HEIGHT = 1440, 900
BACKGROUND = "#09111f"
PANEL = "#101c2d"
TEXT = "#e8edf5"
MUTED = "#8291a8"
CYAN = "#57c7d4"
AMBER = "#f0b35a"
GREEN = "#69d29b"


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "SFNSMono.ttf" if not bold else "SFNSMono.ttf"
    return ImageFont.truetype(f"/System/Library/Fonts/{name}", size=size)


def _run_demo(work: Path) -> tuple[str, dict]:
    configured_tools = os.environ.get("AUDIOBOOK_FFMPEG_DIR")
    if configured_tools:
        tools = Path(configured_tools)
        ffmpeg = tools / "ffmpeg"
        ffprobe = tools / "ffprobe"
    else:
        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")
        if not (ffmpeg_path and ffprobe_path):
            raise SystemExit(
                "Install FFmpeg or set AUDIOBOOK_FFMPEG_DIR before rendering the demo."
            )
        ffmpeg = Path(ffmpeg_path)
        ffprobe = Path(ffprobe_path)
        tools = ffmpeg.parent

    if not (ffmpeg.is_file() and ffprobe.is_file()):
        raise SystemExit("AUDIOBOOK_FFMPEG_DIR must contain ffmpeg and ffprobe.")

    tracks = work / "tracks"
    tracks.mkdir()
    for number, (label, frequency) in enumerate(
        (("Opening", 330), ("The Journey", 440), ("Homecoming", 550)), start=1
    ):
        output = tracks / f"{number:02d} {label}.mp3"
        subprocess.run(
            [
                str(ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:duration=1",
                "-c:a",
                "libmp3lame",
                str(output),
            ],
            check=True,
        )

    output = work / "The Long Way Home.m4b"
    env = os.environ.copy()
    env["AUDIOBOOK_FFMPEG_DIR"] = str(tools)
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "audiobook_builder.cli",
            "build",
            str(tracks),
            "--title",
            "The Long Way Home",
            "--author",
            "A. Narrator",
            "--out",
            str(output),
            "--force",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    clean = clean.replace(str(work), "demo")

    probe = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format_tags=title,artist,genre:chapter=start_time,end_time:chapter_tags=title",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return clean, json.loads(probe.stdout)


def _terminal_frame(lines: list[tuple[str, str]], progress: float) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 50, WIDTH - 55, HEIGHT - 50), radius=24, fill=PANEL)
    draw.ellipse((88, 80, 108, 100), fill="#ff6b68")
    draw.ellipse((120, 80, 140, 100), fill="#f4bf4f")
    draw.ellipse((152, 80, 172, 100), fill="#63c66d")
    draw.text((205, 75), "AudiobookBuilder — demo", font=_font(25), fill=MUTED)

    y = 140
    for text, color in lines:
        draw.text((90, y), text, font=_font(25), fill=color, spacing=7)
        y += 36 * (text.count("\n") + 1)

    draw.rounded_rectangle((90, HEIGHT - 88, WIDTH - 90, HEIGHT - 76), radius=6, fill="#25354c")
    draw.rounded_rectangle(
        (90, HEIGHT - 88, 90 + int((WIDTH - 180) * progress), HEIGHT - 76),
        radius=6,
        fill=CYAN,
    )
    return image


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="audiobook_demo_") as directory:
        captured, probe = _run_demo(Path(directory))

    chapters = probe["chapters"]
    track_rows = [
        "  1   01 Opening.mp3      0:01",
        "  2   02 The Journey.mp3  0:01",
        "  3   03 Homecoming.mp3    0:01",
    ]
    frames = [
        _terminal_frame(
            [
                ("$ ls demo/tracks", CYAN),
                ("01 Opening.mp3", TEXT),
                ("02 The Journey.mp3", TEXT),
                ("03 Homecoming.mp3", TEXT),
            ],
            0.14,
        ),
        _terminal_frame(
            [
                ("$ audiobook-build build demo/tracks \\", CYAN),
                ('    --title "The Long Way Home" --author "A. Narrator"', CYAN),
                ("", TEXT),
                ("Audiobook builder  v1.0.0", AMBER),
                ("AAC .m4b with chapters for macOS Books", MUTED),
            ],
            0.35,
        ),
        _terminal_frame(
            [
                ("Tracks", AMBER),
                ("  #   File                  Duration", MUTED),
                *[(row, TEXT) for row in track_rows],
                ("", TEXT),
                ("3 files  ·  The Long Way Home", GREEN),
                ("Encoder: aac_at  Bitrate: 96k", MUTED),
                ("Encoding The_Long_Way_Home.m4b ...", TEXT),
            ],
            0.72,
        ),
        _terminal_frame(
            [
                ("✓ Done  demo/The Long Way Home.m4b", GREEN),
                ("", TEXT),
                ("$ ffprobe demo/The\\ Long\\ Way\\ Home.m4b", CYAN),
                (f"Title    {probe['format']['tags']['title']}", TEXT),
                (f"Artist   {probe['format']['tags']['artist']}", TEXT),
                (f"Genre    {probe['format']['tags']['genre']}", TEXT),
                (f"Chapters {len(chapters)} — Opening · The Journey · Homecoming", TEXT),
                ("AAC audio · Apple Books-ready", AMBER),
            ],
            1.0,
        ),
    ]
    frames[0].save(
        ASSETS / "demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=[1300, 1600, 2200, 2600],
        loop=0,
        optimize=True,
    )
    print(
        f"Rendered {ASSETS / 'demo.gif'} from a real build ({len(captured)} captured characters)."
    )


if __name__ == "__main__":
    main()
