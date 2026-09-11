# Setup

## 1. venv / Abhängigkeiten

Projekt nutzt `uv` (kein manuelles venv-Aktivieren nötig, `uv run` erledigt das). System-Python 3.14 reicht hier aus – anders als beim Skin-Cancer-Projekt gibt es keine Bibliothek (wie PyTorch), die eine ältere Python-Version braucht.

```fish
cd /mnt/hdd/Projekte/Coding/Python/verspaetungskaskade-cottbus
uv sync
```

## 2. Phase 1 – Linie auswählen

```fish
uv run explore_static_gtfs.py
```

Lädt einmalig das komplette statische VBB-GTFS (`data/gtfs.zip`, ~80 MB, wird gecacht – zum Neuladen die Datei löschen) und listet alle Linien, die mindestens eine Haltestelle mit "Cottbus" im Namen bedienen, sortiert nach Fahrten/Tag. Ergebnis auch als CSV unter `data/kandidaten_linien_cottbus.csv`.

Anderes Suchgebiet: `uv run explore_static_gtfs.py --area <Ortsname>`

## 3. Feed-Gesundheit prüfen, bevor man sich auf eine Linie festlegt

```fish
uv run check_feed_health.py --route <route_id>          # eine Route pruefen
uv run check_feed_health.py --scan-agency 516            # alle Routen von Cottbusverkehr GmbH
```

`--scan-agency` gleicht zusätzlich gegen `calendar.txt` ab, ob eine "fehlende" Route laut Fahrplan gerade überhaupt eine aktive Fahrt haben sollte – unterscheidet also echte Feed-Lücke von bloßer Betriebspause. Ergebnis vom 30.08.2026 (Sonntagnachmittag, per Kalenderabgleich verifiziert – siehe `ERKLAERUNG.md` für Details): **alle vier Cottbus-Straßenbahnlinien (1–4) fehlen systematisch im Live-Feed**, obwohl laut Fahrplan aktive Fahrten liefen. Deshalb Linienwahl auf Bus **16** (`13108_700`) geändert, siehe `ERKLAERUNG.md`.

## 4. Phase 2 – Sammlung (lokal testen)

```fish
uv run collect_delays.py   # ein Snapshot, haengt eine Zeile an data/raw/<datum>.jsonl an
uv run build_sqlite.py     # baut aus allen JSONL-Dateien data/verspaetungen.sqlite neu
```

`collect_delays.py` schreibt bewusst JSONL an, nicht direkt SQLite – Begründung dazu in `ERKLAERUNG.md`. Die automatische Sammlung läuft über `.github/workflows/collect.yml`, ausgelöst per `repository_dispatch` (Event `collect-tick`) von einem externen Zeitgeber (cron-job.org, alle 30 Minuten) – GitHubs eigener `schedule`-Trigger erwies sich für einen dichten Takt als unzuverlässig, und ein zu dichter `repository_dispatch`-Takt (ursprünglich 5 Minuten) hat das kostenlose GitHub-Actions-Kontingent (2000 Min/Monat) nach ~7 Tagen aufgebraucht (Details und Verifikation in `ERKLAERUNG.md`, Abschnitte "Cron-Fix" und "Kostenloses Kontingent aufgebraucht").

## 5. Weitere Phasen

Noch nicht begonnen – Phase 3 (Kaskade sauber definieren), Phase 4 (explorative Analyse), Phase 5 (Modell), Phase 6 (Nutzen beziffern). Reihenfolge und Details siehe `ERKLAERUNG.md`.

## Datenquelle – wichtig zu wissen

- Statisches GTFS (`vbb.de/vbbgtfs`): zweimal wöchentlich aktualisiert (Mi/Fr), CC-BY, keine Authentifizierung nötig.
- GTFS-Realtime (`production.gtfsrt.vbb.de/data`): CC-BY 4.0, keine Auth, aber max. 60 Requests/Minute **und ein aussagekräftiger User-Agent mit Kontaktangabe** (sonst droht Blocking) – in beiden Skripten schon berücksichtigt.
- **Bekanntes, bestätigtes Problem (Stand 30.08.2026):** Der Realtime-Feed fehlt laut VBB-Statusseite seit dem 04.06.2026, 16 Uhr, teilweise Daten. Eigener Health-Check (`check_feed_health.py --scan-agency 516`) bestätigt das konkret für Cottbusverkehr GmbH: **9 von 45 Bus-Routen sind live, alle 4 Tram-Routen fehlen komplett** – letzteres per Fahrplanabgleich verifiziert, also keine bloße Betriebspause. Deshalb Linie **3** (Tram) verworfen, **Bus 16** gewählt. Vor Start der Dauersammlung (Phase 2) den Health-Check noch 1-2x zu anderen Tageszeiten wiederholen, um den Befund zu erhärten.
