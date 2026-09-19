# Blueprint: Absorber

Dieses Dokument ist die Zwischenstufe zwischen Beschreibung und Bau, nach dem Skill
`software-in-worten`: **Text, dessen Anordnung dem Bild entspricht.** Jedes Feld
darin ist eine Frage an einen Menschen, und aus jeder Frage folgt genau eine Zeile
in `config.json`.

---

## Der Wille

> „Ich habe etwas in der Zwischenablage und brauche es als Datei, um darauf zu
> verweisen."

Daraus folgt alles Weitere. Der Nutzer hat kein Interesse an einem Dateimanager,
einem Editor oder einer Historie. Er hat einen Inhalt ohne Ort und braucht einen
Ort. Die Rückgabe ist deshalb nicht die Datei, sondern **ihr Pfad** — denn
verwiesen wird mit dem Pfad, nicht mit dem Inhalt.

## Der Ablauf

```
Inhalt liegt in der Zwischenablage
        ↓
Auslöser: Tray-Klick · Rechtsklick → Einfügen · Strg+V im Fenster
        ↓
Art erkennen         →  Dateiliste · Bild · HTML · Text   (leer → melden, Ende)
        ↓
Symbol der Art zeigen, mittig im weißen Bereich
        ↓
Namen bilden         →  lokales Modell, sonst Zeitstempel + Wortanfang
        ↓
Datei schreiben      →  Zielordner nach Modus (Desktop oder virtuell)
        ↓
Symbol schrumpfen und ausblenden (~600 ms)
        ↓
Pfad in die Zwischenablage · Pfad in „Letzte Dateien" · Pfad 3 s in der Statuszeile
```

**Ein Screen entsteht dort, wo der Ablauf auf einen Menschen wartet.** Das ist hier
genau zweimal der Fall: beim Auslösen und beim Einstellen. Alles dazwischen läuft
durch und bekommt deshalb keine Ansicht, sondern nur das Symbol und die Statuszeile.

---

## Blueprint: Tray

```
 [Trichter-Symbol]   Linksklick → Materialisieren jetzt

   Materialisieren
   Fenster zeigen
   Letzte Dateien ▸   1  2026-09-20_quartalsbericht.txt
                      2  2026-09-20_141233_image.png
                      …  (max. 10, Klick = Pfad in die Zwischenablage)
   ────────────────
   (•) Modus: Desktop
   ( ) Modus: Virtuell
   ────────────────
   Einstellungen…
   Beenden
```

## Blueprint: Fenster „Absorber"

```
 ┌──────────────────────────────────────────────┐
 │                                              │
 │                                              │
 │                   ┌──────┐                   │   Rechtsklick → Einfügen
 │                   │ TXT  │                   │   Strg+V ebenfalls
 │                   └──────┘                   │
 │            (schrumpft, blendet aus)          │
 │                                              │
 ├──────────────────────────────────────────────┤
 │ C:\Users\…\Desktop\2026-09-20_notizen.txt    │   3 s, dann leer
 └──────────────────────────────────────────────┘
```

Der weiße Bereich ist **absichtlich leer**. Er ist kein unfertiger Platzhalter,
sondern die Fläche, auf die man etwas fallen lässt.

## Blueprint: Einstellungen

```
 Zielordner            [ C:\Users\…\Desktop          ]  [ Wählen… ]
 Modus                 (•) Desktop  ( ) Virtuell
 Aufbewahrung virtuell [ 7 ] Tage    0 = nie löschen
 Textformate           [x] .txt  [ ] .md  [ ] .html
 Dateilisten kopieren  [ ] Kopiert markierte Dateien in den Zielordner
 Nach dem Speichern    [x] Pfad der letzten Datei in die Zwischenablage
 Benennung             [x] Dateiname per lokalem Modell   Modell [ auto ]

                                        [ OK ]   [ Abbrechen ]
```

---

## Feldlegende

Jede Zeile trägt drei Dinge: **was** hineingehört, **warum** es gebraucht wird und
**wo es später wirkt**. Die letzten beiden Spalten sind die, die man am ehesten
vergisst und die im Betrieb den meisten Ärger machen.

### Zielordner → `target_dir`

| | |
|---|---|
| **Frage** | Wohin sollen die Dateien geschrieben werden? |
| **Typ** | Pfad (Ordnerwahl), leer erlaubt |
| **Zweck** | Zielverzeichnis jedes Schreibvorgangs im Modus „Desktop" |
| **Wirkt in** | `config.resolve_target_dir()` |
| **Wenn leer** | Vorgabe setzen: der Desktop des Nutzers über `QStandardPaths.DesktopLocation`. Auf diesem Rechner ist das der OneDrive-Desktop — das ist gewollt und **nicht** hart verdrahtet. |
| **Wenn falsch** | Ordner wird angelegt. Ist das unmöglich, meldet die Statuszeile den Fehler und es wird nichts geschrieben. |

### Modus → `mode`

