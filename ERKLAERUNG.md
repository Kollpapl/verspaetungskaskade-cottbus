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

## Checkpoint 2: Berufsverkehr (31.08.2026) – Ergebnis: Fenster verpasst, Cron-Problem bestätigt schwerwiegend

Geplant war 07:15–07:45 Uhr mit denselben manuellen Mehrfach-Läufen wie bei Checkpoint 1. Der Rechner war in diesem Fenster aber aus (siehe Chat-Verlauf), also gab es keine manuellen Läufe – nur der Cron sollte greifen. Ergebnis beim Nachschauen (31.08.2026, gegen Mittag):

**Cron-Verhalten seit dem Scharfschalten (30.08.2026, 16:17 Uhr) bis jetzt (~15 Stunden), `*/5 * * * *` konfiguriert (also theoretisch ~180 Läufe erwartet):**

| Zeitpunkt (UTC) | Zeitpunkt (CEST) |
|---|---|
| 18:05:23 | 20:05 |
| 20:59:56 | 22:59 |
| 23:23:30 | 01:23 |
| 01:26:15 | 03:26 |
| 07:21:50 | 09:21 |

**Nur 5 automatische Läufe in 15 Stunden statt der konfigurierten ~180** – im Schnitt alle 2-3 Stunden statt alle 5 Minuten. Das ist kein einmaliger Anlauf-Jitter mehr (wie am 30.08. noch vermutet), sondern ein durchgehendes Muster über die ganze Nacht. Passt zu einem bekannten, von GitHub selbst dokumentierten Verhalten: Sub-stündliche `schedule`-Trigger (wie `*/5 * * * *`) werden bei GitHub Actions ausdrücklich nicht garantiert und können bei Last "verzögert oder ausgesetzt" werden – in der Praxis heißt das hier: der Cron ist für diesen Anwendungsfall (5-Minuten-Takt, private Repos mit wenig sonstiger Aktivität) faktisch unbrauchbar, nicht nur unzuverlässig.

**Folge für Checkpoint 2:** Nur ein einziger Snapshot landete überhaupt in Fenster-Nähe (09:21 Uhr CEST – schon ~1,5h nach dem eigentlichen Berufsverkehrs-Ziel 07:15–07:45 Uhr). Auswertung dieses einen Snapshots:

- 9 Fahrten, 176 Haltestellen-Updates
- 8 von 176 (≈4,5%) zeigen einen plausiblen, von 0 abweichenden Wert, 0 unplausible Ausreißer
- Feed und Bus 16 liefern also weiterhin echte Daten – aber mit nur einem Snapshot lässt sich kein Kaskaden-Muster über Zeit beobachten, und außerhalb der eigentlichen Spitze ist eine niedrigere Quote (4,5% vs. 16% bei Checkpoint 1) plausibel und kein Alarmsignal.

**Fazit Checkpoint 2: Kein vollwertiger zweiter Beleg wie Checkpoint 1 – dafür aber ein klarer, harter Befund zum Cron-Problem.** Die Linienwahl (Bus 16) bleibt durch Checkpoint 1 inhaltlich bestätigt; ein zweiter Beleg im echten Berufsverkehr steht noch aus.

**Noch offen / nächste Schritte (Stand vor dem Cron-Fix):**
1. ~~Cron-Problem lösen~~ → erledigt, siehe nächster Abschnitt.
2. ~~Echten Berufsverkehr-Nachweis nachholen~~ → erledigt, kam am 01.09.2026 automatisch über die Dauersammlung mit (siehe "Langzeit-Nachkontrolle" unten). Kein weiterer manueller Termin nötig.

**Ab hier läuft nur noch die reine Datensammlung im Hintergrund** – mindestens 3–4 Wochen, bevor Phase 4 (explorative Analyse) sinnvoll wird. Kein aktiver Handlungsbedarf, siehe "Cron-Fix"-Abschnitt für den Langzeitstatus.

## Cron-Fix: repository_dispatch statt schedule (31.08.2026)

