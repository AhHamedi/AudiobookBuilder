"""FFMETADATA1 chapter and tag building."""

from __future__ import annotations

from typing import Optional


def escape_ffmetadata(text: str) -> str:
    text = str(text)
    for char in ("\\", "=", ";", "#", "\n"):
        text = text.replace(char, "\\" + char)
    return text


def build_ffmetadata(
    *,
    title: str,
    artist: str,
    album: Optional[str] = None,
    genre: Optional[str] = "Audiobook",
    chapter_titles_and_durations_ms: list[tuple[str, int]],
) -> str:
    """chapter_titles_and_durations_ms: list of (chapter_title, duration_ms)."""
    lines: list[str] = [";FFMETADATA1", f"title={escape_ffmetadata(title)}"]
    lines.append(f"artist={escape_ffmetadata(artist)}")
    lines.append(f"album={escape_ffmetadata(album or title)}")
    if genre:
        lines.append(f"genre={escape_ffmetadata(genre)}")
    lines.append("")

    current_ms = 0
    for ch_title, duration_ms in chapter_titles_and_durations_ms:
        start = current_ms
        end = current_ms + duration_ms
        lines.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={start}",
                f"END={end}",
                f"title={escape_ffmetadata(ch_title)}",
                "",
            ]
        )
        current_ms = end

    return "\n".join(lines)
