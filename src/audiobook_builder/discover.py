"""Discover, sort, and deduplicate audio files."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

SUPPORTED_AUDIO_EXTENSIONS = frozenset({".mp3", ".m4a", ".wav", ".flac"})


def natural_sort_key(s: str) -> list:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"([0-9]+)", s)]


def discover_audio_files(directory: Path) -> list[Path]:
    directory = directory.resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"Not a directory: {directory}")
    found = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    ]
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(rp)
    unique.sort(key=lambda p: natural_sort_key(p.name))
    return unique


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dedupe_exact_audio_files(files: list[Path]) -> tuple[list[Path], list[tuple[Path, Path]]]:
    """
    Remove exact duplicate files while preserving order.

    Returns ``(kept_files, duplicate_pairs)`` where each pair is ``(duplicate, original)``.
    Hashing is only performed for files that share the same size.
    """
    kept: list[Path] = []
    duplicates: list[tuple[Path, Path]] = []
    by_size: dict[int, list[Path]] = {}

    for path in files:
        by_size.setdefault(path.stat().st_size, []).append(path)

    size_hash_cache: dict[tuple[int, Path], str] = {}
    for path in files:
        same_size = by_size[path.stat().st_size]
        if len(same_size) == 1:
            kept.append(path)
            continue

        path_hash = size_hash_cache.setdefault((path.stat().st_size, path), file_sha256(path))
        original: Optional[Path] = None
        for existing in kept:
            if existing.stat().st_size != path.stat().st_size:
                continue
            existing_hash = size_hash_cache.setdefault(
                (existing.stat().st_size, existing),
                file_sha256(existing),
            )
            if existing_hash == path_hash:
                original = existing
                break

        if original is None:
            kept.append(path)
        else:
            duplicates.append((path, original))

    return kept, duplicates
