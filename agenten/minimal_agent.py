#!/usr/bin/env python3
"""
Der kleinste mögliche Agent – nur die Agenten-Schleife, sonst nichts.

    Agent = LLM + Tools + Schleife

Kein Rechtesystem, keine Freigaben, kein Protokoll. Genau deshalb ist dieser
Agent NICHT für den echten Einsatz geeignet. Vergleiche ihn mit harness/harness.py:
Alles, was dort zusätzlich steht, ist "Harness".

Start:
    python agenten/minimal_agent.py mensch   "Wie viele Lehrer gibt es?"
    python agenten/minimal_agent.py anthropic "Wie viele Lehrer gibt es?"
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.llm import erstelle_llm
from harness.mcp_bruecke import MCPBruecke


async def main(modell: str, frage: str):
    llm = erstelle_llm(modell)

    async with MCPBruecke() as mcp:          # MCP: tools/list
        tools = mcp.tools                     # ALLE Tools – auch das schreibende add_grade!
        system = "Du beantwortest Fragen zur Schul-Datenbank. Nutze die Tools."
        nachrichten = [{"role": "user", "content": frage}]

        while True:                                                   # ── die Agenten-Schleife ──
            antwort = llm.antworte(system, nachrichten, tools)        # 1. LLM fragen
            nachrichten.append({"role": "assistant", "text": antwort["text"],
                                "tool_calls": antwort["tool_calls"]})

            if not antwort["tool_calls"]:                             # 2. Keine Tools mehr? Fertig!
                print("\nANTWORT:", antwort["text"])
                return

            for aufruf in antwort["tool_calls"]:                      # 3. Tools ausführen (MCP: tools/call)
                print(f"→ Tool {aufruf['name']} {aufruf['arguments']}")
                ergebnis = await mcp.rufe_auf(aufruf["name"], aufruf["arguments"])
                nachrichten.append({"role": "tool", "tool_call_id": aufruf["id"],
                                    "name": aufruf["name"], "content": ergebnis})  # 4. Ergebnis zurück


if __name__ == "__main__":
    modell = sys.argv[1] if len(sys.argv) > 1 else "mensch"
    frage = sys.argv[2] if len(sys.argv) > 2 else input("Frage: ")
    asyncio.run(main(modell, frage))
