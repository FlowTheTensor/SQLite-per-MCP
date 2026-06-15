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

if __name__ == "__main__":
    mcp.run(transport="stdio")
