"""
Weg – zeichnet auf, welchen WEG ein Lauf durch die Agenten-Schleife genommen hat,
und speichert ihn als Mermaid-Diagramm (ein Bild aus Kästen und Pfeilen).

Protokoll und Weg ergänzen sich:
    Protokoll  erzählt den Lauf Zeile für Zeile (Konsole + JSONL-Datei)
    Weg        zeigt denselben Lauf als Bild: Wer kam nach wem? Wo hat sich der Weg verzweigt?

Wer ruft was auf?
    harness.py meldet jeden Schritt an den Weg:
        weg.agent(...)       ein Agent startet (bei Delegation: als Unteragent)
        weg.llm(...)         das LLM wird aufgerufen – ein Durchgang der Agenten-Schleife
        weg.tool(...)        ein Tool wird aufgerufen – evtl. mit Freigabe oder vom Harness blockiert
        weg.rueckfrage(...)  der Agent fragt den Menschen
        weg.fertig(...)      der Agent ist fertig (oder das Schrittlimit greift)
    agent.py ruft am Ende weg.speichern(...) auf.

Was ist Mermaid?
    Mermaid ist eine Sprache, in der man Diagramme als TEXT schreibt, z. B.:

        flowchart TD
            k1(["Auftrag"]) --> k2["LLM · Schritt 1"]
            k2 --> k3["Tool list_tables"]

    Ein Programm (hier: mermaid.js im Browser) macht daraus ein Bild.
    Weil das Diagramm reiner Text ist, kann unser Harness es ganz einfach selbst erzeugen.

Die Farben entsprechen den Etiketten in der Konsole:
    blau = LLM   grün = MCP-Tool   magenta = Mensch   rot = Fehler/Notbremse   gelb = Agent
"""

import html
import json
from dataclasses import dataclass, field
from pathlib import Path

# Formen der Kästen in Mermaid: (Zeichen links, Zeichen rechts)
FORMEN = {
    "rechteck": ("[", "]"),     # normaler Schritt (LLM, Tool)
    "rund": ("([", "])"),       # Anfang und Ende, Rückfrage
    "raute": ("{", "}"),        # Entscheidung des Menschen (Freigabe)
    "stopp": ("[[", "]]"),      # Notbremse (blockiert, Schrittlimit)
}

# Farben wie in der Konsole (siehe protokoll.py)
KLASSEN = [
    "classDef llm fill:#dbeafe,stroke:#2563eb,color:#1e3a8a",
    "classDef mcp fill:#dcfce7,stroke:#16a34a,color:#14532d",
    "classDef mensch fill:#fae8ff,stroke:#c026d3,color:#701a75",
    "classDef fehler fill:#fee2e2,stroke:#dc2626,color:#7f1d1d",
    "classDef agent fill:#fef9c3,stroke:#ca8a04,color:#713f12",
]


def kurz(text, laenge: int = 45) -> str:
    """Text einzeilig und kurz machen, damit die Kästen nicht riesig werden."""
    text = " ".join(str(text).split())
    if len(text) > laenge:
        text = text[:laenge] + " …"
    # Zeichen, die Mermaid sonst falsch verstehen würde, als Mermaid-Codes schreiben
    return text.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


@dataclass
class Abschnitt:
    """Ein Agent im Diagramm (in Mermaid ein 'subgraph', also ein Kasten um seine Schritte).
    Bei Delegation bekommt jeder beauftragte Agent einen eigenen Abschnitt."""
    name: str
    eltern: int | None                                # welcher Abschnitt hat ihn beauftragt? (None = der Mensch)
    knoten: list[str] = field(default_factory=list)   # Mermaid-Zeilen der Kästen in diesem Abschnitt
    letztes_llm: str | None = None                    # aktueller LLM-Kasten: von hier gehen Tool-Aufrufe ab
    offen: list[tuple[str, str]] = field(default_factory=list)  # (Kasten, Pfeil-Text): fließt in den NÄCHSTEN LLM-Schritt


