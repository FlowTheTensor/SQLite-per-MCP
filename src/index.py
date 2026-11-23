#!/usr/bin/env python3
"""
SQLite MCP Server - FastMCP Implementation
Ermöglicht LLMs den Zugriff auf eine SQLite-Datenbank über das Model Context Protocol
"""

import sqlite3
import json
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.apps import AppConfig, ResourceCSP, UI_MIME_TYPE

# Pfad zur Datenbank
DB_PATH = Path(__file__).parent.parent / "schule.db"

# FastMCP Server erstellen
mcp = FastMCP("SQLite Schul-Datenbank")

def get_db_connection():
    """Erstellt eine Datenbankverbindung"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Ergebnisse als Dictionary
    return conn

@mcp.tool()
def query_database(query: str) -> str:
    """Führt eine SQL SELECT-Abfrage auf der Schul-Datenbank aus.
    
    Args:
        query: Die SQL SELECT-Abfrage, die ausgeführt werden soll (z.B. 'SELECT * FROM schueler')
    
    Returns:
        JSON-formatierte Ergebnisse der Abfrage
    """
    try:
        # Sicherheitscheck: Nur SELECT-Abfragen erlauben
        if not query.strip().upper().startswith("SELECT"):
            return "Fehler: Nur SELECT-Abfragen sind erlaubt!"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        # Konvertiere Row-Objekte zu Dictionaries
        results = [dict(row) for row in rows]
        
        return json.dumps(results, indent=2, ensure_ascii=False)
    
    except Exception as e:
        return f"Fehler: {str(e)}"

@mcp.tool()
def list_tables() -> str:
    """Listet alle Tabellen in der Datenbank auf.
    
    Returns:
        JSON-formatierte Liste aller Tabellennamen
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        rows = cursor.fetchall()
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
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        conn.close()
        
        results = [dict(row) for row in rows]
        
        return json.dumps(results, indent=2, ensure_ascii=False)
    
    except Exception as e:
        return f"Fehler: {str(e)}"

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

    Keine MCP-Funktion, sondern eine normale Hilfsfunktion. Sie wird von
    add_grade und von note_freigeben (MCP-App) gemeinsam benutzt.
    """
    try:
        if not 1.0 <= note <= 6.0:
            return "Fehler: Die Note muss zwischen 1.0 und 6.0 liegen."
        if art not in ("mündlich", "Schulaufgabe"):
            return "Fehler: art muss 'mündlich' oder 'Schulaufgabe' sein."

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT klasse FROM schueler WHERE id = ?", (schueler_id,))
        schueler = cursor.fetchone()
        cursor.execute("SELECT klasse FROM kurse WHERE id = ?", (kurs_id,))
        kurs = cursor.fetchone()
        if schueler is None or kurs is None:
            conn.close()
            return "Fehler: Schüler oder Kurs existiert nicht."
        if schueler["klasse"] != kurs["klasse"]:
            conn.close()
            return "Fehler: Der Kurs gehört nicht zur Klasse des Schülers."

        from datetime import date
        cursor.execute(
            "INSERT INTO noten (schueler_id, kurs_id, note, datum, art) VALUES (?, ?, ?, ?, ?)",
            (schueler_id, kurs_id, note, date.today().isoformat(), art),
        )
        conn.commit()
        neue_id = cursor.lastrowid
        conn.close()
        return f"OK: Note {note} ({art}) für Schüler {schueler_id} in Kurs {kurs_id} eingetragen (noten.id = {neue_id})."

    except Exception as e:
        return f"Fehler: {str(e)}"


# =====================================================================
# MCP APPS – Tools mit eigener Oberfläche (siehe docs/mcp-apps.md)
#
# Eine MCP-App besteht aus zwei Teilen:
#   1. einer RESSOURCE mit einer HTML-Seite (Adresse beginnt mit ui://)
#   2. einem TOOL, das auf diese Ressource zeigt (AppConfig(resource_uri=...))
#
# Ruft das LLM das Tool auf, zeigt der Host (z. B. Claude Desktop) die
# HTML-Seite direkt im Chat an und übergibt ihr das Ergebnis des Tools.
# Die HTML-Seiten liegen im Ordner src/apps/.
# =====================================================================

APPS_ORDNER = Path(__file__).parent / "apps"

# Die HTML-Seiten laden die Bibliothek für die Verbindung zum Host von diesem
# Server. Das müssen wir dem Host erlauben (CSP = Content Security Policy).
# Ohne diese Angabe blockiert der Host das Skript.
APP_SICHERHEIT = AppConfig(csp=ResourceCSP(resource_domains=["https://cdn.jsdelivr.net"]))


@mcp.resource("ui://schule/notenuebersicht.html", mime_type=UI_MIME_TYPE, app=APP_SICHERHEIT)
def notenuebersicht_seite() -> str:
    """HTML-Seite der App 'Notenübersicht'."""
    return (APPS_ORDNER / "notenuebersicht.html").read_text(encoding="utf-8")


@mcp.resource("ui://schule/notenfreigabe.html", mime_type=UI_MIME_TYPE, app=APP_SICHERHEIT)
def notenfreigabe_seite() -> str:
    """HTML-Seite der App 'Notenfreigabe'."""
    return (APPS_ORDNER / "notenfreigabe.html").read_text(encoding="utf-8")


@mcp.tool(app=AppConfig(resource_uri="ui://schule/notenuebersicht.html"))
def notenuebersicht(klasse: str, fach: str) -> dict:
    """Zeigt eine interaktive Notenübersicht für eine Klasse in einem Fach
    (Notenverteilung und Durchschnitt jedes Schülers).

    Args:
        klasse: z. B. '7a'
        fach: z. B. 'Mathematik'
    """
    conn = get_db_connection()
    schueler = conn.execute(
        """SELECT s.vorname, s.nachname, COUNT(n.id) AS anzahl, ROUND(AVG(n.note), 2) AS durchschnitt
           FROM schueler s
           JOIN kurse k ON k.klasse = s.klasse AND k.fach = ?
           LEFT JOIN noten n ON n.schueler_id = s.id AND n.kurs_id = k.id
           WHERE s.klasse = ?
           GROUP BY s.id ORDER BY durchschnitt""",
        (fach, klasse),
    ).fetchall()
    # Notenverteilung: wie viele Noten liegen bei 1, 2, ... 6 (gerundet)?
    verteilung = conn.execute(
        """SELECT CAST(ROUND(n.note) AS INTEGER) AS stufe, COUNT(*) AS anzahl
           FROM noten n JOIN kurse k ON k.id = n.kurs_id
           WHERE k.klasse = ? AND k.fach = ? GROUP BY stufe""",
        (klasse, fach),
    ).fetchall()
    # Für die Auswahllisten in der Oberfläche
    klassen = [r[0] for r in conn.execute("SELECT DISTINCT klasse FROM kurse")]
    faecher = [r[0] for r in conn.execute("SELECT DISTINCT fach FROM kurse")]
    conn.close()

    klassen.sort(key=lambda k: (int(k[:-1]), k[-1]))  # 5a, 5b, ... 10b statt 10a, 10b, 5a
    return {
        "klasse": klasse,
        "fach": fach,
        "schueler": [dict(r) for r in schueler],
        "verteilung": {str(stufe): 0 for stufe in range(1, 7)} | {str(r["stufe"]): r["anzahl"] for r in verteilung},
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
    conn = get_db_connection()
    kandidaten = conn.execute(
        """SELECT s.id AS schueler_id, s.vorname, s.nachname, k.id AS kurs_id
           FROM schueler s JOIN kurse k ON k.klasse = s.klasse AND k.fach = ?
           WHERE s.klasse = ? AND s.nachname = ?""",
        (fach, klasse, nachname.strip()),
    ).fetchall()
    conn.close()
    return {
        "klasse": klasse,
        "fach": fach,
        "note": note,
        "art": art,
        "kandidaten": [dict(r) for r in kandidaten],
        "hinweis": "Nur ein Vorschlag. Der Mensch entscheidet in der Oberfläche, ob die Note eingetragen wird.",
    }


# visibility=["app"]: Dieses Tool ist nur für die Oberfläche gedacht. Der Host
# zeigt es dem LLM nicht an. ACHTUNG: Das ist eine Absprache, keine Sicherheit!
# Wer direkt mit dem Server spricht, kann es trotzdem aufrufen.
@mcp.tool(app=AppConfig(resource_uri="ui://schule/notenfreigabe.html", visibility=["app"]))
def note_freigeben(schueler_id: int, kurs_id: int, note: float, art: str) -> str:
    """Trägt eine vom Menschen freigegebene Note ein (wird von der Oberfläche aufgerufen)."""
    return note_in_datenbank_schreiben(schueler_id, kurs_id, note, art)


if __name__ == "__main__":
    import sys

    if "--http" in sys.argv:
        # HTTP-Modus: für n8n, Docker oder andere Clients im Netzwerk.
        # Der MCP-Endpunkt ist dann http://<rechner>:8000/mcp
        mcp.run(transport="http", host="0.0.0.0", port=8000)
    else:
        # stdio-Modus (Standard): Claude Desktop und unser Harness starten den
        # Server selbst als Unterprozess und sprechen über stdin/stdout mit ihm.
        mcp.run(transport="stdio")
