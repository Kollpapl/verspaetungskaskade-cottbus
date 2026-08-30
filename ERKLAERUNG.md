# Wo genau entsteht eine Verspätungs-Kaskade im ÖPNV, und wie viel Puffer würde sie stoppen?

Dieses Dokument fasst Fragestellung, Datengrundlage und Plan des Projekts zusammen – von der Grundidee bis zum aktuellen Stand. Der Code liegt im selben Projektordner, Setup-Anleitung in `README.md`.

## Kurz erklärt: Begriffe, die im Dokument immer wieder auftauchen

**GTFS** (General Transit Feed Specification): das weltweite Standardformat, in dem Verkehrsverbünde ihren *Sollfahrplan* veröffentlichen – Tabellen wie "welche Haltestellen hat Linie X, in welcher Reihenfolge, zu welcher geplanten Uhrzeit". Statisch, weil sich das nur zwei- bis dreimal pro Woche ändert (neue Fahrpläne, Baustellen etc.).

**GTFS-Realtime (GTFS-RT)**: die Ergänzung dazu, live und im Sekundentakt aktualisiert – der *Istzustand*: wo ein Fahrzeug gerade tatsächlich ist und wie viele Minuten Verspätung für die nächsten Haltestellen vorhergesagt werden. Kein Klartext, sondern binär codiert (Protocol Buffers), man braucht eine kleine Bibliothek, um es zu lesen.

**Kaskade** (im Kontext dieses Projekts): eine Verspätung, die sich von Haltestelle zu Haltestelle nicht abbaut, sondern hält oder wächst – im Gegensatz zu einer Verspätung, die z. B. an einer Endhaltestelle durch geplante Standzeit einfach wieder verschwindet. Die genaue Definition ist Teil der Arbeit selbst, siehe Phase 3 unten.

## Die Ausgangsfrage

Bus- und Bahnlinien geraten oft nicht an einer einzigen katastrophalen Stelle in Verspätung, sondern durch viele kleine Verzögerungen, die sich von Haltestelle zu Haltestelle aufsummieren – eine Kaskade. Wenn man wüsste, an welcher Haltestelle einer Linie diese Kaskade typischerweise beginnt oder sich verstärkt, ließe sich dort gezielt mit ein paar Minuten mehr Pufferzeit gegensteuern, statt pauschal den ganzen Fahrplan zu entzerren.

**Forschungsfrage:** Wo entlang einer Linie entstehen und verstärken sich Verspätungs-Kaskaden am häufigsten, und wie stark würde gezielter Puffer an genau dieser Stelle die Verspätung am Linienende senken?

## Datenquelle

Der VBB (Verkehrsverbund Berlin-Brandenburg, deckt auch Cottbus ab) stellt beides öffentlich bereit, ohne Zugangsbeschränkung:

- **Statisches GTFS** – der Sollfahrplan als ZIP, zweimal wöchentlich aktualisiert: <https://www.vbb.de/vbbgtfs>
- **GTFS-Realtime** – die Ist-Verspätungen pro Haltestelle, live: <https://production.gtfsrt.vbb.de/data> (max. 60 Abfragen/Minute, aussagekräftiger User-Agent mit Kontaktangabe nötig, sonst Blocking-Risiko)

**Bekanntes Problem, Stand 30.08.2026:** Laut Statusseite fehlen dem Realtime-Feed seit dem 04.06.2026 teilweise Daten, ohne genannten Reparaturzeitpunkt. Muss vor Beginn der Dauersammlung (Phase 2) noch einmal geprüft werden – sonst sammelt man wochenlang Lücken statt brauchbarer Daten.

## Der Plan in sechs Phasen

**Phase 1 – Linie auswählen, Fahrplanstruktur verstehen.** Statisches GTFS laden, `routes.txt`/`trips.txt`/`stop_times.txt`/`stops.txt` durchsuchen. Ziel: eine Linie mit vielen Haltestellen, engem Takt und einem Umsteigeknoten unterwegs – nicht eine, die praktisch nie Verspätung hat.

