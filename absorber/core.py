"""The core of absorber: clipboard content in, a real file on disk out.

Nothing here imports GUI classes. ``mime`` only has to behave like ``QMimeData``
(``hasImage``/``imageData``/``hasText``/``text``/``hasHtml``/``html``/``hasUrls``/``urls``),
which keeps the whole materialisation path testable without a window.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import config as config_module
from .naming import build_stem, unique_path

#: Content kinds, in the order they are probed.
KIND_FILES = "files"
KIND_IMAGE = "image"
KIND_HTML = "html"
KIND_TEXT = "text"


def detect(mime, cfg: dict) -> str:
    """Which kind of content the clipboard holds, honouring the enabled formats.

    Returns "" when there is nothing absorber can turn into a file.
    """
    formats = cfg.get("text_formats") or []
    if cfg.get("copy_file_lists") and mime.hasUrls():
        if any(u.toLocalFile() for u in mime.urls()):
            return KIND_FILES
    if mime.hasImage() and mime.imageData() is not None:
        return KIND_IMAGE
    if "html" in formats and mime.hasHtml() and mime.html().strip():
        return KIND_HTML
    if mime.hasText() and mime.text().strip():
        return KIND_TEXT
    return ""


def materialize(mime, cfg: dict, namer=None) -> list[Path]:
    """Write the clipboard content to disk and return the paths written.

    An empty list means there was nothing to absorb -- that is a normal outcome,
    not an error.
    """
    kind = detect(mime, cfg)
    if not kind:
        return []
    target = config_module.resolve_target_dir(cfg)

    if kind == KIND_FILES:
        return _copy_files(mime, target)

    sample = mime.text() if mime.hasText() else ""
    stem = build_stem(kind, sample, namer)

    if kind == KIND_IMAGE:
        path = unique_path(target, stem, "png")
        image = mime.imageData()
        if not image.save(str(path), "PNG"):
            raise OSError(f"could not write image to {path}")
        return [path]

    if kind == KIND_HTML:
        path = unique_path(target, stem, "html")
        path.write_text(mime.html(), encoding="utf-8")
        return [path]

    path = unique_path(target, stem, config_module.text_extension(cfg))
    path.write_text(mime.text(), encoding="utf-8")
    return [path]


def _copy_files(mime, target: Path) -> list[Path]:
    written = []
    for url in mime.urls():
        source = url.toLocalFile()
        if not source:
            continue
        source_path = Path(source)
        if not source_path.is_file():
            continue  # directories are out of scope for the MVP
        destination = unique_path(target, source_path.stem, source_path.suffix)
        shutil.copy2(source_path, destination)
        written.append(destination)
    return written


def make_namer(cfg: dict):
    """An OllamaNamer when model naming is switched on, else None."""
    if not cfg.get("model_naming"):
        return None
    from .naming import OllamaNamer

    return OllamaNamer(cfg.get("ollama_url", ""), cfg.get("model", "auto"))
