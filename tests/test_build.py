from pathlib import Path

from audiobook_builder.build import (
    concat_path_line,
    guess_book_title_from_files,
    infer_series_name,
    sanitize_filename_base,
)


def test_sanitize_filename_base() -> None:
    assert sanitize_filename_base("  A: Book / Part?  ") == "A_Book_Part"
    assert sanitize_filename_base("." * 8) == ""
    assert len(sanitize_filename_base("x" * 200)) == 120


def test_concat_path_line_escapes_apostrophe(tmp_path: Path) -> None:
    line = concat_path_line(tmp_path / "Author's Track.mp3")
    assert line.startswith("file '")
    assert "Author'\\''s Track.mp3" in line


def test_title_and_series_inference() -> None:
    files = [
        Path("01 Earthsea_ Book 4 1.mp3"),
        Path("01 Earthsea_ Book 4 2.mp3"),
    ]
    assert infer_series_name(files) == "Earthsea"
    assert guess_book_title_from_files(files, series_name="Earthsea") == "Earthsea Book 4"
    assert guess_book_title_from_files([Path("Volume 3 01.mp3")], series_name="Earthsea") == (
        "Earthsea Book 3"
    )
