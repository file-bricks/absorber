# Sichere Ausgabe bei gleichzeitigen Speicherungen

Absorber schreibt Text, Markdown, HTML, Bilder und Dateikopien zunächst in eine
exklusiv angelegte temporäre Datei im Zielordner. Erst nach erfolgreichem Schreiben
reserviert es den endgültigen Namen exklusiv. Unter Unix geschieht dies mit
`O_CREAT | O_EXCL`. Ist der Name schon
belegt, folgen wie bisher `_2`, `_3` usw. Auch ein defekter symbolischer Link zählt
als belegter Name. Die bisherige Funktion `naming.unique_path` bleibt eine reine
Namensvorhersage; sie reserviert keine Datei.

Unter Windows verwendet die Reservierung `CreateFileW` mit `CREATE_NEW` und
`FILE_FLAG_OPEN_REPARSE_POINT`, da die Windows-CRT bei `O_EXCL` defekten Links
folgen kann. Das eigene Windows-Handle wird nach erfolgreichem Anlegen in einen
Python-Dateideskriptor überführt; schlägt diese Überführung fehl, wird das Handle
geschlossen. Die bisherigen Identitäts- und Bereinigungsprüfungen gelten auch hier.

Vor der Veröffentlichung prüft Absorber, ob temporäre Datei und Reservierung noch
die beim Anlegen über den eigenen Dateideskriptor erfasste Identität besitzen.
Die Prüfung verwendet `lstat` und folgt keinem nachträglich eingesetzten Link.
Anschließend ersetzt `os.replace` ausschließlich die eigene Reservierung. Erst
danach wird der Pfad als Ergebnis zurückgegeben.

Bei einem Fehler versucht Absorber, die eigene temporäre Datei und eigene
Reservierung zu entfernen. Eine fremd ersetzte Datei bleibt erhalten. Wenn eine
Dateikopie ein Schreibschutzattribut übernimmt, wird dieses ausschließlich zur
Bereinigung der eigenen temporären Datei angepasst. Die Quelle wird nicht
verändert. Scheitert die Bereinigung oder lässt sich die Identität nicht sicher
feststellen, können eigene temporäre Dateien zurückbleiben; unbekannte Dateien
werden nicht als Ersatz gelöscht. Ein Bereinigungsfehler verdeckt keinen bereits
aufgetretenen Schreibfehler.

Eine Dateiliste wird wie bisher einzeln verarbeitet. Scheitert eine spätere Kopie,
bleiben bereits erfolgreich veröffentlichte frühere Kopien erhalten. Kopierte
Metadaten und Änderungszeiten werden weiterhin von `copy2` übernommen.

Während des kurzen Abschnitts zwischen Reservierung und Ersetzen kann ein leerer
Platzhalter sichtbar sein. Ein gewaltsamer Prozessabbruch kann Platzhalter oder
temporäre Dateien hinterlassen. Die Identitätsprüfung ist keine Sperre gegen eine
externe Änderung zwischen letzter Prüfung und Ersetzen. Es gibt keine zusätzliche
Garantie bei Stromausfall.

Die Regressionen nutzen synthetische Inhalte, tatsächliche parallele Threads und
eine native Qt-Bildkodierung. Die GUI-Suite läuft mit der Qt-Plattform `offscreen`;
sie ist keine Abnahme der echten Windows-Zwischenablage oder des System-Trays.
Konfigurationsdatei, Recent-Liste und virtuelle Aufbewahrung haben getrennte
Lebenszyklen und sind nicht Bestandteil dieses Ausgabefixes.