| | |
|---|---|
| **Frage** | Sollen die Dateien sichtbar liegen oder nur vorübergehend? |
| **Typ** | Auswahl: `desktop` \| `virtual` |
| **Zweck** | **Weiche.** Sie stellt den Zielordner um und schaltet das Aufräumen zu. |
| **Wirkt in** | `config.resolve_target_dir()`, `config.prune_virtual()` |
| **Wenn leer** | `desktop` |
| **Wenn falsch** | Jeder unbekannte Wert verhält sich wie `desktop` — ein Tippfehler darf keine Datei verschwinden lassen. |

### Aufbewahrung virtuell → `virtual_retention_days`

| | |
|---|---|
| **Frage** | Wie lange sollen virtuelle Dateien liegen bleiben? |
| **Typ** | Zahl, 0–365 |
| **Zweck** | Abbruchkriterium beim Aufräumen: älter als N Tage wird gelöscht |
| **Wirkt in** | `config.prune_virtual()`, beim Start |
| **Wenn leer** | 7 |
| **Wenn falsch** | `0` schaltet das Aufräumen ganz ab. Das ist eine gültige Antwort, kein Fehler. |

### Textformate → `text_formats`

| | |
|---|---|
| **Frage** | Als welche Dateiart soll Text gespeichert werden? |
| **Typ** | Mehrfachauswahl aus `txt`, `md`, `html` |
| **Zweck** | Bestimmt die Endung für Text **und** ob HTML überhaupt als eigene Art erkannt wird |
| **Wirkt in** | `core.detect()`, `config.text_extension()` |
| **Wenn leer** | `txt` — Text darf nie ohne Ziel dastehen |
| **Wenn falsch** | Bei mehreren aktiven gewinnt `txt` vor `md`. `html` ist kein Textziel, sondern eine eigene Art. |

### Dateilisten kopieren → `copy_file_lists`

| | |
|---|---|
| **Frage** | Sollen im Explorer kopierte Dateien mitgenommen werden? |
| **Typ** | Ja/Nein |
| **Zweck** | **Gate vor der Erkennung.** Aus ist es, weil eine Explorer-Kopie auch Text mitliefert und der Nutzer meist den Text meint. |
| **Wirkt in** | `core.detect()` |
| **Wenn leer** | Nein |
| **Wenn falsch** | Ordner in der Liste werden übersprungen, nicht rekursiv kopiert. |

### Pfad in die Zwischenablage → `path_to_clipboard`

| | |
|---|---|
| **Frage** | Soll der Pfad der letzten Datei sofort in der Zwischenablage liegen? |
| **Typ** | Ja/Nein |
| **Zweck** | Die eigentliche Rückgabe an den Menschen — damit er verweisen kann |
| **Wirkt in** | `Absorber.absorb()`, nach dem Schreiben |
| **Wenn leer** | Ja |
| **Wenn falsch** | Aus bedeutet, die Zwischenablage bleibt unangetastet. Der Pfad steht dann in der Statuszeile und in „Letzte Dateien". |

### Benennung → `model_naming`, `model`

| | |
|---|---|
| **Frage** | Soll ein lokales Modell den Dateinamen vorschlagen, und welches? |
| **Typ** | Ja/Nein plus Text (Modellname oder `auto`) |
| **Zweck** | Ein sprechender Name statt eines Zeitstempels |
| **Wirkt in** | `naming.OllamaNamer`, `naming.build_stem()` |
| **Wenn leer** | Ja, `auto` = das erste installierte Modell |
| **Wenn falsch** | **Jeder** Fehlschlag ist still: kein Ollama, Zeitüberschreitung, Modell nicht da, leere Antwort — überall greift der Zeitstempel-Name. Ein Namensvorschlag darf eine Datei nie kosten. |

---

## Die Kontrollgrenze

Mit dem Aufruf an Ollama verlässt es die eigene Ebene. Danach gibt es kein
Nachfassen. Deshalb ist alles mitgegeben, was drüben gebraucht wird: der Text,
die Längenbegrenzung (800 Zeichen), die Form der Antwort (3–5 Wörter, keine
Zeichensetzung, keine Endung) — und auf dieser Seite eine Frist von 3 Sekunden
plus ein Fallback, der immer einen Wert liefert.

**Auch der Ausnahmefall liefert einen Wert zurück.** Das ist die Regel, nach der
`build_stem()` gebaut ist: Es gibt keinen Pfad, der ohne Namen endet.

## Was absichtlich keinen Screen bekommt

| Bedingung | Warum unsichtbar |
|---|---|
| Kollisionszähler `_2`, `_3` | reine Mechanik |
| Zeitüberschreitung beim Modell | reine Mechanik, Fallback greift |
| Anlegen des Zielordners | reine Mechanik |
| Aufräumen alter virtueller Dateien | läuft beim Start durch |

Wer diese Verzweigungen zeigt, verwechselt Ablaufdiagramm mit Oberfläche.
