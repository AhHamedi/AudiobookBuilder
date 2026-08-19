import subprocess
from pathlib import Path

import pytest

from audiobook_builder import ffmpeg
from audiobook_builder.ffmpeg import FFmpegError


def test_resolve_ffmpeg_uses_explicit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("ffmpeg", "ffprobe"):
        binary = tmp_path / name
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        binary.chmod(0o755)
    monkeypatch.setenv("AUDIOBOOK_FFMPEG_DIR", str(tmp_path))

    assert ffmpeg.resolve_ffmpeg_binaries() == (
        str(tmp_path / "ffmpeg"),
        str(tmp_path / "ffprobe"),
    )


def test_resolve_ffmpeg_rejects_incomplete_explicit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDIOBOOK_FFMPEG_DIR", str(tmp_path))
    with pytest.raises(FFmpegError, match="must contain executable"):
        ffmpeg.resolve_ffmpeg_binaries()


def test_resolve_ffmpeg_uses_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIOBOOK_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(
        ffmpeg.shutil,
        "which",
        lambda name: f"/usr/local/bin/{name}",
    )
    assert ffmpeg.resolve_ffmpeg_binaries() == (
        "/usr/local/bin/ffmpeg",
        "/usr/local/bin/ffprobe",
    )


def test_resolve_ffmpeg_reports_missing_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIOBOOK_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name: None)
    with pytest.raises(FFmpegError, match="brew install ffmpeg"):
        ffmpeg.resolve_ffmpeg_binaries()


@pytest.mark.parametrize(
    ("encoder", "requested", "expected"),
    [("aac", "128k", "128k"), ("aac_at", "128k", "96k"), ("aac_at", "64K", "64k")],
)
def test_normalize_aac_bitrate(encoder: str, requested: str, expected: str) -> None:
    assert ffmpeg.normalize_aac_bitrate(encoder, requested) == expected


@pytest.mark.parametrize("requested", ["", "0k", "96", "fast", "-1k"])
def test_normalize_aac_bitrate_rejects_invalid_values(requested: str) -> None:
    with pytest.raises(FFmpegError, match="Invalid bitrate"):
        ffmpeg.normalize_aac_bitrate("aac", requested)


def test_select_aac_encoder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ffmpeg, "ffmpeg_available_encoders", lambda: {"aac", "aac_at"})
    assert ffmpeg.select_aac_encoder("auto") == "aac_at"
    assert ffmpeg.select_aac_encoder("aac") == "aac"
    with pytest.raises(FFmpegError, match="not available"):
        ffmpeg.select_aac_encoder("libfdk_aac")


def test_ffmpeg_available_encoders_parses_audio_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ffmpeg, "resolve_ffmpeg_binaries", lambda: ("ffmpeg", "ffprobe"))
    monkeypatch.setattr(
        ffmpeg.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout=" A..... aac AAC\n V..... h264 H.264\n A..... aac_at AAC AT\n"
        ),
    )
    assert ffmpeg.ffmpeg_available_encoders() == {"aac", "aac_at"}


def test_check_ffmpeg_wraps_failed_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ffmpeg, "resolve_ffmpeg_binaries", lambda: ("ffmpeg", "ffprobe"))

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(ffmpeg.subprocess, "run", fail)
    with pytest.raises(FFmpegError, match="ffmpeg not working"):
        ffmpeg.check_ffmpeg()


def test_run_ffmpeg_reports_process_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ffmpeg, "resolve_ffmpeg_binaries", lambda: ("ffmpeg", "ffprobe"))
    monkeypatch.setattr(
        ffmpeg.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, stdout="", stderr="bad input"
        ),
    )
    with pytest.raises(FFmpegError, match="bad input"):
        ffmpeg.run_ffmpeg(["-i", "missing.mp3"])
