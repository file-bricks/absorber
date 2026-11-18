"""Configuration for absorber: load, save, defaults, resolved paths."""

from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

from ._fs import (
    is_owned_by_current_user,
    is_reparse_or_symlink,
    path_lock,
    remove_owned,
    write_json_atomic,
)

APP_NAME = "absorber"

DEFAULTS: dict = {
    "mode": "desktop",  # "desktop" | "virtual"
    "target_dir": "",  # empty -> user's desktop
    "text_formats": ["txt"],  # any of "txt", "md", "html"
    "copy_file_lists": False,
    "path_to_clipboard": True,
    "model_naming": True,
    "model": "auto",
    "ollama_url": "http://127.0.0.1:11434",
    "virtual_retention_days": 7,
    "recent_max": 10,
}

# Order in which a text format is picked when several are enabled.
TEXT_FORMAT_ORDER = ("txt", "md")


def _qt_location(enum_name: str) -> Path:
    """Resolve a QStandardPaths location without requiring a running QApplication."""
    from PySide6.QtCore import QCoreApplication, QStandardPaths

    if QCoreApplication.applicationName() != APP_NAME:
        QCoreApplication.setApplicationName(APP_NAME)
    location = getattr(QStandardPaths.StandardLocation, enum_name)
    return Path(QStandardPaths.writableLocation(location))


def config_dir() -> Path:
    return _qt_location("AppConfigLocation")


def config_path() -> Path:
    return config_dir() / "config.json"


def desktop_dir() -> Path:
    """The user's desktop. On this host Qt resolves it to the OneDrive desktop."""
    return _qt_location("DesktopLocation")


def virtual_dir() -> Path:
    return _qt_location("TempLocation") / APP_NAME


def load(path: Path | None = None) -> dict:
    """Load config, filling in every missing key from DEFAULTS.

    A broken or unreadable file is not fatal: absorber falls back to defaults so the
    tray keeps working instead of refusing to start.
    """
    path = path or config_path()
    cfg = dict(DEFAULTS)
    try:
        with path_lock(path):
            stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if isinstance(stored, dict):
        cfg.update({k: v for k, v in stored.items() if k in DEFAULTS})
    return cfg


def save(cfg: dict, path: Path | None = None) -> Path:
    path = path or config_path()
    return write_json_atomic(path, cfg)


def resolve_target_dir(cfg: dict) -> Path:
    """The directory the next file is written to, per mode and target_dir."""
    if cfg.get("mode") == "virtual":
        target = virtual_dir()
    else:
        configured = (cfg.get("target_dir") or "").strip()
        target = Path(configured) if configured else desktop_dir()
    target.mkdir(parents=True, exist_ok=True)
    return target


def text_extension(cfg: dict) -> str:
    """Extension used for plain text, honouring the enabled text formats."""
    enabled = cfg.get("text_formats") or []
    for ext in TEXT_FORMAT_ORDER:
        if ext in enabled:
            return ext
    return "txt"  # never leave the user without a place to put text


def _is_owned_virtual_file(item: Path, item_stat: os.stat_result) -> bool:
    if item.name.startswith(".") and item.name.endswith(".tmp"):
        return False
    return (
        not is_reparse_or_symlink(item_stat)
        and stat.S_ISREG(item_stat.st_mode)
        and is_owned_by_current_user(item_stat)
        and item_stat.st_nlink == 1
    )


def prune_virtual(cfg: dict, now: float | None = None) -> list[Path]:
    """Delete owned regular files in the virtual folder older than virtual_retention_days."""
    days = int(cfg.get("virtual_retention_days", 7))
    folder = virtual_dir()
    if days <= 0:
        return []
    try:
        folder_stat = folder.lstat()
    except OSError:
        return []
    if (
        is_reparse_or_symlink(folder_stat)
        or not stat.S_ISDIR(folder_stat.st_mode)
        or not is_owned_by_current_user(folder_stat)
    ):
        return []
    cutoff = (now if now is not None else time.time()) - days * 86400
    removed = []
    for item in folder.iterdir():
        try:
            item_stat = item.lstat()
            if (
                _is_owned_virtual_file(item, item_stat)
                and item_stat.st_mtime < cutoff
                and remove_owned(item, item_stat)
            ):
                removed.append(item)
        except OSError:
            continue  # a locked or vanished file is not worth failing the sweep over
    return removed
