import json
import time
from pathlib import Path

from absorber import config


def test_load_missing_file_returns_defaults(tmp_path):
    assert config.load(tmp_path / "nope.json") == config.DEFAULTS


def test_load_broken_json_returns_defaults(tmp_path):
    broken = tmp_path / "config.json"
    broken.write_text("{not json", encoding="utf-8")
    assert config.load(broken) == config.DEFAULTS


def test_load_fills_missing_keys(tmp_path):
    partial = tmp_path / "config.json"
    partial.write_text(json.dumps({"mode": "virtual"}), encoding="utf-8")
    loaded = config.load(partial)
    assert loaded["mode"] == "virtual"
    assert loaded["recent_max"] == config.DEFAULTS["recent_max"]


def test_load_ignores_unknown_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"nonsense": 1}), encoding="utf-8")
    assert "nonsense" not in config.load(path)


def test_save_round_trip(tmp_path):
    path = tmp_path / "sub" / "config.json"
    cfg = dict(config.DEFAULTS, mode="virtual", target_dir="C:\\out")
    config.save(cfg, path)
    assert config.load(path) == cfg


def test_save_leaves_no_temp_file(tmp_path):
    path = tmp_path / "config.json"
    config.save(dict(config.DEFAULTS), path)
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"]


def test_text_extension_prefers_txt():
    assert config.text_extension({"text_formats": ["md", "txt"]}) == "txt"


def test_text_extension_uses_md_when_only_md():
    assert config.text_extension({"text_formats": ["md"]}) == "md"


def test_text_extension_never_returns_html():
    assert config.text_extension({"text_formats": ["html"]}) == "txt"


def test_text_extension_on_empty_selection():
    assert config.text_extension({"text_formats": []}) == "txt"


def test_resolve_target_dir_uses_configured_folder(tmp_path):
    cfg = dict(config.DEFAULTS, target_dir=str(tmp_path / "out"))
    assert config.resolve_target_dir(cfg) == tmp_path / "out"


def test_resolve_target_dir_falls_back_to_desktop(tmp_path, monkeypatch):
    desktop = tmp_path / "desktop"
    monkeypatch.setattr(config, "desktop_dir", lambda: desktop)
    assert config.resolve_target_dir(dict(config.DEFAULTS)) == desktop


def test_resolve_target_dir_virtual_mode(tmp_path, monkeypatch):
    virtual = tmp_path / "virtual"
    monkeypatch.setattr(config, "virtual_dir", lambda: virtual)
    cfg = dict(config.DEFAULTS, mode="virtual", target_dir=str(tmp_path / "ignored"))
    assert config.resolve_target_dir(cfg) == virtual


def test_prune_virtual_removes_old_files(tmp_path, monkeypatch):
    virtual = tmp_path / "virtual"
    virtual.mkdir()
    monkeypatch.setattr(config, "virtual_dir", lambda: virtual)
    old, fresh = virtual / "old.txt", virtual / "fresh.txt"
    old.write_text("x", encoding="utf-8")
    fresh.write_text("y", encoding="utf-8")
    now = time.time()
    import os

    os.utime(old, (now - 8 * 86400, now - 8 * 86400))
    removed = config.prune_virtual({"virtual_retention_days": 7}, now=now)
    assert removed == [old]
    assert fresh.exists()


def test_prune_virtual_disabled_with_zero_days(tmp_path, monkeypatch):
    virtual = tmp_path / "virtual"
    virtual.mkdir()
    (virtual / "old.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(config, "virtual_dir", lambda: virtual)
    assert config.prune_virtual({"virtual_retention_days": 0}) == []


def test_prune_virtual_on_missing_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "virtual_dir", lambda: tmp_path / "gone")
    assert config.prune_virtual({"virtual_retention_days": 7}) == []


def test_qt_paths_are_real_directories():
    """The Qt-resolved locations must be usable paths, not empty strings."""
    for folder in (config.config_dir(), config.desktop_dir(), config.virtual_dir()):
        assert isinstance(folder, Path)
        assert str(folder)