**Phase 2 – Datensammlung automatisieren.** Ein Skript fragt den GTFS-RT-Feed regelmäßig ab, filtert auf die gewählte Linie (`trip_id`, gematcht gegen die statischen Daten), extrahiert die vorhergesagten Verspätungen pro Haltestelle und hängt sie an eine SQLite-Datenbank an. Muss über mehrere Wochen laufen (sonst nur Zufallsrauschen statt Muster) – dafür geeignet: GitHub-Actions-Workflow mit Zeitplan, läuft in der Cloud, kein eigenes Dauerlaufgerät nötig.

**Phase 3 – "Kaskade" wissenschaftlich sauber definieren.** Arbeitsdefinition zum Diskutieren: Eine Verspätung an Haltestelle N ist Teil einer Kaskade, wenn sie an Haltestelle N+1 nicht kleiner wird, sondern gleich bleibt oder wächst – über mehrere aufeinanderfolgende Haltestellen. Lässt sich pro Fahrt als eine Art Verspätungs-Verlaufskurve darstellen.

**Phase 4 – Explorative Analyse.** Mit den gesammelten Wochen an Daten: An welchen Haltestellen entsteht die erste Verspätung am häufigsten? Wo bricht die Kaskade von selbst wieder ab (z. B. Endhaltestellen mit Standzeit)? Ergibt die "kritischen Punkte" mit echten Zahlen statt Vermutung.

**Phase 5 – Modell und Eigenanteil.** Ein Warteschlangen- oder Regressionsmodell simuliert: Wenn am kritischen Punkt X Minuten mehr Puffer eingeplant würden, wie verändert sich die Verspätung entlang der restlichen Route? Kalibriert auf einem Teil der historischen Daten, geprüft auf einem anderen, nie gesehenen Teil (wie beim Trust-Score im [[skin-cancer-shortcut-detection-project|Skin-Cancer-Projekt]] – damit die Zahl nicht einfach passend gemacht wirkt).

**Phase 6 – Realer Nutzen konkret machen.** Zielaussage am Ende: "An Haltestelle X würde ein Puffer von Y Minuten die durchschnittliche Endverspätung der Linie um Z% senken" – übersetzt sich in echte Kosten/Nutzen (weniger Anschlussverluste, weniger Ausgleichsfahrten).

## Wichtiger Zwischenschritt: Feed-Gesundheit geprüft, bevor eine Linie festgelegt wurde

Bevor eine Linie endgültig gewählt wurde, wurde die bekannte Datenlücke im VBB-Realtime-Feed (siehe oben, seit 04.06.2026) konkret für die Kandidatenlinien geprüft, statt sie nur zur Kenntnis zu nehmen – mit `check_feed_health.py`. Wichtig dabei: ein einzelner Snapshot mit "0 Treffer" für eine Linie kann auch einfach heißen, dass gerade keine Fahrt unterwegs ist (Betriebspause). Deshalb prüft das Skript zusätzlich gegen `calendar.txt`, ob laut Fahrplan überhaupt eine Fahrt aktiv sein sollte, bevor "0 Treffer" als echte Feed-Lücke gewertet wird.

**Ergebnis (30.08.2026, Sonntag ca. 15:46 Uhr, `check_feed_health.py --scan-agency 516` für Cottbusverkehr GmbH):**

- 9 von 45 Bus-Routen sind aktuell im Live-Feed vertreten, 36 fehlen.
- **Alle vier Straßenbahnlinien (1–4) fehlen komplett** – und das, obwohl laut Fahrplan zum Prüfzeitpunkt für Linie 2, 3 und 4 jeweils mehrere Fahrten aktiv unterwegs sein sollten (4–6 Fahrten im ±20-Minuten-Fenster um den Prüfzeitpunkt). Das ist also **keine Betriebspause, sondern eine echte, systematische Feed-Lücke** – bestätigt genau das im Mentoring angesprochene Problem, konkret für unsere Zielregion.
- Zum Vergleich: bei anderen Straßenbahnbetreibern im selben Feed (BVG, Potsdam, Brandenburg an der Havel) sind die meisten bis alle Tram-Routen live vertreten – der Ausfall betrifft spezifisch Cottbusverkehr GmbH, nicht Straßenbahnen im VBB-Netz generell.
- Bus **16** (`route_id 13108_700`) dagegen: live im Feed, mit 5 aktiven Fahrten im Prüf-Zeitfenster, alle mit plausiblen Verspätungswerten (aktuell durchgehend 0 – nachvollziehbar für einen ruhigen Sonntagnachmittag, wird in Phase 2 über mehrere Wochen weiterbeobachtet).

