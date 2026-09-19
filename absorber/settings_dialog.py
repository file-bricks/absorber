"""The settings dialog. One widget per field of docs/BLUEPRINT.md."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QWidget,
)

from .config import DEFAULTS, desktop_dir


def _row(*widgets) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch(1)
    return box


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Absorber - Einstellungen")
        self._cfg = dict(cfg)
        form = QFormLayout(self)

        self.target = QLineEdit(cfg.get("target_dir", ""))
        self.target.setPlaceholderText(str(desktop_dir()))
        browse = QPushButton("Wählen…")
        browse.clicked.connect(self._browse)
        form.addRow("Zielordner", _row(self.target, browse))

        self.mode_desktop = QRadioButton("Desktop")
        self.mode_virtual = QRadioButton("Virtuell")
        (self.mode_virtual if cfg.get("mode") == "virtual" else self.mode_desktop).setChecked(True)
        form.addRow("Modus", _row(self.mode_desktop, self.mode_virtual))

        self.retention = QSpinBox()
        self.retention.setRange(0, 365)
        self.retention.setValue(int(cfg.get("virtual_retention_days", 7)))
        self.retention.setSuffix(" Tage")
        form.addRow("Aufbewahrung virtuell", _row(self.retention, QLabel("0 = nie löschen")))

        formats = cfg.get("text_formats") or []
        self.fmt_txt = QCheckBox(".txt")
        self.fmt_md = QCheckBox(".md")
        self.fmt_html = QCheckBox(".html")
        for key, box in (("txt", self.fmt_txt), ("md", self.fmt_md), ("html", self.fmt_html)):
            box.setChecked(key in formats)
        form.addRow("Textformate", _row(self.fmt_txt, self.fmt_md, self.fmt_html))

        self.copy_lists = QCheckBox("Kopiert markierte Dateien in den Zielordner")
        self.copy_lists.setChecked(bool(cfg.get("copy_file_lists")))
        form.addRow("Dateilisten kopieren", self.copy_lists)

        self.path_to_clipboard = QCheckBox("Pfad der letzten Datei in die Zwischenablage")
        self.path_to_clipboard.setChecked(bool(cfg.get("path_to_clipboard", True)))
        form.addRow("Nach dem Speichern", self.path_to_clipboard)

        self.model_naming = QCheckBox("Dateiname per lokalem Modell")
        self.model_naming.setChecked(bool(cfg.get("model_naming", True)))
        self.model = QLineEdit(cfg.get("model", "auto"))
        self.model.setPlaceholderText("auto")
        self.model.setMaximumWidth(180)
        form.addRow("Benennung", _row(self.model_naming, QLabel("Modell"), self.model))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Zielordner wählen", self.target.text() or str(desktop_dir())
        )
        if chosen:
            self.target.setText(chosen)

    def values(self) -> dict:
        """The edited config. Unknown keys of the original config are preserved."""
        formats = [
            key
            for key, box in (("txt", self.fmt_txt), ("md", self.fmt_md), ("html", self.fmt_html))
            if box.isChecked()
        ]
        cfg = dict(self._cfg)
        cfg.update(
            {
                "target_dir": self.target.text().strip(),
                "mode": "virtual" if self.mode_virtual.isChecked() else "desktop",
                "virtual_retention_days": self.retention.value(),
                # An empty selection would leave text with nowhere to go, so txt stays.
                "text_formats": formats or ["txt"],
                "copy_file_lists": self.copy_lists.isChecked(),
                "path_to_clipboard": self.path_to_clipboard.isChecked(),
                "model_naming": self.model_naming.isChecked(),
                "model": self.model.text().strip() or DEFAULTS["model"],
            }
        )
        return cfg
