#!/usr/bin/env python3
"""
Startet einen Agenten (oder ein Agenten-Team) aus agenten/definitionen/.

Beispiele (im Projektordner, venv aktiviert):

    # Du spielst selbst das LLM – kein API-Key nötig
    python agenten/agent.py --agent datenbank-analyst --modell mensch

    # Mit lokalem Ollama-Modell
    python agenten/agent.py --agent datenbank-analyst --modell ollama "Wie viele Schüler hat die 7a?"

    # Mit Claude über die Anthropic-API (ANTHROPIC_API_KEY muss gesetzt sein)
    python agenten/agent.py --agent notenverwalter --modell anthropic

    # Multiagentensystem: der Koordinator verteilt Arbeit an andere Agenten
    python agenten/agent.py --agent koordinator --modell anthropic "Zwischenstand Informatik 10a als Rückmeldung an die Klasse"

    # Welche Agenten gibt es?
    python agenten/agent.py --liste
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import Harness, MCPBruecke, Mensch, Protokoll, alle_definitionen, erstelle_llm, lade_definition


async def main():
    parser = argparse.ArgumentParser(description="Agenten-Harness für die Schul-Datenbank")
    parser.add_argument("auftrag", nargs="?", help="Auftrag an den Agenten (sonst wird gefragt)")
    parser.add_argument("--agent", default="datenbank-analyst", help="Name der Definitionsdatei (ohne .md)")
    parser.add_argument("--modell", default="mensch", help="anthropic | ollama | openai | mensch")
    parser.add_argument("--modellname", default=None, help="z.B. claude-haiku-5-5 oder qwen2.5:7b")
    parser.add_argument("--url", default=None, help="Basis-URL für OpenAI-kompatible Server")
    parser.add_argument("--alles-erlauben", action="store_true",
                        help="Keine Freigaben abfragen (höhere Autonomie – nur zum Ausprobieren!)")
    parser.add_argument("--leise", action="store_true", help="HARNESS-Zeilen ausblenden")
    parser.add_argument("--liste", action="store_true", help="Verfügbare Agenten anzeigen")
    args = parser.parse_args()

    if args.liste:
        for name in alle_definitionen():
            d = lade_definition(name)
            print(f"  {name:<20} {d.beschreibung}")
        return

    protokoll = Protokoll(ausfuehrlich=not args.leise)
    mensch = Mensch(protokoll, alles_erlauben=args.alles_erlauben)
    llm = erstelle_llm(args.modell, args.modellname, args.url)

    protokoll.schreibe("HARNESS", "Starte MCP-Server (src/index.py) und frage seine Tools ab (tools/list) …")
    async with MCPBruecke() as mcp:
        protokoll.schreibe("MCP", f"Server bietet an: {', '.join(t['name'] for t in mcp.tools)}")
        harness = Harness(llm, mcp, mensch, protokoll)

        # S1: Auftrag
        if args.auftrag:
            auftrag = args.auftrag
            protokoll.schreibe("MENSCH", f"Auftrag: {auftrag}")
        else:
            auftrag = mensch.auftrag_holen()

        # Agenten-Schleife starten
        ergebnis = await harness.starte_agent(args.agent, auftrag)

        # S5: Ergebnis
        mensch.ergebnis_zeigen(ergebnis)
        harness.verbrauch_anzeigen()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # S4: Abbruch durch den Menschen
        print("\n\033[95m[MENSCH ] Abbruch mit Strg+C – der Agent wurde gestoppt.\033[0m")
    except RuntimeError as e:
        print(f"\033[91m{e}\033[0m")
        sys.exit(1)
