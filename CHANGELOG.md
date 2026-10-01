# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier festgehalten.
Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Behoben

- Gleichzeitige Speicherungen konnten denselben vermeintlich freien Dateinamen
  wählen und sich überschreiben. Text, Markdown, HTML, Bilder und Dateikopien
  werden jetzt zunächst privat geschrieben und anschließend unter einem exklusiv
  reservierten Namen veröffentlicht. Fehler bereinigen nur Dateien mit eigener
  nachgewiesener Identität; vorhandene Dateien erhalten weiterhin `_2`, `_3` usw.

- Der `QShortcut` für Strg+V wurde mit einer `StandardKey` statt einer
  `QKeySequence` und einem `activated=`-Schlüsselwort gebaut. Zur Laufzeit
  funktionierte das, es traf aber keine dokumentierte Überladung — eine Form,
  die sich leicht so schreiben lässt, dass sie richtig aussieht und trotzdem nie
  auslöst. Jetzt explizit gebaut und verbunden, mit einem Test, der die Bindung
  **und** das Auslösen belegt.
- Das Kontextmenü wurde im selben Schritt gebaut und per `exec()` angezeigt.
  Das Bauen war dadurch nicht prüfbar, ohne den Test zu blockieren;
  `build_context_menu()` ist jetzt für sich testbar.
- In einem Test war `entries` formal ungebunden, falls die Schleife nicht liefe.

### Hinzugefügt

- Je ein Test für die beiden Auslöser des Einfügens (Strg+V und Kontextmenü),
  damit 93 statt 91 Tests. Pyright meldet über Paket und Tests 0 Fehler.

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
