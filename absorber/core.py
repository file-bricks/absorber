"""The core of absorber: clipboard content in, a real file on disk out.

Nothing here imports GUI classes. ``mime`` only has to behave like ``QMimeData``
(``hasImage``/``imageData``/``hasText``/``text``/``hasHtml``/``html``/``hasUrls``/``urls``),
which keeps the whole materialisation path testable without a window.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from . import config as config_module
from .naming import build_stem

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
        image = mime.imageData()
        def write_image(stage: Path) -> None:
            if not image.save(str(stage), "PNG"):
                raise OSError("Bild konnte nicht vollständig gespeichert werden.")
        return [_write_unique(target, stem, "png", write_image)]

    if kind == KIND_HTML:
        return [_write_unique(target, stem, "html",
                              lambda stage: stage.write_text(mime.html(), encoding="utf-8"))]

    return [_write_unique(target, stem, config_module.text_extension(cfg),
                          lambda stage: stage.write_text(mime.text(), encoding="utf-8"))]


def _copy_files(mime, target: Path) -> list[Path]:
    written = []
    for url in mime.urls():
        source = url.toLocalFile()
        if not source:
            continue
        source_path = Path(source)
        if not source_path.is_file():
            continue  # directories are out of scope for the MVP
        destination = _write_unique(target, source_path.stem, source_path.suffix,
                                    lambda stage, source=source_path: shutil.copy2(source, stage))
        written.append(destination)
    return written


def _owned(path: Path, identity: os.stat_result) -> bool:
    """Check the directory entry itself, without following a replacement symlink."""
    current = path.lstat()
    return stat.S_ISREG(current.st_mode) and os.path.samestat(current, identity)


def _remove_owned(path: Path, identity: os.stat_result) -> None:
    try:
        if not _owned(path, identity):
            return
        try:
            path.unlink()
        except PermissionError:
            # copy2 may copy a readonly attribute to our stage, never to its source.
            if _owned(path, identity):
                path.chmod(stat.S_IREAD | stat.S_IWRITE)
                if _owned(path, identity):
                    path.unlink()
    except FileNotFoundError:
        pass


def _exclusive_file(path: Path) -> int:
    if os.name != "nt":
        return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    # The Windows CRT follows dangling symlinks even with O_EXCL. CREATE_NEW
    # together with OPEN_REPARSE_POINT reserves the directory entry itself.
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    handle = create(os.path.abspath(path), 0x40000000, 0x7, None, 1,
                    0x80 | 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        # A successful conversion transfers handle ownership to the descriptor.
        return msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
    except BaseException:
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        close(handle)
        raise


def _write_unique(directory: Path, stem: str, extension: str,
                  write: Callable[[Path], object]) -> Path:
    """Write privately, then replace only an exclusively reserved output name."""
    extension = extension.lstrip(".")
    name = f"{stem}.{extension}"
    if not stem or stem in (".", "..") or any(char in name for char in ("/", "\\")):
        raise ValueError("Ausgabename muss ein einzelner Dateiname sein.")
    if os.name == "nt" and ":" in name:
        raise ValueError("Ausgabename darf keinen alternativen Datenstrom enthalten.")
    stage = reservation = None
    stage_identity = reservation_identity = None
    try:
        fd, filename = tempfile.mkstemp(prefix=".absorber-", suffix=".tmp", dir=directory)
        stage = Path(filename)
        try:
            stage_identity = os.fstat(fd)
        finally:
            os.close(fd)
        write(stage)
        counter = 1
        while True:
            suffix = "" if counter == 1 else f"_{counter}"
            candidate = directory / f"{stem}{suffix}.{extension}"
            try:
                fd = _exclusive_file(candidate)
            except FileExistsError:
                counter += 1
                continue
            except PermissionError as error:
                # Windows reports EACCES for an existing directory under O_EXCL.
                # Advance only if a real directory entry can be confirmed.
                try:
                    candidate.lstat()
                except OSError:
                    raise error
                counter += 1
                continue
            reservation = candidate
            try:
                reservation_identity = os.fstat(fd)
            finally:
                os.close(fd)
            break
        if not _owned(reservation, reservation_identity) or not _owned(stage, stage_identity):
            raise OSError("Reservierte Ausgabedatei wurde während des Schreibens ersetzt.")
        os.replace(stage, reservation)
        result = reservation
        reservation = None
        return result
    finally:
        for path, identity in ((stage, stage_identity), (reservation, reservation_identity)):
            if path is None or identity is None:
                continue
            try:
                _remove_owned(path, identity)
            except OSError:
                # Keep the original error; never fall back to deleting unknown files.
                try:
                    print("Temporäre Absorber-Datei konnte nicht bereinigt werden.", file=sys.stderr)
                except Exception:  # noqa: BLE001, S110 -- Preserve the original write error.
                    pass


def make_namer(cfg: dict):
    """An OllamaNamer when model naming is switched on, else None."""
    if not cfg.get("model_naming"):
        return None
    from .naming import OllamaNamer

    return OllamaNamer(cfg.get("ollama_url", ""), cfg.get("model", "auto"))
