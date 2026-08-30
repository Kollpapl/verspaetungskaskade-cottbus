"""
Phase 1: statisches VBB-GTFS herunterladen und Linien im Cottbus-Gebiet ranken.

Lädt einmalig data/gtfs.zip (ca. 80 MB, ganzes VBB-Netz Berlin-Brandenburg,
zweimal woechentlich von VBB aktualisiert), extrahiert die benoetigten Dateien
und listet alle Linien, die mindestens eine Haltestelle mit "Cottbus" im Namen
bedienen -- sortiert danach, wie ergiebig sie fuer die Kaskaden-Frage sind
(viele Haltestellen, viele Fahrten pro Tag).

Aufruf:
    uv run explore_static_gtfs.py
    uv run explore_static_gtfs.py --area Cottbus   # anderer Suchbegriff moeglich
"""

import argparse
import zipfile
from pathlib import Path

import pandas as pd
import requests

GTFS_URL = "https://www.vbb.de/vbbgtfs"  # redirect -> gtfs.zip, ~80 MB
DATA_DIR = Path(__file__).parent / "data"
ZIP_PATH = DATA_DIR / "gtfs.zip"


def download_gtfs_if_needed() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if ZIP_PATH.exists():
        print(f"Nutze vorhandene {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1e6:.1f} MB). "
              f"Zum Neu-Laden Datei loeschen.")
        return
    print(f"Lade {GTFS_URL} ...")
    headers = {"User-Agent": "verspaetungskaskade-cottbus-projekt/0.1 (privates Schulprojekt)"}
    with requests.get(GTFS_URL, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(ZIP_PATH, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    print(f"Gespeichert: {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1e6:.1f} MB)")


def load_table(name: str) -> pd.DataFrame:
    with zipfile.ZipFile(ZIP_PATH) as z:
        with z.open(name) as f:
            return pd.read_csv(f, dtype=str, low_memory=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", default="Cottbus",
                         help="Suchbegriff im Haltestellennamen (default: Cottbus)")
    args = parser.parse_args()

    download_gtfs_if_needed()

    print("Lade stops.txt ...")
    stops = load_table("stops.txt")
    area_stops = stops[stops["stop_name"].str.contains(args.area, case=False, na=False)]
    print(f"{len(area_stops)} Haltestellen mit '{args.area}' im Namen gefunden.")
    if area_stops.empty:
        print("Keine Treffer -- Suchbegriff pruefen (z.B. anderer Ortsname).")
        return

    print("Lade stop_times.txt (groesste Datei, kann etwas dauern) ...")
    stop_times = load_table("stop_times.txt")
    area_stop_times = stop_times[stop_times["stop_id"].isin(area_stops["stop_id"])]

    print("Lade trips.txt und routes.txt ...")
    trips = load_table("trips.txt")
    routes = load_table("routes.txt")

    area_trips = trips[trips["trip_id"].isin(area_stop_times["trip_id"].unique())]
    area_routes = routes[routes["route_id"].isin(area_trips["route_id"].unique())]

    # Pro Route: wie viele Haltestellen im Suchgebiet, wie viele Fahrten insgesamt,
    # wie viele Haltestellen entlang der GESAMTEN Linie (nicht nur im Suchgebiet).
    rows = []
    for _, route in area_routes.iterrows():
        route_trip_ids = area_trips.loc[area_trips["route_id"] == route["route_id"], "trip_id"]
        route_stop_times = stop_times[stop_times["trip_id"].isin(route_trip_ids)]
        n_area_stops = route_stop_times[route_stop_times["stop_id"].isin(area_stops["stop_id"])][
            "stop_id"
        ].nunique()
        n_total_stops = route_stop_times["stop_id"].nunique()
        n_trips = route_trip_ids.nunique()
        rows.append(
            {
                "route_id": route["route_id"],
                "kurzname": route.get("route_short_name", ""),
                "langname": route.get("route_long_name", ""),
                "typ": route.get("route_type", ""),
                f"haltestellen_in_{args.area}": n_area_stops,
                "haltestellen_gesamt": n_total_stops,
                "fahrten_gesamt": n_trips,
            }
        )

    result = pd.DataFrame(rows).sort_values(
        ["fahrten_gesamt", "haltestellen_gesamt"], ascending=False
    )

    out_path = DATA_DIR / f"kandidaten_linien_{args.area.lower()}.csv"
    result.to_csv(out_path, index=False)
    print(f"\n{len(result)} Linien bedienen mindestens eine Haltestelle in {args.area}.")
    print(f"Vollstaendige Tabelle: {out_path}\n")
    print(result.head(25).to_string(index=False))
    print(
        "\nHinweis: route_type-Codes -> 0=Strassenbahn, 3=Bus, 2=Zug/Regionalbahn "
        "(volle Liste: https://gtfs.org/schedule/reference/#routestxt)."
    )
    print(
        "Fuer die Kaskaden-Frage lohnt sich eine Linie mit vielen Haltestellen, "
        "engem Takt (hohe fahrten_gesamt) und moeglichst einem Umsteigeknoten "
        "unterwegs -- keine, die kaum je Verspaetung hat."
    )


if __name__ == "__main__":
    main()
