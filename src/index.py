#!/usr/bin/env python3
"""
MCP-Server für die Schul-Datenbank (schule.db)

Dieser Server bietet über das Model Context Protocol (MCP) Werkzeuge an.
Er weiß nichts über KI. Er wartet nur auf Anfragen und beantwortet sie.

    Wer spricht mit diesem Server?            Wie?
    ─────────────────────────────────────────────────────────────────
    Claude Desktop          (Teil 1, 1b)      stdio  (startet den Server selbst)
    unser eigener Harness   (Teil 2)          stdio  (agenten/harness/mcp_bruecke.py)
    n8n im Docker-Container (Teil 2, Kap. 6)  HTTP   (python src/index.py --http)

Ein MCP-Server kann zwei Arten von Dingen anbieten:

    TOOLS       Funktionen, die ein Client aufrufen kann       (MCP: tools/list, tools/call)
    RESSOURCEN  Inhalte, die ein Client lesen kann, z. B.      (MCP: resources/list, resources/read)
                HTML-Seiten für MCP Apps

Aufbau dieser Datei:
    1. Grundlagen: Server und Datenbankverbindung
    2. Lesende Tools                      (Teil 1)
    3. Schreibendes Tool add_grade        (Teil 2: Freigabe durch den Menschen)
    4. MCP Apps: Tools mit Oberfläche     (Teil 1b)
    5. Start: stdio oder HTTP
"""

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP, UI_MIME_TYPE


# =====================================================================
# 1. GRUNDLAGEN
# =====================================================================

DB_PATH = Path(__file__).parent.parent / "schule.db"

# Das ist der MCP-Server. Der Name erscheint z. B. in Claude Desktop.
mcp = FastMCP("SQLite Schul-Datenbank")


