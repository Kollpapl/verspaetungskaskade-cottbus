"""
Diagnose: ist der VBB-GTFS-RT-Feed für unsere Kandidatenlinie(n) überhaupt brauchbar?

Hintergrund: der Feed fehlt laut VBB-Statusseite seit 04.06.2026, 16 Uhr, teilweise
Daten (kein Reparaturtermin genannt), und es gibt unabhängig dokumentierte Fälle von
unplausiblen Verspätungswerten (z.B. angeblich -30 Minuten). Bevor wir wochenlang
sammeln, prüfen wir empirisch: kommen für unsere Linie überhaupt Live-Fahrten, und
sehen die delay-Werte plausibel aus?

Zwei Modi:

    uv run check_feed_health.py                    # eine Route pruefen (default: Linie 3)
    uv run check_feed_health.py --route 12889_900

    uv run check_feed_health.py --scan-agency 516   # ALLE Routen einer Agency pruefen
                                                     # (516 = Cottbusverkehr GmbH) und pro
                                                     # fehlender Route gegenchecken, ob
                                                     # gerade ueberhaupt eine Fahrt laut
                                                     # Fahrplan unterwegs sein sollte
                                                     # (sonst waer "0 Treffer" evtl. nur
                                                     # Betriebspause, kein Feed-Fehler)

    uv run check_feed_health.py --staging           # gegen den Staging-Feed statt Production
"""

import argparse
import datetime
import zipfile
from pathlib import Path

import pandas as pd
import requests
from google.transit import gtfs_realtime_pb2

PRODUCTION_URL = "https://production.gtfsrt.vbb.de/data"
STAGING_URL = "https://staging.gtfsrt.vbb.de/data"
HEADERS = {"User-Agent": "verspaetungskaskade-cottbus-projekt/0.1 (privates Schulprojekt)"}
ZIP_PATH = Path(__file__).parent / "data" / "gtfs.zip"

# Als "wahrscheinlich Datenfehler statt echte Verspätung" markieren, siehe ERKLAERUNG.md
PLAUSIBEL_MIN_SEK, PLAUSIBEL_MAX_SEK = -25 * 60, 25 * 60


def fetch_feed(url: str) -> gtfs_realtime_pb2.FeedMessage:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)
    return feed


def load_table(name: str) -> pd.DataFrame:
    with zipfile.ZipFile(ZIP_PATH) as z:
        with z.open(name) as f:
            return pd.read_csv(f, dtype=str, low_memory=False)


def check_single_route(feed: gtfs_realtime_pb2.FeedMessage, route_id: str) -> None:
    treffer, unplausibel = 0, 0
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        if tu.trip.route_id != route_id:
            continue
        treffer += 1
        delays = [stu.arrival.delay for stu in tu.stop_time_update if stu.HasField("arrival")]
        verdaechtig = [d for d in delays if not (PLAUSIBEL_MIN_SEK <= d <= PLAUSIBEL_MAX_SEK)]
        if verdaechtig:
            unplausibel += 1
        marker = "  <- unplausible Werte dabei!" if verdaechtig else ""
        print(f"{tu.trip.trip_id}  delays(s)={delays[:5]}{marker}")

    print(f"\n{treffer} aktive Fahrten auf Route {route_id} im aktuellen Snapshot.")
    if treffer == 0:
        print(
            "-> 0 Treffer: entweder gerade keine Fahrt unterwegs (Uhrzeit pruefen) "
            "oder die Linie fehlt im Feed. --scan-agency prueft das automatisch gegen "
            "den Fahrplan."
        )
    elif unplausibel:
        print(f"-> {unplausibel}/{treffer} Fahrten mit Werten ausserhalb +-25 Min.")
    else:
        print("-> alle Treffer mit plausiblen Werten (+-25 Min).")


def scan_agency(feed: gtfs_realtime_pb2.FeedMessage, agency_id: str) -> None:
    routes = load_table("routes.txt")
    trips = load_table("trips.txt")
    stop_times = load_table("stop_times.txt")
    calendar = load_table("calendar.txt")

    agency_routes = routes[routes.agency_id == agency_id]
    if agency_routes.empty:
        print(f"Keine Routen fuer agency_id={agency_id} im statischen GTFS gefunden.")
        return

    feed_route_ids = {
        e.trip_update.trip.route_id for e in feed.entity if e.HasField("trip_update")
    }

    today = datetime.date.today()
    weekday_col = today.strftime("%A").lower()
    today_str = today.strftime("%Y%m%d")
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    window_start = (datetime.datetime.now() - datetime.timedelta(minutes=20)).strftime("%H:%M:%S")
    window_end = (datetime.datetime.now() + datetime.timedelta(minutes=20)).strftime("%H:%M:%S")

    rows = []
    for _, route in agency_routes.iterrows():
        rid = route["route_id"]
        im_feed = rid in feed_route_ids

        route_trips = trips[trips.route_id == rid]
        active_service = calendar[
            calendar.service_id.isin(route_trips.service_id)
            & (calendar[weekday_col] == "1")
            & (calendar.start_date <= today_str)
            & (calendar.end_date >= today_str)
        ]
        todays_trips = route_trips[route_trips.service_id.isin(active_service.service_id)]
        st_today = stop_times[stop_times.trip_id.isin(todays_trips.trip_id)]
        # Hinweis: calendar_dates.txt (Ausnahmen/Feiertage) hier bewusst nicht beruecksichtigt,
        # fuer eine grobe Sollte-gerade-fahren-Einschaetzung reicht calendar.txt.
        soll_gerade_fahren = st_today[
            (st_today.departure_time >= window_start) & (st_today.departure_time <= window_end)
        ]["trip_id"].nunique()

        rows.append(
            {
                "route_id": rid,
                "kurzname": route.get("route_short_name", ""),
                "typ": route.get("route_type", ""),
                "im_live_feed": im_feed,
                f"fahrten_geplant_{window_start[:5]}-{window_end[:5]}": soll_gerade_fahren,
            }
        )

    result = pd.DataFrame(rows).sort_values(["im_live_feed", "typ"], ascending=[False, True])
    print(f"Stand {now_str}, {len(result)} Routen fuer agency_id={agency_id}:\n")
    print(result.to_string(index=False))

    fehlend_aber_sollte_fahren = result[
        (~result.im_live_feed) & (result[result.columns[-1]] > 0)
    ]
    print(
        f"\n{(~result.im_live_feed).sum()}/{len(result)} Routen fehlen im Live-Feed. "
        f"Davon {len(fehlend_aber_sollte_fahren)} mit laut Fahrplan gerade aktiven Fahrten "
        f"(also mutmasslich echte Feed-Luecke, keine Betriebspause):"
    )
    if not fehlend_aber_sollte_fahren.empty:
        print(fehlend_aber_sollte_fahren.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", default="12890_900", help="route_id (default: Linie 3)")
    parser.add_argument("--scan-agency", help="agency_id: alle Routen dieser Agency pruefen")
    parser.add_argument("--staging", action="store_true", help="Staging- statt Production-Feed")
    args = parser.parse_args()

    url = STAGING_URL if args.staging else PRODUCTION_URL
    print(f"Frage {url} ab ...")
    feed = fetch_feed(url)
    print(f"Feed-Timestamp: {feed.header.timestamp}, {len(feed.entity)} Eintraege insgesamt.\n")

    if args.scan_agency:
        scan_agency(feed, args.scan_agency)
    else:
        check_single_route(feed, args.route)


if __name__ == "__main__":
    main()
