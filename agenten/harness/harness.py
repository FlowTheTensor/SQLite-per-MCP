"""
Der HARNESS – das Rahmenprogramm, das aus einem Sprachmodell einen Agenten macht.

Ein LLM allein kann nur Text erzeugen. Erst der Harness macht daraus einen Agenten:

    1. Kontext bauen      System-Prompt + Verlauf + Toolliste zusammenstellen
    2. LLM aufrufen       "Was willst du als Nächstes tun?"
    3. Entscheiden        Will das LLM ein Tool? -> prüfen, ob es das DARF
    4. Ausführen          Tool wirklich aufrufen (MCP), ggf. vorher Mensch fragen
    5. Zurückmelden       Ergebnis in den Verlauf schreiben
    6. Wiederholen        bis das LLM fertig ist oder das Schrittlimit erreicht ist

Das ist die berühmte AGENTEN-SCHLEIFE (agent loop).

Merke: Berechtigungen werden HIER im Code erzwungen – nicht durch den Prompt.
Ein LLM kann man überreden, ein Programm nicht.
"""

import asyncio
import json
from datetime import date

from .definition import AgentDefinition, lade_definition
from .protokoll import kuerzen

# Tools, die nicht vom MCP-Server kommen, sondern vom Harness selbst
FRAGE_MENSCH_TOOL = {
    "name": "frage_mensch",
    "description": "Stellt dem Menschen eine Rückfrage, wenn der Auftrag unklar ist oder eine Entscheidung nötig ist.",
    "input_schema": {
        "type": "object",
        "properties": {"frage": {"type": "string", "description": "Die Frage an den Menschen"}},
        "required": ["frage"],
    },
}


def delegations_tool(ziel: AgentDefinition) -> dict:
    """Für Multiagentensysteme: Ein anderer Agent wird dem LLM als 'Tool' angeboten."""
    return {
        "name": f"delegiere_an_{ziel.name}",
        "description": f"Gibt eine Teilaufgabe an den Agenten '{ziel.name}' ab. {ziel.beschreibung} "
                       f"Der Agent kennt den bisherigen Verlauf NICHT – formuliere den Auftrag vollständig.",
        "input_schema": {
            "type": "object",
            "properties": {"auftrag": {"type": "string", "description": "Vollständiger, eigenständiger Auftrag"}},
            "required": ["auftrag"],
        },
    }


