#!/usr/bin/env python3
"""
SQLite MCP Server - FastMCP Implementation
Ermöglicht LLMs den Zugriff auf eine SQLite-Datenbank über das Model Context Protocol
"""

import sqlite3
import json
from pathlib import Path
from fastmcp import FastMCP

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

if __name__ == "__main__":
    mcp.run(transport="stdio")
