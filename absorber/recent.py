"""The 'recent files' list shown in the tray menu."""

from __future__ import annotations

import json
from pathlib import Path

from .config import config_dir


def recent_path() -> Path:
    return config_dir() / "recent.json"


def load(path: Path | None = None) -> list[str]:
    path = path or recent_path()
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(e) for e in entries] if isinstance(entries, list) else []


def add(paths, limit: int = 10, store: Path | None = None) -> list[str]:
    """Put the given paths at the front, drop duplicates, cap at ``limit``."""
    store = store or recent_path()
    entries = load(store)
    for item in reversed([str(p) for p in paths]):
        if item in entries:
            entries.remove(item)
        entries.insert(0, item)
    entries = entries[: max(1, limit)]
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return entries


def existing(limit: int = 10, store: Path | None = None) -> list[str]:
    """Recent entries that are still on disk -- a deleted file must not be offered."""
    return [e for e in load(store) if Path(e).exists()][:limit]
