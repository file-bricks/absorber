# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier festgehalten.
Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung [Semantic Versioning](https://semver.org/lang/de/).

## [0.1.0] - 2026-09-20

Erste Fassung. Zwischenablage hinein, Datei heraus, Pfad zurück.

### Hinzugefügt

- **Tray-Symbol als Trichter** mit Linksklick zum sofortigen Materialisieren.
  Das Symbol wird gezeichnet statt mitgeliefert, damit kein Asset-Pfad brechen kann.
- **Fenster** mit weißem Bereich, Rechtsklick auf „Einfügen" und Strg+V.
  Nach dem Einfügen erscheint ein Symbol für die Dateiart, schrumpft und blendet
  über etwa 600 ms aus; eine Statuszeile zeigt den Pfad drei Sekunden lang.
- **Unterstützte Inhalte:** Bild (nach PNG), Text (nach `.txt` oder `.md`),
  formatierter Text (nach `.html`, abschaltbar), Dateiliste (Kopie in den
  Zielordner, abschaltbar).
- **Zwei Modi:** `desktop` schreibt in den Zielordner, `virtual` in einen
  temporären Ordner mit Aufbewahrungsfrist. In beiden Modi führt das Tray-Menü
  die letzten zehn Dateien; ein Klick kopiert deren Pfad.
- **Benennung per lokalem Modell** über Ollama, mit Erkennung in einer Sekunde
  und Namensanfrage in drei. Jeder Fehlschlag fällt still auf
  `YYYY-MM-DD_HHMMSS_<slug>` zurück; Namensgleichheit zählt mit `_2`, `_3` hoch.
- **Einstellungsdialog** mit einem Bedienelement je Feld aus `docs/BLUEPRINT.md`.
- **Launcher** `START.bat` und `start.sh`, beide leiten ihre Pfade aus dem eigenen
  Skriptstandort ab.
- 91 Tests. Der Kern ist ohne GUI prüfbar, die Oberfläche läuft headless über
  `QT_QPA_PLATFORM=offscreen`.

### Behoben

- Ein langer Pfad in der Statuszeile verbreiterte das Fenster auf gut das
  Doppelte und zog dabei das mittig positionierte Symbol aus der Mitte. Die
  Statuszeile elidiert jetzt in der Mitte und treibt die Fensterbreite nicht
  mehr; der vollständige Pfad steht im Tooltip.

[0.1.0]: https://github.com/file-bricks/absorber/releases/tag/v0.1.0
