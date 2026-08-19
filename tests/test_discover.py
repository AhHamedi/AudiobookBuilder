from pathlib import Path

from audiobook_builder.discover import (
    dedupe_exact_audio_files,
    discover_audio_files,
    natural_sort_key,
)


def test_natural_sort_orders_track_numbers_numerically() -> None:
    names = ["track 10.mp3", "track 2.mp3", "track 1.mp3"]
    assert sorted(names, key=natural_sort_key) == [
        "track 1.mp3",
        "track 2.mp3",
        "track 10.mp3",
    ]


def test_discover_audio_files_is_case_insensitive_and_non_recursive(tmp_path: Path) -> None:
    (tmp_path / "02 Chapter.FLAC").write_bytes(b"flac")
    (tmp_path / "01 Intro.MP3").write_bytes(b"mp3")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "00 Hidden.mp3").write_bytes(b"nested")

    assert [path.name for path in discover_audio_files(tmp_path)] == [
        "01 Intro.MP3",
        "02 Chapter.FLAC",
    ]


def test_dedupe_exact_audio_files_preserves_first_copy(tmp_path: Path) -> None:
    original = tmp_path / "01.mp3"
    duplicate = tmp_path / "02.mp3"
    unique = tmp_path / "03.mp3"
    original.write_bytes(b"same bytes")
    duplicate.write_bytes(b"same bytes")
    unique.write_bytes(b"different!")

    kept, duplicates = dedupe_exact_audio_files([original, duplicate, unique])

    assert kept == [original, unique]
    assert duplicates == [(duplicate, original)]
