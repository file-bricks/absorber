"""Synthetic output-ownership regressions; no real clipboard or model access."""
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from conftest import FakeImage, FakeMime

from absorber import core


def make_mime(kind, text, source):
    if kind == "image":
        return FakeMime(image=FakeImage(text.encode()))
    if kind == "files":
        return FakeMime(urls=[str(source)])
    if kind == "html":
        return FakeMime(text=text, html=text)
    return FakeMime(text=text)


@pytest.mark.parametrize("kind", ["text", "markdown", "html", "image", "files"])
def test_parallel_materializations_keep_both_payloads(cfg, tmp_path, monkeypatch, kind):
    target = Path(cfg["target_dir"])
    cfg.update(copy_file_lists=True, text_formats=["html"] if kind == "html" else ["md"] if kind == "markdown" else ["txt"])
    sources = []
    for label in ("A", "B"):
        source = tmp_path / label / "same.dat"
        source.parent.mkdir()
        source.write_bytes(("synthetic-" + label).encode())
        sources.append(source)
    monkeypatch.setattr(core, "build_stem", lambda *a: "same")
    barrier = threading.Barrier(2)
    original_text, original_bytes, original_copy = Path.write_text, Path.write_bytes, shutil.copy2

    def text_write(path, value, *a, **k):
        if path.parent == target and value.startswith("synthetic-"):
            barrier.wait(timeout=10)
        return original_text(path, value, *a, **k)

    def bytes_write(path, value, *a, **k):
        if path.parent == target and value.startswith(b"synthetic-"):
            barrier.wait(timeout=10)
        return original_bytes(path, value, *a, **k)

    def copy(source, destination, *a, **k):
        barrier.wait(timeout=10)
        return original_copy(source, destination, *a, **k)

    monkeypatch.setattr(Path, "write_text", text_write)
    monkeypatch.setattr(Path, "write_bytes", bytes_write)
    monkeypatch.setattr(core.shutil, "copy2", copy)
    with ThreadPoolExecutor(max_workers=2) as pool:
        returned = list(pool.map(lambda pair: core.materialize(make_mime(kind, "synthetic-" + pair[0], pair[1]), cfg), zip(("A", "B"), sources)))
    paths = [result[0] for result in returned]
    assert paths[0] != paths[1]
    assert {path.read_bytes() for path in paths} == {b"synthetic-A", b"synthetic-B"}
    assert set(target.iterdir()) == set(paths)
    assert [source.read_bytes() for source in sources] == [b"synthetic-A", b"synthetic-B"]


@pytest.mark.parametrize("kind", ["text", "html", "image", "files"])
def test_failed_write_leaves_no_partial_output(cfg, tmp_path, monkeypatch, kind):
    target = Path(cfg["target_dir"])
    cfg.update(copy_file_lists=True, text_formats=["html", "txt"])
    source = tmp_path / "source.dat"
    source.write_bytes(b"original-source")
    original_write = Path.write_text
    error = OSError("synthetic partial write")

    def partial(path, value, *a, **k):
        original_write(path, "partial", encoding="utf-8")
        raise error

    def partial_copy(source, destination, *a, **k):
        Path(destination).write_bytes(b"partial")
        raise error

    class BadImage:
        def save(self, path, fmt):
            Path(path).write_bytes(b"partial")
            return False

    monkeypatch.setattr(Path, "write_text", partial)
    monkeypatch.setattr(core.shutil, "copy2", partial_copy)
    mime = FakeMime(image=BadImage()) if kind == "image" else make_mime(kind, "synthetic-text", source)
    with pytest.raises(OSError) as caught:
        core.materialize(mime, cfg)
    if kind != "image":
        assert caught.value is error
    assert list(target.iterdir()) == []
    assert source.read_bytes() == b"original-source"


