"""
Phase 3: "Kaskade" sauber definieren und auf den gesammelten Daten auszählen.

Liest alle Snapshots aus data/raw/ (ab START_DATUM), baut daraus pro Fahrt
(Betriebstag + trip_id) einen Verspätungsverlauf aus echten Messpunkten und
wendet die Kaskaden-Definition an. Begründung jeder Regel: ERKLAERUNG.md,
Abschnitt "Phase 3".

Aufruf:
    uv run phase3_kaskaden.py            # Zusammenfassung im Terminal
Ergebnisse:
    data/phase3_fahrten.csv              # eine Zeile pro Fahrt
    data/phase3_haltestellen.csv         # pro Haltestelle: wie oft wächst/schrumpft die Verspätung dort
"""

import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

DATA = Path(__file__).parent / "data"
RAW = DATA / "raw"
START_DATUM = "2026-10-01"  # erster Tag nach dem Billing-Reset, ab hier lückenlos
BERLIN = ZoneInfo("Europe/Berlin")

# --- Die Definition (alle Werte in Sekunden) ---------------------------------
PLAUSIBEL_MIN = -5 * 60  # früher als 5 min zu früh abgefahren = Datenfehler
PLAUSIBEL_MAX = 25 * 60  # wie im Sammelskript: mehr als 25 min = Datenfehler/Ausfall
# Werte seit Phase 4 angepasst: der Feed springt in Schritten von ~1 Minute (Rundung der
# Fahrplanzeiten), ein Sprung um genau eine Minute ist also Rauschen, kein Ereignis.
# Begründung: ERKLAERUNG.md, Abschnitt "Phase 4 – Ein-Minuten-Sprünge".
SPUERBAR = 120  # ab 2 Minuten zählt eine Verspätung als "vorhanden"
TOLERANZ = 75  # bis gut eine Minute Rückgang gilt noch als "gleich geblieben"
ZUWACHS = 90  # mehr als eine Minute (also mehr als ein Rundungsschritt) = hier "entsteht" Verspätung
MIN_LAENGE = 3  # so viele Messpunkte in Folge braucht eine Kaskade


def lade_haltestellennamen() -> dict[str, str]:
    """stop_id -> Name aus dem neuesten statischen GTFS (stop_ids sind versionsstabil)."""
    zips = sorted(DATA.glob("gtfs*.zip"), key=lambda p: p.stat().st_mtime)
    if not zips:
        return {}
    with zipfile.ZipFile(zips[-1]) as z, z.open("stops.txt") as fh:
        return {r["stop_id"]: r["stop_name"] for r in csv.DictReader(io.TextIOWrapper(fh, "utf-8-sig"))}


def einordnen(stop: dict, ist_letzte: bool) -> tuple[str, int | None]:
    """
    Der VBB-Feed kennt pro Haltestelle drei Muster (ausgezählt in ERKLAERUNG.md):
      0 / X  -> Abfahrt wurde gemeldet (Messpunkt), Verspätung X
      X / X  -> Wert nur vom letzten Messpunkt weitergereicht (Prognose)
      0 / 0  -> keine Information (NICHT "pünktlich", siehe ERKLAERUNG.md)
    An der Endhaltestelle gibt es keine Abfahrt, dort steht der weitergereichte Wert als X / 0.
    """
    a, d = stop["arrival_delay"] or 0, stop["departure_delay"] or 0
    if a == 0 and d != 0:
        return "mess", d
    if a != 0 and (a == d or (ist_letzte and d == 0)):
        return "prognose", a
    return "leer", None


