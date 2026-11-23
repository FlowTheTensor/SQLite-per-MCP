"""
Agenten-Definition – ein Agent ist hier eine einfache Textdatei.

Aufbau einer Datei in agenten/definitionen/  (z.B. datenbank-analyst.md):

    ---
    name: datenbank-analyst
    beschreibung: Wofür ist dieser Agent da? (Das liest ein Koordinator!)
    tools: list_tables, describe_table, query_database
    tools_mit_freigabe: add_grade
    mensch_fragen: ja
    delegiert_an: pruefer
    max_schritte: 10
    ---
    Ab hier steht der System-Prompt: Rolle, Ziel, Regeln, Antwortformat.

Bedeutung der Felder:
    tools               MCP-Tools, die der Agent OHNE Nachfrage benutzen darf
    tools_mit_freigabe  MCP-Tools, bei denen der Harness vorher den Menschen fragt
    (alle anderen MCP-Tools bekommt der Agent gar nicht zu sehen!)
    mensch_fragen       ja/nein – darf der Agent dem Menschen Rückfragen stellen?
    delegiert_an        andere Agenten, an die dieser Agent Aufgaben abgeben darf
    max_schritte        Sicherheitsgrenze: maximale Anzahl an LLM-Aufrufen

Das gleiche Prinzip (Markdown-Datei mit Kopfbereich) verwenden auch echte
Werkzeuge wie Claude Code für ihre "Subagents".
"""

from dataclasses import dataclass, field
from pathlib import Path

DEFINITIONS_ORDNER = Path(__file__).resolve().parent.parent / "definitionen"


@dataclass
class AgentDefinition:
    name: str
    beschreibung: str
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    tools_mit_freigabe: list[str] = field(default_factory=list)
    mensch_fragen: bool = False
    delegiert_an: list[str] = field(default_factory=list)
    max_schritte: int = 10


def _liste(wert: str) -> list[str]:
    return [x.strip() for x in wert.split(",") if x.strip()]


def lade_definition(name: str) -> AgentDefinition:
    datei = DEFINITIONS_ORDNER / f"{name}.md"
    if not datei.exists():
        vorhanden = ", ".join(sorted(p.stem for p in DEFINITIONS_ORDNER.glob("*.md")))
        raise FileNotFoundError(f"Agent '{name}' nicht gefunden. Vorhanden: {vorhanden}")

    inhalt = datei.read_text(encoding="utf-8")
    _, kopf, prompt = inhalt.split("---", 2)

    felder = {}
    for zeile in kopf.strip().splitlines():
        zeile = zeile.split("#", 1)[0]  # Kommentare erlauben
        if ":" in zeile:
            schluessel, wert = zeile.split(":", 1)
            felder[schluessel.strip()] = wert.strip()

    return AgentDefinition(
        name=felder.get("name", name),
        beschreibung=felder.get("beschreibung", ""),
        system_prompt=prompt.strip(),
        tools=_liste(felder.get("tools", "")),
        tools_mit_freigabe=_liste(felder.get("tools_mit_freigabe", "")),
        mensch_fragen=felder.get("mensch_fragen", "nein").lower() in ("ja", "true", "yes"),
        delegiert_an=_liste(felder.get("delegiert_an", "")),
        max_schritte=int(felder.get("max_schritte", "10")),
    )


def alle_definitionen() -> list[str]:
    return sorted(p.stem for p in DEFINITIONS_ORDNER.glob("*.md"))
