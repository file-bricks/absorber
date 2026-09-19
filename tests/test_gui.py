"""Smoke tests for the GUI. They run headless via QT_QPA_PLATFORM=offscreen."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QMimeData  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from absorber import config as config_module  # noqa: E402
from absorber import core, recent  # noqa: E402
from absorber.__main__ import Absorber  # noqa: E402
from absorber.settings_dialog import SettingsDialog  # noqa: E402
from absorber.tray import funnel_icon  # noqa: E402
from absorber.window import AbsorberWindow  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def absorber(qapp, tmp_path, monkeypatch):
    """An Absorber whose config, recent list and target all live in tmp_path."""
    monkeypatch.setattr(config_module, "config_dir", lambda: tmp_path / "conf")
    monkeypatch.setattr(recent, "config_dir", lambda: tmp_path / "conf")
    monkeypatch.setattr(config_module, "virtual_dir", lambda: tmp_path / "virtual")
    (tmp_path / "conf").mkdir()
    instance = Absorber(qapp)
    instance.cfg["target_dir"] = str(tmp_path / "out")
    instance.cfg["model_naming"] = False
    yield instance
    instance.tray.hide()
    instance.window.close()


def set_clipboard(qapp, **kwargs):
    mime = QMimeData()
    if "text" in kwargs:
        mime.setText(kwargs["text"])
    if "html" in kwargs:
        mime.setHtml(kwargs["html"])
    qapp.clipboard().setMimeData(mime)


# --- window ---------------------------------------------------------------


def test_window_opens_with_canvas_and_status(qapp):
    window = AbsorberWindow(lambda: None)
    window.show()
    assert window.isVisible()
    assert window.canvas.isVisible()
    assert window.status.text() == ""
    window.close()


def test_ctrl_v_is_wired_to_absorbing(qapp):
    """A paste shortcut is easy to build so that it type-checks but never fires.
    Assert the binding and that triggering it actually reaches the callback."""
    calls = []
    window = AbsorberWindow(lambda: calls.append(1))
    assert window.paste_shortcut.key().toString() == "Ctrl+V"
    assert window.paste_shortcut.isEnabled()
    window.paste_shortcut.activated.emit()
    assert calls == [1]


def test_context_menu_paste_is_wired_to_absorbing(qapp):
    calls = []
    window = AbsorberWindow(lambda: calls.append(1))
    entries = [a for a in window.build_context_menu().actions() if a.text() == "Einfügen"]
    assert len(entries) == 1
    entries[0].trigger()
    assert calls == [1]


def test_window_close_hides_instead_of_destroying(qapp):
    window = AbsorberWindow(lambda: None)
    window.show()
    window.close()
    assert not window.isVisible()


def test_flash_shows_then_keeps_the_symbol_alive(qapp):
    window = AbsorberWindow(lambda: None)
    window.show()
    window.flash(core.KIND_TEXT)
    assert window.symbol.isVisible()
    assert window.symbol.text() == "TXT"
    window.close()


def test_report_writes_to_the_status_line(qapp):
    window = AbsorberWindow(lambda: None)
    window.report("C:\\out\\x.txt")
    assert window.status.toolTip() == "C:\\out\\x.txt"


def test_a_long_path_does_not_widen_the_window(qapp):
    """Regression: an unelided path label pushed the window to ~960 px and
    dragged the centred kind symbol off centre with it."""
    window = AbsorberWindow(lambda: None)
    window.show()
    before = window.width()
    window.report("C:\\" + "\\".join(f"very-long-directory-name-{i}" for i in range(12)))
    qapp.processEvents()
    assert window.width() == before
    assert window.status.toolTip().endswith("-11")  # the full path is still available
    window.close()


def test_the_symbol_stays_centred_after_a_long_path(qapp):
    window = AbsorberWindow(lambda: None)
    window.show()
    qapp.processEvents()
    window.report("C:\\" + "\\".join(f"long-directory-{i}" for i in range(12)))
    qapp.processEvents()
    window.flash(core.KIND_TEXT)
    symbol_centre = window.symbol.geometry().center().x()
    assert abs(symbol_centre - window.canvas.rect().center().x()) <= 1
    window.close()


# --- tray -----------------------------------------------------------------


def test_funnel_icon_is_drawable():
    assert not funnel_icon().isNull()


def test_tray_menu_has_the_expected_entries(absorber):
    labels = [a.text() for a in absorber.tray.menu.actions() if a.text()]
    assert "Materialisieren" in labels
    assert "Fenster zeigen" in labels
    assert "Letzte Dateien" in labels
    assert "Einstellungen…" in labels
    assert "Beenden" in labels
    assert "Modus: Desktop" in labels and "Modus: Virtuell" in labels


def test_tray_recent_menu_starts_empty(absorber):
    entries = absorber.tray.recent_menu.actions()
    assert len(entries) == 1
    assert not entries[0].isEnabled()


# --- the whole loop -------------------------------------------------------


def test_pasting_text_creates_a_file(absorber, qapp, tmp_path):
    set_clipboard(qapp, text="Ein Testtext für Absorber")
    paths = absorber.absorb()
    assert len(paths) == 1
    assert paths[0].parent == tmp_path / "out"
    assert paths[0].read_text(encoding="utf-8") == "Ein Testtext für Absorber"


def test_the_path_lands_in_the_clipboard(absorber, qapp):
    set_clipboard(qapp, text="hello")
    path = absorber.absorb()[0]
    assert qapp.clipboard().text() == str(path)


def test_the_path_stays_out_of_the_clipboard_when_switched_off(absorber, qapp):
    absorber.cfg["path_to_clipboard"] = False
    set_clipboard(qapp, text="keep me")
    absorber.absorb()
    assert qapp.clipboard().text() == "keep me"


def test_the_new_file_shows_up_in_the_tray_list(absorber, qapp):
    set_clipboard(qapp, text="listed")
    path = absorber.absorb()[0]
    labels = [a.text() for a in absorber.tray.recent_menu.actions()]
    assert Path(path).name in labels


def test_clicking_a_recent_entry_copies_its_path(absorber, qapp):
    absorber.copy_path("C:\\somewhere\\file.txt")
    assert qapp.clipboard().text() == "C:\\somewhere\\file.txt"


def test_empty_clipboard_reports_instead_of_failing(absorber, qapp):
    qapp.clipboard().setMimeData(QMimeData())
    assert absorber.absorb() == []
    assert "Nichts" in absorber.window.status.toolTip()


def test_switching_mode_persists(absorber, tmp_path):
    absorber.set_mode("virtual")
    assert config_module.load(tmp_path / "conf" / "config.json")["mode"] == "virtual"


def test_virtual_mode_writes_to_the_virtual_folder(absorber, qapp, tmp_path):
    absorber.set_mode("virtual")
    set_clipboard(qapp, text="virtual text")
    assert absorber.absorb()[0].parent == tmp_path / "virtual"


# --- settings dialog ------------------------------------------------------


def test_settings_dialog_round_trips_the_config(qapp):
    cfg = dict(config_module.DEFAULTS, mode="virtual", target_dir="C:\\out")
    assert SettingsDialog(cfg).values() == cfg


def test_settings_dialog_never_leaves_text_homeless(qapp):
    dialog = SettingsDialog(dict(config_module.DEFAULTS))
    dialog.fmt_txt.setChecked(False)
    dialog.fmt_md.setChecked(False)
    dialog.fmt_html.setChecked(False)
    assert dialog.values()["text_formats"] == ["txt"]


def test_settings_dialog_empty_model_falls_back_to_auto(qapp):
    dialog = SettingsDialog(dict(config_module.DEFAULTS))
    dialog.model.setText("   ")
    assert dialog.values()["model"] == "auto"