def get_db_connection():
    """Öffnet eine Verbindung zur Datenbank.

    Jedes Tool öffnet eine eigene Verbindung und schließt sie danach wieder.
    So blockiert der Server die Datei nicht für andere Programme.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Zeilen wie ein Dictionary benutzen: zeile["nachname"]
    return conn


# =====================================================================
# 2. LESENDE TOOLS (Teil 1)
#
# So wird aus einer Python-Funktion ein MCP-Tool:
#
#   @mcp.tool()                         ← "Biete diese Funktion als Tool an"
#   def query_database(query: str):     ← Funktionsname  = Name des Tools
#                                         Typangabe str  = Parameter-Beschreibung für das LLM
#       """Führt eine SQL ..."""        ← Docstring      = Beschreibung, die das LLM liest!
#
# Das LLM sieht NUR Name, Docstring und Parameter, niemals den Code darunter.
# Ein guter Docstring ist deshalb genauso wichtig wie guter Code.
# =====================================================================

@mcp.tool()
def query_database(query: str) -> str:
    """Führt eine SQL SELECT-Abfrage auf der Schul-Datenbank aus.

    Args:
        query: Die SQL SELECT-Abfrage, die ausgeführt werden soll (z.B. 'SELECT * FROM schueler')

    Returns:
        JSON-formatierte Ergebnisse der Abfrage
    """
    try:
        # Sicherheitscheck: Nur SELECT-Abfragen erlauben.
        # Dieser Schutz liegt im SERVER. Er gilt also für jeden Client, egal ob
        # Claude Desktop, unser Harness oder n8n.
        if not query.strip().upper().startswith("SELECT"):
            return "Fehler: Nur SELECT-Abfragen sind erlaubt!"

        conn = get_db_connection()
        rows = conn.execute(query).fetchall()
        conn.close()

        # Antwort als JSON-Text: [{"spalte": wert, ...}, ...]
        results = [dict(row) for row in rows]
        return json.dumps(results, indent=2, ensure_ascii=False)

    except Exception as e:
        # Fehler werden als Text zurückgegeben. So kann das LLM sie lesen
        # und z. B. seine SQL-Abfrage verbessern.
        return f"Fehler: {str(e)}"


@mcp.tool()
def list_tables() -> str:
    """Listet alle Tabellen in der Datenbank auf.

    Returns:
        JSON-formatierte Liste aller Tabellennamen
    """
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        conn.close()

        results = [dict(row) for row in rows]
        return json.dumps(results, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Fehler: {str(e)}"


@mcp.tool()
def describe_table(table_name: str) -> str:
    """Zeigt die Struktur einer Tabelle (Spalten und Datentypen).

    Args:
        table_name: Der Name der Tabelle, die beschrieben werden soll

    Returns:
        JSON-formatierte Tabellenstruktur mit Spalteninformationen
    """
    try:
        conn = get_db_connection()
        # Achtung: Hier wird der Tabellenname direkt in die SQL eingesetzt, weil
        # PRAGMA keine ?-Platzhalter erlaubt. Bei anderen Befehlen wäre das eine
        # Lücke für SQL-Injection. PRAGMA table_info kann aber nur lesen.
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        conn.close()

        results = [dict(row) for row in rows]
        return json.dumps(results, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Fehler: {str(e)}"


# =====================================================================
# 3. SCHREIBENDES TOOL (Teil 2)
#
# add_grade verändert die Datenbank. Der Server kann nicht erkennen, ob ein
# Mensch zugestimmt hat. Die Freigabe muss deshalb der HARNESS einholen:
#   - Claude Desktop fragt "Erlauben?"
#   - unser Harness fragt bei 'tools_mit_freigabe'
#   - n8n zeigt in Workflow C eine Freigabe-Seite
# Der Server prüft nur, ob die Werte gültig sind.
# =====================================================================

@mcp.tool()
def add_grade(schueler_id: int, kurs_id: int, note: float, art: str = "mündlich") -> str:
    """SCHREIBENDES Tool: Trägt eine neue Note in die Datenbank ein.

    Achtung: Dieses Tool verändert Daten! Ein guter Harness sollte vor dem
    Aufruf die Freigabe eines Menschen einholen (Human-in-the-Loop).

    Args:
        schueler_id: id des Schülers aus der Tabelle schueler
        kurs_id: id des Kurses aus der Tabelle kurse (Kurs muss zur Klasse des Schülers passen)
        note: Note zwischen 1.0 und 6.0
        art: 'mündlich' oder 'Schulaufgabe'

    Returns:
        Bestätigung mit der id der neuen Note oder eine Fehlermeldung
    """
    return note_in_datenbank_schreiben(schueler_id, kurs_id, note, art)


def note_in_datenbank_schreiben(schueler_id: int, kurs_id: int, note: float, art: str) -> str:
    """Prüft die Werte und schreibt eine Note in die Datenbank.

    Das ist KEIN Tool (kein @mcp.tool davor), sondern eine normale Hilfsfunktion.
    Zwei Tools benutzen sie gemeinsam: add_grade (Teil 2) und note_freigeben
    (Teil 1b). So gelten für beide Wege genau dieselben Prüfungen.
    """
    try:
        # Prüfung 1: gültige Werte?
        if not 1.0 <= note <= 6.0:
            return "Fehler: Die Note muss zwischen 1.0 und 6.0 liegen."
        if art not in ("mündlich", "Schulaufgabe"):
            return "Fehler: art muss 'mündlich' oder 'Schulaufgabe' sein."

        conn = get_db_connection()

        # Prüfung 2: Gibt es Schüler und Kurs, und passt der Kurs zur Klasse?
        schueler = conn.execute("SELECT klasse FROM schueler WHERE id = ?", (schueler_id,)).fetchone()
        kurs = conn.execute("SELECT klasse FROM kurse WHERE id = ?", (kurs_id,)).fetchone()
        if schueler is None or kurs is None:
            conn.close()
            return "Fehler: Schüler oder Kurs existiert nicht."
        if schueler["klasse"] != kurs["klasse"]:
            conn.close()
            return "Fehler: Der Kurs gehört nicht zur Klasse des Schülers."

        # Schreiben. Die ? sind Platzhalter: SQLite setzt die Werte sicher ein,
        # so ist keine SQL-Injection möglich.
        cursor = conn.execute(
            "INSERT INTO noten (schueler_id, kurs_id, note, datum, art) VALUES (?, ?, ?, ?, ?)",
            (schueler_id, kurs_id, note, date.today().isoformat(), art),
        )
        conn.commit()  # erst jetzt ist die Änderung wirklich gespeichert
        neue_id = cursor.lastrowid
        conn.close()
        return f"OK: Note {note} ({art}) für Schüler {schueler_id} in Kurs {kurs_id} eingetragen (noten.id = {neue_id})."

    except Exception as e:
        return f"Fehler: {str(e)}"


# =====================================================================
# 4. MCP APPS: Tools mit eigener Oberfläche (Teil 1b, siehe docs/mcp-apps.md)
#
# Eine MCP-App besteht aus zwei Teilen:
#   a) einer RESSOURCE: eine HTML-Seite unter einer Adresse mit ui://
#   b) einem TOOL, das auf diese Ressource zeigt: AppConfig(resource_uri="ui://...")
#
# Ablauf in Claude Desktop:
#   1. Das LLM ruft das Tool auf (z. B. notenuebersicht).
#   2. Der Host holt die HTML-Seite (resources/read) und zeigt sie im Chat an.
#   3. Der Host gibt der Seite das Ergebnis des Tools.
#   4. Klickt der Mensch in der Seite, kann sie selbst Tools aufrufen,
#      ohne dass das LLM gefragt wird.
#
# Die HTML-Seiten liegen in src/apps/. Wer dort nachsieht, findet dieselben
# Tool-Namen wieder (z. B. callServerTool({ name: "notenuebersicht", ... })).
# =====================================================================

APPS_ORDNER = Path(__file__).parent / "apps"

# Die HTML-Seiten laden eine JavaScript-Bibliothek für die Verbindung zum Host
# von https://cdn.jsdelivr.net. Das muss der Server ausdrücklich erlauben
# (CSP = Content Security Policy). Ohne diese Angabe blockiert der Host das Skript.
APP_SICHERHEIT = AppConfig(csp=ResourceCSP(resource_domains=["https://cdn.jsdelivr.net"]))


# ---------- a) Die Ressourcen: HTML-Seiten ----------
# mime_type=UI_MIME_TYPE ("text/html;profile=mcp-app") sagt dem Host:
# "Das ist die Oberfläche einer MCP-App, bitte im Chat anzeigen."

@mcp.resource("ui://schule/notenuebersicht.html", mime_type=UI_MIME_TYPE, app=APP_SICHERHEIT)
def notenuebersicht_seite() -> str:
    """HTML-Seite der App 'Notenübersicht'."""
    return (APPS_ORDNER / "notenuebersicht.html").read_text(encoding="utf-8")


@mcp.resource("ui://schule/notenfreigabe.html", mime_type=UI_MIME_TYPE, app=APP_SICHERHEIT)
def notenfreigabe_seite() -> str:
    """HTML-Seite der App 'Notenfreigabe'."""
    return (APPS_ORDNER / "notenfreigabe.html").read_text(encoding="utf-8")


# ---------- b) Die Tools, die auf die Seiten zeigen ----------
# Diese Tools geben ein Dictionary zurück statt Text. Daraus macht FastMCP
#   - JSON-Text für das LLM          (content)
#   - ein fertiges Objekt für die App (structuredContent)
# Beide enthalten dieselben Daten.

@mcp.tool(app=AppConfig(resource_uri="ui://schule/notenuebersicht.html"))
def notenuebersicht(klasse: str, fach: str) -> dict:
    """Zeigt eine interaktive Notenübersicht für eine Klasse in einem Fach
    (Notenverteilung und Durchschnitt jedes Schülers).

    Args:
        klasse: z. B. '7a'
        fach: z. B. 'Mathematik'
    """
    # Wer ruft dieses Tool auf?
    #   - das LLM, wenn jemand im Chat nach einer Übersicht fragt
    #   - die App selbst, wenn der Mensch dort Klasse oder Fach wechselt
    conn = get_db_connection()

    # Jeder Schüler der Klasse mit Anzahl und Durchschnitt seiner Noten im Fach
    schueler = conn.execute(
        """SELECT s.vorname, s.nachname,
                  COUNT(n.id)            AS anzahl,
                  ROUND(AVG(n.note), 2)  AS durchschnitt
           FROM schueler s
           JOIN kurse k      ON k.klasse = s.klasse AND k.fach = ?
           LEFT JOIN noten n ON n.schueler_id = s.id AND n.kurs_id = k.id
           WHERE s.klasse = ?
           GROUP BY s.id
           ORDER BY durchschnitt""",
        (fach, klasse),
    ).fetchall()

    # Notenverteilung: Wie viele Noten liegen (gerundet) bei 1, 2, ... 6?
    stufen = conn.execute(
        """SELECT CAST(ROUND(n.note) AS INTEGER) AS stufe, COUNT(*) AS anzahl
           FROM noten n JOIN kurse k ON k.id = n.kurs_id
           WHERE k.klasse = ? AND k.fach = ?
           GROUP BY stufe""",
        (klasse, fach),
    ).fetchall()

    # Alle Klassen und Fächer für die Auswahllisten in der Oberfläche
    klassen = [zeile["klasse"] for zeile in conn.execute("SELECT DISTINCT klasse FROM kurse")]
    faecher = [zeile["fach"] for zeile in conn.execute("SELECT DISTINCT fach FROM kurse")]
    conn.close()

    # Jede Notenstufe soll im Diagramm vorkommen, auch wenn es 0 Noten gibt
    verteilung = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0}
    for zeile in stufen:
        verteilung[str(zeile["stufe"])] = zeile["anzahl"]

    # Sinnvoll sortieren: 5a, 5b, 6a ... 10b (statt 10a, 10b, 5a ...)
    klassen.sort(key=lambda k: (int(k[:-1]), k[-1]))

    return {
        "klasse": klasse,
        "fach": fach,
        "schueler": [dict(zeile) for zeile in schueler],
        "verteilung": verteilung,
        "klassen": klassen,
        "faecher": faecher,
    }


@mcp.tool(app=AppConfig(resource_uri="ui://schule/notenfreigabe.html"))
def note_vorschlagen(klasse: str, nachname: str, fach: str, note: float, art: str = "mündlich") -> dict:
    """Schlägt eine neue Note vor. Trägt NICHTS ein!

    Zeigt dem Menschen eine Freigabe-Oberfläche mit Namen und Fach. Erst wenn
    der Mensch dort auf 'Eintragen' klickt, wird die Note gespeichert.
    Benutze dieses Tool, wenn jemand eine Note eintragen möchte.

    Args:
        klasse: z. B. '7a'
        nachname: Nachname des Schülers
        fach: z. B. 'Mathematik'
        note: Note zwischen 1.0 und 6.0
        art: 'mündlich' oder 'Schulaufgabe'
    """
    # Wer ruft dieses Tool auf? Das LLM.
    # Es liest nur. Es sucht alle passenden Schüler und den Kurs heraus, damit
    # die Oberfläche Namen statt ids zeigen kann. Bei mehreren Treffern wählt
    # später der Mensch in der Oberfläche aus.
    conn = get_db_connection()
    kandidaten = conn.execute(
        """SELECT s.id AS schueler_id, s.vorname, s.nachname, k.id AS kurs_id
           FROM schueler s
           JOIN kurse k ON k.klasse = s.klasse AND k.fach = ?
           WHERE s.klasse = ? AND s.nachname = ?""",
        (fach, klasse, nachname.strip()),
    ).fetchall()
    conn.close()

    return {
        "klasse": klasse,
        "fach": fach,
        "note": note,
        "art": art,
        "kandidaten": [dict(zeile) for zeile in kandidaten],
        # Dieser Satz ist für das LLM gedacht: Es soll nicht behaupten, die Note sei schon eingetragen.
        "hinweis": "Nur ein Vorschlag. Der Mensch entscheidet in der Oberfläche, ob die Note eingetragen wird.",
    }


# visibility=["app"]: Dieses Tool ist nur für die Oberfläche gedacht. Der Host
# zeigt es dem LLM nicht an. Das LLM kann die Freigabe also nicht umgehen.
# ACHTUNG: Das ist eine Absprache, keine Sicherheit! Wer direkt mit dem Server
# spricht (z. B. agenten/minimal_agent.py), sieht und benutzt es trotzdem.
@mcp.tool(app=AppConfig(resource_uri="ui://schule/notenfreigabe.html", visibility=["app"]))
def note_freigeben(schueler_id: int, kurs_id: int, note: float, art: str) -> str:
    """Trägt eine vom Menschen freigegebene Note ein (wird von der Oberfläche aufgerufen)."""
    # Wer ruft dieses Tool auf? Die App, wenn der Mensch auf "Ja, eintragen" klickt.
    return note_in_datenbank_schreiben(schueler_id, kurs_id, note, art)


# =====================================================================
# 5. START
#
#   python src/index.py          → stdio: Der Client startet den Server selbst
#                                  und spricht über stdin/stdout mit ihm.
#                                  (Claude Desktop, unser Harness)
#   python src/index.py --http   → HTTP: Der Server läuft selbstständig und
#                                  wartet auf http://<rechner>:8000/mcp
#                                  (n8n, andere Rechner im Netz)
# =====================================================================

if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="http", host="0.0.0.0", port=8000)
    else:
        mcp.run(transport="stdio")
