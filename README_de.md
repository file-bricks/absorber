# Absorber

[English](README.md) | **Deutsch**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![GUI: PySide6](https://img.shields.io/badge/GUI-PySide6-41cd52.svg)](https://doc.qt.io/qtforpython/)
[![Offline-first](https://img.shields.io/badge/offline--first-ja-brightgreen.svg)]()
[![Ecosystem: file-bricks](https://img.shields.io/badge/ecosystem-file--bricks-blueviolet.svg)](https://github.com/file-bricks)

> Du hast etwas in der Zwischenablage und brauchst es als Datei — weil du darauf
> verweisen willst. Absorber macht eine daraus und gibt dir den Pfad zurück.

![Das Absorber-Fenster direkt nach dem Einfügen eines Textes](docs/window.png)

Absorber sitzt als Trichter im System-Tray. Ein Klick darauf, und was in der
Zwischenablage liegt, wird eine echte Datei: ein Bild wird ein PNG, Text wird eine
`.txt`, formatierter Text kann eine `.html` werden. Der Pfad der neuen Datei landet
sofort wieder in der Zwischenablage — bereit zum Einfügen in einen Chat, einen Prompt,
ein Ticket oder eine Kommandozeile.

Das Fenster selbst ist absichtlich ein weißes Rechteck. Es ist kein unfertiger
Platzhalter, sondern die Fläche, auf die man etwas fallen lässt.

---

## Inhalt

| Abschnitt | Worum es geht |
|---|---|
| [Wozu](#wozu) | Das Problem dahinter |
| [Installation](#installation) | Voraussetzungen und Einrichtung |
| [Bedienung](#bedienung) | Tray, Fenster, Tastatur |
| [Einstellungen](#einstellungen) | Jede Option und ihre Wirkung |
| [Benennung per lokalem Modell](#benennung-per-lokalem-modell) | Optionale Ollama-Anbindung |
| [Nicht zu verwechseln mit Gardener](#nicht-zu-verwechseln-mit-gardener) | Namensgleichheit, anderes Werkzeug |
| [Entwicklung](#entwicklung) | Tests und Aufbau |
| [Roadmap](#roadmap) | Was in 0.1.0 bewusst fehlt |

---

## Wozu

Der Inhalt der Zwischenablage hat keine Adresse. Man kann ihn nicht verlinken, nicht
anhängen, nicht als Dateiverweis in einen Prompt geben und keinem Werkzeug übergeben,
das einen Pfad erwartet. Der übliche Umweg ist „Editor öffnen, einfügen, speichern
unter, Ordner suchen, benennen, Pfad kopieren" — sechs Schritte für etwas, das einer
sein sollte.

Absorber macht einen daraus, und das Ergebnis ist der **Pfad**, nicht die Datei.
Verwiesen wird mit Pfaden.

## Installation

Voraussetzung: Python 3.11 oder neuer.

```bash
git clone https://github.com/file-bricks/absorber.git
cd absorber
pip install -e .
```

Starten:

```bash
python -m absorber        # oder: absorber
START.bat                 # Windows
./start.sh                # macOS / Linux
```

Windows zuerst, aber nichts im Kern ist Windows-only: Zwischenablage, Tray und Pfade
laufen alle über Qt.

## Bedienung

| Aktion | Was passiert |
|---|---|
| **Linksklick auf das Tray-Symbol** | Zwischenablage sofort materialisieren |
| **Tray → Materialisieren** | Dasselbe, über das Menü |
| **Tray → Letzte Dateien** | Die letzten 10 Dateien; ein Klick kopiert ihren Pfad |
| **Tray → Modus** | Zwischen Desktop und virtuell umschalten |
| **Rechtsklick im Fenster → Einfügen** | Materialisieren, mit Symbol für die Dateiart |
| **Strg+V im Fenster** | Dasselbe |

Nach dem Schreiben erscheint die Art der erzeugten Datei als Symbol in der Mitte des
weißen Bereichs, schrumpft und blendet aus. Die Statuszeile zeigt den Pfad drei
Sekunden lang; der vollständige Pfad steht immer im Tooltip.

Das Fenster zu schließen beendet Absorber nicht. Es lebt im Tray weiter. Beendet wird
dort.

### Was materialisiert werden kann

| In der Zwischenablage | Wird zu | Anmerkung |
|---|---|---|
| Ein Bild | `.png` | Screenshots, kopierte Bilder |
| Text | `.txt` oder `.md` | Welches davon, ist eine Einstellung |
| Formatierter Text / HTML | `.html` | Standardmäßig aus |
| Eine Dateiliste | Kopien im Zielordner | Standardmäßig aus |

## Einstellungen

Zu öffnen über **Tray → Einstellungen…**. Die Konfiguration liegt als `config.json` im
Konfigurationsverzeichnis der Plattform (unter Windows `%APPDATA%\absorber\`).

| Einstellung | Vorgabe | Wirkung |
|---|---|---|
| **Zielordner** | dein Desktop | Wohin im Desktop-Modus geschrieben wird. Leer bedeutet den Desktop, aufgelöst durch Qt — auf einem Rechner mit umgeleiteten Ordnern ist das der OneDrive-Desktop, und das ist so gewollt. |
| **Modus** | Desktop | `Desktop` schreibt in den Zielordner. `Virtuell` schreibt in einen temporären Ordner und räumt selbst auf. |
| **Aufbewahrung virtuell** | 7 Tage | Wie lange virtuelle Dateien liegen bleiben. `0` schaltet das Aufräumen ganz ab. |
| **Textformate** | `.txt` | Welche Endungen Text bekommen darf. Wer `.html` anhakt, macht formatierten Text zusätzlich zu einer eigenen Art. |
| **Dateilisten kopieren** | aus | Ob im Dateimanager kopierte Dateien in den Zielordner dupliziert werden. |
| **Pfad in die Zwischenablage** | an | Legt den Pfad der neuen Datei in die Zwischenablage. Das ist die eigentliche Antwort auf dein Anliegen. |
| **Dateiname per Modell** | an | Ein lokales Modell nach einem Dateinamen fragen. |
| **Modell** | `auto` | `auto` nimmt das erste installierte Modell, sonst eines benennen. |

Eine vollständige Feldlegende — was jedes Feld fragt, warum der Wert gebraucht wird und
wo er wirkt — steht in [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md).

## Benennung per lokalem Modell

Läuft [Ollama](https://ollama.com/) unter `http://127.0.0.1:11434`, fragt Absorber dort
nach einem Namen aus drei bis fünf Wörtern, gebildet aus den ersten 800 Zeichen des
Textes.

**Jeder Fehlschlag ist still und kostet nichts.** Kein Ollama, eine Zeitüberschreitung,
ein fehlendes Modell, eine leere Antwort — in jedem dieser Fälle greift der
Ersatzname:

```
2026-09-20_141233_besprechungsnotizen-von-heute    Text, benannt nach den ersten Wörtern
2026-09-20_141233_image                            ein Bild
2026-09-20_141233_image_2                          und das nächste, bei Namensgleichheit
```

Ein Namensvorschlag darf niemals eine Datei kosten. Die Verfügbarkeitsprüfung bekommt
eine Sekunde, die Namensanfrage drei.

## Nicht zu verwechseln mit Gardener

[Gardener](https://github.com/ellmos-ai/GARDENER) verwendet die Begriffe `absorb()`,
`materialize()` und `.absorber/` für das Einziehen von **Dateien in seine Datenbank**.
Das ist ein anderes Werkzeug für ein anderes Problem, und die beiden haben nichts
miteinander zu tun. Absorber hier geht den umgekehrten Weg: Inhalt der Zwischenablage
**heraus** ins Dateisystem.

## Entwicklung

```bash
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest
```

91 Tests, ohne Netzzugriff und ohne echte Zwischenablage. Der Kern ist bewusst frei von
GUI-Importen:

| Modul | Zuständigkeit |
|---|---|
| `absorber/core.py` | Art erkennen, Datei schreiben, Pfade zurückgeben |
| `absorber/naming.py` | Slugs, Namensgleichheit, Ollama-Client mit injizierbarem HTTP |
| `absorber/config.py` | Vorgaben, Laden/Speichern, aufgelöste Ordner, virtuelles Aufräumen |
| `absorber/recent.py` | Die Liste der letzten Dateien |
| `absorber/window.py` | Weißer Bereich, Einfügen, das schrumpfende Symbol |
| `absorber/tray.py` | Trichter-Symbol, Menü, Liste der letzten Dateien |
| `absorber/settings_dialog.py` | Ein Bedienelement je Blueprint-Feld |

## Roadmap

Bewusst nicht in 0.1.0 enthalten:

- **Globaler Hotkey** — materialisieren, ohne den Tray anzufassen
- **Autostart** — mit der Sitzung starten
- **Weitere Formate** — RTF, SVG, Audio aus der Zwischenablage
- **Ordner** in kopierten Dateilisten (werden derzeit übersprungen)

## Lizenz

MIT — siehe [LICENSE](LICENSE).
