import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from audiobook_builder.build import build_m4b
from audiobook_builder.ffmpeg import FFmpegError, resolve_ffmpeg_binaries


@pytest.mark.integration
def test_end_to_end_m4b_contains_aac_metadata_and_chapters(tmp_path: Path) -> None:
    try:
        ffmpeg, ffprobe = resolve_ffmpeg_binaries()
    except FFmpegError:
        pytest.skip("FFmpeg is not installed")

    tracks = []
    for number, frequency in enumerate((440, 550), start=1):
        track = tmp_path / f"{number:02d} Chapter {number}.wav"
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={frequency}:duration=0.5",
                str(track),
            ],
            check=True,
        )
        tracks.append(track)

    output = tmp_path / "Demo Book.m4b"
    build_m4b(tracks, output, title="Demo Book", author="Demo Author", encoder="aac")

    probe = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_chapters",
            "-show_format",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(probe.stdout)

    assert payload["streams"][0]["codec_name"] == "aac"
    assert payload["format"]["tags"]["title"] == "Demo Book"
    assert payload["format"]["tags"]["artist"] == "Demo Author"
    assert payload["format"]["tags"]["genre"] == "Audiobook"
    assert [chapter["tags"]["title"] for chapter in payload["chapters"]] == [
        "01 Chapter 1",
        "02 Chapter 2",
    ]
    assert float(payload["chapters"][0]["end_time"]) == pytest.approx(0.5, abs=0.02)
    assert float(payload["chapters"][1]["start_time"]) == pytest.approx(0.5, abs=0.02)

    cover = tmp_path / "cover.jpg"
    Image.new("RGB", (128, 128), "#123456").save(cover)
    covered_output = tmp_path / "Covered Book.m4b"
    build_m4b(
        tracks,
        covered_output,
        title="Covered Book",
        author="Demo Author",
        cover=cover,
        encoder="aac",
    )
    covered_probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-of", "json", str(covered_output)],
        capture_output=True,
        text=True,
        check=True,
    )
    covered_streams = json.loads(covered_probe.stdout)["streams"]
    video_stream = next(stream for stream in covered_streams if stream["codec_type"] == "video")
    assert video_stream["disposition"]["attached_pic"] == 1