class Weg:
    def __init__(self):
        self.abschnitte: list[Abschnitt] = []
        self.ausserhalb: list[str] = []   # Kästen außerhalb der Agenten (Auftrag und Ergebnis beim Menschen)
        self.pfeile: list[str] = []
        self._zaehler = 0

    # ------------------------------------------------------------------
    # Hilfsfunktionen: einen Kasten bzw. einen Pfeil anlegen
    # ------------------------------------------------------------------
    def _kasten(self, abschnitt: int | None, form: str, text: str, farbe: str) -> str:
        self._zaehler += 1
        kid = f"k{self._zaehler}"
        links, rechts = FORMEN[form]
        zeile = f'{kid}{links}"{text}"{rechts}:::{farbe}'
        if abschnitt is None:
            self.ausserhalb.append(zeile)
        else:
            self.abschnitte[abschnitt].knoten.append(zeile)
        return kid

    def _pfeil(self, von: str, nach: str, text: str = ""):
        self.pfeile.append(f"{von} -->|{text}| {nach}" if text else f"{von} --> {nach}")

    # ------------------------------------------------------------------
    # Diese Methoden ruft harness.py auf
    # ------------------------------------------------------------------
    def agent(self, name: str, auftrag: str, eltern: int | None = None) -> int:
        """Ein Agent startet. Rückgabe: Nummer seines Abschnitts (braucht der Harness für alle weiteren Meldungen)."""
        self.abschnitte.append(Abschnitt(name, eltern))
        a = len(self.abschnitte) - 1
        if eltern is None:
            # S1: Der Mensch gibt den Auftrag
            start = self._kasten(None, "rund", f"👤 Auftrag:<br/>{kurz(auftrag)}", "mensch")
        else:
            # Delegation: Der Auftrag kommt vom LLM des beauftragenden Agenten
            start = self._kasten(a, "rund", f"📨 Auftrag:<br/>{kurz(auftrag)}", "agent")
            self._pfeil(self.abschnitte[eltern].letztes_llm, start, "delegiert")
        self.abschnitte[a].offen = [(start, "")]
        return a

    def llm(self, a: int, schritt: int):
        """Ein Durchgang der Agenten-Schleife: Alles, was offen ist, fließt in diesen LLM-Aufruf."""
        ab = self.abschnitte[a]
        k = self._kasten(a, "rechteck", f"🧠 LLM · Schritt {schritt}", "llm")
        for von, text in ab.offen:
            self._pfeil(von, k, text)
        ab.offen = []
        ab.letztes_llm = k

    def tool(self, a: int, name: str, argumente: dict | None = None,
             freigabe: bool | None = None, blockiert: bool = False):
        """Das LLM wollte ein Tool. freigabe=None: ohne Nachfrage; True/False: Mensch hat zugestimmt/abgelehnt."""
        ab = self.abschnitte[a]
        von, text = ab.letztes_llm, ""

        if blockiert:
            k = self._kasten(a, "stopp", f"⛔ {name}<br/>vom Harness blockiert", "fehler")
            self._pfeil(von, k)
            ab.offen.append((k, ""))
            return

        if freigabe is not None:
            # S2: Der Mensch entscheidet – der Weg verzweigt sich
            frage = self._kasten(a, "raute", f"👤 Freigabe?<br/>{name}", "mensch")
            self._pfeil(von, frage)
            if not freigabe:
                ab.offen.append((frage, "nein"))   # Tool wird NICHT ausgeführt, zurück zum LLM
                return
            von, text = frage, "ja"

        werte = " ".join(str(v) for v in (argumente or {}).values())
        k = self._kasten(a, "rechteck", f"🔧 {name}<br/>{kurz(werte)}" if werte else f"🔧 {name}", "mcp")
        self._pfeil(von, k, text)
        ab.offen.append((k, ""))

    def rueckfrage(self, a: int, frage: str):
        """S3: Der Agent fragt den Menschen; die Antwort geht zurück an das LLM."""
        ab = self.abschnitte[a]
        k = self._kasten(a, "rund", f"👤 Rückfrage:<br/>{kurz(frage)}", "mensch")
        self._pfeil(ab.letztes_llm, k)
        ab.offen.append((k, ""))

    def fertig(self, a: int, schrittlimit: bool = False):
        """Der Agent endet – entweder weil das LLM fertig ist oder weil die Notbremse (S4) greift."""
        ab = self.abschnitte[a]
        if schrittlimit:
            k = self._kasten(a, "stopp", "⛔ Schrittlimit erreicht", "fehler")
            for von, text in ab.offen:
                self._pfeil(von, k, text)
            ab.offen = []
        elif ab.eltern is None:
            # S5: Das Ergebnis geht an den Menschen
            k = self._kasten(None, "rund", "✅ Ergebnis an den Menschen", "mensch")
            self._pfeil(ab.letztes_llm, k)
        else:
            k = self._kasten(a, "rund", "■ fertig", "agent")
            self._pfeil(ab.letztes_llm, k)

        # Bei Delegation: Das Ergebnis fließt in den nächsten LLM-Schritt des Auftraggebers
        if ab.eltern is not None:
            self.abschnitte[ab.eltern].offen.append((k, "Ergebnis"))

    # ------------------------------------------------------------------
    # Ausgabe als Mermaid-Text und als Dateien
    # ------------------------------------------------------------------
    def als_mermaid(self) -> str:
        zeilen = ["flowchart TD"]
        zeilen += ["    " + z for z in self.ausserhalb]
        for i, ab in enumerate(self.abschnitte):
            titel = f"🤖 Agent {ab.name}"
            if ab.eltern is not None:
                titel += f" · beauftragt von {self.abschnitte[ab.eltern].name}"
            zeilen.append(f'    subgraph a{i}["{titel}"]')
            zeilen += ["        " + z for z in ab.knoten]
            zeilen.append("    end")
            zeilen.append(f"    style a{i} fill:#fffbeb,stroke:#ca8a04")
        zeilen += ["    " + p for p in self.pfeile]
        zeilen += ["    " + k for k in KLASSEN]
        return "\n".join(zeilen)

    def speichern(self, protokoll_datei: Path) -> Path | None:
        """Speichert den Weg neben der Protokolldatei:
            lauf_..._weg.html  im Browser öffnen (zeichnet das Bild)
            lauf_..._weg.md    Mermaid-Text, z. B. für GitHub oder mermaid.live
        Rückgabe: Pfad der HTML-Datei (None, wenn noch kein Agent gelaufen ist)."""
        if not self.abschnitte:
            return None
        mermaid = self.als_mermaid()
        basis = protokoll_datei.with_suffix("")

        md = basis.with_name(basis.name + "_weg.md")
        md.write_text(f"# Weg des Laufs {protokoll_datei.stem}\n\n```mermaid\n{mermaid}\n```\n", encoding="utf-8")

        seite = basis.with_name(basis.name + "_weg.html")
        seite.write_text(
            HTML_VORLAGE.replace("{{TITEL}}", html.escape(protokoll_datei.stem))
                        .replace("{{MERMAID}}", html.escape(mermaid)),
            encoding="utf-8")
        return seite


# Die HTML-Seite lädt nur das Zeichenprogramm mermaid.js aus dem Internet.
# Das Diagramm selbst wird im Browser gezeichnet – die Daten des Laufs verlassen den Rechner nicht.
HTML_VORLAGE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Weg {{TITEL}}</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem; background: #fff; color: #222; }
  .legende span { display: inline-block; padding: .15rem .6rem; margin-right: .4rem; border-radius: .3rem; border: 1px solid; }
</style>
</head>
<body>
<h1>Weg des Laufs {{TITEL}}</h1>
<p class="legende">
  <span style="background:#dbeafe;border-color:#2563eb">🧠 LLM</span>
  <span style="background:#dcfce7;border-color:#16a34a">🔧 MCP-Tool</span>
  <span style="background:#fae8ff;border-color:#c026d3">👤 Mensch</span>
  <span style="background:#fef9c3;border-color:#ca8a04">🤖 Agent</span>
  <span style="background:#fee2e2;border-color:#dc2626">⛔ Notbremse</span>
</p>
<pre class="mermaid">
{{MERMAID}}
</pre>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true, securityLevel: "strict" });
</script>
</body>
</html>
"""