def test_real_qimage_output_is_readable_and_private_stage_removed(cfg):
    from PySide6.QtGui import QColor, QImage

    image = QImage(2, 2, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    result = core.materialize(FakeMime(image=image), cfg)[0]
    loaded = QImage(str(result))
    assert loaded.size() == image.size()
    assert loaded.pixelColor(0, 0) == QColor("red")
    assert list(result.parent.iterdir()) == [result]


def test_dangling_symlink_counts_as_collision(cfg, tmp_path, monkeypatch):
    target = Path(cfg["target_dir"])
    target.mkdir()
    original = target / "same.txt"
    missing = tmp_path / "unrelated-missing.txt"
    try:
        original.symlink_to(missing)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege unavailable (1314)")
        raise
    monkeypatch.setattr(core, "build_stem", lambda *a: "same")
    result = core.materialize(FakeMime(text="synthetic"), cfg)[0]
    assert result.name == "same_2.txt"
    assert original.is_symlink()
    assert not missing.exists()


def test_same_folder_file_copy_preserves_original(cfg, monkeypatch):
    target = Path(cfg["target_dir"])
    target.mkdir()
    source = target / "source.txt"
    source.write_bytes(b"source")
    cfg["copy_file_lists"] = True
    result = core.materialize(FakeMime(urls=[str(source)]), cfg)[0]
    assert result.name == "source_2.txt"
    assert source.read_bytes() == result.read_bytes() == b"source"


@pytest.mark.parametrize("readonly", [False, True])
def test_publication_error_preserves_source_and_cleans_owned_files(cfg, tmp_path, monkeypatch, readonly):
    source = tmp_path / "source.txt"
    source.write_bytes(b"original-source")
    cfg["copy_file_lists"] = True
    error = PermissionError("synthetic publication failure")
    if readonly:
        source.chmod(0o444)
    original_mode = source.stat().st_mode
    def fail(*args):
        raise error
    monkeypatch.setattr(core.os, "replace", fail)
    try:
        with pytest.raises(PermissionError) as caught:
            core.materialize(FakeMime(urls=[str(source)]), cfg)
        assert caught.value is error
        assert source.read_bytes() == b"original-source"
        assert source.stat().st_mode == original_mode
        assert list(Path(cfg["target_dir"]).iterdir()) == []
    finally:
        source.chmod(0o600)


def test_foreign_replacement_of_reservation_is_preserved(cfg, tmp_path, monkeypatch):
    target = Path(cfg["target_dir"])
    original = tmp_path / "foreign-original.bin"
    original.write_bytes(b"foreign-original")
    expected = target / "reserved.txt"
    original_open, original_close = os.open, os.close
    descriptor = set()
    def opened(path, flags, *args, **kwargs):
        fd = original_open(path, flags, *args, **kwargs)
        if Path(path) == expected and flags & os.O_EXCL:
            descriptor.add(fd)
        return fd
    def closed(fd):
        original_close(fd)
        if fd in descriptor:
            descriptor.remove(fd)
            expected.unlink()
            os.link(original, expected)
    monkeypatch.setattr(core, "build_stem", lambda *a: "reserved")
    monkeypatch.setattr(core.os, "open", opened)
    monkeypatch.setattr(core.os, "close", closed)
    with pytest.raises(OSError):
        core.materialize(FakeMime(text="synthetic"), cfg)
    assert list(target.iterdir()) == [expected]
    assert os.path.samefile(expected, original)
    assert original.read_bytes() == expected.read_bytes() == b"foreign-original"


def test_partial_file_batch_keeps_completed_files_and_sources(cfg, tmp_path, monkeypatch):
    first, second = tmp_path / "first.txt", tmp_path / "second.txt"
    first.write_bytes(b"first-original")
    second.write_bytes(b"second-original")
    cfg["copy_file_lists"] = True
    original_copy = shutil.copy2
    error = OSError("second copy failed")
    def copy(source, stage, *args, **kwargs):
        if Path(source) == second:
            Path(stage).write_bytes(b"partial")
            raise error
        return original_copy(source, stage, *args, **kwargs)
    monkeypatch.setattr(core.shutil, "copy2", copy)
    with pytest.raises(OSError) as caught:
        core.materialize(FakeMime(urls=[str(first), str(second)]), cfg)
    assert caught.value is error
    target = Path(cfg["target_dir"])
    assert list(target.iterdir()) == [target / "first.txt"]
    assert (target / "first.txt").read_bytes() == first.read_bytes() == b"first-original"
    assert second.read_bytes() == b"second-original"


def test_preexisting_files_and_foreign_temporary_file_untouched(cfg, monkeypatch):
    target = Path(cfg["target_dir"])
    target.mkdir()
    existing = {"same.txt": b"old", "same_2.txt": b"old-two", ".absorber-foreign.tmp": b"foreign"}
    for name, value in existing.items():
        (target / name).write_bytes(value)
    monkeypatch.setattr(core, "build_stem", lambda *a: "same")
    result = core.materialize(FakeMime(text="synthetic"), cfg)[0]
    assert result.name == "same_3.txt"
    assert {name: (target / name).read_bytes() for name in existing} == existing
    assert {p.name for p in target.iterdir()} == {*existing, result.name}


@pytest.mark.parametrize("kind", ["directory", "readonly-file"])
def test_preexisting_directory_or_readonly_file_is_a_collision(cfg, monkeypatch, kind):
    target = Path(cfg["target_dir"])
    target.mkdir()
    original = target / "same.txt"
    if kind == "directory":
        original.mkdir()
    else:
        original.write_bytes(b"readonly-original")
        original.chmod(0o444)
    monkeypatch.setattr(core, "build_stem", lambda *a: "same")
    try:
        result = core.materialize(FakeMime(text="synthetic"), cfg)[0]
        assert result.name == "same_2.txt"
        if kind == "directory":
            assert original.is_dir()
        else:
            assert original.read_bytes() == b"readonly-original"
    finally:
        if kind == "readonly-file":
            original.chmod(0o600)


def test_cleanup_and_error_reporting_failure_do_not_mask_write_error(cfg, monkeypatch):
    import sys

    primary = PermissionError("primary synthetic error")
    def publication_failure(*args):
        raise primary
    def cleanup_failure(*args):
        raise OSError("secondary synthetic cleanup error")
    class FailedStderr:
        def write(self, text):
            raise RuntimeError("secondary reporting error")
    with monkeypatch.context() as patch:
        patch.setattr(core.os, "replace", publication_failure)
        patch.setattr(core, "_remove_owned", cleanup_failure)
        patch.setattr(sys, "stderr", FailedStderr())
        with pytest.raises(PermissionError) as caught:
            core.materialize(FakeMime(text="synthetic"), cfg)
    assert caught.value is primary


def test_reservation_permission_denial_is_not_assumed_collision(cfg, monkeypatch):
    target = Path(cfg["target_dir"])
    original_open = os.open
    error = PermissionError("reservation forbidden")
    monkeypatch.setattr(core, "build_stem", lambda *a: "same")
    def opened(path, *args, **kwargs):
        if Path(path) == target / "same.txt":
            raise error
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(core.os, "open", opened)
    with pytest.raises(PermissionError) as caught:
        core.materialize(FakeMime(text="synthetic"), cfg)
    assert caught.value is error
    assert list(target.iterdir()) == []
