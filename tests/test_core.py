from pathlib import Path

import pytest

from absorber import core
from conftest import FakeImage, FakeMime


def test_detect_nothing_on_empty_clipboard(cfg):
    assert core.detect(FakeMime(), cfg) == ""


def test_detect_nothing_on_whitespace_only_text(cfg):
    assert core.detect(FakeMime(text="   \n  "), cfg) == ""


def test_detect_text(cfg):
    assert core.detect(FakeMime(text="hi"), cfg) == core.KIND_TEXT


def test_detect_image_wins_over_text(cfg):
    mime = FakeMime(text="alt text", image=FakeImage())
    assert core.detect(mime, cfg) == core.KIND_IMAGE


def test_detect_html_only_when_enabled(cfg):
    mime = FakeMime(text="plain", html="<b>rich</b>")
    assert core.detect(mime, cfg) == core.KIND_TEXT
    cfg["text_formats"] = ["txt", "html"]
    assert core.detect(mime, cfg) == core.KIND_HTML


def test_detect_files_only_when_enabled(cfg, tmp_path):
    source = tmp_path / "a.pdf"
    source.write_bytes(b"pdf")
    mime = FakeMime(text="a.pdf", urls=[str(source)])
    assert core.detect(mime, cfg) == core.KIND_TEXT
    cfg["copy_file_lists"] = True
    assert core.detect(mime, cfg) == core.KIND_FILES


def test_detect_ignores_non_local_urls(cfg):
    cfg["copy_file_lists"] = True
    mime = FakeMime(text="https://example.org", urls=[""])
    assert core.detect(mime, cfg) == core.KIND_TEXT


# --- materialising --------------------------------------------------------


def test_materialize_text_writes_utf8(cfg):
    paths = core.materialize(FakeMime(text="Grüße aus München"), cfg)
    assert len(paths) == 1
    assert paths[0].suffix == ".txt"
    assert paths[0].read_text(encoding="utf-8") == "Grüße aus München"
    assert paths[0].stem.endswith("_gruesse-aus-muenchen")


def test_materialize_text_honours_markdown_setting(cfg):
    cfg["text_formats"] = ["md"]
    assert core.materialize(FakeMime(text="# title"), cfg)[0].suffix == ".md"


def test_materialize_text_falls_back_to_txt_when_no_format_enabled(cfg):
    cfg["text_formats"] = []
    assert core.materialize(FakeMime(text="orphan"), cfg)[0].suffix == ".txt"


def test_materialize_html(cfg):
    cfg["text_formats"] = ["txt", "html"]
    paths = core.materialize(FakeMime(text="rich", html="<p>rich</p>"), cfg)
    assert paths[0].suffix == ".html"
    assert paths[0].read_text(encoding="utf-8") == "<p>rich</p>"


def test_materialize_image(cfg):
    paths = core.materialize(FakeMime(image=FakeImage(b"PNGDATA")), cfg)
    assert paths[0].suffix == ".png"
    assert paths[0].read_bytes() == b"PNGDATA"
    assert paths[0].stem.endswith("_image")


def test_materialize_image_failure_is_reported(cfg):
    with pytest.raises(OSError):
        core.materialize(FakeMime(image=FakeImage(ok=False)), cfg)


def test_materialize_empty_clipboard_returns_nothing(cfg):
    assert core.materialize(FakeMime(), cfg) == []


def test_materialize_creates_the_target_directory(cfg):
    target = Path(cfg["target_dir"])
    assert not target.exists()
    core.materialize(FakeMime(text="x"), cfg)
    assert target.is_dir()


def test_materialize_twice_does_not_overwrite(cfg):
    first = core.materialize(FakeMime(text="same text"), cfg)[0]
    second = core.materialize(FakeMime(text="same text"), cfg)[0]
    assert first != second
    assert first.exists() and second.exists()


def test_materialize_copies_file_list(cfg, tmp_path):
    cfg["copy_file_lists"] = True
    a, b = tmp_path / "a.pdf", tmp_path / "b.txt"
    a.write_bytes(b"A")
    b.write_text("B", encoding="utf-8")
    paths = core.materialize(FakeMime(urls=[str(a), str(b)]), cfg)
    assert [p.name for p in paths] == ["a.pdf", "b.txt"]
    assert paths[0].read_bytes() == b"A"


def test_materialize_skips_directories_in_a_file_list(cfg, tmp_path):
    cfg["copy_file_lists"] = True
    folder = tmp_path / "folder"
    folder.mkdir()
    assert core.materialize(FakeMime(urls=[str(folder)]), cfg) == []


def test_materialize_uses_virtual_folder_in_virtual_mode(cfg, tmp_path, monkeypatch):
    virtual = tmp_path / "virtual"
    monkeypatch.setattr(core.config_module, "virtual_dir", lambda: virtual)
    cfg["mode"] = "virtual"
    assert core.materialize(FakeMime(text="x"), cfg)[0].parent == virtual


def test_make_namer_respects_the_setting(cfg):
    assert core.make_namer(cfg) is None
    cfg["model_naming"] = True
    assert core.make_namer(cfg) is not None


def test_materialize_uses_the_namer_for_text(cfg):
    class Namer:
        def suggest(self, text):
            return "named-by-the-model"

    path = core.materialize(FakeMime(text="anything"), cfg, namer=Namer())[0]
    assert path.stem.endswith("_named-by-the-model")
