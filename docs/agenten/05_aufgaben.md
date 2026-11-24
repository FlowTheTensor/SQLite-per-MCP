# 5 · Aufgaben

Die Aufgaben bauen aufeinander auf. Alle Befehle werden im Projektordner mit aktivierter venv ausgeführt.
Aufgaben mit 🧠 brauchen ein echtes LLM (`--modell anthropic` oder `--modell ollama`), alle anderen funktionieren mit `--modell mensch`.

---

## Phase A · Unplugged-Rollenspiel „Wer macht was?“ (ohne Computer)

Bildet Vierergruppen. Jede Person bekommt eine Rolle und **darf nur das tun, was ihre Rolle erlaubt**:

| Rolle | Darf | Darf nicht |
|---|---|---|
| **Mensch** | Auftrag auf einen Zettel schreiben, Freigaben erteilen | mit dem LLM direkt reden |
| **Harness** | Zettel weitergeben, Regeln prüfen, Protokoll führen | selbst entscheiden, was getan wird |
| **LLM** | auf Zettel antworten: Text **oder** „Tool X mit Y bitte“ | selbst in die Datenbank schauen, sich etwas merken (jeder Zettel wird nach dem Lesen umgedreht!) |
| **MCP-Server** | eine ausgedruckte Tabelle lesen und Ergebnisse aufschreiben | etwas anderes als `SELECT` ausführen |

Auftrag des Menschen: *„Wie viele Schüler hat die Klasse 7a?“*

**Auswertung:**
1. Wie oft ging ein Zettel zum LLM? Warum musste der Harness alte Zettel immer wieder mitgeben?
2. Wer hätte verhindern können, dass das LLM „Lösche alle Noten“ ausführt?

---

## Phase B · Du bist das LLM

```powershell
python agenten/minimal_agent.py mensch "Wie viele Lehrer unterrichten Informatik?"
```

Du siehst jetzt genau, was ein LLM sieht. Antworte z. B. mit:

```
tool describe_table {"table_name": "lehrer"}
tool query_database {"query": "SELECT COUNT(*) FROM lehrer WHERE fach1='Informatik' OR fach2='Informatik'"}
Vier Lehrkräfte unterrichten Informatik.
```

1. Welche drei Teile bekommst du bei jedem Schritt angezeigt?
2. Das LLM „sieht“ die Datenbank nie direkt. Woher weißt du, welche Spalten es gibt?
3. Antworte als LLM mit `tool add_grade {"schueler_id": 1, "kurs_id": 1, "note": 6.0}`. Was passiert? **Warum ist das beim Minimal-Agenten ein Problem?**

---

## Phase C · Harness untersuchen

Starte denselben Versuch mit dem vollständigen Harness:

```powershell
python agenten/agent.py --agent datenbank-analyst --modell mensch "Wie viele Lehrer unterrichten Informatik?"
```

1. Welche Tools bietet der Harness dem LLM jetzt an? Welches fehlt – und warum?
2. Versuche trotzdem `tool add_grade {...}`. Notiere die Zeile aus dem Protokoll.
3. Versuche `tool query_database {"query": "DELETE FROM noten"}`. Welche Schutzschicht greift hier – Harness oder MCP-Server?
4. Öffne die neueste Datei in `agenten/protokolle/`. Finde den vollständigen System-Prompt. Welcher Teil stammt aus der Definitionsdatei, welcher wurde vom Harness ergänzt?
5. Fülle die Tabelle aus *Kapitel 2* („Aufgaben des Harness“) aus, indem du die Funktionen in `harness/harness.py` suchst.

---

## Phase D · Mensch-Maschine-Schnittstellen erleben

```powershell
python agenten/agent.py --agent notenverwalter --modell mensch "Trage für Werner aus der 7a eine mündliche 2 in Mathe ein."
```