Rohausgabe des Scans liegt in `data/feed_health_cottbusverkehr_*.txt`.

## Aktueller Stand

Projekt gerade aufgesetzt, Phase 1 abgeschlossen: Linie gewählt. `explore_static_gtfs.py` lädt das statische GTFS und listet alle Linien, die mindestens eine Haltestelle in Cottbus bedienen, sortiert nach Fahrten/Tag. Erster Lauf (30.08.2026): 81 Linien gefunden. Ergiebigste Kandidaten nach den Kriterien aus Phase 1 (viele Haltestellen, enger Takt), inkl. Live-Feed-Status:

| Linie | Typ | Haltestellen | Fahrten/Tag | Im Live-Feed? |
|---|---|---|---|---|
| 3 (Straßenbahn) | Tram | 67, alle in Cottbus | 415 | ❌ fehlt systematisch |
| 4 (Straßenbahn) | Tram | 42, alle in Cottbus | 399 | ❌ fehlt systematisch |
| 2 (Straßenbahn) | Tram | 59, alle in Cottbus | 392 | ❌ fehlt systematisch |
| **16 (Bus)** | **Bus** | **55, alle in Cottbus** | **266** | **✅ bestätigt live** |
| 1 (Straßenbahn) | Tram | 34, alle in Cottbus | 98 | ❌ fehlt systematisch |

**Linienwahl: Bus 16** (`route_id 13108_700`), statt der ursprünglich vorgeschlagenen Tram-Linie 3 – einzige Wahl aus den ergiebigsten Kandidaten, die tatsächlich Live-Daten liefert. Trade-off gegenüber der Tram bewusst in Kauf genommen: als Bus ist sie im gemischten Straßenverkehr unterwegs statt größtenteils auf eigenem Gleiskörper, Verspätungsursachen also potenziell stärker mit allgemeinem Autoverkehr vermischt statt rein netzinternen Effekten zuzuordnen – das wird bei der späteren Interpretation (Phase 4/5) berücksichtigt. Dafür: komplett innerhalb Cottbus, 266 Fahrten/Tag, 55 Haltestellen – nach wie vor eine ergiebige Linie für die Kaskaden-Frage. Vollständige Tabelle mit allen 81 Linien: `data/kandidaten_linien_cottbus.csv`.

## Phase 2 – Sammlung aufgebaut, aber noch nicht scharf geschaltet

Wichtige Erkenntnis vom Sonntagnachmittag-Check: der Feed lebt für Bus 16, aber alle Verspätungswerte waren durchgehend 0 – nachvollziehbar für einen ruhigen Sonntagnachmittag, aber genau deshalb der am wenigsten aussagekräftige Testfall dafür, ob der Feed unter echter Last (Berufsverkehr, Stau, Verspätungen) überhaupt sinnvolle, von 0 abweichende Werte liefert. Statt "irgendwann anders nochmal prüfen" wurde das zum Teil von Phase 2 selbst gemacht:

**Design-Entscheidung: JSONL statt direkt SQLite fürs Sammeln.** Ein Cron-Workflow, der wochenlang alle paar Minuten eine SQLite-Datei verändert und committet, erzeugt Binär-Diffs (bläht das Git-Repo unnötig auf) und riskiert bei einem mitten im Schreiben abgebrochenen Lauf (Netzwerk-Timeout, Rate-Limit) eine korrupte Datenbankdatei statt nur eines fehlenden Datenpunkts. Deshalb: `collect_delays.py` hängt pro Tag eine reine JSONL-Datei an (`data/raw/<datum>.jsonl`, eine Zeile pro Snapshot) – git-freundlich diffbar, ein abgebrochener Lauf verursacht höchstens eine unvollständige letzte Zeile. Die SQLite-Datenbank für die spätere Analyse wird davon getrennt, als eigener wiederholbarer Schritt, lokal aus den JSONL-Dateien gebaut (`build_sqlite.py`) – nicht Teil der automatisierten Sammlung.

