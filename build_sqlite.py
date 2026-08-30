"""
Baut aus den gesammelten data/raw/*.jsonl-Dateien eine SQLite-Datenbank für die
Analyse (Phase 4/5). Bewusst ein separater, jederzeit wiederholbarer Schritt statt
Teil der automatisierten Sammlung, siehe ERKLAERUNG.md ("Design-Entscheidung JSONL
statt SQLite fürs Sammeln").

Aufruf:
    uv run build_sqlite.py                # baut data/verspaetungen.sqlite komplett neu
    uv run build_sqlite.py --out other.db  # anderer Zieldateiname
"""

import argparse
import json
import sqlite3
from pathlib import Path

RAW_DIR = Path(__file__).parent / "data" / "raw"
DEFAULT_OUT = Path(__file__).parent / "data" / "verspaetungen.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_time TEXT NOT NULL,
    feed_timestamp INTEGER,
    total_entities_in_feed INTEGER,
    route_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stop_updates (
    snapshot_time TEXT NOT NULL,
    route_id TEXT NOT NULL,
    trip_id TEXT NOT NULL,
    stop_id TEXT NOT NULL,
    seq INTEGER,
    arrival_delay INTEGER,
    departure_delay INTEGER,
    plausible INTEGER
);

CREATE INDEX IF NOT EXISTS idx_stop_updates_trip ON stop_updates(trip_id, seq);
CREATE INDEX IF NOT EXISTS idx_stop_updates_stop ON stop_updates(stop_id);
"""


def build(out_path: Path) -> None:
    if not RAW_DIR.exists():
        print(f"{RAW_DIR} existiert nicht -- noch keine Rohdaten gesammelt.")
        return

    jsonl_files = sorted(RAW_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print(f"Keine .jsonl-Dateien in {RAW_DIR} gefunden.")
        return

    if out_path.exists():
        out_path.unlink()  # immer komplett neu bauen, kein inkrementelles Update

    con = sqlite3.connect(out_path)
    con.executescript(SCHEMA)

    n_snapshots, n_stop_updates, n_defekte_zeilen = 0, 0, 0
    for path in jsonl_files:
        with path.open() as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    # z.B. abgebrochener Actions-Lauf mitten im Schreiben -- betrifft
                    # dann hoechstens die letzte Zeile einer Datei, siehe ERKLAERUNG.md
                    n_defekte_zeilen += 1
                    print(f"Uebersprungen (kaputte Zeile): {path.name}:{line_no}")
                    continue

                con.execute(
                    "INSERT INTO snapshots VALUES (?, ?, ?, ?)",
                    (
                        record["snapshot_time"],
                        record.get("feed_timestamp"),
                        record.get("total_entities_in_feed"),
                        record["route_id"],
                    ),
                )
                n_snapshots += 1
                for trip in record.get("trips", []):
                    for stop in trip.get("stops", []):
                        con.execute(
                            "INSERT INTO stop_updates VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                record["snapshot_time"],
                                record["route_id"],
                                trip["trip_id"],
                                stop["stop_id"],
                                stop.get("seq"),
                                stop.get("arrival_delay"),
                                stop.get("departure_delay"),
                                int(stop.get("plausible", True)),
                            ),
                        )
                        n_stop_updates += 1

    con.commit()
    con.close()
    print(
        f"{out_path}: {n_snapshots} Snapshots, {n_stop_updates} Haltestellen-Updates "
        f"aus {len(jsonl_files)} Dateien ({n_defekte_zeilen} defekte Zeilen uebersprungen)."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.out)


if __name__ == "__main__":
    main()
