"""Entry point: wires clipboard, core, window and tray together."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from . import config as config_module
from . import core, recent
from .settings_dialog import SettingsDialog
from .tray import AbsorberTray
from .window import AbsorberWindow


class Absorber(QObject):
    """Everything the tray and the window can ask absorber to do."""

    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self.cfg = config_module.load()
        self.window = AbsorberWindow(self.absorb)
        self.tray = AbsorberTray(self, parent=app)
        self.tray.show()
        config_module.prune_virtual(self.cfg)

    # --- actions ---------------------------------------------------------

    def absorb(self) -> list[Path]:
        mime = self.app.clipboard().mimeData()
        kind = core.detect(mime, self.cfg)
        if not kind:
            self._report("Nichts in der Zwischenablage, das sich speichern lässt.")
            return []
        if self.window.isVisible():
            self.window.flash(kind)
        try:
            paths = core.materialize(mime, self.cfg, core.make_namer(self.cfg))
        except OSError as error:
            self._report(f"Fehler: {error}")
            return []
        if not paths:
            self._report("Nichts gespeichert.")
            return []

        recent.add(paths, limit=int(self.cfg.get("recent_max", 10)))
        self.tray.refresh()
        if self.cfg.get("path_to_clipboard", True):
            self.app.clipboard().setText(str(paths[-1]))
        suffix = f" (+{len(paths) - 1})" if len(paths) > 1 else ""
        self._report(f"{paths[-1]}{suffix}")
        return paths

    def copy_path(self, path: str) -> None:
        self.app.clipboard().setText(path)
        self._report(f"Pfad kopiert: {path}")

    def set_mode(self, mode: str) -> None:
        self.cfg["mode"] = mode
        config_module.save(self.cfg)
        self._report(f"Modus: {mode}")

    def show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.cfg, self.window)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self.cfg = dialog.values()
            config_module.save(self.cfg)
            self.tray.refresh()
            self._report("Einstellungen gespeichert.")

    def quit(self) -> None:
        self.tray.hide()
        self.app.quit()

    def _report(self, message: str) -> None:
        self.window.report(message)
        if not self.window.isVisible():
            self.tray.showMessage("Absorber", message, self.tray.icon(), 2500)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="absorber", description=__doc__)
    parser.add_argument("--window", action="store_true", help="Fenster beim Start zeigen")
    parser.add_argument(
        "--smoke",
        type=float,
        metavar="SEKUNDEN",
        help="Startbeleg: kurz laufen lassen, dann selbst beenden",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    app = QApplication(sys.argv[:1])
    app.setApplicationName(config_module.APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # closing the window must not end the app

    absorber = Absorber(app)
    if args.window or args.smoke:
        absorber.show_window()
    if not absorber.tray.isSystemTrayAvailable() and not args.smoke:
        QMessageBox.warning(
            absorber.window,
            "Absorber",
            "Kein System-Tray verfügbar. Absorber läuft nur im Fenster.",
        )
        absorber.show_window()
    if args.smoke:
        QTimer.singleShot(int(args.smoke * 1000), absorber.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
