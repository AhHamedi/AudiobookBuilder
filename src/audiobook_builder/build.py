"""Orchestrate concat, metadata, encode, optional cover."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from audiobook_builder.discover import natural_sort_key
from audiobook_builder.ffmpeg import (
    ffprobe_duration_seconds,
    normalize_aac_bitrate,
    run_ffmpeg,
    select_aac_encoder,
)
from audiobook_builder.metadata import build_ffmetadata


def concat_path_line(path: Path) -> str:
    s = str(path.resolve())
    s = s.replace("'", "'\\''")
    return f"file '{s}'"


def sanitize_filename_base(name: str, max_len: int = 120) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name).strip("._")
    return name[:max_len] if len(name) > max_len else name


def infer_series_name(files: list[Path]) -> Optional[str]:
    """Infer a series name from titles like ``01 Series Name_ Book 4 1``."""
    counts: dict[str, int] = {}
    for path in files:
        stem = path.stem.replace("_", " ").strip()
        match = re.match(r"^\d+\s+(.+?)\s+Book\s+\d+(?:\s+\d+)?$", stem, re.IGNORECASE)
        if not match:
            continue
        series_name = re.sub(r"\s+", " ", match.group(1)).strip()
        if not series_name:
            continue
        counts[series_name] = counts.get(series_name, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], len(item[0])))[0]


def guess_book_title_from_files(
    files: list[Path],
    *,
    series_name: Optional[str] = None,
) -> str:
    """Generate a clean audiobook title from a group's first filename."""
    if not files:
        return "Audiobook"

    stem = re.sub(r"\s+", " ", files[0].stem.replace("_", " ")).strip()
    stem = re.sub(r"^\d+\s+", "", stem)

    volume_match = re.match(r"^Volume\s+(\d+)(?:\s+\d+)?$", stem, re.IGNORECASE)
    if volume_match:
        volume_number = volume_match.group(1)
        if series_name:
            return f"{series_name} Book {volume_number}"
        return f"Volume {volume_number}"

    stem = re.sub(r"(?i)\b(Book\s+\d+)\s+\d+$", r"\1", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem[:200] if stem else "Audiobook"


def default_title_from_files(files: list[Path]) -> str:
    return guess_book_title_from_files(files)


def build_m4b(
    files: list[Path],
    output: Path,
    *,
    title: str,
    author: str,
    bitrate: str = "96k",
    cover: Optional[Path] = None,
    dry_run: bool = False,
    stream_output: bool = False,
    encoder: str = "auto",
) -> None:
    if not files:
        raise ValueError("No audio files to merge.")
    files = sorted(files, key=lambda p: natural_sort_key(p.name))
    durations_ms: list[tuple[str, int]] = []
    for p in files:
        sec = ffprobe_duration_seconds(p)
        durations_ms.append((p.stem, int(sec * 1000)))

    meta_content = build_ffmetadata(
        title=title,
        artist=author,
        album=title,
        chapter_titles_and_durations_ms=durations_ms,
    )

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if dry_run:
        return

    with tempfile.TemporaryDirectory(prefix="audiobook_builder_") as tmp:
        tmp_path = Path(tmp)
        concat_file = tmp_path / "concat.txt"
        meta_file = tmp_path / "metadata.txt"
        concat_file.write_text(
            "\n".join(concat_path_line(p) for p in files) + "\n", encoding="utf-8"
        )
        meta_file.write_text(meta_content, encoding="utf-8")

        selected_encoder = select_aac_encoder(encoder)
        selected_bitrate = normalize_aac_bitrate(selected_encoder, bitrate)
        stage_out = tmp_path / "stage.m4b"
        final_out = tmp_path / output.name

        args = [
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-f",
            "ffmetadata",
            "-i",
            str(meta_file),
            "-map_metadata",
            "1",
            "-map_chapters",
            "1",
            "-c:a",
            selected_encoder,
            "-b:a",
            selected_bitrate,
            "-vn",
            "-movflags",
            "+faststart",
            str(stage_out),
        ]
        run_ffmpeg(args, title="Encode audiobook", stream_output=stream_output)

        if cover:
            cover = cover.resolve()
            if not cover.is_file():
                raise FileNotFoundError(f"Cover image not found: {cover}")
            cover_args = [
                "-y",
                "-i",
                str(stage_out),
                "-i",
                str(cover),
                "-map_metadata",
                "0",
                "-map_chapters",
                "0",
                "-map",
                "0:a:0",
                "-map",
                "1:v:0",
                "-c",
                "copy",
                "-disposition:v:0",
                "attached_pic",
                str(final_out),
            ]
            run_ffmpeg(cover_args, title="Attach cover art", stream_output=stream_output)
        else:
            final_out = stage_out

        shutil.move(str(final_out), str(output))
