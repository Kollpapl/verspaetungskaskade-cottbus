"""
Phase 2: ein Snapshot des GTFS-RT-Feeds für die gewählte Linie, angehängt an eine
tägliche JSONL-Datei (eine Zeile pro Aufruf).

Bewusst NICHT direkt in eine SQLite-Datenbank geschrieben: bei einem Cron-Workflow,
der das alle paar Minuten wochenlang laufen lässt und committet, gibt JSONL saubere,
diffbare Text-Zeilen statt Binär-Diffs, und ein abgebrochener Lauf (Netzwerk-Timeout,
Rate-Limit) kostet höchstens eine unvollständige letzte Zeile statt einer korrupten
Datenbankdatei. Die SQLite-Datenbank wird bei Bedarf separat aus den JSONL-Dateien
gebaut, siehe build_sqlite.py.

Aufruf:
    uv run collect_delays.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from google.transit import gtfs_realtime_pb2

FEED_URL = "https://production.gtfsrt.vbb.de/data"
ROUTE_ID = "13108_700"  # Bus 16, Cottbusverkehr GmbH -- siehe ERKLAERUNG.md fuer Begruendung
HEADERS = {"User-Agent": "verspaetungskaskade-cottbus-projekt/0.1 (privates Schulprojekt)"}
PLAUSIBLE_MAX_DELAY = 25 * 60  # Sekunden -- grober Filter gegen bekannte Datenfehler im Feed
OUT_DIR = Path(__file__).parent / "data" / "raw"


def collect() -> None:
    now = datetime.now(timezone.utc)
    resp = requests.get(FEED_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)

    trips = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        if tu.trip.route_id != ROUTE_ID:
            continue
        stops = []
        for stu in tu.stop_time_update:
            a = stu.arrival.delay if stu.HasField("arrival") else None
            d = stu.departure.delay if stu.HasField("departure") else None
            plausible = all(v is None or abs(v) <= PLAUSIBLE_MAX_DELAY for v in (a, d))
            stops.append(
                {
                    "stop_id": stu.stop_id,
                    "seq": stu.stop_sequence,
                    "arrival_delay": a,
                    "departure_delay": d,
                    "plausible": plausible,
                }
            )
        trips.append({"trip_id": tu.trip.trip_id, "stops": stops})

    record = {
        "snapshot_time": now.isoformat(),
        "feed_timestamp": feed.header.timestamp,
        "total_entities_in_feed": len(feed.entity),
        "route_id": ROUTE_ID,
        "trips": trips,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"{now:%Y-%m-%d}.jsonl"
    with out_file.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(
        f"{now.isoformat()}: {len(trips)} Fahrten auf Route {ROUTE_ID} erfasst "
        f"(Feed gesamt: {len(feed.entity)} Eintraege) -> {out_file}"
    )


if __name__ == "__main__":
    collect()
