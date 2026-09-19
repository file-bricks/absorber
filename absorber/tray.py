"""The tray icon: a funnel, a click that absorbs, and the recent-files list."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QActionGroup, QBrush, QIcon, QPainter, QPixmap, QPolygonF
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import recent

RECENT_LABEL_CHARS = 42


def funnel_icon(size: int = 64) -> QIcon:
    """Draw the funnel. Painted rather than shipped, so no asset path can break."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(Qt.GlobalColor.white))
    painter.setPen(Qt.PenStyle.NoPen)
    u = size / 16
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(2 * u, 2 * u),
                QPointF(14 * u, 2 * u),
                QPointF(9.5 * u, 8 * u),
                QPointF(9.5 * u, 14 * u),
                QPointF(6.5 * u, 12 * u),
                QPointF(6.5 * u, 8 * u),
            ]
        )
    )
    painter.end()
    return QIcon(pixmap)


class AbsorberTray(QSystemTrayIcon):
    def __init__(self, controller, parent=None):
        super().__init__(funnel_icon(), parent)
        self.controller = controller
        self.setToolTip("Absorber - Zwischenablage als Datei")
        self.activated.connect(self._on_activated)

        self.menu = QMenu()
        self.action_absorb = self.menu.addAction("Materialisieren")
        self.action_absorb.triggered.connect(controller.absorb)
        self.action_window = self.menu.addAction("Fenster zeigen")
        self.action_window.triggered.connect(controller.show_window)

        self.recent_menu = QMenu("Letzte Dateien", self.menu)
        self.menu.addMenu(self.recent_menu)
        self.menu.addSeparator()

        self.mode_group = QActionGroup(self.menu)
        self.mode_group.setExclusive(True)
        self.mode_actions = {}
        for key, label in (("desktop", "Modus: Desktop"), ("virtual", "Modus: Virtuell")):
            action = QAction(label, self.menu, checkable=True)
            action.triggered.connect(lambda _checked, k=key: controller.set_mode(k))
            self.mode_group.addAction(action)
            self.menu.addAction(action)
            self.mode_actions[key] = action

        self.menu.addSeparator()
        self.action_settings = self.menu.addAction("Einstellungen…")
        self.action_settings.triggered.connect(controller.show_settings)
        self.action_quit = self.menu.addAction("Beenden")
        self.action_quit.triggered.connect(controller.quit)

        self.setContextMenu(self.menu)
        self.refresh()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.controller.absorb()

    def refresh(self) -> None:
        """Rebuild the recent list and re-check the current mode."""
        cfg = self.controller.cfg
        action = self.mode_actions.get(cfg.get("mode", "desktop"))
        if action:
            action.setChecked(True)

        self.recent_menu.clear()
        entries = recent.existing(limit=int(cfg.get("recent_max", 10)))
        if not entries:
            empty = self.recent_menu.addAction("(noch nichts)")
            empty.setEnabled(False)
            return
        for entry in entries:
            name = Path(entry).name
            label = name if len(name) <= RECENT_LABEL_CHARS else name[:RECENT_LABEL_CHARS - 1] + "…"
            item = self.recent_menu.addAction(label)
            item.setToolTip(entry)
            item.triggered.connect(lambda _checked, p=entry: self.controller.copy_path(p))
