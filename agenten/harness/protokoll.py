"""
Protokoll (Trace) – macht sichtbar, WER gerade WAS tut.

Jede Zeile in der Konsole beginnt mit einem Etikett:

    [MENSCH]   Eingaben und Entscheidungen des Menschen
    [HARNESS]  Was das Rahmenprogramm (der Harness) tut
    [LLM]      Was das Sprachmodell antwortet bzw. entscheidet
    [MCP]      Aufrufe an den MCP-Server und dessen Antworten
    [AGENT]    Start/Ende eines (Unter-)Agenten im Multiagentensystem

Zusätzlich wird alles maschinenlesbar in eine JSONL-Datei geschrieben
(eine JSON-Zeile pro Ereignis) im Ordner agenten/protokolle/.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Unter Windows ANSI-Farben in der Konsole aktivieren
if os.name == "nt":
    os.system("")

# Ausgaben immer als UTF-8 (Umlaute, Emojis) – wichtig unter Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

FARBEN = {
    "MENSCH": "\033[95m",   # magenta
    "HARNESS": "\033[90m",  # grau
    "LLM": "\033[94m",      # blau
    "MCP": "\033[92m",      # grün
    "AGENT": "\033[93m",    # gelb
    "FEHLER": "\033[91m",   # rot
}
RESET = "\033[0m"

PROTOKOLL_ORDNER = Path(__file__).resolve().parent.parent / "protokolle"


class Protokoll:
    def __init__(self, ausfuehrlich: bool = True):
        self.ausfuehrlich = ausfuehrlich
        PROTOKOLL_ORDNER.mkdir(exist_ok=True)
        zeit = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.datei = PROTOKOLL_ORDNER / f"lauf_{zeit}.jsonl"

    def schreibe(self, wer: str, text: str, tiefe: int = 0, daten=None, nur_datei: bool = False):
        """Ein Ereignis ausgeben (Konsole) und speichern (Datei)."""
        eintrag = {
            "zeit": datetime.now().isoformat(timespec="seconds"),
            "wer": wer,
            "tiefe": tiefe,
            "text": text,
        }
        if daten is not None:
            eintrag["daten"] = daten
        with open(self.datei, "a", encoding="utf-8") as f:
            f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")

        if nur_datei:
            return
        if wer == "HARNESS" and not self.ausfuehrlich:
            return
        einzug = "    │ " * tiefe
        farbe = FARBEN.get(wer, "")
        zeilen = str(text).splitlines() or [""]
        print(f"{einzug}{farbe}[{wer:<7}]{RESET} {zeilen[0]}")
        for zeile in zeilen[1:]:
            print(f"{einzug}{' ' * 10}{zeile}")


def kuerzen(text: str, laenge: int = 400) -> str:
    """Lange Tool-Ergebnisse für die Konsole kürzen (die Datei enthält alles)."""
    text = str(text)
    if len(text) <= laenge:
        return text
    return text[:laenge] + f" … [{len(text) - laenge} Zeichen gekürzt]"