def lade_fahrten() -> dict[tuple[str, str], dict]:
    """(Betriebstag, trip_id) -> {seq: (stop_id, art, wert, snapshot_zeit)}; spätere Snapshots überschreiben."""
    fahrten: dict[tuple[str, str], dict] = defaultdict(dict)
    snapshots_pro_tag: Counter = Counter()
    for datei in sorted(RAW.glob("*.jsonl")):
        if datei.stem < START_DATUM:
            continue
        for zeile in datei.open():
            try:
                snap = json.loads(zeile)
            except json.JSONDecodeError:
                continue  # abgebrochener Lauf -> halbe letzte Zeile
            zeit = datetime.fromisoformat(snap["snapshot_time"]).astimezone(BERLIN)
            # Nachtfahrten nach Mitternacht gehören zum Vortag (Betriebstag endet ~3 Uhr)
            tag = zeit.date().isoformat() if zeit.hour >= 3 else (zeit.date().fromordinal(zeit.date().toordinal() - 1)).isoformat()
            snapshots_pro_tag[tag] += 1
            for trip in snap["trips"]:
                stops = trip["stops"]
                for i, s in enumerate(stops):
                    art, wert = einordnen(s, i == len(stops) - 1)
                    alt = fahrten[(tag, trip["trip_id"])].get(s["seq"])
                    # Ein Messpunkt wird nie von einer späteren Prognose/Leere überschrieben
                    if alt and alt[1] == "mess" and art != "mess":
                        continue
                    fahrten[(tag, trip["trip_id"])][s["seq"]] = (s["stop_id"], art, wert, zeit)
    lade_fahrten.snapshots_pro_tag = snapshots_pro_tag
    return fahrten


def messverlauf(stops: dict) -> tuple[list[tuple[int, str, int]], int]:
    """Nur plausible Messpunkte, nach Haltestellenfolge sortiert. Zweiter Wert: verworfene Punkte."""
    verlauf, verworfen = [], 0
    for seq in sorted(stops):
        stop_id, art, wert, _ = stops[seq]
        if art != "mess":
            continue
        if not PLAUSIBEL_MIN <= wert <= PLAUSIBEL_MAX:
            verworfen += 1
            continue
        verlauf.append((seq, stop_id, wert))
    return verlauf, verworfen


def laengste_kaskade(verlauf: list[tuple[int, str, int]]) -> list[tuple[int, str, int]]:
    """
    Kaskade = mindestens MIN_LAENGE aufeinanderfolgende Messpunkte, an denen
      (1) die Verspätung spürbar ist (>= SPUERBAR) und
      (2) sie gegenüber dem vorherigen Messpunkt nicht kleiner wird (Toleranz TOLERANZ).
    Gibt die längste solche Folge zurück (leer, wenn keine).
    """
    beste, aktuell = [], []
    for p in verlauf:
        if p[2] >= SPUERBAR and (not aktuell or p[2] >= aktuell[-1][2] - TOLERANZ):
            aktuell.append(p)
        else:
            aktuell = [p] if p[2] >= SPUERBAR else []
        if len(aktuell) > len(beste):
            beste = list(aktuell)
    return beste if len(beste) >= MIN_LAENGE else []


