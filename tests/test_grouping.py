from pathlib import Path

from audiobook_builder.grouping import discover_subfolder_groups, group_by_leading_number


def test_group_by_leading_number_and_volume(tmp_path: Path) -> None:
    files = [
        tmp_path / "02 Book Two 01.mp3",
        tmp_path / "01 Book One 02.mp3",
        tmp_path / "01 Book One 01.mp3",
        tmp_path / "Volume 3 01.mp3",
        tmp_path / "Bonus.mp3",
    ]

    groups = group_by_leading_number(files)

    assert [path.name for path in groups["01"]] == ["01 Book One 01.mp3", "01 Book One 02.mp3"]
    assert groups["02"] == [files[0]]
    assert groups["v3"] == [files[3]]
    assert groups["_other"] == [files[4]]


def test_discover_subfolder_groups_ignores_empty_folders(tmp_path: Path) -> None:
    book = tmp_path / "Book 2"
    book.mkdir()
    (book / "01.mp3").write_bytes(b"audio")
    (tmp_path / "Empty").mkdir()

    groups = discover_subfolder_groups(tmp_path)

    assert list(groups) == ["Book 2"]
    assert groups["Book 2"][0].name == "01.mp3"
