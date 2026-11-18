"""Shared filesystem safety helpers: ownership checks, path locks, and atomic JSON writes."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

_REPARSE_TAGS = frozenset(
    tag
    for name in ("IO_REPARSE_TAG_SYMLINK", "IO_REPARSE_TAG_MOUNT_POINT")
    if (tag := getattr(stat, name, 0))
)

_LOCK_GUARD = threading.Lock()
_PATH_LOCKS: dict[Path, threading.RLock] = {}


def is_reparse_or_symlink(st: os.stat_result) -> bool:
    """Return True if *st* is a symlink or Windows mount/symlink reparse point."""
    return stat.S_ISLNK(st.st_mode) or getattr(st, "st_reparse_tag", 0) in _REPARSE_TAGS


def is_owned_by_current_user(st: os.stat_result) -> bool:
    """Verify POSIX UID ownership where available; returns True on platforms without getuid."""
    getuid = getattr(os, "getuid", None)
    if getuid is None:
        return True
    return st.st_uid == getuid()


def path_lock(path: Path) -> threading.RLock:
    """Return a re-entrant per-path lock keyed by normalized path without following leaf symlinks."""
    normalized = Path(os.path.abspath(os.fspath(path)))
    with _LOCK_GUARD:
        lock = _PATH_LOCKS.get(normalized)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[normalized] = lock
        return lock


def owned_regular_file(path: Path, identity: os.stat_result) -> bool:
    """Check the directory entry itself without following a replacement symlink."""
    current = path.lstat()
    return (
        not is_reparse_or_symlink(current)
        and stat.S_ISREG(current.st_mode)
        and os.path.samestat(current, identity)
    )


def remove_owned(
    path: Path,
    identity: os.stat_result,
    *,
    owned_check: Callable[[Path, os.stat_result], bool] = owned_regular_file,
) -> bool:
    """Remove *path* only while it still refers to the file identified by *identity*."""
    try:
        if not owned_check(path, identity):
            return False
        try:
            path.unlink()
            return True
        except PermissionError:
            # Copies from read-only sources inherit readonly bits on the owned file.
            if owned_check(path, identity):
                os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
                if owned_check(path, identity):
                    path.unlink()
                    return True
            return False
    except FileNotFoundError:
        return False


def refresh_owned_mtime(
    path: Path,
    identity: os.stat_result,
    timestamp: float | None = None,
) -> None:
    """Set access/modification times on an owned file without touching any external source."""
    if not owned_regular_file(path, identity):
        raise OSError(f"Refusing to update timestamp on unowned file: {path}")
    times = None if timestamp is None else (timestamp, timestamp)
    try:
        os.utime(path, times)
    except PermissionError:
        if not owned_regular_file(path, identity):
            raise
        mode = stat.S_IMODE(path.lstat().st_mode)
        os.chmod(path, mode | stat.S_IWRITE)
        try:
            if not owned_regular_file(path, identity):
                raise
            os.utime(path, times)
        finally:
            if owned_regular_file(path, identity):
                os.chmod(path, mode)


def _assert_safe_json_target(path: Path) -> None:
    try:
        target_stat = path.lstat()
    except FileNotFoundError:
        return
    if is_reparse_or_symlink(target_stat) or not stat.S_ISREG(target_stat.st_mode):
        raise OSError(f"Refusing to overwrite non-regular target: {path}")


def _replace_file(stage: Path, path: Path) -> None:
    """Publish *stage* onto *path*, retrying brief Windows reader sharing contention."""
    delays = (0.002, 0.005, 0.01, 0.02, 0.04)
    for attempt in range(len(delays) + 1):
        try:
            os.replace(stage, path)
            return
        except PermissionError as exc:
            # Windows MoveFileExW fails with WinError 5/32 while another reader holds dst.
            if os.name != "nt" or getattr(exc, "winerror", None) not in (5, 32) or attempt == len(delays):
                raise
            time.sleep(delays[attempt])
            _assert_safe_json_target(path)


def write_json_atomic(path: Path, payload: object, *, lock_acquired: bool = False) -> Path:
    """Serialize *payload* first and publish it atomically via an exclusive staging file."""
    data = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")

    def _write() -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        _assert_safe_json_target(path)
        stage: Path | None = None
        stage_identity: os.stat_result | None = None
        fd: int | None = None
        try:
            fd, filename = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
            )
            stage = Path(filename)
            stage_identity = os.fstat(fd)
            with os.fdopen(fd, "wb") as handle:
                fd = None
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if not owned_regular_file(stage, stage_identity):
                raise OSError(f"Staging file was replaced before publication: {stage}")
            _assert_safe_json_target(path)
            _replace_file(stage, path)
            return path
        except BaseException:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if stage is not None and stage_identity is not None:
                try:
                    remove_owned(stage, stage_identity)
                except OSError:
                    pass
            raise

    if lock_acquired:
        return _write()
    with path_lock(path):
        return _write()
