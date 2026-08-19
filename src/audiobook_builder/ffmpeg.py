"""FFmpeg / ffprobe invocation."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class FFmpegError(RuntimeError):
    """Raised when ffmpeg or ffprobe fails."""


def resolve_ffmpeg_binaries() -> tuple[str, str]:
    """
    Resolve ffmpeg and ffprobe executables.

    Order:
    1. ``AUDIOBOOK_FFMPEG_DIR`` — directory containing both ``ffmpeg`` and ``ffprobe``.
    2. ``PATH`` (``shutil.which``).
    """
    env_dir = os.environ.get("AUDIOBOOK_FFMPEG_DIR", "").strip()
    if env_dir:
        base = Path(env_dir).expanduser().resolve()
        ff = base / "ffmpeg"
        fp = base / "ffprobe"
        if ff.is_file() and os.access(ff, os.X_OK) and fp.is_file() and os.access(fp, os.X_OK):
            return str(ff), str(fp)
        raise FFmpegError(
            f"AUDIOBOOK_FFMPEG_DIR must contain executable ffmpeg and ffprobe binaries: {base}"
        )

    w_ff = shutil.which("ffmpeg")
    w_fp = shutil.which("ffprobe")
    if w_ff and w_fp:
        return w_ff, w_fp

    raise FFmpegError(
        "ffmpeg and ffprobe were not found. Install them with `brew install ffmpeg`, "
        "or set AUDIOBOOK_FFMPEG_DIR to a directory containing both executables."
    )


def check_ffmpeg() -> None:
    ff, fp = resolve_ffmpeg_binaries()
    for name, path in (("ffmpeg", ff), ("ffprobe", fp)):
        try:
            subprocess.run(
                [path, "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise FFmpegError(f"{name} not working at {path}") from e


def ffmpeg_available_encoders() -> set[str]:
    ff, _ = resolve_ffmpeg_binaries()
    try:
        result = subprocess.run(
            [ff, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError) as error:
        raise FFmpegError(f"Could not inspect FFmpeg encoders: {error}") from error
    encoders: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("A"):
            encoders.add(parts[1])
    return encoders


def select_aac_encoder(preferred: Optional[str] = None) -> str:
    """
    Pick the AAC encoder to use.

    ``preferred`` may be:
    - ``None`` / ``auto``: prefer ``aac_at`` on macOS when available, else ``aac``
    - an explicit encoder name like ``aac`` or ``aac_at``
    """
    encoders = ffmpeg_available_encoders()
    if preferred and preferred != "auto":
        if preferred not in encoders:
            raise FFmpegError(f"Requested encoder '{preferred}' is not available.")
        return preferred
    if "aac_at" in encoders:
        return "aac_at"
    if "aac" in encoders:
        return "aac"
    raise FFmpegError("No AAC encoder available in ffmpeg.")


def normalize_aac_bitrate(encoder: str, requested_bitrate: str) -> str:
    """
    Normalize bitrate for a selected AAC encoder.

    ``aac_at`` on macOS commonly clamps mono 32 kHz spoken-word content to 96k.
    We normalize proactively to avoid warnings and keep throughput high.
    """
    match = re.fullmatch(r"([1-9]\d*)[kK]", requested_bitrate.strip())
    if not match:
        raise FFmpegError(
            f"Invalid bitrate '{requested_bitrate}'. Use a positive value such as 64k or 96k."
        )

    value = int(match.group(1))
    if encoder == "aac_at" and value > 96:
        return "96k"
    return f"{value}k"


def ffprobe_duration_seconds(path: Path) -> float:
    _, fp = resolve_ffmpeg_binaries()
    cmd = [
        fp,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(
            f"ffprobe failed for {path}:\n{result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        return float(result.stdout.strip())
    except ValueError as e:
        raise FFmpegError(f"Could not parse duration for {path}") from e


def run_ffmpeg(
    args: list[str],
    *,
    title: str = "ffmpeg",
    stream_output: bool = False,
) -> None:
    ff, _ = resolve_ffmpeg_binaries()
    try:
        proc = subprocess.run(
            [ff, *args],
            capture_output=not stream_output,
            text=True,
        )
    except OSError as error:
        raise FFmpegError(f"Could not start {title}: {error}") from error
    if proc.returncode != 0:
        if stream_output:
            err = f"{title} failed. See ffmpeg output above."
        else:
            err = proc.stderr.strip() or proc.stdout.strip()
        raise FFmpegError(f"{title} failed:\n{err}")