def main() -> None:
    namen = lade_haltestellennamen()
    fahrten = lade_fahrten()
    snaps = lade_fahrten.snapshots_pro_tag

    zeilen, pro_halt = [], defaultdict(Counter)
    verworfen_gesamt = 0
    for (tag, trip_id), stops in sorted(fahrten.items()):
        verlauf, verworfen = messverlauf(stops)
        verworfen_gesamt += verworfen
        kaskade = laengste_kaskade(verlauf)
        for (_, _, v0), (_, stop_id, v1) in zip(verlauf, verlauf[1:]):
            delta = v1 - v0
            pro_halt[stop_id]["paare"] += 1
            pro_halt[stop_id]["summe_delta"] += delta
            if delta >= ZUWACHS:
                pro_halt[stop_id]["waechst"] += 1
            elif delta <= -ZUWACHS:
                pro_halt[stop_id]["schrumpft"] += 1
        if kaskade:
            pro_halt[kaskade[0][1]]["kaskaden_start"] += 1
        wochentag = datetime.fromisoformat(tag).strftime("%a")
        zeilen.append({
            "tag": tag,
            "wochentag": wochentag,
            "trip_id": trip_id,
            "messpunkte": len(verlauf),
            "verworfen": verworfen,
            "max_verspaetung_s": max((p[2] for p in verlauf), default=""),
            "letzte_verspaetung_s": verlauf[-1][2] if verlauf else "",
            "kaskade": bool(kaskade),
            "kaskade_laenge": len(kaskade),
            "kaskade_start": namen.get(kaskade[0][1], kaskade[0][1]) if kaskade else "",
            "kaskade_zuwachs_s": kaskade[-1][2] - kaskade[0][2] if kaskade else "",
        })

    with (DATA / "phase3_fahrten.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(zeilen[0]))
        w.writeheader()
        w.writerows(zeilen)
    with (DATA / "phase3_haltestellen.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["stop_id", "name", "messpaare", "waechst", "schrumpft", "mittl_delta_s", "kaskaden_start"])
        for stop_id, c in sorted(pro_halt.items(), key=lambda kv: -kv[1]["waechst"]):
            w.writerow([stop_id, namen.get(stop_id, ""), c["paare"], c["waechst"], c["schrumpft"],
                        round(c["summe_delta"] / c["paare"]) if c["paare"] else "", c["kaskaden_start"]])

    # --- Zusammenfassung ------------------------------------------------------
    mit_mess = [z for z in zeilen if z["messpunkte"]]
    mit_2 = [z for z in zeilen if z["messpunkte"] >= 2]
    kask = [z for z in zeilen if z["kaskade"]]
    print(f"Zeitraum: {min(z['tag'] for z in zeilen)} bis {max(z['tag'] for z in zeilen)}, "
          f"{len(snaps)} Betriebstage, {sum(snaps.values())} Snapshots")
    print(f"Fahrten im Feed:                 {len(zeilen)}")
    print(f"  davon mit >=1 Messpunkt:       {len(mit_mess)} ({100*len(mit_mess)/len(zeilen):.0f} %)")
    print(f"  davon mit >=2 Messpunkten:     {len(mit_2)} ({100*len(mit_2)/len(zeilen):.0f} %)  <- nur hier ist ein Verlauf sichtbar")
    print(f"  Messpunkte pro Fahrt (Median, nur mit Messung): {median(z['messpunkte'] for z in mit_mess)}")
    print(f"  verworfene unplausible Messpunkte: {verworfen_gesamt}")
    print(f"Fahrten mit Kaskade:             {len(kask)} ({100*len(kask)/len(mit_2):.0f} % der Fahrten mit Verlauf)")
    if kask:
        print(f"  Zuwachs innerhalb der Kaskade (Median): {median(z['kaskade_zuwachs_s'] for z in kask)} s")
        print("  Häufigste Startpunkte:")
        for name, n in Counter(z["kaskade_start"] for z in kask).most_common(6):
            print(f"    {n:4d}  {name}")
    print("Haltestellen, an denen die Verspätung am häufigsten um >=1 min wächst:")
    top = sorted(pro_halt.items(), key=lambda kv: -kv[1]["waechst"])[:8]
    for stop_id, c in top:
        print(f"    {c['waechst']:4d}x wächst, {c['schrumpft']:3d}x schrumpft, von {c['paare']:4d}  {namen.get(stop_id, stop_id)}")
    print("Tage mit auffällig wenig Fahrten im Feed (unter 60 % des Medians gleicher Wochentage):")
    pro_tag = Counter(z["tag"] for z in zeilen)
    nach_wt = defaultdict(list)
    for tag, n in pro_tag.items():
        nach_wt[datetime.fromisoformat(tag).weekday()].append(n)
    for tag, n in sorted(pro_tag.items()):
        m = median(nach_wt[datetime.fromisoformat(tag).weekday()])
        if n < 0.6 * m:
            print(f"    {tag} ({datetime.fromisoformat(tag).strftime('%a')}): {n} Fahrten, üblich ~{m:.0f}")


if __name__ == "__main__":
    main()