**GitHub-Actions-Workflow** (`.github/workflows/collect.yml`): checkt aus, installiert Abhängigkeiten via `uv sync`, ruft `collect_delays.py` auf, committet und pusht `data/raw/`. Zwei Dinge dabei zu beachten, nicht als Bug misszuverstehen:

- GitHub Actions garantiert bei `schedule`-Cron nur einen *Mindest*-Abstand von 5 Minuten – bei hoher Systemlast auf GitHubs Seite kann ein Lauf verzögert oder ausgelassen werden. Lücken oder unregelmäßige Abstände zwischen den `snapshot_time`-Zeitstempeln sind also normal und müssen in Phase 4 eingeplant werden (z.B. nicht einfach "Minuten seit letztem Snapshot" als exakte 5 annehmen).
- `concurrency: group: collector, cancel-in-progress: false` verhindert, dass zwei Läufe gleichzeitig gegen denselben Branch pushen, falls ein Lauf mal länger braucht als der Abstand bis zum nächsten.

**Der Cron-Trigger ist aktuell absichtlich auskommentiert** (`on:` enthält nur `workflow_dispatch`, manuell auslösbar über die GitHub-Weboberfläche oder `gh workflow run collect.yml`). Geplantes Vorgehen, um ihn scharf zu schalten – das ist der eigentliche, gezieltere zweite Health-Check:

1. Heute Abend einmal manuell auslösen (Feierabendverkehr).
2. Morgen früh im Berufsverkehr (~7:30 Uhr) nochmal.
3. Beide `data/raw/<datum>.jsonl`-Einträge prüfen: liefert der Feed unter Last plausible, von 0 abweichende Verspätungswerte für Bus 16? Wenn ja, Cron-Zeile in `collect.yml` einkommentieren und pushen – erst dann startet die eigentliche mehrwöchige Dauersammlung.

**Technischer Testlauf (30.08.2026, 14:11 Uhr UTC):** Repo `github.com/Kollpapl/verspaetungskaskade-cottbus` (privat) angelegt, Workflow einmal manuell über `workflow_dispatch` ausgelöst, um die Pipeline selbst zu prüfen (Checkout → `uv sync` → sammeln → committen → pushen) – nicht als Ersatz für den Berufsverkehr-Check, sondern als reiner Technik-Test. Lief fehlerfrei durch, 7 aktive Fahrten erfasst und nach `data/raw/2026-08-30.jsonl` committet. Dabei zwei GitHub-seitige Stolpersteine gefixt, die sonst jeden Lauf hätten scheitern lassen: das GitHub-Token brauchte das `workflow`-Scope, um `.github/workflows/` überhaupt pushen zu dürfen, und das Repo hatte standardmäßig nur Lese-Rechte für den `GITHUB_TOKEN` im Workflow (`default_workflow_permissions`), musste auf `write` gesetzt werden, sonst schlägt `git push` im letzten Schritt fehl.

**Cron scharf geschaltet (30.08.2026, 16:17 Uhr)** – mit einer Anpassung gegenüber dem ursprünglichen Plan: statt zwei einzeln von Hand getimte Läufe (hätte eine externe Zeitsteuerung mit eigenem GitHub-Zugang gebraucht, der hier nicht eingerichtet ist) einfach den Cron-Trigger selbst aktiviert. GitHub Actions' eigener Scheduler deckt Feierabendverkehr (heute Abend), Berufsverkehr (morgen ab 07:30 Uhr) und alles dazwischen automatisch ab, alle 5 Minuten – inhaltlich dasselbe Ergebnis wie die zwei geplanten Testläufe, nur ohne den Umweg. Die ersten ~18h Rohdaten (`data/raw/2026-08-30.jsonl` und `2026-08-31.jsonl`) sind der eigentliche Health-Check.

