"""
Mensch-Maschine-Schnittstellen – ALLE Stellen, an denen ein Mensch eingreift.

Bewusst in einer einzigen Datei gesammelt, damit man sie leicht findet:

    S1  Auftrag      Mensch -> Agent    Der Mensch formuliert das Ziel.
    S2  Freigabe     Agent  -> Mensch   Vor riskanten Aktionen (z.B. Daten schreiben)
                                        fragt der Harness: "Darf ich?"
    S3  Rückfrage    Agent  -> Mensch   Der Agent ist unsicher und fragt nach.
    S4  Abbruch      Mensch -> Harness  Strg+C oder Schrittlimit beendet den Agenten.
    S5  Ergebnis     Agent  -> Mensch   Die Antwort + das Protokoll (Nachvollziehbarkeit).

    (S0  Definition  Mensch -> Agent    Schon VOR dem Lauf legt ein Mensch in der
                                        Definitionsdatei fest, was der Agent darf.)
"""

import json


class Mensch:
    def __init__(self, protokoll, alles_erlauben: bool = False):
        self.protokoll = protokoll
        # alles_erlauben=True schaltet S2 ab -> höhere Autonomie, höheres Risiko!
        self.alles_erlauben = alles_erlauben

    # S1 ---------------------------------------------------------------
    def auftrag_holen(self) -> str:
        auftrag = input("\n\033[95mDein Auftrag an den Agenten:\033[0m ").strip()
        self.protokoll.schreibe("MENSCH", f"Auftrag: {auftrag}")
        return auftrag

    # S2 ---------------------------------------------------------------
    def freigabe(self, agent: str, tool: str, argumente: dict, tiefe: int = 0) -> tuple[bool, str]:
        beschreibung = f"Agent '{agent}' möchte '{tool}' aufrufen mit {json.dumps(argumente, ensure_ascii=False)}"
        if self.alles_erlauben:
            self.protokoll.schreibe("HARNESS", f"Automatisch erlaubt (--alles-erlauben): {beschreibung}", tiefe)
            return True, ""
        self.protokoll.schreibe("HARNESS", f"⚠ FREIGABE NÖTIG: {beschreibung}", tiefe)
        while True:
            antwort = input("\033[95m   Erlauben? [j]a / [n]ein: \033[0m").strip().lower()
            if antwort in ("j", "ja", "y"):
                self.protokoll.schreibe("MENSCH", "Freigabe erteilt ✔", tiefe)
                return True, ""
            if antwort in ("n", "nein"):
                grund = input("\033[95m   Begründung für den Agenten (optional): \033[0m").strip()
                self.protokoll.schreibe("MENSCH", f"Freigabe verweigert ✘ {grund}", tiefe)
                return False, grund

    # S3 ---------------------------------------------------------------
    def rueckfrage(self, agent: str, frage: str, tiefe: int = 0) -> str:
        self.protokoll.schreibe("AGENT", f"❓ {agent} fragt dich: {frage}", tiefe)
        antwort = input("\033[95m   Deine Antwort: \033[0m").strip()
        self.protokoll.schreibe("MENSCH", f"Antwort: {antwort}", tiefe)
        return antwort or "(keine Antwort)"

    # S5 ---------------------------------------------------------------
    def ergebnis_zeigen(self, text: str):
        print("\n\033[1m════════════════ ERGEBNIS ════════════════\033[0m")
        print(text)
        print("\033[1m══════════════════════════════════════════\033[0m")
        print(f"\033[90mVollständiges Protokoll: {self.protokoll.datei}\033[0m")

    # S4 steckt im Harness (Schrittlimit) und in agent.py (Strg+C).