1. Spiele das LLM so, dass es zuerst mit `frage_mensch` nachfragt. Welche Schnittstelle (S0–S5) ist das?
2. Rufe `add_grade` auf und **verweigere** die Freigabe mit einer Begründung. Was bekommt das LLM als Ergebnis zurück?
3. Starte erneut mit `--alles-erlauben`. Welche Autonomiestufe ist das jetzt? Was hat sich verändert?
4. 🧠 Führe den Auftrag mit einem echten LLM aus. Stellt es eine Rückfrage? Ist die Freigabe-Meldung für dich verständlich genug, um verantwortungsvoll „j“ zu drücken?

---

## Phase E · Multiagentensystem 🧠

```powershell
python agenten/agent.py --agent koordinator --modell anthropic "Schreibe eine kurze Zwischenstand-Rückmeldung für die Klasse 10a in Informatik, die ich vor der nächsten Schulaufgabe an alle verschicken kann."
```

1. Zeichne ein Sequenzdiagramm: Welcher Agent wurde wann von wem beauftragt?
2. Lies die Aufträge, die der Koordinator an die Unteragenten geschickt hat. Sind sie vollständig, sodass man sie **ohne Vorwissen** verstehen kann?
3. Hat der Prüfer etwas korrigiert? Wenn nicht: Wie könntet ihr testen, ob er überhaupt funktioniert?
4. Vergleiche die Token-Tabelle am Ende mit einem Lauf von `datenbank-analyst` allein. Um welchen Faktor war das Team teurer?
5. Enthält die Rückmeldung an die Klasse Namen oder Einzelnoten von Schülern? Welche Zeile in welcher Definitionsdatei sorgt dafür?

> Ohne API-Key: Ihr könnt das Team auch mit `--modell mensch` spielen. Dann übernehmt ihr nacheinander die Rolle *jedes* Agenten – ihr merkt dabei sehr deutlich, dass jeder Agent nur seinen eigenen Kontext sieht.

---

## Phase F · Eigene Agenten definieren

1. **Neuer Spezialist:** Lege `agenten/definitionen/statistiker.md` an. Er soll nur lesen dürfen und Notenverteilungen (wie viele 1er, 2er, …) für eine Klasse und ein Fach ermitteln. Teste ihn.
2. **Ins Team aufnehmen:** Ergänze den Koordinator so, dass er den Statistiker beauftragen kann (`delegiert_an` und Prompt).
3. **Rechte testen:** Gib einem Agenten absichtlich zu wenige Tools (z. B. nur `query_database`, ohne `describe_table`). Wie geht das LLM damit um?
4. **Prompt vs. Code:** Schreibe in den Prompt des `datenbank-analyst`: „Trage niemals Noten ein.“ und gib ihm gleichzeitig `add_grade` in `tools`. Versuche dann, ihn per Auftrag zum Eintragen zu überreden. Was lernst du daraus über Sicherheit?

---

## Phase G · Programmieren (für Fortgeschrittene)

1. **Bessere Freigabe:** Ändere `Mensch.freigabe()` so, dass statt `schueler_id: 37` der Name des Schülers und das Fach angezeigt werden. (Tipp: Der Harness kann vor der Freigabe selbst eine `SELECT`-Abfrage über `self.mcp` ausführen.)
2. **Budget:** Ergänze den Harness um ein Token-Budget: Überschreitet ein Lauf z. B. 20 000 Tokens, bricht er ab (S4).
3. **Neues Tool:** Ergänze in `src/index.py` ein Tool `average_grade(schueler_id, fach)`. Muss es freigegeben werden? Begründe.
4. **Parallele Agenten:** Ändere den Harness so, dass mehrere `delegiere_an_...`-Aufrufe in einem Schritt mit `asyncio.gather` gleichzeitig laufen.

---

## Abschluss-Reflexion

Beantworte schriftlich (je 3–5 Sätze):

1. Erkläre einer Person ohne Informatik-Kenntnisse den Unterschied zwischen **LLM**, **Agent** und **Harness**.
2. An welchen Stellen sollte ein Mensch bei einem Agenten, der in einer Schule mit echten Noten arbeitet, unbedingt eingreifen können? Begründe mit den Schnittstellen S0–S5.
3. „Mehr Agenten sind immer besser.“ Nimm Stellung.
