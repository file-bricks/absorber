"""Regression tests for atomic config/recent writes and virtual prune ownership/retention."""

from __future__ import annotations

import os
import stat
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from absorber import _fs, config, core, recent
from tests.conftest import FakeMime


def _try_symlink(link: Path, target: Path, *, target_is_directory: bool = False) -> bool:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError):
        return False
    return True


def test_config_save_uses_unique_staging_without_fixed_tmp(tmp_path):
    path = tmp_path / "config.json"
    config.save({"mode": "virtual"}, path)
    assert config.load(path)["mode"] == "virtual"
    assert not path.with_suffix(".json.tmp").exists()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_config_save_error_preserves_existing_file_and_cleans_stage(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    config.save({"mode": "virtual"}, path)

    with pytest.raises(TypeError):
        config.save({"bad": object()}, path)
    assert config.load(path)["mode"] == "virtual"
    assert list(tmp_path.glob(".*.tmp")) == []

    def fail_replace(_src, _dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(_fs.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        config.save({"mode": "custom"}, path)

    assert config.load(path)["mode"] == "virtual"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_config_save_and_recent_add_reject_directory_and_symlink_targets(tmp_path):
    outside = tmp_path / "source.txt"
    outside.write_text("keep-source-intact", encoding="utf-8")

    cfg_dir_target = tmp_path / "cfg_as_dir"
    cfg_dir_target.mkdir()
    with pytest.raises(OSError):
        config.save({"mode": "desktop"}, cfg_dir_target)

    recent_dir_target = tmp_path / "recent_as_dir"
    recent_dir_target.mkdir()
    with pytest.raises(OSError):
        recent.add(["a.txt"], store=recent_dir_target)

    cfg_link = tmp_path / "config-link.json"
    if _try_symlink(cfg_link, outside):
        with pytest.raises(OSError):
            config.save({"mode": "desktop"}, cfg_link)
        assert outside.read_text(encoding="utf-8") == "keep-source-intact"

    recent_link = tmp_path / "recent-link.json"
    if _try_symlink(recent_link, outside):
        with pytest.raises(OSError):
            recent.add(["a.txt"], store=recent_link)
        assert outside.read_text(encoding="utf-8") == "keep-source-intact"


def test_config_save_does_not_follow_preplanted_json_tmp_symlink(tmp_path):
    outside = tmp_path / "source.txt"
    outside.write_text("protected", encoding="utf-8")
    cfg_path = tmp_path / "config.json"
    legacy_tmp = cfg_path.with_suffix(".json.tmp")
    if not _try_symlink(legacy_tmp, outside):
        legacy_tmp.write_text("unmodified-legacy-tmp", encoding="utf-8")

    config.save({"mode": "virtual"}, cfg_path)
    assert config.load(cfg_path)["mode"] == "virtual"
    assert outside.read_text(encoding="utf-8") == "protected"
    if not legacy_tmp.is_symlink():
        assert legacy_tmp.read_text(encoding="utf-8") == "unmodified-legacy-tmp"


def test_config_save_concurrent_writes_and_reads_remain_valid(tmp_path):
    path = tmp_path / "config.json"

    def write_variant(index: int) -> None:
        cfg = dict(config.DEFAULTS)
        cfg["recent_max"] = 10 + index
        config.save(cfg, path)
        loaded = config.load(path)
        assert "recent_max" in loaded

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_variant, range(32)))

    assert 10 <= config.load(path)["recent_max"] < 42
    assert list(tmp_path.glob(".*.tmp")) == []


def test_recent_add_error_preserves_existing_entries(tmp_path, monkeypatch):
    store = tmp_path / "recent.json"
    recent.add(["keep.txt"], store=store)

    def fail_replace(_src, _dst):
        raise PermissionError("simulated atomic replace denial")

    monkeypatch.setattr(_fs.os, "replace", fail_replace)
    with pytest.raises(PermissionError, match="simulated atomic replace denial"):
        recent.add(["new.txt"], store=store)

    assert recent.load(store) == ["keep.txt"]
    assert list(tmp_path.glob(".*.tmp")) == []


def test_recent_add_concurrent_threads_do_not_lose_entries(tmp_path):
    store = tmp_path / "recent.json"
    total = 16

    def add_one(index: int) -> None:
        recent.add([f"entry-{index}.txt"], limit=total, store=store)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(add_one, range(total)))

    entries = recent.load(store)
    assert len(entries) == total
    assert set(entries) == {f"entry-{i}.txt" for i in range(total)}


def test_virtual_mode_fresh_copy_of_old_file_survives_prune_and_source_keeps_mtime(tmp_path, monkeypatch):
    virtual = tmp_path / "virtual"
    monkeypatch.setattr(config, "virtual_dir", lambda: virtual)

    old_ts = time.time() - 30 * 86400
    source = tmp_path / "ancient.txt"
    source.write_text("from-archive", encoding="utf-8")
    os.utime(source, (old_ts, old_ts))

    conf = dict(config.DEFAULTS)
    conf["mode"] = "virtual"
    conf["copy_file_lists"] = True
    conf["virtual_retention_days"] = 7
    conf["model_naming"] = False

    written = core.materialize(FakeMime(urls=[str(source)]), conf)
    assert len(written) == 1
    copied = written[0]
    assert copied.parent == virtual
    assert copied.read_text(encoding="utf-8") == "from-archive"
    assert abs(source.stat().st_mtime - old_ts) < 2.0

    assert config.prune_virtual(conf) == []
    assert copied.exists()

    future = time.time() + 8 * 86400
    assert config.prune_virtual(conf, now=future) == [copied]
    assert not copied.exists()
    assert source.exists()


