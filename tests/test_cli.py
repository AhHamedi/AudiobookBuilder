from pathlib import Path

import pytest
from typer.testing import CliRunner

from audiobook_builder import __version__
from audiobook_builder.cli import _batch_group_sort_key, _resolve_parallel_jobs, app

runner = CliRunner()


def test_version_option() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_parallel_job_resolution(monkeypatch) -> None:
    monkeypatch.setattr("audiobook_builder.cli.os.cpu_count", lambda: 12)
    assert _resolve_parallel_jobs(0, 10) == 4
    assert _resolve_parallel_jobs(8, 3) == 3
    assert _resolve_parallel_jobs(0, 0) == 1


def test_batch_group_sort_key_orders_named_numbered_and_other() -> None:
    assert sorted(["_other", "v3", "10", "2", "Alpha"], key=_batch_group_sort_key) == [
        "Alpha",
        "2",
        "v3",
        "10",
        "_other",
    ]


def test_build_dry_run_lists_tracks_without_ffmpeg(tmp_path: Path) -> None:
    (tmp_path / "02 Chapter.MP3").write_bytes(b"two")
    (tmp_path / "01 Intro.mp3").write_bytes(b"one")

    result = runner.invoke(app, ["build", str(tmp_path), "--author", "Author", "--dry-run"])

    assert result.exit_code == 0
    assert "01 Intro.mp3" in result.stdout
    assert "02 Chapter.MP3" in result.stdout
    assert "Dry run" in result.stdout


def test_build_reports_empty_folder(tmp_path: Path) -> None:
    result = runner.invoke(app, ["build", str(tmp_path), "--author", "Author", "--dry-run"])
    assert result.exit_code == 1
    assert "No audio files found" in result.stdout


def test_build_invokes_encoder_with_normalized_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "01 Intro.mp3").write_bytes(b"audio")
    calls = []
    monkeypatch.setattr("audiobook_builder.cli.check_ffmpeg", lambda: None)
    monkeypatch.setattr(
        "audiobook_builder.cli._resolve_encoder_label", lambda encoder, bitrate: ("aac", bitrate)
    )
    monkeypatch.setattr("audiobook_builder.cli.ffprobe_duration_seconds", lambda path: 61.0)
    monkeypatch.setattr(
        "audiobook_builder.cli.build_m4b", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    result = runner.invoke(
        app,
        [
            "build",
            str(tmp_path),
            "--author",
            "Author",
            "--title",
            "Demo Book",
            "--out",
            str(tmp_path / "custom-name"),
        ],
    )

    assert result.exit_code == 0
    assert calls[0][0][1].name == "custom-name.m4b"
    assert calls[0][1]["title"] == "Demo Book"
    assert "1:01" in result.stdout


def test_build_declined_overwrite_exits_without_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "01 Intro.mp3").write_bytes(b"audio")
    output = tmp_path / "existing.m4b"
    output.write_bytes(b"keep")
    monkeypatch.setattr("audiobook_builder.cli.check_ffmpeg", lambda: None)

    result = runner.invoke(
        app,
        ["build", str(tmp_path), "--author", "Author", "--out", str(output)],
        input="n\n",
    )

    assert result.exit_code == 0
    assert output.read_bytes() == b"keep"


def test_batch_dry_run_supports_numbered_groups(tmp_path: Path) -> None:
    (tmp_path / "01 Series Book 1 01.mp3").write_bytes(b"one")
    (tmp_path / "02 Series Book 2 01.mp3").write_bytes(b"two")

    result = runner.invoke(app, ["batch", str(tmp_path), "--author", "Author", "--dry-run"])

    assert result.exit_code == 0
    assert "Batch plan" in result.stdout
    assert "Series Book 1" in result.stdout
    assert "Series Book 2" in result.stdout


def test_batch_dry_run_supports_subfolders(tmp_path: Path) -> None:
    book = tmp_path / "Book One"
    book.mkdir()
    (book / "01 Intro.flac").write_bytes(b"one")

    result = runner.invoke(
        app,
        [
            "batch",
            str(tmp_path),
            "--author",
            "Author",
            "--one-subfolder-per-book",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Book One" in result.stdout


def test_batch_sequential_and_parallel_encode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "series"
    root.mkdir()
    (root / "01 Series Book 1 01.mp3").write_bytes(b"one")
    (root / "02 Series Book 2 01.mp3").write_bytes(b"two")
    outputs = []
    monkeypatch.setattr("audiobook_builder.cli.check_ffmpeg", lambda: None)
    monkeypatch.setattr(
        "audiobook_builder.cli._resolve_encoder_label", lambda encoder, bitrate: ("aac", bitrate)
    )
    monkeypatch.setattr(
        "audiobook_builder.cli.build_m4b",
        lambda files, output, **kwargs: outputs.append(output),
    )

    sequential = runner.invoke(
        app,
        [
            "batch",
            str(root),
            "--author",
            "Author",
            "--out-dir",
            str(tmp_path / "sequential"),
            "--jobs",
            "1",
        ],
    )
    parallel = runner.invoke(
        app,
        [
            "batch",
            str(root),
            "--author",
            "Author",
            "--out-dir",
            str(tmp_path / "parallel"),
            "--jobs",
            "2",
        ],
    )

    assert sequential.exit_code == 0
    assert parallel.exit_code == 0
    assert len(outputs) == 4
    assert "Starting parallel batch" in parallel.stdout