## Problem entdeckt: Cron feuert nicht von selbst

**Befund (30.08.2026, laufend seit 16:17 Uhr geprüft):** Der Cron-Trigger (`*/5 * * * *`) hat über 2 Stunden lang (~24 mögliche 5-Minuten-Zeitpunkte) **keinen einzigen automatischen Lauf ausgelöst** – geprüft über `gh api repos/.../actions/runs --jq '.workflow_runs[] | select(.event=="schedule")'`, durchgehend leer. GitHub-Statusseite zeigt keine Störung, die Workflow-Datei ist auf GitHub korrekt (Schedule nicht auskommentiert), Actions ist aktiviert – die Ursache ist damit noch nicht gefunden. Ein bekanntes, dokumentiertes GitHub-Verhalten ist, dass `schedule`-Events bei hoher Systemlast verzögert werden können (laut GitHub-Doku bis zu ~1 Stunde), aber 2+ Stunden ganz ohne einen einzigen Lauf geht darüber hinaus. **Das ist ein ungelöstes Problem, kein erledigter Haken** – für die eigentliche mehrwöchige Dauersammlung muss das noch gefixt werden (mögliche nächste Schritte: Workflow-Datei nochmal mit trivialer Änderung neu pushen, ob das den Scheduler "aufweckt"; alternative Trigger-Mechanismen wie ein externer Cron-Dienst, der per `repository_dispatch` anstößt; GitHub-Support/Community-Forum nach ähnlichen Fällen durchsuchen).

**Übergangslösung:** Bis das geklärt ist, werden die Rush-Hour-Checks manuell per `gh workflow run collect.yml -R Kollpapl/verspaetungskaskade-cottbus` nachgebildet (mehrere Läufe im Abstand von ~6-8 Minuten über das jeweilige Zeitfenster verteilt).

## Checkpoint 1: Feierabendverkehr (30.08.2026, 18:11–18:32 Uhr) – Ergebnis: Feed liefert echtes Signal

Vier Läufe manuell ausgelöst (18:11, 18:17, 18:25, 18:32 Uhr), macht in Summe 507 Haltestellen-Updates über 4 Snapshots für Bus 16. Auswertung (`build_sqlite.py` + SQL):

- **80 von 507 Updates (≈16%) zeigen einen von 0 abweichenden Verspätungswert** – Werte reichen von 61 bis 255 Sekunden (ca. 1-4 Minuten), alle klar innerhalb der plausiblen ±25-Minuten-Grenze. Kein einziger unplausibler Ausreißer (wie die andernorts gemeldeten -30-Minuten-Fälle).
- Die übrigen ~84% zeigen exakt 0 – nachvollziehbar, die meisten Fahrten sind pünktlich, das ist kein Zeichen für einen kaputten Feed.
- Einzelne Fahrten zeigen denselben Verspätungswert konsistent über mehrere aufeinanderfolgende Haltestellen (z.B. durchgehend 68s bei einer Fahrt über 3 Snapshots hinweg) – das ist normales GTFS-RT-Verhalten (eine einmal gemeldete Verspätung wird für nachfolgende Haltestellen fortgeschrieben, wenn keine neue Korrektur vorliegt), kein Datenfehler.

**Fazit Checkpoint 1: Bus 16 liefert unter echter Last plausible, echte Verspätungssignale – der eigentliche Zweck des Health-Checks ist erfüllt.** Die Linienwahl (Bus 16 statt der toten Cottbus-Trams) ist damit inhaltlich bestätigt, unabhängig vom noch ungelösten Cron-Problem.

## Checkpoint 2: Berufsverkehr (ausstehend)

Geplant für morgen (31.08.2026) ca. 07:15–07:45 Uhr, gleiches Vorgehen (manuelle Läufe, da Cron noch nicht zuverlässig).

**Noch offen / nächste Schritte:**
1. Checkpoint 2 morgen früh durchführen und auswerten.
2. Cron-Problem klären, bevor die eigentliche mehrwöchige Dauersammlung wirklich unbeaufsichtigt laufen kann – aktuell würde ohne manuelles Nachhelfen praktisch nichts gesammelt.
