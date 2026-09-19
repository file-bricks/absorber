"""The window: a white area, a right-click paste, and a shrinking kind symbol."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
)
from PySide6.QtGui import QAction, QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import core

#: Text shown inside the kind symbol. No image assets, no paths to get wrong.
KIND_LABELS = {
    core.KIND_IMAGE: "PNG",
    core.KIND_TEXT: "TXT",
    core.KIND_HTML: "HTML",
    core.KIND_FILES: "FILES",
    "": "?",
}

SYMBOL_MS = 600
STATUS_MS = 3000


class AbsorberWindow(QWidget):
    """Deliberately empty. The white area is the whole point: drop something in."""

    def __init__(self, absorb_callback, parent=None):
        super().__init__(parent)
        self._absorb = absorb_callback
        self.setWindowTitle("Absorber")
        self.resize(460, 320)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.canvas = QLabel(self)
        self.canvas.setStyleSheet("background: #ffffff;")
        layout.addWidget(self.canvas, 1)

        self.status = QLabel("", self)
        self.status.setStyleSheet(
            "background: #f2f2f2; color: #333; padding: 4px 8px; font-size: 11px;"
        )
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # A long path must not push the window wider than the user sized it.
        self.status.setSizePolicy(
            QSizePolicy.Policy.Ignored, self.status.sizePolicy().verticalPolicy()
        )
        self._status_text = ""
        layout.addWidget(self.status, 0)

        self.symbol = QLabel(self.canvas)
        self.symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.symbol.setStyleSheet(
            "background: #2d6cdf; color: white; border-radius: 12px;"
            "font-size: 22px; font-weight: bold;"
        )
        self.symbol.hide()
        self._effect = QGraphicsOpacityEffect(self.symbol)
        self.symbol.setGraphicsEffect(self._effect)
        self._animation = None

        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self.report(""))

        QShortcut(QKeySequence.StandardKey.Paste, self, activated=self._absorb)

    def _show_menu(self, position):
        menu = QMenu(self)
        paste = QAction("Einfügen", menu)
        paste.triggered.connect(self._absorb)
        menu.addAction(paste)
        menu.exec(self.mapToGlobal(position))

    def flash(self, kind: str) -> None:
        """Show the kind symbol, then shrink and fade it out."""
        self.symbol.setText(KIND_LABELS.get(kind, KIND_LABELS[""]))
        side = 96
        centre = self.canvas.rect().center()
        start = QRect(centre.x() - side // 2, centre.y() - side // 2, side, side)
        end = QRect(centre.x() - 8, centre.y() - 8, 16, 16)
        self.symbol.setGeometry(start)
        self._effect.setOpacity(1.0)
        self.symbol.show()
        self.symbol.raise_()

        group = QParallelAnimationGroup(self)
        shrink = QPropertyAnimation(self.symbol, b"geometry", group)
        shrink.setDuration(SYMBOL_MS)
        shrink.setStartValue(start)
        shrink.setEndValue(end)
        shrink.setEasingCurve(QEasingCurve.Type.InCubic)
        fade = QPropertyAnimation(self._effect, b"opacity", group)
        fade.setDuration(SYMBOL_MS)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        group.addAnimation(shrink)
        group.addAnimation(fade)
        group.finished.connect(self.symbol.hide)
        group.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)
        self._animation = group  # keep a reference so it is not collected mid-flight

    def report(self, message: str) -> None:
        self._status_text = message
        self.status.setToolTip(message)
        self._elide_status()
        if message:
            self._status_timer.start(STATUS_MS)

    def _elide_status(self) -> None:
        """Shorten the middle of a long path so both ends stay readable."""
        width = max(0, self.status.width() - 16)  # the stylesheet padding
        metrics = QFontMetrics(self.status.font())
        self.status.setText(
            metrics.elidedText(self._status_text, Qt.TextElideMode.ElideMiddle, width)
            if width
            else self._status_text
        )

    def resizeEvent(self, event):  # noqa: N802 - Qt name
        super().resizeEvent(event)
        self._elide_status()

    def closeEvent(self, event):  # noqa: N802 - Qt name
        """Closing hides the window; absorber keeps living in the tray."""
        event.ignore()
        self.hide()
