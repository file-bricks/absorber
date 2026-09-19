"""Configuration for absorber: load, save, defaults, resolved paths."""

from __future__ import annotations

import json
from pathlib import Path

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
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if isinstance(stored, dict):
        cfg.update({k: v for k, v in stored.items() if k in DEFAULTS})
    return cfg


def save(cfg: dict, path: Path | None = None) -> Path:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path


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


def prune_virtual(cfg: dict, now: float | None = None) -> list[Path]:
    """Delete files in the virtual folder older than virtual_retention_days."""
    import time

    days = int(cfg.get("virtual_retention_days", 7))
    folder = virtual_dir()
    if days <= 0 or not folder.is_dir():
        return []
    cutoff = (now if now is not None else time.time()) - days * 86400
    removed = []
    for item in folder.iterdir():
        try:
            if item.is_file() and item.stat().st_mtime < cutoff:
                item.unlink()
                removed.append(item)
        except OSError:
            continue  # a locked or vanished file is not worth failing the sweep over
    return removed