GitHubs eigener `schedule`-Trigger war für den 5-Minuten-Takt nachweislich ungeeignet (siehe Checkpoint 2 oben: nur 5 von ~180 erwarteten Läufen). Lösung: `collect.yml` löst jetzt zusätzlich auf einen `repository_dispatch`-Event (`collect-tick`) aus, der von einem externen Zeitgeber ausgelöst wird – GitHubs Scheduler wird dabei komplett umgangen. Die `schedule`-Zeile bleibt auskommentiert als dokumentierte Referenz im Workflow stehen.

**Setup:**
- Fine-grained Personal Access Token (Repository access: nur dieses Repo, Permission: `Contents: Read and write`) – lebt ausschließlich im externen Dienst, nirgends im Repo oder in dieser Dokumentation.
- Kostenloser Account bei [cron-job.org](https://cron-job.org): Job schickt alle 5 Minuten `POST https://api.github.com/repos/Kollpapl/verspaetungskaskade-cottbus/dispatches` mit `{"event_type": "collect-tick"}` im Body, Header `Accept: application/vnd.github+json`, `Authorization: Bearer <Token>`, `X-GitHub-Api-Version: 2022-11-28`.

**Verifikation (31.08.2026, 10:30–12:10 Uhr UTC, 1h40 beobachtet):**

**21 von 21 erwarteten Läufen angekommen, lückenlos alle 5 Minuten, alle erfolgreich** – kein einziger Ausfall in der gesamten Beobachtungszeit. Deutlicher Unterschied zum alten Verfahren (5 Läufe in 15 Stunden).

**Fazit: Cron-Problem gelöst.** Die mehrwöchige Dauersammlung kann jetzt unbeaufsichtigt laufen – auch ohne dass der lokale Rechner an ist, da cron-job.org unabhängig vom eigenen Rechner läuft. Der ursprünglich verpasste Berufsverkehr-Nachweis (Checkpoint 2) wird dadurch am nächsten Werktagmorgen automatisch mit dichter Abdeckung nachgeliefert, ohne dass dafür extra ein manueller Termin nötig ist.

**Langzeit-Nachkontrolle (01.09.2026, 09:10 Uhr UTC – 22h40 seit dem letzten Check beobachtet):** 268 von ~273 erwarteten Läufen angekommen, **0 Fehlschläge**. Eine einzige unruhige Phase nachts zwischen 04:55–05:40 Uhr UTC (drei Lücken statt exakt alle 5 Minuten, vermutlich kurzer Hänger bei cron-job.org oder der GitHub-API), sonst durchgehend im 5-Minuten-Takt. Damit bestätigt: der Fix hält auch über einen vollen Tag/Nacht-Zyklus, in dem der eigene Rechner die ganze Zeit aus war – die Sammlung läuft nachweislich unabhängig vom eigenen PC.

**Bonus – Berufsverkehr-Nachweis kam automatisch mit:** Der 01.09.2026 ist ein Dienstag (Werktag). Genau in diese Nacht-Lücke fiel zufällig auch das Zielfenster 07:15–07:45 Uhr CEST (=05:15–05:45 UTC), trotzdem liegen 7 Snapshots im Fenster 05:02–05:55 Uhr UTC vor. Anteil plausibler, von 0 abweichender Verspätungen steigt darin von 15/108 (~14%) auf bis zu 67/156 (~43%) – deutlich höher als der Feierabend-Wert aus Checkpoint 1 (~16%). Damit ist der ursprünglich verpasste Berufsverkehr-Nachweis (Checkpoint 2) durch die laufende Dauersammlung faktisch nachgeliefert, ganz ohne manuellen Eingriff – wie in Schritt 6 des Fix-Plans vorhergesagt.

## Kostenloses Kontingent aufgebraucht (11.09.2026)

**Befund:** Bei einer Routineprüfung (`gh api .../actions/runs`) zeigte sich, dass alle Läufe seit dem **07.09.2026, 20:20 Uhr UTC** fehlschlugen – 3,5 Tage Sammellücke, unbemerkt, weil niemand aktiv hingeschaut hat. GitHubs Fehlermeldung: *"recent account payments have failed or your spending limit needs to be increased"*.

**Ursache, konkret nachgerechnet:** Kein echtes Zahlungsproblem, sondern das kostenlose GitHub-Actions-Kontingent für private Repos (**2000 Minuten/Monat**) war aufgebraucht. Vom 31.08. (Cron-Fix) bis zum 07.09. lief der 5-Minuten-Takt **7,4 Tage durchgehend zuverlässig** – das sind ca. 2.134 Läufe, und GitHub rechnet jeden Lauf mit mindestens 1 abgerechneter Minute ab. 2.134 Minuten > 2.000 Minuten Freikontingent, exakt an dem Punkt gerissen, an dem die Läufe stoppten. Das Spending-Limit steht auf 0 $ (Standard ohne hinterlegte Zahlungsmethode) – GitHub startet dann einfach keine weiteren Läufe, statt automatisch zu belasten. Es wurde also nichts abgebucht, aber die Sammlung stand still.

**Strukturelles Problem:** Bei durchgehendem 5-Minuten-Takt hätte sich das jeden Monat nach ~7 Tagen wiederholt (Rest des Monats: Blackout) – für eine mehrwöchige Dauersammlung nicht tragbar.

**Fix: Takt auf 30 Minuten gestreckt** (in cron-job.org konfiguriert, keine Codeänderung am Workflow nötig – der Takt lebt komplett im externen Zeitgeber, nicht in `collect.yml`):

| Takt | Läufe/Tag | Min/Monat | Anteil Freikontingent |
|---|---|---|---|
| 5 Min (alt) | 288 | 8.640 | 432% |
| 20 Min | 72 | 2.160 | 108% – reicht nicht |
| 25 Min | 58 | 1.728 | 86% |
| **30 Min (gewählt)** | 48 | 1.440 | **72%** – komfortabler Puffer für manuelle Testläufe |

**Trade-off, bewusst akzeptiert:** Gröbere Zeitauflösung der Snapshots (alle 30 statt alle 5 Minuten) – muss in Phase 4 mitgedacht werden, ähnlich wie die bereits dokumentierten unregelmäßigen Abständen durch den `schedule`-Trigger vorher. Im Gegenzug: 0 € Kosten, keine hinterlegte Zahlungsmethode nötig, kein monatlich wiederkehrender Blackout.

**Offen:** Der aktuelle Monat ist bis zum Kontingent-Reset weiterhin blockiert (GitHub setzt das Kontingent monatlich zurück, genaues Reset-Datum steht im GitHub-Billing-Dashboard unter "Plans and usage" – wurde noch nicht geprüft). Bis dahin sammelt sich nichts, danach greift automatisch der neue 30-Minuten-Takt.

**Nachkontrolle (25.09.2026, 10:32 Uhr UTC):** Der 30-Minuten-Takt ist korrekt aktiv (Läufe kommen zuverlässig alle 30 Min an), aber **jeder einzelne Lauf failt weiterhin mit derselben Meldung wie am 11.09.** – die Sperre gilt für den ganzen restlichen Monat, nicht nur bis zum Fix. Letzter erfolgreicher Lauf bleibt **07.09.2026, 20:20 Uhr UTC** – zu diesem Zeitpunkt also **17,5 Tage durchgehender Ausfall, keine einzige neue Zeile seit `2026-09-07.jsonl`**. Reset laut Nutzerangabe erst zum Monatsende (~01.10.), 30-Min-Takt greift danach automatisch, keine weitere Aktion nötig. Für die "mindestens 3–4 Wochen"-Anforderung aus dem Sechs-Phasen-Plan bedeutet das: die durchgehende Sammelphase startet de facto ab dem Reset neu, Phase 4 realistisch nicht vor **Ende Oktober** statt wie ursprünglich gedacht Ende September.

## Phase 3 – Kaskade definiert (11.11.2026)

**Datengrundlage:** 01.10.–11.11.2026, 43 Betriebstage, 1.988 Snapshots (alle 30 Min), **2.610 Fahrten** von Bus 16. Ausgewertet mit `phase3_kaskaden.py`.

### Erst verstehen, was im Feed eigentlich steht

Beim Auszählen aller 155.186 Haltestellen-Einträge zeigte sich: Der VBB-Feed kennt pro Haltestelle genau **drei Muster** (Ankunfts-/Abfahrtsverspätung):

| Muster | Anzahl | Bedeutung |
|---|---|---|
| `0 / X` | 10.048 | Die **Abfahrt wurde gemeldet** – das ist ein echter Messpunkt |
| `X / X` | 19.576 | Der Wert vom letzten Messpunkt wird nur **weitergereicht** (Prognose für die restliche Strecke) |
| `0 / 0` | 125.562 | **Keine Information** |

Wichtigste Konsequenz: **`0` heißt im Feed meistens nicht „pünktlich“, sondern „weiß ich nicht“.** Hätte man einfach alle Werte gemittelt, wäre Bus 16 viel pünktlicher erschienen, als er ist, und die Prognosen hätten die Messungen kopiert. Deshalb zählen in der Analyse **nur die Messpunkte**. Preis dafür: Eine Abfahrt mit exakt 0 Sekunden Verspätung sieht aus wie „keine Info“. Man sieht also, wie eine Verspätung schrumpft, aber nicht sicher, wann sie ganz auf 0 fällt.

Weitere Regeln:
- **Eine Fahrt** = Betriebstag + `trip_id`. Die `trip_id`s wiederholen sich täglich, und der Betriebstag endet um 3 Uhr nachts. Sieht man dieselbe Fahrt in mehreren Snapshots, gilt der neueste Wert. Eine Prognose überschreibt aber nie eine Messung.
- **Unplausibel** (verworfen, 43 Punkte): mehr als 25 Min zu spät oder mehr als 5 Min zu früh. Typischer Fall: Ein Bus fährt am Start gar nicht los, und die „Verspätung“ wächst dann auf 40 Minuten. Das ist ein Ausfall, keine Kaskade.

### Die Definition

> **Kaskade** = mindestens **3 aufeinanderfolgende Messpunkte** einer Fahrt, an denen die Verspätung **spürbar** ist (mindestens 1 Minute) und gegenüber dem vorigen Messpunkt **nicht kleiner** wird (Toleranz 30 Sekunden).
> **Entstehungsort** = eine Haltestelle, an der die Verspätung gegenüber dem vorigen Messpunkt um mindestens 1 Minute **wächst**.

Warum diese Zahlen:
- **1 Minute** ist die Auflösung, in der Fahrgäste und Fahrpläne denken.
- **30 Sekunden Toleranz** fängt Rundung und Ungenauigkeit der Ortung ab.
- **3 Punkte**, weil bei zweien noch Zufall sein kann. Ab drei hält die Verspätung über eine Strecke an.

Alle Schwellen stehen oben im Skript und lassen sich zum Testen verschieben (Sensitivitätsprüfung für Phase 4).

> **Update aus Phase 4:** Die Schwellen wurden auf **2 Minuten spürbar / 75 s Toleranz / Zuwachs ab 90 s** angehoben, weil der Feed in Ein-Minuten-Schritten rauscht (siehe unten). Die Zahlen in diesem Abschnitt stammen noch von der ersten Version (60/30/60). Mit den neuen Schwellen haben **32 %** statt 41 % der Fahrten eine Kaskade.

### Erste Zahlen

| | |
|---|---|
| Fahrten mit mindestens 1 Messpunkt | 2.182 (84 %) |
| Fahrten mit mindestens 2 Messpunkten (nur hier ist ein **Verlauf** sichtbar) | 1.661 (64 %) |
| Messpunkte pro Fahrt (Median) | 3 |
| **Fahrten mit Kaskade** | **683 = 41 % der Fahrten mit Verlauf** |
| Zuwachs innerhalb einer Kaskade (Median) | 167 s ≈ 2¾ min |

Häufigste **Startpunkte** von Kaskaden: Stadthalle Puschkinpromenade (115), Stadtverwaltung (84), Stadthalle Post (80), Welzower Str./Thiemstr. (69), BTU / Campus Sachsendorf Nord (69), BTU / Mensa (48). Die Innenstadt um die Stadthalle sticht also klar heraus.

Wo die Verspätung am häufigsten **wächst** (gegenüber dem vorigen Messpunkt):

| Haltestelle | wächst | schrumpft | Messpaare |
|---|---|---|---|
| Finsterwalder Str. | 346 | 6 | 451 |
| Spreewaldbahnhof | 309 | 19 | 433 |
| Hauptbahnhof (Richtung A) | 176 | 33 | 263 |
| Welzower Str./Thiemstr. | 175 | 35 | 297 |
| Hauptbahnhof (Richtung B) | 169 | 152 | 415 |
| Ausbesserungswerk | 169 | 28 | 275 |

### Was man ehrlich dazusagen muss (für Phase 4)

1. **Verdächtig gleichmäßig:** An Finsterwalder Str. und Spreewaldbahnhof wächst die Verspätung meist um **genau etwa eine Minute** (Median +65 s bzw. +62 s, mittlere Hälfte 55–75 s). In beiden Fällen kommt der Bus fast immer direkt vom Hauptbahnhof. Ein echter Stau würde breiter streuen. Laut Fahrplan sind für Hauptbahnhof → Finsterwalder Str. 2 Minuten eingeplant. Zwei Erklärungen sind möglich: Entweder ist die Fahrzeit dort systematisch eine Minute zu knapp (das wäre ein echter, sehr konkreter Befund), oder es ist ein Mess-Effekt. Dann würde etwa die Abfahrt am Hauptbahnhof anders erfasst als an normalen Haltestellen. **Muss in Phase 4 geklärt werden**, bevor daraus ein Ergebnis wird.
2. **Grobe Abtastung:** Bei 30 Minuten zwischen zwei Snapshots erwischt man jede Fahrt nur ein- bis zweimal. Daher kommt der Median von nur 3 Messpunkten pro Fahrt, und die **Endverspätung** fehlt oft. Für Phase 5/6 („Puffer X senkt die Endverspätung um Z %“) wäre ein dichterer Takt deutlich besser. Kostenlos ginge das, wenn das Repo **öffentlich** wäre, denn öffentliche Repos haben bei GitHub Actions keine Minutengrenze. Mehr als die öffentlichen VBB-Daten steht nicht drin, der Zugangsschlüssel liegt nur bei cron-job.org. Das ist eine Entscheidung für das Team.
3. **Tage mit wenig Fahrten:** 03.10. (Tag der Deutschen Einheit) und 31.10. (Reformationstag, in Brandenburg Feiertag) sind durch Feiertage erklärt. Am **02.11. (Montag)** gab es nur 37 statt üblicher ~76 Fahrten im Feed, das ist ungeklärt. Das Skript listet solche Tage automatisch auf, damit sie in Phase 4 gesondert behandelt werden können.
4. **Bus statt Tram:** Wie schon bei der Linienwahl gilt: Verspätungen mischen sich mit dem allgemeinen Autoverkehr. Ein Puffer im Fahrplan hilft gegen beides, aber die *Ursache* lässt sich nicht allein aus diesen Daten trennen.

## Phase 4 – Explorative Analyse (11.11.2026)

Skript: `phase4_analyse.py` (Ausgabe auch in `data/phase4_ergebnisse.txt`). Datengrundlage wie Phase 3.

### Ein-Minuten-Sprünge: das Rätsel vom Hauptbahnhof ist größtenteils Rauschen

Ausgezählt wurde, um wie viel sich die Verspätung zwischen zwei Messpunkten ändert:

| Sprung | Anteil |
|---|---|
| ±0 | 32 % |
| **genau +1 min** | **31 %** |
| **genau −1 min** | **19 %** |
| ±30 s | 1 % |
| ≥ +90 s | 7 % |

Echte Verkehrseffekte würden gleichmäßig streuen, auch über ±30 s. Hier sind aber **die Hälfte aller Änderungen exakt eine Minute**, und ±30 s kommt fast nie vor. Ein vollständiger Live-Abruf (11.11., mit allen Feldern) zeigt den Grund. Der Feed schreibt an einem Messpunkt die Ankunft als *pünktlich nach Plan* und nur die Abfahrt mit Verspätung. Die Plan-Zeiten haben nur ganze Minuten, also hüpft die Verspätung um ganze Minuten, sobald der Fahrplan und die wirkliche Fahrzeit um Sekunden auseinanderliegen. Ein Beispiel aus dem Abruf: 254 → 194 → 319 → 259 → 322 Sekunden. Das ist ein Zickzack um ±60 s, kein echtes Auf und Ab.

**Folgen:**
- Ein Sprung um genau eine Minute gilt ab jetzt als Rauschen. Die Schwellen in `phase3_kaskaden.py` wurden angehoben: spürbar ab 2 min, Toleranz 75 s, Zuwachs ab 90 s.
- Die „verdächtig gleichmäßigen +1 min“ an Finsterwalder Str. und Spreewaldbahnhof aus Phase 3 waren **überwiegend dieses Rauschen**. An Finsterwalder Str. bleiben von 346 Zuwächsen nur **96** echte (über 90 s) übrig.

### Wie stark hängt das Ergebnis an der Definition?

| Schwellen (spürbar / Toleranz / Mindestlänge) | Fahrten mit Kaskade | häufigster Start |
|---|---|---|
| 60 s / 30 s / 3 (Phase-3-Version) | 41 % | Stadthalle Puschkinpromenade |
| 60 s / 75 s / 3 | 57 % | Stadthalle Puschkinpromenade |
| **120 s / 75 s / 3 (gewählt)** | **32 %** | **Stadthalle Puschkinpromenade** |
| 180 s / 75 s / 3 | 19 % | Hauptbahnhof |
| 120 s / 75 s / 4 | 21 % | Stadthalle Puschkinpromenade |

**Lesart:** *Wie oft* es Kaskaden gibt, hängt stark an der Definition (19–57 %). Eine Prozentzahl darf deshalb nie ohne die Definition daneben genannt werden. *Wo* sie beginnen, ist dagegen stabil. Das ist die belastbare Aussage.

### Ergebnis 1: Viele Busse sind schon am Start zu spät

Stadthalle Puschkinpromenade ist die **Starthaltestelle** Richtung Uhlandstr. Kaskaden, die dort beginnen, heißen also: Der Bus fährt schon verspätet los. Vermutlich kommt die Verspätung von der vorigen Fahrt mit, weil die Wendezeit nicht reicht. Bei den Fahrten, deren Abfahrt am Start gemessen wurde, waren **46 %** (Richtung Uhlandstr., 291 Fahrten) bzw. **42 %** (Richtung Stadthalle, 73 Fahrten) mindestens 2 min zu spät.
⚠️ Diese Prozentzahl ist **zu hoch geschätzt**: Eine pünktliche Abfahrt (genau 0) ist im Feed nicht von „keine Info“ zu unterscheiden und fehlt deshalb in der Zählung. Die Aussage „ein erheblicher Teil fährt verspätet los“ hält, die genaue Zahl nicht.

### Ergebnis 2: Der kritische Abschnitt ist der Hauptbahnhof, in beide Richtungen

Wo die Verspätung um mehr als 90 s wächst (also echte Zuwächse, kein Rauschen):

| Richtung | Haltestelle (Zuwachs gegenüber dem Messpunkt davor) | wächst | schrumpft | von |
|---|---|---|---|---|
| → Stadthalle | Spreewaldbahnhof (direkt nach Hbf) | 122 | 1 | 433 |
| → Uhlandstr. | Finsterwalder Str. (direkt nach Hbf) | 96 | 2 | 451 |
| → Uhlandstr. | Hauptbahnhof | 79 | 7 | 415 |
| → Stadthalle | Hauptbahnhof | 63 | 2 | 263 |
| → Stadthalle | Welzower Str./Thiemstr. | 51 | 2 | 297 |
| → Stadthalle | BTU / Campus Sachsendorf (Nord) | 45 | 3 | 161 |

Die vier größten Zuwachs-Stellen liegen alle **am oder direkt nach dem Hauptbahnhof**. Im Fahrplan (GTFS) hat der Bus dort **0 Minuten Haltezeit**. Das ist eine naheliegende Erklärung, denn am Bahnhof steigen viele Leute mit Gepäck ein und aus, und eventuell wartet der Bus auf Züge. Bestätigt ist das noch nicht, siehe „Nächste Schritte“.

**Abbau** passiert dagegen kaum: Die Stelle mit dem stärksten Rückgang schafft das nur 10–12-mal (Stadthalle Post, Welzower Str./Klinikum, Waldweg). Wer einmal verspätet ist, bleibt es also bis zum Ende. Genau das ist das Kaskaden-Verhalten aus der Fragestellung.

### Ergebnis 3: Die Tageszeit passt zum Verkehr

Anteil der Fahrten mit Kaskade (Fahrten mit Verlauf):

| | 04–07 | 07–09 | 09–13 | 13–16 | 16–19 | 19–24 |
|---|---|---|---|---|---|---|
| Mo–Fr | 24 % | **37 %** | 29 % | **40 %** | **39 %** | 25 % |
| Sa/So | (n=3) | 24 % | 19 % | 25 % | 27 % | 21 % |

Im Berufs- und Schulverkehr gibt es deutlich mehr Kaskaden als abends und am Wochenende. Das spricht dafür, dass nach dem Herausfiltern des Rauschens ein **echtes Verkehrssignal** übrig bleibt.

### Sammelskript verbessert (Phase 4)

Zwei Unschärfen ließen sich in den alten Daten nicht mehr reparieren: (a) ist eine 0 pünktlich oder fehlt sie, und (b) welche Haltestellen hatte der Bus beim Snapshot schon passiert? Der Feed liefert beides mit, `collect_delays.py` hat es nur nicht gespeichert. Seit Phase 4 speichert das Skript zusätzlich `arrival_time`, `departure_time`, ob die Verspätung wirklich gesetzt war (`*_delay_gesetzt`), `start_date` und `update_timestamp`. Die alten Felder bleiben gleich, alle Auswertungen laufen weiter. Probelauf am 11.11. gegen den Live-Feed war erfolgreich. **Wirkt erst, wenn die Änderung auf GitHub gepusht ist.**

### Nächste Schritte

1. Änderung pushen, dann **2–3 Wochen** mit den neuen Feldern sammeln. Damit lassen sich echte Pünktlichkeit und tatsächliche Haltezeit am Hauptbahnhof direkt messen (Abfahrt minus Ankunft).
2. Dichteren Takt prüfen. Bei einem öffentlichen Repo hat GitHub Actions keine Minutengrenze, dann ginge wieder alle 5 statt alle 30 Minuten. Mehr Messpunkte pro Fahrt heißt: Die Endverspätung wird sichtbar.
3. **Phase 5** kann mit dem Hauptbahnhof als Kandidat anfangen: Was ändert sich an der Endverspätung, wenn dort 1 oder 2 Minuten Haltezeit eingeplant werden?

### Repo öffentlich (11.11.2026)

Damit ein dichterer Takt kostenlos möglich ist, ist das Repo seit dem 11.11. **öffentlich**, denn öffentliche Repos haben bei GitHub Actions keine Minutengrenze. Vorher wurde geprüft, dass keine Zugangsschlüssel in der Historie stehen. Das Token für cron-job.org lebt nur dort. Private E-Mail-Adressen in alten Commits wurden per `git filter-repo --mailmap` durch die anonyme GitHub-Adresse ersetzt. Inhalt und Commit-Anzahl sind unverändert, nur die Commit-IDs sind neu.

**Takt:** Der Takt wird in cron-job.org eingestellt (nicht in `collect.yml`). Er kann jetzt wieder auf **5 Minuten**. Speicherbedarf grob: heute etwa 0,5 MB pro Tag bei 30 Minuten; mit 5-Minuten-Takt und den neuen Feldern werden es etwa 4–5 MB pro Tag, also rund 150 MB im Monat im Git-Repo. Für die restliche Projektlaufzeit ist das unkritisch. Nach Projektende den Zeitgeber abschalten.