class Harness:
    def __init__(self, llm, mcp, mensch, protokoll):
        self.llm = llm
        self.mcp = mcp
        self.mensch = mensch
        self.protokoll = protokoll
        self.verbrauch = {}  # Tokens pro Agent

    # ------------------------------------------------------------------
    # Schritt 1: Kontext bauen
    # ------------------------------------------------------------------
    def _tools_fuer(self, d: AgentDefinition, tiefe: int) -> list[dict]:
        mcp_tools = {t["name"]: t for t in self.mcp.tools}
        sichtbar = []
        for name in d.tools + d.tools_mit_freigabe:
            if name in mcp_tools:
                sichtbar.append(mcp_tools[name])
            else:
                self.protokoll.schreibe("FEHLER", f"Tool '{name}' gibt es auf dem MCP-Server nicht.", tiefe)
        if d.mensch_fragen:
            sichtbar.append(FRAGE_MENSCH_TOOL)
        for ziel in d.delegiert_an:
            sichtbar.append(delegations_tool(lade_definition(ziel)))
        return sichtbar

    def _system_prompt(self, d: AgentDefinition) -> str:
        return (
            f"{d.system_prompt}\n\n"
            f"--- vom Harness ergänzt ---\n"
            f"Du bist der Agent '{d.name}'. Heute ist der {date.today().strftime('%d.%m.%Y')}.\n"
            f"Nutze nur die Tools, die dir angeboten werden. Antworte auf Deutsch.\n"
            f"Wenn du fertig bist, antworte mit Text und rufe kein Tool mehr auf."
        )

    # ------------------------------------------------------------------
    # Die Agenten-Schleife
    # ------------------------------------------------------------------
    async def starte_agent(self, name: str, auftrag: str, tiefe: int = 0) -> str:
        d = lade_definition(name)
        tools = self._tools_fuer(d, tiefe)
        system = self._system_prompt(d)
        nachrichten = [{"role": "user", "content": auftrag}]

        self.protokoll.schreibe("AGENT", f"▶ Agent '{d.name}' startet (Gehirn: {self.llm.name})", tiefe)
        self.protokoll.schreibe("HARNESS", f"Tools für '{d.name}': {', '.join(t['name'] for t in tools) or '(keine)'}", tiefe)
        self.protokoll.schreibe("HARNESS", "System-Prompt", tiefe, daten=system, nur_datei=True)

        for schritt in range(1, d.max_schritte + 1):
            # Schritt 2: LLM aufrufen
            self.protokoll.schreibe(
                "HARNESS", f"Schritt {schritt}/{d.max_schritte}: sende {len(nachrichten)} Nachricht(en) "
                           f"+ {len(tools)} Tool(s) an das LLM …", tiefe)
            antwort = await asyncio.to_thread(self.llm.antworte, system, nachrichten, tools)
            self._zaehle(d.name, antwort.get("verbrauch", {}))

            if antwort["text"]:
                self.protokoll.schreibe("LLM", antwort["text"], tiefe)
            nachrichten.append({"role": "assistant", "text": antwort["text"], "tool_calls": antwort["tool_calls"]})

            # Keine Tool-Wünsche mehr -> der Agent ist fertig
            if not antwort["tool_calls"]:
                self.protokoll.schreibe("AGENT", f"■ Agent '{d.name}' ist fertig ({schritt} Schritt(e)).", tiefe)
                return antwort["text"]

            # Schritte 3–5: jeden Tool-Wunsch prüfen, ausführen, zurückmelden
            for aufruf in antwort["tool_calls"]:
                self.protokoll.schreibe(
                    "LLM", f"möchte Tool '{aufruf['name']}' mit {json.dumps(aufruf['arguments'], ensure_ascii=False)}",
                    tiefe)
                ergebnis = await self._fuehre_aus(d, aufruf, tiefe)
                nachrichten.append({"role": "tool", "tool_call_id": aufruf["id"],
                                    "name": aufruf["name"], "content": ergebnis})

        # S4: Schrittlimit als Notbremse
        meldung = f"Abbruch durch den Harness: Schrittlimit von {d.max_schritte} erreicht."
        self.protokoll.schreibe("FEHLER", meldung, tiefe)
        return meldung

    # ------------------------------------------------------------------
    # Schritte 3 + 4: Berechtigung prüfen und ausführen
    # ------------------------------------------------------------------
    async def _fuehre_aus(self, d: AgentDefinition, aufruf: dict, tiefe: int) -> str:
        name, argumente = aufruf["name"], aufruf["arguments"]

        # a) Rückfrage an den Menschen (S3)
        if name == "frage_mensch" and d.mensch_fragen:
            return await asyncio.to_thread(self.mensch.rueckfrage, d.name, argumente.get("frage", ""), tiefe)

        # b) Delegation an einen anderen Agenten (Multiagentensystem)
        if name.startswith("delegiere_an_"):
            ziel = name.removeprefix("delegiere_an_")
            if ziel not in d.delegiert_an:
                return self._verweigert(d, name, tiefe)
            ergebnis = await self.starte_agent(ziel, argumente.get("auftrag", ""), tiefe + 1)
            self.protokoll.schreibe("HARNESS", f"Ergebnis von '{ziel}' geht zurück an '{d.name}'.", tiefe)
            return ergebnis

        # c) MCP-Tool ohne Nachfrage
        if name in d.tools:
            return await self._mcp(name, argumente, tiefe)

        # d) MCP-Tool mit Freigabe durch den Menschen (S2)
        if name in d.tools_mit_freigabe:
            erlaubt, grund = await asyncio.to_thread(self.mensch.freigabe, d.name, name, argumente, tiefe)
            if not erlaubt:
                return f"Der Mensch hat den Aufruf von '{name}' ABGELEHNT. Begründung: {grund or 'keine'}"
            return await self._mcp(name, argumente, tiefe)

        # e) Alles andere ist verboten – egal, was das LLM will
        return self._verweigert(d, name, tiefe)

    async def _mcp(self, name: str, argumente: dict, tiefe: int) -> str:
        self.protokoll.schreibe("MCP", f"tools/call → {name}", tiefe)
        ergebnis = await self.mcp.rufe_auf(name, argumente)
        self.protokoll.schreibe("MCP", f"Ergebnis: {kuerzen(ergebnis)}", tiefe, daten=ergebnis)
        return ergebnis

    def _verweigert(self, d: AgentDefinition, name: str, tiefe: int) -> str:
        self.protokoll.schreibe("FEHLER", f"Harness blockiert: '{d.name}' darf '{name}' nicht benutzen.", tiefe)
        return f"Fehler: Du hast keine Berechtigung für das Tool '{name}'."

    def _zaehle(self, agent: str, v: dict):
        summe = self.verbrauch.setdefault(agent, {"eingabe": 0, "ausgabe": 0, "aufrufe": 0})
        summe["eingabe"] += v.get("eingabe", 0)
        summe["ausgabe"] += v.get("ausgabe", 0)
        summe["aufrufe"] += 1

    def verbrauch_anzeigen(self):
        if not any(v["eingabe"] or v["ausgabe"] for v in self.verbrauch.values()):
            return  # z.B. im Modus "mensch" werden keine Tokens gezählt
        print("\n\033[90mLLM-Aufrufe und Tokens pro Agent:")
        for agent, v in self.verbrauch.items():
            print(f"  {agent:<20} {v['aufrufe']:>3} Aufrufe   {v['eingabe']:>7} Tokens rein   {v['ausgabe']:>6} Tokens raus")
        print("\033[0m", end="")
