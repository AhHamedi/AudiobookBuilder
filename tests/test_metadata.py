from audiobook_builder.metadata import build_ffmetadata, escape_ffmetadata


def test_escape_ffmetadata_reserved_characters() -> None:
    assert escape_ffmetadata("A=B; C#D\\E") == r"A\=B\; C\#D\\E"


def test_build_ffmetadata_has_contiguous_chapters() -> None:
    metadata = build_ffmetadata(
        title="Demo",
        artist="Author",
        chapter_titles_and_durations_ms=[("Intro", 1250), ("Chapter 1", 2750)],
    )

    assert metadata.startswith(
        ";FFMETADATA1\ntitle=Demo\nartist=Author\nalbum=Demo\ngenre=Audiobook"
    )
    assert "START=0\nEND=1250\ntitle=Intro" in metadata
    assert "START=1250\nEND=4000\ntitle=Chapter 1" in metadata
