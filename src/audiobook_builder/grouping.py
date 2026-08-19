"""Group audio files for batch builds."""

from __future__ import annotations

import re
from pathlib import Path

from audiobook_builder.discover import natural_sort_key

_LEADING_DIGITS = re.compile(r"^(\d+)")
_VOLUME = re.compile(r"^Volume\s+(\d+)", re.IGNORECASE)


def group_by_leading_number(files: list[Path]) -> dict[str, list[Path]]:
    """Group paths by leading digits (``01 …``) or ``Volume N …`` in the basename."""
    groups: dict[str, list[Path]] = {}
    ungrouped: list[Path] = []
    for p in files:
        m = _LEADING_DIGITS.match(p.name)
        if m:
            key = m.group(1)
            groups.setdefault(key, []).append(p)
            continue
        m = _VOLUME.match(p.name)
        if m:
            # Distinct from numeric-prefix groups (e.g. ``11 …`` vs Volume 11)
            key = f"v{m.group(1)}"
            groups.setdefault(key, []).append(p)
            continue
        ungrouped.append(p)
    for key in groups:
        groups[key].sort(key=lambda x: natural_sort_key(x.name))
    if ungrouped:
        groups.setdefault("_other", [])
        groups["_other"].extend(sorted(ungrouped, key=lambda x: natural_sort_key(x.name)))
    return groups


def discover_subfolder_groups(root: Path) -> dict[str, list[Path]]:
    """One group per immediate child directory that contains audio."""
    from audiobook_builder.discover import discover_audio_files

    root = root.resolve()
    groups: dict[str, list[Path]] = {}
    for child in sorted(root.iterdir(), key=lambda p: natural_sort_key(p.name)):
        if not child.is_dir():
            continue
        audio = discover_audio_files(child)
        if audio:
            groups[child.name] = audio
    return groups
