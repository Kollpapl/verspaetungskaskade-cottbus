"""
Phase 4: explorative Analyse auf Basis der Phase-3-Definition.

Beantwortet:
  1. Springt der Feed in Minutenschritten? (Rundungs-Rauschen erkennen)
  2. Wie robust ist die Kaskaden-Quote gegenüber den Schwellen? (Sensitivität)
  3. Wie spät fahren die Busse schon an der Starthaltestelle los?
  4. Wo wächst die Verspätung, wo baut sie sich wieder ab? (je Richtung)
  5. Wann (Uhrzeit, Werktag/Wochenende) gibt es die meisten Kaskaden?

Aufruf:
    uv run phase4_analyse.py
Ergebnis zusätzlich als data/phase4_ergebnisse.txt
"""

import contextlib
import io
from collections import Counter, defaultdict
from datetime import date
from statistics import median

import phase3_kaskaden as p3

ZIEL_A = "Uhlandstr."  # Richtung Sachsendorf
ZIEL_B = "Stadthalle"  # Richtung Innenstadt (Endet an Puschkinpromenade oder Post)


def richtung(stops: dict, namen: dict) -> str:
    letzte = namen.get(stops[max(stops)][0], "")
    return "→ Uhlandstr." if ZIEL_A in letzte else "→ Stadthalle" if ZIEL_B in letzte else "andere"


def kurz(name: str) -> str:
    return name.removeprefix("Cottbus, ")


def prozent(a: int, b: int) -> str:
    return f"{100 * a / b:.0f} %" if b else "–"


def main() -> None:
    namen = p3.lade_haltestellennamen()
    fahrten = p3.lade_fahrten()

    daten = []  # (richtung, wochenende, stunde, verlauf, erster_seq)
    for (tag, _), stops in fahrten.items():
        verlauf, _ = p3.messverlauf(stops)
        zeiten = [z for (_, art, _, z) in stops.values() if art == "mess"] or [z for (*_, z) in stops.values()]
        wochenende = date.fromisoformat(tag).weekday() >= 5
        daten.append((richtung(stops, namen), wochenende, min(zeiten).hour, verlauf, min(stops)))
    mit_verlauf = [d for d in daten if len(d[3]) >= 2]

    # 1. Rundungs-Rauschen ------------------------------------------------------
    print("1. Sprünge zwischen zwei Messpunkten (gerundet auf 30 s)")
    spruenge = Counter()
    for *_, verlauf, _ in mit_verlauf:
        for a, b in zip(verlauf, verlauf[1:]):
            spruenge[round((b[2] - a[2]) / 30) * 30] += 1
    gesamt = sum(spruenge.values())
    for k in (-120, -90, -60, -30, 0, 30, 60, 90, 120, 180):
        print(f"   {k:+5d} s: {spruenge[k]:5d}  ({prozent(spruenge[k], gesamt)})")
    print(f"   -> genau ±1 min: {prozent(spruenge[60] + spruenge[-60], gesamt)} aller Sprünge,"
          f" ±30 s nur {prozent(spruenge[30] + spruenge[-30], gesamt)}")

    # 2. Sensitivität -----------------------------------------------------------
    print("\n2. Anteil Fahrten mit Kaskade je nach Schwelle (von", len(mit_verlauf), "Fahrten mit Verlauf)")
    original = (p3.SPUERBAR, p3.TOLERANZ, p3.MIN_LAENGE)
    for sp, tol, ml in [(60, 30, 3), (60, 75, 3), (120, 75, 3), (180, 75, 3), (120, 75, 4)]:
        p3.SPUERBAR, p3.TOLERANZ, p3.MIN_LAENGE = sp, tol, ml
        k = [p3.laengste_kaskade(d[3]) for d in mit_verlauf]
        k = [x for x in k if x]
        top = Counter(kurz(namen.get(x[0][1], "?")) for x in k).most_common(2)
        markiert = "  <- gewählt" if (sp, tol, ml) == original else ""
        print(f"   ab {sp:3d} s, Toleranz {tol:2d} s, ≥{ml} Punkte: {prozent(len(k), len(mit_verlauf)):>5}"
              f"   häufigster Start: {top[0][0]} ({top[0][1]}){markiert}")
    p3.SPUERBAR, p3.TOLERANZ, p3.MIN_LAENGE = original

    # 3. Verspätung schon am Start ----------------------------------------------
    print("\n3. Abfahrt an der Starthaltestelle (nur Fahrten, bei denen der Start gemessen wurde)")
    for r in ("→ Uhlandstr.", "→ Stadthalle"):
        start = [d[3][0][2] for d in daten if d[0] == r and d[3] and d[3][0][0] == d[4]]
        ohne = sum(1 for d in daten if d[0] == r and d[3] and d[3][0][0] != d[4])
        if start:
            print(f"   {r}: {len(start)} Fahrten, Median {median(start):.0f} s, "
                  f"≥2 min zu spät: {prozent(sum(v >= 120 for v in start), len(start))}"
                  f"   (bei {ohne} weiteren Fahrten war der Start nicht gemessen)")

    # 4. Wo wächst / schrumpft die Verspätung, je Richtung -----------------------
    print(f"\n4. Wo wächst (≥ +{p3.ZUWACHS} s) bzw. schrumpft (≤ −{p3.ZUWACHS} s) die Verspätung?")
    for r in ("→ Uhlandstr.", "→ Stadthalle"):
        c = defaultdict(Counter)
        for d in mit_verlauf:
            if d[0] != r:
                continue
            for a, b in zip(d[3], d[3][1:]):
                delta = b[2] - a[2]
                c[b[1]]["n"] += 1
                c[b[1]]["+"] += delta >= p3.ZUWACHS
                c[b[1]]["-"] += delta <= -p3.ZUWACHS
        print(f"   {r}")
        for stop_id, z in sorted(c.items(), key=lambda kv: -kv[1]["+"])[:5]:
            print(f"     wächst {z['+']:3d}x / schrumpft {z['-']:3d}x von {z['n']:3d}  {kurz(namen.get(stop_id, '?'))}")
        abbau = sorted(c.items(), key=lambda kv: -kv[1]["-"])[:3]
        print("     stärkster Abbau: " + ", ".join(f"{kurz(namen.get(s, '?'))} ({z['-']}x)" for s, z in abbau))

    # 5. Tageszeit / Wochentag --------------------------------------------------
    print("\n5. Anteil Fahrten mit Kaskade nach Tageszeit (Fahrten mit Verlauf)")
    bloecke = [(4, 7, "04–07"), (7, 9, "07–09"), (9, 13, "09–13"), (13, 16, "13–16"), (16, 19, "16–19"), (19, 24, "19–24")]
    for we, label in ((False, "Mo–Fr"), (True, "Sa/So")):
        teile = []
        for von, bis, txt in bloecke:
            gruppe = [d for d in mit_verlauf if d[1] == we and von <= d[2] < bis]
            k = sum(1 for d in gruppe if p3.laengste_kaskade(d[3]))
            teile.append(f"{txt}: {prozent(k, len(gruppe)):>5} (n={len(gruppe)})")
        print(f"   {label}  " + "   ".join(teile))


if __name__ == "__main__":
    puffer = io.StringIO()
    with contextlib.redirect_stdout(puffer):
        main()
    text = puffer.getvalue()
    print(text, end="")
    (p3.DATA / "phase4_ergebnisse.txt").write_text(text)