def test_virtual_mode_readonly_old_source_refreshes_mtime_and_prunes_cleanly(tmp_path, monkeypatch):
    virtual = tmp_path / "virtual"
    monkeypatch.setattr(config, "virtual_dir", lambda: virtual)

    old_ts = time.time() - 30 * 86400
    source = tmp_path / "readonly-old.txt"
    source.write_text("readonly-content", encoding="utf-8")
    os.utime(source, (old_ts, old_ts))
    os.chmod(source, stat.S_IREAD)
    try:
        conf = dict(config.DEFAULTS)
        conf["mode"] = "virtual"
        conf["copy_file_lists"] = True
        conf["virtual_retention_days"] = 7
        conf["model_naming"] = False

        written = core.materialize(FakeMime(urls=[str(source)]), conf)
        assert len(written) == 1
        copied = written[0]
        assert abs(source.stat().st_mtime - old_ts) < 2.0
        assert config.prune_virtual(conf) == []
        assert copied.exists()

        future = time.time() + 8 * 86400
        assert config.prune_virtual(conf, now=future) == [copied]
        assert not copied.exists()
    finally:
        if source.exists():
            os.chmod(source, stat.S_IREAD | stat.S_IWRITE)
        if virtual.exists():
            for leftover in virtual.iterdir():
                if leftover.is_file():
                    os.chmod(leftover, stat.S_IREAD | stat.S_IWRITE)


def test_desktop_mode_copy2_still_preserves_source_mtime(tmp_path):
    old_ts = 1_600_000_000.0
    source = tmp_path / "preserved.txt"
    source.write_text("keep-mtime", encoding="utf-8")
    os.utime(source, (old_ts, old_ts))

    conf = dict(config.DEFAULTS)
    conf["mode"] = "desktop"
    conf["copy_file_lists"] = True
    conf["target_dir"] = str(tmp_path / "out")
    conf["model_naming"] = False

    written = core.materialize(FakeMime(urls=[str(source)]), conf)
    assert len(written) == 1
    assert abs(written[0].stat().st_mtime - old_ts) < 2.0


def test_prune_virtual_skips_staging_dirs_hardlinks_and_symlinks(tmp_path, monkeypatch):
    virtual = tmp_path / "virtual"
    virtual.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(config, "virtual_dir", lambda: virtual)

    now = 1_700_000_000.0
    old_ts = now - 10 * 86400

    owned_old = virtual / "owned-old.txt"
    owned_old.write_text("old", encoding="utf-8")
    os.utime(owned_old, (old_ts, old_ts))

    staging = virtual / ".absorber-12345.tmp"
    staging.write_text("staging", encoding="utf-8")
    os.utime(staging, (old_ts, old_ts))

    nested_dir = virtual / "subdir"
    nested_dir.mkdir()
    nested_file = nested_dir / "inside.txt"
    nested_file.write_text("inside", encoding="utf-8")
    os.utime(nested_file, (old_ts, old_ts))

    external_target = outside / "external.txt"
    external_target.write_text("external", encoding="utf-8")
    os.utime(external_target, (old_ts, old_ts))

    hardlinked = virtual / "hardlinked.txt"
    try:
        os.link(external_target, hardlinked)
        has_hardlink = True
    except (OSError, NotImplementedError):
        has_hardlink = False

    symlinked = virtual / "sym.txt"
    has_symlink = _try_symlink(symlinked, external_target)

    removed = config.prune_virtual({"virtual_retention_days": 7}, now=now)
    assert removed == [owned_old]
    assert not owned_old.exists()
    assert staging.exists()
    assert nested_file.exists()
    assert external_target.exists()
    if has_hardlink:
        assert hardlinked.exists()
    if has_symlink:
        assert symlinked.is_symlink()


def test_prune_virtual_ignores_symlinked_virtual_folder_and_foreign_uid(tmp_path, monkeypatch):
    real_outside = tmp_path / "outside-dir"
    real_outside.mkdir()
    keep = real_outside / "keep.txt"
    keep.write_text("keep", encoding="utf-8")
    old_ts = time.time() - 30 * 86400
    os.utime(keep, (old_ts, old_ts))

    virtual_link = tmp_path / "virtual-link"
    if _try_symlink(virtual_link, real_outside, target_is_directory=True):
        monkeypatch.setattr(config, "virtual_dir", lambda: virtual_link)
        assert config.prune_virtual({"virtual_retention_days": 7}) == []
        assert keep.exists()

    foreign_dir = tmp_path / "virtual-uid"
    foreign_dir.mkdir()
    foreign_file = foreign_dir / "foreign.txt"
    foreign_file.write_text("foreign", encoding="utf-8")
    os.utime(foreign_file, (old_ts, old_ts))
    monkeypatch.setattr(config, "virtual_dir", lambda: foreign_dir)
    monkeypatch.setattr(_fs.os, "getuid", lambda: 999999, raising=False)
    # Without matching UID ownership, prune_virtual must leave the directory untouched.
    foreign_stat = os.stat_result((0, 0, 0, 0, 1000, 0, 0, 0, 0, 0))
    assert _fs.is_owned_by_current_user(foreign_stat) is False
    assert config.prune_virtual({"virtual_retention_days": 7}) == []
    assert foreign_file.exists()
