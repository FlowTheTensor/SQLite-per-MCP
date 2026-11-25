#!/usr/bin/env python3
"""
LLM spielen – in Chat-Fenstern statt im Terminal.

Dasselbe wie  python agenten/agent.py --modell mensch,  nur bequemer:
DU bist das Sprachmodell und antwortest in einem Chat-Fenster.

    python agenten/llm_spielen.py
    python agenten/llm_spielen.py --agent notenverwalter
    python agenten/llm_spielen.py --agent koordinator "Zwischenstand Informatik 10a"

Die Fenster
-----------
    HAUPTFENSTER  "Mensch & Harness"
        👤 Der Mensch gibt den Auftrag, beantwortet Rückfragen, erteilt Freigaben.
        ⚙  Graue Zeilen zeigen, was der Harness gerade tut.

    EIN FENSTER PRO AGENT  "🤖 <agent> – du bist das LLM"
        Genau das, was der Harness diesem Agenten zeigt: System-Prompt, Tools, Verlauf.
        Unten gibst DU als LLM die Antwort ein.

    Delegiert ein Agent (delegiere_an_X), öffnet sich das Fenster von X und kommt nach vorn.
    Ist X fertig, kommt das Fenster des Auftraggebers wieder nach vorn.
    Wird X ein zweites Mal beauftragt, wird sein Fenster geleert: neues Gedächtnis!
    So sieht man: Jeder Agent hat seinen EIGENEN Kontext – den baut der Harness für ihn.

Wer spricht mit wem?
--------------------

    ┌── Hauptfenster (Mensch) ──┐   ┌── Agenten-Fenster (DU als LLM) ──┐
    │ Auftrag, Rückfrage,       │   │ Kontext des Agenten, Tool-Wünsche, │
    │ Freigabe, Ergebnis        │   │ Endantwort                         │
    └───────────┬───────────────┘   └──────────────┬─────────────────────┘
                │   beide über Warteschlangen      │      (tkinter, Haupt-Thread)
                ▼                                  ▼
    ┌──────────── Harness (eigener Thread) ─────────────────┐
    │  derselbe Harness wie in agent.py:                    │
    │  Agenten-Schleife, Rechteprüfung, Delegation          │
    └──────────────┬────────────────────────────────────────┘
                   │ stdio / JSON-RPC (MCP)
                   ▼
            src/index.py (MCP-Server)  ──SQL──►  schule.db

Am Harness wird NICHTS geändert. Wir tauschen nur zwei Bausteine aus:
    - das "Gehirn":  FensterLLM statt MenschLLM   (fragt im Fenster statt mit input())
    - den Menschen:  FensterMensch statt Mensch   (Freigabe und Rückfrage im Fenster)
Das zeigt nebenbei: Dem Harness ist es egal, WER das LLM ist und WIE der Mensch eingreift.

Warum zwei Threads?
    Fenster müssen ständig auf Klicks reagieren (Haupt-Thread, tkinter).
    Der Harness muss gleichzeitig auf deine Antwort WARTEN können (eigener Thread).
    Die beiden reden nur über zwei Warteschlangen (queue.Queue) miteinander:
        _auftraege  Harness -> Fenster   "Zeig diese Nachricht an", "Agent X ist dran"
        _antworten  Fenster -> Harness   "Das hat der Mensch / das LLM eingegeben"

Aufbau der Datei:
    1. Hilfetext          – was im Hilfe-Fenster steht
    2. FensterLLM         – das "Gehirn": schickt den Kontext ans Agenten-Fenster und wartet auf dich
    3. FensterMensch      – Mensch-Maschine-Schnittstellen S2, S3, S5 im Hauptfenster
    4. FensterProtokoll   – Harness-Meldungen zusätzlich als graue Zeilen im Hauptfenster
    5. Verlauf            – ein Chat mit Sprechblasen (benutzen beide Fensterarten)
    6. AgentFenster       – ein Fenster pro Agent: Kontext + LLM-Eingabe
    7. HauptFenster       – Mensch & Harness, startet den Lauf
    8. Start

Benötigt keine weiteren Pakete: tkinter gehört zu Python.
"""

import argparse
import asyncio
import json
import queue
import re
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import Harness, MCPBruecke, Mensch, Protokoll, alle_definitionen, lade_definition
from harness.llm import als_llm_antwort, zerlege_llm_eingabe


# ============================================================================
# 1. Hilfetext
# ============================================================================
# Aufbau: Liste von (Art, Text).  Art ist "h1", "h2", "text", "code" oder "hinweis".
# Zeilen der Art "code" kann man im Hilfe-Fenster anklicken: Dann landen sie im LLM-Eingabefeld
# des Agenten, der gerade dran ist.
HILFE = [
    ("h1", "So spielst du das LLM"),
    ("text", "Du bist jetzt das Sprachmodell (LLM) eines Agenten. Jeder Agent hat sein EIGENES Fenster. "
             "Darin siehst du genau das, was ein echtes LLM sehen würde:\n"
             "  • rechts »Das sieht das LLM«: den System-Prompt und deine Tools\n"
             "  • im Chat: den Auftrag und die Ergebnisse deiner Tool-Aufrufe\n\n"
             "Im Hauptfenster »Mensch & Harness« sitzt der Mensch: Er gibt den Auftrag, beantwortet "
             "Rückfragen und erteilt Freigaben. Dort siehst du auch, was der Harness gerade tut.\n\n"
             "Wichtig: Als LLM kannst du NICHTS selbst ausführen. Du kannst nur aufschreiben, was du gern "
             "hättest. Ausführen tut das der Harness, und vorher prüft er, ob du das darfst."),

    ("h2", "Deine zwei Möglichkeiten"),
    ("text", "1) TOOL-AUFRUF: »Harness, führe dieses Tool für mich aus.«\n"
             "   Die Eingabe beginnt mit dem Wort  tool .\n"
             "   Danach bekommst du das Ergebnis links im Chat (🔧) und bist wieder dran.\n\n"
             "2) ENDANTWORT: »Ich bin fertig.«\n"
             "   Jeder Text, der NICHT mit  tool  beginnt.\n"
             "   Damit endet der Agent. Deine Antwort geht an den, der ihn beauftragt hat:\n"
             "   an den Menschen oder an einen anderen Agenten."),
    ("hinweis", "Der Harness rät nicht, was du meinst. Er schaut nur auf die FORM: Beginnt deine "
                "Eingabe mit »tool«, ist es ein Tool-Aufruf, sonst eine Endantwort. "
                "Unter dem Eingabefeld siehst du schon beim Tippen, wie der Harness deine Eingabe verstehen wird."),

    ("h2", "Aufbau eines Tool-Aufrufs"),
    ("code", 'tool NAME {"argument": "wert"}'),
    ("text", "  • zuerst das Wort  tool\n"
             "  • dann der Name des Tools, OHNE Klammern\n"
             "  • dann die Argumente als JSON-Objekt in { }. Hat das Tool keine Argumente, lässt du sie weg.\n"
             "  • Die Namen der Argumente stehen bei den Tools in Klammern, z. B. describe_table(table_name).\n"
             "  • JSON braucht doppelte Anführungszeichen \" \". Zahlen schreibt man ohne Anführungszeichen."),
    ("hinweis", "Bequemer: Klick rechts auf einen Tool-Knopf. Dann steht die passende Vorlage schon im "
                "Eingabefeld, und du musst nur noch die Werte eintragen."),

    ("h2", "Beispiele: die Datenbank erkunden"),
    ("text", "Welche Tabellen gibt es? (kein Argument)"),
    ("code", "tool list_tables"),
    ("text", "Welche Spalten hat die Tabelle noten?"),
    ("code", 'tool describe_table {"table_name": "noten"}'),
    ("text", "Eine Abfrage stellen: Wie viele Schüler hat die 7a?"),
    ("code", "tool query_database {\"query\": \"SELECT COUNT(*) AS anzahl FROM schueler WHERE klasse = '7a'\"}"),
    ("text", "Texte INNERHALB der SQL-Abfrage schreibst du mit einfachen Anführungszeichen ' ', "
             "damit sie sich nicht mit den doppelten von JSON beißen."),

    ("h2", "Beispiel: eine ganze Notenübersicht, Schritt für Schritt"),
    ("text", "Auftrag des Menschen: »Notenübersicht: Durchschnitt pro Klasse und Fach«\n\n"
             "Schritt 1 – Tabellen ansehen:"),
    ("code", "tool list_tables"),
    ("text", "   ← links kommt: schueler, lehrer, kurse, noten\n\n"
             "Schritt 2 – Spalten der wichtigen Tabellen ansehen:"),
    ("code", 'tool describe_table {"table_name": "noten"}'),
    ("code", 'tool describe_table {"table_name": "kurse"}'),
    ("text", "   ← noten hat kurs_id und note, kurse hat id, fach und klasse\n\n"
             "Schritt 3 – die eigentliche Abfrage:"),
    ("code", 'tool query_database {"query": "SELECT k.klasse, k.fach, ROUND(AVG(n.note),2) AS schnitt, '
             'COUNT(*) AS anzahl FROM noten n JOIN kurse k ON n.kurs_id = k.id GROUP BY k.klasse, k.fach '
             'ORDER BY k.klasse, k.fach"}'),
    ("text", "   ← links kommt eine Liste, z. B. 10a | Informatik | 2.05 | 12\n\n"
             "Schritt 4 – Endantwort (OHNE »tool«), mit Zahlen nur aus dem Ergebnis:"),
    ("code", "Notenübersicht: 10a Informatik Schnitt 2,05 (12 Noten), 10b Informatik 3,41 (8 Noten), … "
             "SQL: SELECT k.klasse, k.fach, ROUND(AVG(n.note),2) … GROUP BY k.klasse, k.fach"),

    ("h2", "Beispiele für besondere Tools"),
    ("text", "Diese Tools hat nicht jeder Agent. Schau rechts im Agenten-Fenster nach, ob du sie hast."),
    ("text", "Den Menschen zurückfragen (wenn der Auftrag unklar ist) – z. B. koordinator, notenverwalter:"),
    ("code", 'tool frage_mensch {"frage": "Für welche Klasse und welches Fach soll die Übersicht sein?"}'),
    ("text", "   ← Das Hauptfenster kommt nach vorn, und der Mensch antwortet dort im Feld »Mensch«. "
             "Seine Antwort kommt als Tool-Ergebnis zu dir.\n\n"
             "Eine Note eintragen – nur notenverwalter, und nur mit Freigabe durch einen Menschen:"),
    ("code", 'tool add_grade {"schueler_id": 7, "kurs_id": 2, "note": 2.0, "art": "mündlich"}'),
    ("text", "   ← Vorher die ids mit query_database herausfinden! Der Harness fragt den Menschen, ob er "
             "das erlaubt. Sagt er Nein, bekommst du die Ablehnung als Ergebnis.\n\n"
             "Eine Teilaufgabe an einen anderen Agenten abgeben – nur koordinator:"),
    ("code", 'tool delegiere_an_datenbank-analyst {"auftrag": "Berechne den Notendurchschnitt der Klasse 10a '
             'in Informatik und gib die verwendete SQL-Abfrage mit an."}'),

    ("h2", "Mehrere Agenten: ein Fenster pro Agent"),
    ("text", "Startest du als koordinator, spielst du nacheinander MEHRERE Agenten. Umschalten musst du "
             "dabei nie – das macht der Harness:\n\n"
             "  1. Im Fenster »koordinator« schreibst du  tool delegiere_an_datenbank-analyst {\"auftrag\": \"…\"}\n"
             "  2. 🔀 Der Harness startet den datenbank-analyst. Sein EIGENES Fenster öffnet sich und kommt nach "
             "vorn.\n     Ab jetzt bist du der datenbank-analyst. Er kennt nur den Auftrag (📨), nicht den Verlauf "
             "des Koordinators.\n     Das Fenster des Koordinators wartet so lange (⏳).\n"
             "  3. Als datenbank-analyst arbeitest du ganz normal mit Tools und gibst am Ende eine ENDANTWORT.\n"
             "  4. 🔙 Das Fenster »koordinator« kommt wieder nach vorn. Die Endantwort des Analysten steht dort\n"
             "     als Tool-Ergebnis (🔧 »Antwort von datenbank-analyst«). Das Analysten-Fenster bleibt zum "
             "Nachlesen offen (✔ fertig).\n"
             "  5. Als koordinator delegierst du weiter (z. B. an pruefer) oder gibst die Endantwort an den Menschen.\n\n"
             "Wird ein Agent ein zweites Mal beauftragt, wird sein Fenster geleert: Er hat ein neues, leeres "
             "Gedächtnis.\nDie »Kette« oben im Agenten-Fenster zeigt, wer wen beauftragt hat, z. B.  "
             "koordinator → datenbank-analyst"),
    ("hinweis", "Genau so arbeitet der Harness mit einem echten LLM: Für jeden Agenten baut er einen eigenen "
                "Kontext (System-Prompt, Tools, Verlauf) – das sind hier die getrennten Fenster. Das LLM selbst "
                "»weiß« nicht, dass es gerade die Rolle gewechselt hat; es bekommt einfach einen anderen Kontext."),

    ("h2", "Was passiert nach deinem Tool-Wunsch?"),
    ("text", "Der Harness prüft in dieser Reihenfolge (siehe harness/harness.py, _fuehre_aus):\n"
             "  1. frage_mensch?           → Rückfrage an den Menschen\n"
             "  2. delegiere_an_…?         → anderer Agent startet (eigenes Fenster)\n"
             "  3. Tool in deiner Liste?   → wird über MCP ausgeführt\n"
             "  4. Tool mit Freigabe?      → erst den Menschen fragen, dann ausführen\n"
             "  5. alles andere            → BLOCKIERT: »Du hast keine Berechtigung …«\n\n"
             "Probier ruhig ein Tool aus, das nicht in deiner Liste steht. Du wirst sehen: Der Harness "
             "lässt sich nicht überreden."),

    ("h2", "Typische Stolpersteine"),
    ("text", "  list_tables()            → ohne »tool« ist das eine ENDANTWORT, der Agent ist sofort fertig\n"
             "  tool list_tables()       → keine Klammern hinter den Namen\n"
             "  tool describe_table noten        → Argumente immer als JSON mit Namen\n"
             "  {'table_name': 'noten'}  → JSON braucht doppelte Anführungszeichen\n"
             "  Zahlen erfinden          → jede Zahl in der Endantwort muss aus einem Tool-Ergebnis stammen"),

    ("h2", "Bedienung"),
    ("text", "  Gelber Rahmen     zeigt, wo gerade eine Eingabe erwartet wird\n"
             "  Enter             senden\n"
             "  Umschalt + Enter  neue Zeile (für längere Endantworten)\n"
             "  Tool-Knöpfe       Vorlage ins LLM-Feld einfügen\n"
             "  Klick auf ein Beispiel hier in der Hilfe  → landet im LLM-Feld des Agenten, der dran ist\n"
             "  ⏹ Abbrechen       (Hauptfenster) stoppt den Lauf – wie Strg+C im Terminal, Schnittstelle S4\n"
             "  Im Terminal läuft das ausführliche Protokoll des Harness mit."),
]


# ============================================================================
# Hilfsmittel für die zwei Threads
# ============================================================================
class LaufAbgebrochen(Exception):
    """Der Mensch hat auf ⏹ Abbrechen geklickt (Schnittstelle S4)."""


ABBRUCH = object()  # besonderer Wert in der Warteschlange _antworten: "bitte abbrechen"


# ============================================================================
# 2. FensterLLM – DU bist das Gehirn
# ============================================================================
class FensterLLM:
    """Gleiche Schnittstelle wie AnthropicLLM, OpenAIKompatibelLLM und MenschLLM (harness/llm.py):

        antworte(system, nachrichten, tools)  ->  {"text", "tool_calls", "verbrauch"}

    Wer ruft es auf?  Der Harness in jedem Schritt der Agenten-Schleife
    (harness.py: starte_agent -> self.llm.antworte). Das läuft im Harness-Thread.
    """

    def __init__(self, haupt: "HauptFenster"):
        self.name = "mensch im Chat-Fenster (du bist das LLM)"
        self.haupt = haupt
        self._gesehen = {}    # pro Agent: wie viele Nachrichten schon in seinem Fenster stehen
        self._letzter = None  # welcher Agent zuletzt dran war (wichtig bei Delegation)
        self._aufrufe = {}    # pro Agent: wievielter LLM-Aufruf das ist
        self._kette = []      # wer hat wen beauftragt, z. B. ["koordinator", "datenbank-analyst"]

    def antworte(self, system: str, nachrichten: list, tools: list) -> dict:
        h = self.haupt
        # Welcher Agent ist das? Der Harness schreibt es in den System-Prompt (harness.py: _system_prompt).
        treffer = re.search(r"Du bist der Agent '([^']+)'", system)
        agent = treffer.group(1) if treffer else "agent"

        # --- a) Wer bin ich gerade? ---
        # Du musst den Agenten NIE selbst wechseln. Das macht der Harness:
        #   delegiere_an_X  -> der Harness startet X, und du spielst ab jetzt X
        #   X antwortet mit Text (Endantwort) -> der Harness kehrt zum Auftraggeber zurück
        # Die Kette merkt sich, wer wen beauftragt hat. Delegation läuft verschachtelt
        # (erst wenn X fertig ist, geht es beim Auftraggeber weiter), darum reicht ein Stapel.
        if agent in self._kette:
            while self._kette[-1] != agent:
                self._kette.pop()           # Unteragenten sind fertig -> zurück nach oben
        else:
            self._kette.append(agent)       # neuer (Unter-)Agent

        if agent not in self._gesehen:
            art = "start" if self._letzter is None else "hin"
            self._gesehen[agent] = 0
            self._aufrufe[agent] = 0
        elif len(nachrichten) < self._gesehen[agent]:
            art = "neu"                     # Verlauf kürzer als vorhin -> Agent wurde neu gestartet
            self._gesehen[agent] = 0
        elif agent != self._letzter:
            art = "zurueck"                 # ein Unteragent ist fertig, der Auftraggeber macht weiter
        else:
            art = "weiter"                  # derselbe Agent ist wieder dran
        vorher = self._letzter
        self._letzter = agent
        self._aufrufe[agent] += 1

        # --- b) Nur die NEUEN Nachrichten an das Agenten-Fenster schicken ---
        neue = nachrichten[self._gesehen[agent]:]
        self._gesehen[agent] = len(nachrichten) + 1  # +1: deine Antwort gleich
        h.im_fenster(h.agent_ist_dran, agent, art, vorher, list(self._kette),
                     system, tools, self._aufrufe[agent], list(neue))

        # --- c) Auf deine Eingabe im Agenten-Fenster warten ---
        eingabe = h.warte_auf("llm", agent=agent)
        return als_llm_antwort(zerlege_llm_eingabe(eingabe))


# ============================================================================
# 3. FensterMensch – die Mensch-Maschine-Schnittstellen im Hauptfenster
# ============================================================================
class FensterMensch(Mensch):
    """Wie Mensch (harness/mensch.py), nur fragt es im Fenster statt mit input().

    S1 Auftrag   -> Feld »Mensch« im Hauptfenster (HauptFenster._mensch_senden)
    S2 Freigabe  -> Dialogfenster Ja/Nein          (freigabe)
    S3 Rückfrage -> Feld »Mensch« im Hauptfenster  (rueckfrage)
    S4 Abbruch   -> Knopf ⏹ Abbrechen
    S5 Ergebnis  -> Ergebnis-Blase im Hauptfenster (ergebnis_zeigen)

    Wer ruft es auf?  Der Harness (harness.py: _fuehre_aus), im Harness-Thread.
    """

    def __init__(self, protokoll, haupt: "HauptFenster", alles_erlauben: bool = False):
        super().__init__(protokoll, alles_erlauben)
        self.haupt = haupt

    # S2 ---------------------------------------------------------------
    def freigabe(self, agent: str, tool: str, argumente: dict, tiefe: int = 0) -> tuple[bool, str]:
        beschreibung = f"Agent '{agent}' möchte '{tool}' aufrufen mit {json.dumps(argumente, ensure_ascii=False)}"
        if self.alles_erlauben:
            self.protokoll.schreibe("HARNESS", f"Automatisch erlaubt (--alles-erlauben): {beschreibung}", tiefe)
            return True, ""
        self.protokoll.schreibe("HARNESS", f"⚠ FREIGABE NÖTIG: {beschreibung}", tiefe)

        h = self.haupt
        h.im_fenster(h.freigabe_dialog, agent, beschreibung)  # Dialog öffnet sich im Fenster-Thread …
        erlaubt, grund = h.warte_auf("freigabe")             # … und wir warten hier auf das Ergebnis
        if erlaubt:
            self.protokoll.schreibe("MENSCH", "Freigabe erteilt ✔", tiefe)
        else:
            self.protokoll.schreibe("MENSCH", f"Freigabe verweigert ✘ {grund}", tiefe)
        return erlaubt, grund

    # S3 ---------------------------------------------------------------
    def rueckfrage(self, agent: str, frage: str, tiefe: int = 0) -> str:
        self.protokoll.schreibe("AGENT", f"❓ {agent} fragt dich: {frage}", tiefe)
        antwort = self.haupt.warte_auf("mensch", hinweis=f"❓ {agent} fragt dich: {frage}", agent=agent)
        self.protokoll.schreibe("MENSCH", f"Antwort: {antwort}", tiefe)
        return antwort or "(keine Antwort)"

    # S5 ---------------------------------------------------------------
    def ergebnis_zeigen(self, text: str):
        h = self.haupt
        h.im_fenster(h.verlauf.blase, "links", "📋 Ergebnis für den Menschen (S5)", text, "ergebnis")


# ============================================================================
# 4. FensterProtokoll – Harness-Meldungen auch im Hauptfenster
# ============================================================================
class FensterProtokoll(Protokoll):
    """Schreibt wie gewohnt ins Terminal und in die JSONL-Datei (harness/protokoll.py)
    und zeigt die Meldungen zusätzlich als graue Zeilen im Hauptfenster.
    MENSCH-Meldungen nicht: Die stehen dort schon als Blasen."""

    def __init__(self, haupt: "HauptFenster"):
        super().__init__(ausfuehrlich=True)
        self.haupt = haupt

    def schreibe(self, wer, text, tiefe=0, daten=None, nur_datei=False):
        super().schreibe(wer, text, tiefe, daten, nur_datei)
        if nur_datei or wer == "MENSCH":
            return
        if wer == "HARNESS" and not self.haupt.harness_zeilen_zeigen:
            return
        self.haupt.im_fenster(self.haupt.verlauf.notiz, wer, str(text), tiefe)


# ============================================================================
# 5. Verlauf – ein Chat mit Sprechblasen
# ============================================================================
FARBEN = {
    "hintergrund": "#f4f4f6",
    "chat": "#ffffff",
    "mensch": "#f3e5f5",       # Mensch (lila, wie [MENSCH] im Terminal)
    "mensch_rand": "#8e24aa",
    "tool": "#e8f5e9",         # Tool-Ergebnisse vom Harness (grün, wie [MCP] im Terminal)
    "tool_rand": "#2e7d32",
    "auftrag": "#fff8e1",      # Auftrag an einen Agenten (gelb, wie [AGENT])
    "auftrag_rand": "#f9a825",
    "ergebnis": "#eceff1",
    "ergebnis_rand": "#37474f",
    "llm": "#e3f2fd",          # DU als LLM (blau, wie [LLM] im Terminal)
    "llm_rand": "#1565c0",
    "wechsel": "#fff3e0",      # Hinweis auf Wechsel zwischen Agenten (orange)
    "wechsel_rand": "#ef6c00",
    "aktiv": "#ffd54f",        # Rahmen um das Feld, in dem gerade eine Eingabe erwartet wird
    "inaktiv": "#d0d0d0",
    "ok": "#2e7d32",
    "warnung": "#e65100",
    "fehler": "#c62828",
    "grau": "#757575",
}
# Jedes Agenten-Fenster bekommt eine eigene Farbe für Kopfzeile und Rahmen
AGENTEN_FARBEN = ["#1565c0", "#6a1b9a", "#00838f", "#ad1457", "#5d4037", "#2e7d32"]

SCHRIFT = ("Segoe UI", 10)
SCHRIFT_FETT = ("Segoe UI", 10, "bold")
SCHRIFT_KLEIN = ("Segoe UI", 9)
MONO = ("Consolas", 10)


class Verlauf:
    """Ein Text-Feld, in das Sprechblasen (kleine Frames) eingebettet werden.

        blase(seite, ...)  links oder rechts eine Sprechblase
        notiz(wer, text)   kleine graue Zeile in der Mitte (Harness-Meldungen)
        kasten(titel, ...) auffälliger Hinweis in der Mitte (z. B. Agentenwechsel)
    """

    def __init__(self, eltern):
        self.rahmen = tk.Frame(eltern, bg=FARBEN["chat"])
        self.text = tk.Text(self.rahmen, bg=FARBEN["chat"], relief="flat", wrap="word",
                            state="disabled", cursor="arrow", padx=8, pady=8)
        rollbalken = tk.Scrollbar(self.rahmen, command=self.text.yview)
        self.text.configure(yscrollcommand=rollbalken.set)
        rollbalken.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        for seite in ("links", "rechts", "mitte"):
            self.text.tag_configure(seite, justify={"links": "left", "rechts": "right", "mitte": "center"}[seite])
        self.text.bind("<Configure>", self._umbruch_anpassen)
        self.blasen: list[tk.Label] = []   # Texte, die sich an die Breite anpassen (62 %)
        self.notizen: list[tk.Label] = []  # graue Zeilen (fast volle Breite)

    def blase(self, seite: str, titel: str, text: str, art: str, mono: bool = False):
        """Eine Sprechblase links oder rechts. art bestimmt die Farbe (siehe FARBEN)."""
        rahmen = tk.Frame(self.text, bg=FARBEN[art], highlightthickness=2,
                          highlightbackground=FARBEN[f"{art}_rand"], padx=10, pady=6)
        tk.Label(rahmen, text=titel, font=SCHRIFT_FETT, fg=FARBEN[f"{art}_rand"], bg=FARBEN[art],
                 anchor="w").pack(anchor="w")
        inhalt = tk.Label(rahmen, text=text, font=MONO if mono else SCHRIFT, bg=FARBEN[art],
                          justify="left", anchor="w", wraplength=self._blasen_breite())
        inhalt.pack(anchor="w")
        self.blasen.append(inhalt)
        for w in (rahmen, inhalt):
            w.bind("<Double-Button-1>", lambda e, t=text: self._kopieren(t))  # Doppelklick kopiert
        self._einfuegen(rahmen, seite, (rahmen, inhalt))

    def notiz(self, wer: str, text: str, tiefe: int = 0):
        """Eine kleine graue Zeile in der Mitte: Was macht der Harness gerade?"""
        farbe = {"FEHLER": FARBEN["fehler"], "AGENT": "#b07d00", "MCP": FARBEN["tool_rand"],
                 "LLM": FARBEN["llm_rand"]}.get(wer, FARBEN["grau"])
        einzeilig = " ".join(text.split())  # mehrzeilige Ergebnisse (JSON) zu einer Zeile zusammenziehen
        if len(einzeilig) > 160:
            einzeilig = einzeilig[:160] + " …"
        label = tk.Label(self.text, text=f"{'│ ' * tiefe}[{wer}] {einzeilig}", font=SCHRIFT_KLEIN, fg=farbe,
                         bg=FARBEN["chat"], wraplength=self._notiz_breite())
        self.notizen.append(label)
        self._einfuegen(label, "mitte", (label,), abstand=False)

    def kasten(self, titel: str, text: str, art: str = "wechsel"):
        """Ein auffälliger Kasten in der Mitte."""
        rahmen = tk.Frame(self.text, bg=FARBEN[art], highlightthickness=3,
                          highlightbackground=FARBEN[f"{art}_rand"], padx=14, pady=8)
        tk.Label(rahmen, text=titel, font=("Segoe UI", 11, "bold"), fg=FARBEN[f"{art}_rand"],
                 bg=FARBEN[art]).pack()
        inhalt = tk.Label(rahmen, text=text, font=SCHRIFT, bg=FARBEN[art], justify="center",
                          wraplength=self._blasen_breite())
        inhalt.pack()
        self.blasen.append(inhalt)
        self._einfuegen(rahmen, "mitte", (rahmen, inhalt))

    def leeren(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.blasen.clear()
        self.notizen.clear()

    # --- intern ---
    def _einfuegen(self, widget, seite: str, mausrad_widgets: tuple, abstand: bool = True):
        # Mausrad über der Blase soll den Chat rollen (sonst "schluckt" die Blase das Ereignis)
        for w in mausrad_widgets:
            w.bind("<MouseWheel>", lambda e: self.text.yview_scroll(int(-e.delta / 120), "units"))
        self.text.configure(state="normal")
        self.text.insert("end", "\n", seite)
        self.text.window_create("end", window=widget, padx=4, pady=4 if abstand else 0)
        self.text.tag_add(seite, "end-2c linestart", "end-1c")
        if abstand:
            self.text.insert("end", "\n", seite)
        self.text.configure(state="disabled")
        self._ans_ende_rollen()

    def _ans_ende_rollen(self):
        # Kurz warten, bis tkinter die neue Blase ausgemessen hat – sonst rollt es nicht ganz nach unten.
        def rollen():
            self.text.yview_moveto(1.0)
            self.text.xview_moveto(0)  # immer am linken Rand bleiben
        self.text.after(30, rollen)

    def _blasen_breite(self) -> int:
        return max(280, int(self.text.winfo_width() * 0.62))

    def _notiz_breite(self) -> int:
        return max(280, self.text.winfo_width() - 60)

    def _umbruch_anpassen(self, _ereignis=None):
        """Fenster wurde größer/kleiner -> Zeilenumbruch anpassen. Ohne Umbruch wäre eine lange
        Zeile breiter als der Chat, und er würde seitlich verrutschen."""
        for inhalt in self.blasen:
            inhalt.configure(wraplength=self._blasen_breite())
        for notiz in self.notizen:
            notiz.configure(wraplength=self._notiz_breite())

    def _kopieren(self, text: str):
        self.text.clipboard_clear()
        self.text.clipboard_append(text)


def tool_vorlage(tool: dict) -> str:
    """Baut aus dem Eingabe-Schema eines Tools eine Vorlage, z. B.
        tool describe_table {"table_name": ""}
    Texte werden "", Zahlen 0 – so sieht man gleich, was man ausfüllen muss."""
    eigenschaften = tool["input_schema"].get("properties", {})
    if not eigenschaften:
        return f"tool {tool['name']}"
    platzhalter = {"integer": 0, "number": 0.0, "boolean": False}
    werte = {name: platzhalter.get(info.get("type"), "") for name, info in eigenschaften.items()}
    return f"tool {tool['name']} {json.dumps(werte, ensure_ascii=False)}"


# ============================================================================
# 6. AgentFenster – ein Fenster pro Agent (das, was sein LLM sieht)
# ============================================================================
class AgentFenster:
    """Zeigt den Kontext EINES Agenten und nimmt deine Antwort als sein LLM entgegen.

    Wer ruft was auf?
        HauptFenster.agent_ist_dran  -> kontext_zeigen, nachrichten_zeigen, dran
        du (Enter / Senden)          -> _senden  -> Warteschlange -> Harness
    """

    def __init__(self, haupt: "HauptFenster", name: str, nummer: int):
        self.haupt = haupt
        self.name = name
        self.farbe = AGENTEN_FARBEN[nummer % len(AGENTEN_FARBEN)]
        self.tools: list[dict] = []
        self.tool_namen: set[str] = set()
        self.erster_auftrag_gezeigt = False

        self.fenster = tk.Toplevel(haupt.root)
        self.fenster.title(f"🤖 {name} – du bist das LLM")
        self.fenster.configure(bg=self.farbe)
        # Leicht versetzt zum Hauptfenster, jedes weitere Agenten-Fenster ein Stück weiter
        breite = min(1100, int(haupt.root.winfo_screenwidth() * 0.8))
        hoehe = min(760, int(haupt.root.winfo_screenheight() * 0.82))
        x = haupt.root.winfo_rootx() + 60 + 40 * nummer
        y = haupt.root.winfo_rooty() + 30 + 30 * nummer
        self.fenster.geometry(f"{breite}x{hoehe}+{x}+{y}")
        self.fenster.minsize(800, 520)
        # Schließen versteckt das Fenster nur – der Agent könnte ja noch einmal drankommen
        self.fenster.protocol("WM_DELETE_WINDOW", self.fenster.withdraw)

        innen = tk.Frame(self.fenster, bg=FARBEN["hintergrund"])
        innen.pack(fill="both", expand=True, padx=4, pady=4)  # farbiger Rand = Farbe des Agenten
        # Reihenfolge ist wichtig: Wird das Fenster zu klein, schneidet tkinter zuerst ab, was
        # ZULETZT eingepackt wurde. Darum kommt die Eingabe (unten) VOR dem Chat (Mitte):
        # So bleibt das Eingabefeld immer sichtbar, und nur der Chat wird kleiner.
        self._kopf_bauen(innen)
        self._eingabe_bauen(innen)
        self._mitte_bauen(innen)

    # --- Aufbau ---
    def _kopf_bauen(self, eltern):
        kopf = tk.Frame(eltern, bg=FARBEN["hintergrund"], padx=10, pady=6)
        kopf.pack(fill="x")
        tk.Label(kopf, text=f"🤖 {self.name}", font=("Segoe UI", 15, "bold"), fg=self.farbe,
                 bg=FARBEN["hintergrund"]).pack(side="left")
        tk.Button(kopf, text="❓ Hilfe", font=SCHRIFT_FETT, bg="#fff3cd", relief="groove",
                  command=self.haupt.hilfe_oeffnen).pack(side="right", padx=4)
        self.status = tk.Label(kopf, text="", font=SCHRIFT_FETT, bg=FARBEN["hintergrund"])
        self.status.pack(side="right", padx=10)
        self.kette_label = tk.Label(eltern, text="", font=SCHRIFT, fg=FARBEN["wechsel_rand"],
                                    bg=FARBEN["hintergrund"], anchor="w", padx=10)
        self.kette_label.pack(fill="x")

    def _mitte_bauen(self, eltern):
        mitte = tk.PanedWindow(eltern, orient="horizontal", sashwidth=6, bg=FARBEN["hintergrund"])
        mitte.pack(fill="both", expand=True, padx=8)

        links = tk.Frame(mitte, bg=FARBEN["chat"])
        spalten = tk.Frame(links, bg=FARBEN["chat"])
        spalten.pack(fill="x")
        tk.Label(spalten, text="📨 Auftrag  ·  🔧 Ergebnisse vom Harness", font=SCHRIFT_FETT,
                 fg=FARBEN["tool_rand"], bg=FARBEN["chat"]).pack(side="left", padx=10, pady=4)
        tk.Label(spalten, text=f"🤖 Du als {self.name}", font=SCHRIFT_FETT,
                 fg=FARBEN["llm_rand"], bg=FARBEN["chat"]).pack(side="right", padx=10, pady=4)
        self.verlauf = Verlauf(links)
        self.verlauf.rahmen.pack(fill="both", expand=True)
        mitte.add(links, stretch="always", minsize=420)

        seite = tk.Frame(mitte, bg=FARBEN["llm"], padx=10, pady=8)
        tk.Label(seite, text="🧠 Das sieht das LLM", font=("Segoe UI", 12, "bold"),
                 fg=FARBEN["llm_rand"], bg=FARBEN["llm"]).pack(anchor="w")
        self.kontext_titel = tk.Label(seite, text="", font=SCHRIFT, bg=FARBEN["llm"], justify="left", anchor="w")
        self.kontext_titel.pack(anchor="w", fill="x", pady=(2, 6))
        # Tools unten verankern und VOR dem System-Prompt einpacken: Bei wenig Platz wird der
        # System-Prompt kleiner (er hat einen Rollbalken), die Tool-Knöpfe bleiben sichtbar.
        self.tool_liste = tk.Frame(seite, bg=FARBEN["llm"])
        self.tool_liste.pack(side="bottom", fill="x", pady=(2, 0))
        tk.Label(seite, text="Deine Tools – Klick fügt eine Vorlage ein:", font=SCHRIFT_FETT,
                 bg=FARBEN["llm"]).pack(side="bottom", anchor="w")
        tk.Label(seite, text="System-Prompt (vom Harness gebaut):", font=SCHRIFT_FETT,
                 bg=FARBEN["llm"]).pack(anchor="w")
        system_rahmen = tk.Frame(seite, bg=FARBEN["llm"])
        system_rahmen.pack(fill="both", expand=True, pady=(2, 8))
        self.system_text = tk.Text(system_rahmen, height=4, wrap="word", font=SCHRIFT_KLEIN, relief="flat",
                                   state="disabled", bg="#f8fbff")
        system_rollbalken = tk.Scrollbar(system_rahmen, command=self.system_text.yview)
        self.system_text.configure(yscrollcommand=system_rollbalken.set)
        system_rollbalken.pack(side="right", fill="y")
        self.system_text.pack(fill="both", expand=True)
        mitte.add(seite, minsize=280, width=350)

    def _eingabe_bauen(self, eltern):
        self.llm_rahmen = tk.Frame(eltern, bg=FARBEN["llm"], highlightthickness=3,
                                   highlightbackground=FARBEN["inaktiv"], padx=8, pady=6)
        self.llm_rahmen.pack(side="bottom", fill="x", padx=8, pady=8)
        tk.Label(self.llm_rahmen, text=f"🤖 DEINE ANTWORT ALS LLM VON  {self.name}", font=("Segoe UI", 11, "bold"),
                 fg=FARBEN["llm_rand"], bg=FARBEN["llm"]).pack(anchor="w")
        tk.Label(self.llm_rahmen, text='tool NAME {"argument": "wert"}  →  Tool-Aufruf\n'
                                       "anderer Text  →  Endantwort (der Agent ist fertig)",
                 font=SCHRIFT_KLEIN, fg=FARBEN["grau"], bg=FARBEN["llm"], justify="left").pack(anchor="w")
        self.eingabe = tk.Text(self.llm_rahmen, height=4, wrap="word", font=MONO)
        self.eingabe.pack(fill="x", pady=4)
        self.eingabe.bind("<Return>", lambda e: self._senden() or "break")
        self.eingabe.bind("<KP_Enter>", lambda e: self._senden() or "break")
        # Umschalt+Enter: eigene Bindung, die nichts tut. Ohne sie würde <Return> oben auch hier greifen
        # und senden. So fügt tkinter ganz normal eine neue Zeile ein.
        self.eingabe.bind("<Shift-Return>", lambda e: None)
        self.eingabe.bind("<KeyRelease>", lambda e: self._erkennung_zeigen())

        zeile = tk.Frame(self.llm_rahmen, bg=FARBEN["llm"])
        zeile.pack(fill="x")
        self.erkennung = tk.Label(zeile, text="", font=SCHRIFT_FETT, bg=FARBEN["llm"], anchor="w",
                                  justify="left", wraplength=700)
        self.erkennung.pack(side="left", fill="x", expand=True)
        self.knopf = tk.Button(zeile, text="Senden ⏎", command=self._senden, state="disabled")
        self.knopf.pack(side="right")

    # --- Anzeige (aufgerufen vom HauptFenster) ---
    def kontext_zeigen(self, system: str, tools: list, aufruf: int, kette: list):
        self.kette_label.configure(text=("Kette: " + "  →  ".join(kette)) if len(kette) > 1
                                   else "direkt vom Menschen beauftragt")
        self.kontext_titel.configure(text=f"LLM-Aufruf Nr. {aufruf} für {self.name}")
        self.system_text.configure(state="normal")
        self.system_text.delete("1.0", "end")
        self.system_text.insert("1.0", system)
        self.system_text.configure(state="disabled")

        if [t["name"] for t in tools] == [t["name"] for t in self.tools]:
            return  # gleiche Tools wie vorher -> Knöpfe nicht neu bauen
        self.tools = tools
        self.tool_namen = {t["name"] for t in tools}
        for kind in self.tool_liste.winfo_children():
            kind.destroy()
        if not tools:
            tk.Label(self.tool_liste, text="(keine Tools – du kannst nur antworten)", bg=FARBEN["llm"],
                     font=SCHRIFT_KLEIN).pack(anchor="w")
        for t in tools:
            parameter = ", ".join(t["input_schema"].get("properties", {}).keys())
            tk.Button(self.tool_liste, text=f"{t['name']}({parameter})", font=MONO, anchor="w",
                      relief="groove", bg="white",
                      command=lambda t=t: self.vorlage_einfuegen(tool_vorlage(t))).pack(fill="x", pady=(4, 0))
            beschreibung = (t["description"] or "").strip().splitlines()
            tk.Label(self.tool_liste, text=beschreibung[0] if beschreibung else "", font=SCHRIFT_KLEIN,
                     fg=FARBEN["grau"], bg=FARBEN["llm"], wraplength=320, justify="left",
                     anchor="w").pack(fill="x")

    def nachrichten_zeigen(self, nachrichten: list, kette: list, erster_auftrag_vom_menschen: bool):
        """Die neuen Nachrichten aus dem Verlauf, den der Harness diesem Agenten schickt."""
        for n in nachrichten:
            if n["role"] == "user":
                von = kette[-2] if len(kette) > 1 else "dem Menschen"
                if erster_auftrag_vom_menschen:
                    von = "dem Menschen"
                self.verlauf.blase("links", f"📨 Auftrag von {von} an {self.name}", n["content"], "auftrag")
            elif n["role"] == "tool":
                text = n["content"]
                if len(text) > 3000:
                    text = text[:3000] + "\n… (gekürzt – das vollständige Ergebnis steht im Protokoll)"
                name = n["name"]
                if name.startswith("delegiere_an_"):
                    titel = f"🔧 Harness: Antwort von {name.removeprefix('delegiere_an_')} (Ergebnis von {name})"
                elif name == "frage_mensch":
                    titel = "🔧 Harness: Antwort des Menschen (Ergebnis von frage_mensch)"
                else:
                    titel = f"🔧 Harness: Ergebnis von {name}"
                self.verlauf.blase("links", titel, text, "tool", mono=True)
            # role "assistant" = deine eigenen Antworten -> stehen schon rechts im Chat

    def dran(self):
        """Du bist als dieser Agent dran: Fenster nach vorn, gelber Rahmen, Cursor ins Feld."""
        self.fenster.deiconify()
        self.fenster.lift()
        self.fenster.focus_force()
        self.llm_rahmen.configure(highlightbackground=FARBEN["aktiv"], highlightcolor=FARBEN["aktiv"])
        self.knopf.configure(state="normal")
        self.status.configure(text="🟡 Du bist dran", fg="#b07d00")
        self.eingabe.focus_set()
        self._erkennung_zeigen()

    def warten(self, text: str):
        """Dieser Agent wartet (auf den Harness, einen Unteragenten oder den Menschen)."""
        self.llm_rahmen.configure(highlightbackground=FARBEN["inaktiv"], highlightcolor=FARBEN["inaktiv"])
        self.knopf.configure(state="disabled")
        self.status.configure(text=text, fg=FARBEN["grau"])

    def neu_starten(self):
        """Der Agent wurde noch einmal beauftragt: neues, leeres Gedächtnis."""
        self.verlauf.leeren()
        self.verlauf.kasten("🔄 NEUES GEDÄCHTNIS",
                            f"{self.name} wurde noch einmal beauftragt. Der Harness startet ihn mit leerem "
                            f"Verlauf – er erinnert sich an nichts von vorhin!")

    # --- deine Eingabe ---
    def vorlage_einfuegen(self, vorlage: str):
        """Schreibt eine Vorlage ins LLM-Feld und setzt den Cursor in das erste leere "" (falls vorhanden)."""
        self.eingabe.delete("1.0", "end")
        self.eingabe.insert("1.0", vorlage)
        stelle = vorlage.find('""')
        if stelle >= 0:
            self.eingabe.mark_set("insert", f"1.0 + {stelle + 1} chars")
        self.eingabe.focus_set()
        self._erkennung_zeigen()

    def _senden(self):
        if not self.haupt.wartet_auf_llm(self.name):
            self.status.configure(text="Du bist gerade nicht dran.", fg=FARBEN["warnung"])
            return
        text = self.eingabe.get("1.0", "end").strip()
        if not text:
            return
        zerlegt = zerlege_llm_eingabe(text)
        if zerlegt["art"] == "fehler":
            messagebox.showwarning("Ungültige Eingabe", f"{zerlegt['meldung']}\n\nBeispiel:\n"
                                   'tool describe_table {"table_name": "noten"}', parent=self.fenster)
            return
        if zerlegt["art"] == "text" and self._sieht_aus_wie_tool(text):
            if not messagebox.askyesno(
                    "Wirklich Endantwort?",
                    "Deine Eingabe sieht aus wie ein Tool-Aufruf, beginnt aber nicht mit »tool«.\n\n"
                    "Der Harness behandelt sie deshalb als ENDANTWORT, und der Agent ist sofort fertig.\n\n"
                    "Trotzdem so senden?", parent=self.fenster):
                return

        self.eingabe.delete("1.0", "end")
        self._erkennung_zeigen()
        if zerlegt["art"] == "tool":
            anzeige = f"tool {zerlegt['name']}"
            if zerlegt["argumente"]:
                anzeige += " " + json.dumps(zerlegt["argumente"], ensure_ascii=False)
            self.verlauf.blase("rechts", f"🤖 Du als {self.name}: Tool-Wunsch an den Harness", anzeige, "llm",
                               mono=True)
            self.warten("⚙ Der Harness bearbeitet deinen Tool-Wunsch …")
        else:
            self.verlauf.blase("rechts", f"🤖 Du als {self.name}: Endantwort", text, "llm")
            self.warten("✔ fertig – Endantwort abgegeben")
        self.haupt.llm_hat_geantwortet(text)

    def _sieht_aus_wie_tool(self, text: str) -> bool:
        """Beginnt der Text mit einem Tool-Namen, z. B. "list_tables()" oder "{list_tables()}"?"""
        erstes_wort = re.split(r"[\s({]", text.lstrip("{[( "), maxsplit=1)[0]
        return erstes_wort in self.tool_namen

    def _erkennung_zeigen(self):
        """Zeigt schon beim Tippen, wie der Harness die Eingabe verstehen wird."""
        text = self.eingabe.get("1.0", "end").strip()
        if not text:
            self.erkennung.configure(text="", fg=FARBEN["grau"])
            return
        zerlegt = zerlege_llm_eingabe(text)
        if zerlegt["art"] == "fehler":
            self.erkennung.configure(text=f"✘ {zerlegt['meldung']}", fg=FARBEN["fehler"])
        elif zerlegt["art"] == "tool" and zerlegt["name"] not in self.tool_namen:
            self.erkennung.configure(
                text=f"⚠ TOOL-AUFRUF: »{zerlegt['name']}« steht nicht in deiner Liste – der Harness wird es blockieren.",
                fg=FARBEN["warnung"])
        elif zerlegt["art"] == "tool":
            self.erkennung.configure(text=f"✔ Wird erkannt als TOOL-AUFRUF: {zerlegt['name']}", fg=FARBEN["ok"])
        elif self._sieht_aus_wie_tool(text):
            self.erkennung.configure(
                text="⚠ Sieht aus wie ein Tool-Aufruf, beginnt aber nicht mit »tool« → wäre eine ENDANTWORT!",
                fg=FARBEN["warnung"])
        else:
            self.erkennung.configure(text="✔ Wird erkannt als ENDANTWORT – danach ist der Agent fertig.",
                                     fg=FARBEN["llm_rand"])

    def schliessen(self):
        self.fenster.destroy()


# ============================================================================
# 7. HauptFenster – Mensch & Harness
# ============================================================================
class HauptFenster:
    def __init__(self, root: tk.Tk, agent: str, auftrag: str | None, alles_erlauben: bool):
        self.root = root
        self.start_auftrag = auftrag

        # --- Verbindung zwischen den Threads (siehe Dateikopf) ---
        self._auftraege = queue.Queue()  # Harness -> Fenster
        self._antworten = queue.Queue()  # Fenster -> Harness
        self._warte_auf = None           # worauf wartet der Harness? ("llm", agent) | ("mensch", agent) | None
        self.lauf_aktiv = False
        self.harness_zeilen_zeigen = True  # normale Variable, damit der Harness-Thread sie lesen darf

        self.agenten: dict[str, AgentFenster] = {}  # ein Fenster pro Agent
        self.aktiver_agent: str | None = None
        self.weg_datei = None
        self.hilfe_fenster = None

        root.title("LLM spielen – Mensch & Harness")
        breite = min(1000, int(root.winfo_screenwidth() * 0.75))
        hoehe = min(760, int(root.winfo_screenheight() * 0.82))
        root.geometry(f"{breite}x{hoehe}+20+20")
        root.minsize(760, 500)
        root.configure(bg=FARBEN["hintergrund"])

        # Unten VOR der Mitte einpacken, damit das Mensch-Feld bei kleinem Fenster sichtbar bleibt
        self._oben_bauen(alles_erlauben)
        self._unten_bauen(agent)
        self._mitte_bauen()

        root.protocol("WM_DELETE_WINDOW", self._schliessen)
        root.after(50, self._auftraege_abarbeiten)
        self._bereit_fuer_neuen_lauf()

    # ------------------------------------------------------------------
    # Aufbau der Oberfläche
    # ------------------------------------------------------------------
    def _oben_bauen(self, alles_erlauben: bool):
        leiste = tk.Frame(self.root, bg=FARBEN["hintergrund"], pady=6, padx=10)
        leiste.pack(fill="x")
        tk.Label(leiste, text="👤 Mensch  ·  ⚙ Harness", font=("Segoe UI", 13, "bold"),
                 fg=FARBEN["mensch_rand"], bg=FARBEN["hintergrund"]).pack(side="left")

        tk.Button(leiste, text="❓ Hilfe: So spielst du das LLM", font=SCHRIFT_FETT, bg="#fff3cd",
                  relief="groove", padx=10, command=self.hilfe_oeffnen).pack(side="right", padx=4)
        self.knopf_neu = tk.Button(leiste, text="↻ Neuer Lauf", command=self._neuer_lauf, relief="groove")
        self.knopf_neu.pack(side="right", padx=4)
        self.knopf_abbruch = tk.Button(leiste, text="⏹ Abbrechen", command=self._abbrechen, relief="groove")
        self.knopf_abbruch.pack(side="right", padx=4)
        self.knopf_weg = tk.Button(leiste, text="🗺 Weg anzeigen", command=self._weg_oeffnen, relief="groove")
        self.knopf_weg.pack(side="right", padx=4)

        zeile2 = tk.Frame(self.root, bg=FARBEN["hintergrund"], padx=10)
        zeile2.pack(fill="x")
        tk.Label(zeile2, text="Die Agenten (= du als LLM) bekommen eigene Fenster.", font=SCHRIFT_KLEIN,
                 fg=FARBEN["grau"], bg=FARBEN["hintergrund"]).pack(side="left")
        self.alles_erlauben = tk.BooleanVar(value=alles_erlauben)
        tk.Checkbutton(zeile2, text="Alles erlauben (keine Freigaben)", variable=self.alles_erlauben,
                       bg=FARBEN["hintergrund"]).pack(side="right", padx=8)
        self.zeilen_var = tk.BooleanVar(value=True)
        tk.Checkbutton(zeile2, text="Harness-Meldungen anzeigen", variable=self.zeilen_var,
                       bg=FARBEN["hintergrund"], command=self._zeilen_umschalten).pack(side="right", padx=8)

    def _mitte_bauen(self):
        self.verlauf = Verlauf(self.root)
        self.verlauf.rahmen.pack(fill="both", expand=True, padx=10, pady=(6, 0))

    def _unten_bauen(self, agent: str):
        # Beide unten verankert: zuerst die Statuszeile (ganz unten), darüber das Mensch-Feld
        self.status = tk.Label(self.root, text="", anchor="w", font=SCHRIFT_KLEIN, fg=FARBEN["grau"],
                               bg=FARBEN["hintergrund"], padx=10)
        self.status.pack(side="bottom", fill="x", pady=(0, 4))

        self.mensch_rahmen = tk.Frame(self.root, bg=FARBEN["mensch"], highlightthickness=3,
                                      highlightbackground=FARBEN["inaktiv"], padx=8, pady=6)
        self.mensch_rahmen.pack(side="bottom", fill="x", padx=10, pady=8)
        tk.Label(self.mensch_rahmen, text="👤 MENSCH", font=("Segoe UI", 11, "bold"),
                 fg=FARBEN["mensch_rand"], bg=FARBEN["mensch"]).pack(anchor="w")

        # S1: An welchen Agenten geht der Auftrag? (Nur vor dem Lauf wählbar.)
        zeile = tk.Frame(self.mensch_rahmen, bg=FARBEN["mensch"])
        zeile.pack(fill="x", pady=(2, 0))
        tk.Label(zeile, text="Auftrag an:", font=SCHRIFT_FETT, bg=FARBEN["mensch"]).pack(side="left")
        self.agent_wahl = ttk.Combobox(zeile, values=alle_definitionen(), state="readonly", width=18)
        self.agent_wahl.set(agent)
        self.agent_wahl.pack(side="left", padx=(4, 8))
        self.agent_wahl.bind("<<ComboboxSelected>>", lambda e: self._agent_info_zeigen())
        self.agent_info = tk.Label(zeile, text="", font=SCHRIFT_KLEIN, fg=FARBEN["grau"], bg=FARBEN["mensch"],
                                   anchor="w", justify="left", wraplength=560)
        self.agent_info.pack(side="left", fill="x")
        self._agent_info_zeigen()

        self.mensch_hinweis = tk.Label(self.mensch_rahmen, text="", font=SCHRIFT, bg=FARBEN["mensch"],
                                       justify="left", anchor="w", wraplength=800)
        self.mensch_hinweis.pack(anchor="w", fill="x")
        self.mensch_eingabe = tk.Text(self.mensch_rahmen, height=3, wrap="word", font=SCHRIFT)
        self.mensch_eingabe.pack(fill="x", pady=4)
        self.mensch_eingabe.bind("<Return>", lambda e: self._mensch_senden() or "break")
        self.mensch_eingabe.bind("<KP_Enter>", lambda e: self._mensch_senden() or "break")
        self.mensch_eingabe.bind("<Shift-Return>", lambda e: None)  # Umschalt+Enter = neue Zeile
        self.mensch_knopf = tk.Button(self.mensch_rahmen, text="Senden ⏎", command=self._mensch_senden)
        self.mensch_knopf.pack(anchor="e")

    # ------------------------------------------------------------------
    # Verbindung Harness-Thread <-> Fenster-Thread
    # ------------------------------------------------------------------
    def im_fenster(self, funktion, *argumente):
        """Vom HARNESS-Thread aus aufrufen: "Führe das bitte im Fenster-Thread aus."
        (tkinter darf nur aus dem Thread bedient werden, der die Fenster gebaut hat.)"""
        self._auftraege.put((funktion, argumente))

    def _auftraege_abarbeiten(self):
        """Läuft im FENSTER-Thread alle 50 ms und erledigt, was der Harness bestellt hat."""
        try:
            while True:
                funktion, argumente = self._auftraege.get_nowait()
                funktion(*argumente)
        except queue.Empty:
            pass
        self.root.after(50, self._auftraege_abarbeiten)

    def warte_auf(self, seite: str, hinweis: str = "", agent: str | None = None):
        """Vom HARNESS-Thread aus aufrufen: Eingabe freischalten und warten, bis sie kommt.

        seite = "llm"      -> Agenten-Fenster von agent (du als LLM)
                "mensch"   -> Feld »Mensch« im Hauptfenster (Rückfrage)
                "freigabe" -> es ist schon ein Ja/Nein-Dialog offen
        """
        if seite == "llm":
            self.im_fenster(self._llm_freischalten, agent)
        elif seite == "mensch":
            self.im_fenster(self._mensch_freischalten, hinweis, agent)
        antwort = self._antworten.get()  # <- Hier wartet der Harness-Thread.
        if antwort is ABBRUCH:
            raise LaufAbgebrochen()
        return antwort

    def wartet_auf_llm(self, agent: str) -> bool:
        return self._warte_auf == ("llm", agent)

    def llm_hat_geantwortet(self, text: str):
        """Ein Agenten-Fenster meldet deine Antwort -> weiter an den Harness."""
        self._warte_auf = None
        self._status("⚙ Der Harness arbeitet …")
        self._antworten.put(text)

    # ------------------------------------------------------------------
    # Der Lauf (im Harness-Thread)
    # ------------------------------------------------------------------
    def _lauf_starten(self, auftrag: str):
        agent = self.agent_wahl.get()
        self.lauf_aktiv = True
        self._antworten = queue.Queue()  # frische Warteschlange, damit kein alter Abbruch übrig ist
        self.weg_datei = None
        self.agent_wahl.configure(state="disabled")
        self.knopf_abbruch.configure(state="normal")
        self.knopf_neu.configure(state="disabled")
        self.knopf_weg.configure(state="disabled")
        self._mensch_sperren()
        self._status("⚙ Der Harness startet den MCP-Server (src/index.py) …")
        threading.Thread(target=self._lauf_thread, args=(agent, auftrag, self.alles_erlauben.get()),
                         daemon=True).start()

    def _lauf_thread(self, agent: str, auftrag: str, alles_erlauben: bool):
        try:
            asyncio.run(self._lauf(agent, auftrag, alles_erlauben))
        except LaufAbgebrochen:
            self.im_fenster(self.verlauf.notiz, "FEHLER", "⏹ Abbruch durch den Menschen (S4) – der Agent wurde gestoppt.")
        except Exception as e:  # z. B. MCP-Server startet nicht
            self.im_fenster(self.verlauf.notiz, "FEHLER", f"Fehler: {e}")
        finally:
            self.im_fenster(self._lauf_beendet)

    async def _lauf(self, agent: str, auftrag: str, alles_erlauben: bool):
        """Dasselbe wie main() in agent.py – nur mit den Fenster-Bausteinen."""
        protokoll = FensterProtokoll(self)
        mensch = FensterMensch(protokoll, self, alles_erlauben)
        llm = FensterLLM(self)
        protokoll.schreibe("MENSCH", f"Auftrag: {auftrag}")
        protokoll.schreibe("HARNESS", "Starte MCP-Server (src/index.py) und frage seine Tools ab (tools/list) …")
        async with MCPBruecke() as mcp:
            protokoll.schreibe("MCP", f"Server bietet an: {', '.join(t['name'] for t in mcp.tools)}")
            harness = Harness(llm, mcp, mensch, protokoll)
            try:
                ergebnis = await harness.starte_agent(agent, auftrag)   # die Agenten-Schleife
                mensch.ergebnis_zeigen(ergebnis)
            finally:
                self.weg_datei = harness.weg.speichern(protokoll.datei)
                self.im_fenster(self.verlauf.notiz, "HARNESS", f"Protokoll: {protokoll.datei}")

    # ------------------------------------------------------------------
    # Ein Agent ist dran (aufgerufen über die Warteschlange von FensterLLM)
    # ------------------------------------------------------------------
    def agent_ist_dran(self, agent: str, art: str, vorher: str | None, kette: list,
                       system: str, tools: list, aufruf: int, neue_nachrichten: list):
        """art: "start" (erster Agent), "hin" (neuer Unteragent), "zurueck" (Unteragent fertig),
                "neu" (Agent wird noch einmal beauftragt), "weiter" (derselbe Agent ist wieder dran)"""
        neues_fenster = agent not in self.agenten
        if neues_fenster:
            self.agenten[agent] = AgentFenster(self, agent, len(self.agenten))
        fenster = self.agenten[agent]

        # Andere Fenster und das Hauptfenster über den Wechsel informieren
        if art == "hin":
            self.agenten[vorher].warten(f"⏳ wartet auf {agent}")
            self.agenten[vorher].verlauf.kasten(
                f"⏳ Du hast an {agent} delegiert",
                f"Der Harness hat {agent} gestartet – in einem eigenen Fenster.\n"
                f"Dieses Fenster wartet, bis {agent} fertig ist. Dann geht es hier weiter.")
            self.verlauf.kasten(f"🔀 Harness startet {agent}",
                                f"Auftrag von {vorher}. {agent} bekommt ein eigenes Fenster mit eigenem Kontext.\n"
                                f"Kette: {'  →  '.join(kette)}")
        elif art == "neu":
            if vorher in self.agenten and vorher != agent:
                self.agenten[vorher].warten(f"⏳ wartet auf {agent}")
            fenster.neu_starten()
            self.verlauf.kasten(f"🔀 Harness startet {agent} NEU",
                                f"Auftrag von {kette[-2] if len(kette) > 1 else 'dem Menschen'}. "
                                f"Sein Fenster wird geleert: neues Gedächtnis.")
        elif art == "zurueck":
            if vorher in self.agenten:
                self.agenten[vorher].warten("✔ fertig – Endantwort abgegeben")
            fenster.verlauf.kasten(f"🔙 Zurück bei {agent}",
                                   f"{vorher} ist fertig. Seine Endantwort steht gleich unten als Tool-Ergebnis.")
            self.verlauf.kasten(f"🔙 {vorher} ist fertig – zurück zu {agent}", f"Kette: {'  →  '.join(kette)}")
        elif art == "start":
            self.verlauf.kasten(f"▶ Harness startet {agent}",
                                f"{agent} bekommt ein eigenes Fenster. Dort spielst du sein LLM.")

        fenster.kontext_zeigen(system, tools, aufruf, kette)
        fenster.nachrichten_zeigen(neue_nachrichten, kette, erster_auftrag_vom_menschen=(art == "start"))
        self.aktiver_agent = agent

    def _llm_freischalten(self, agent: str):
        self._warte_auf = ("llm", agent)
        self._mensch_sperren()
        self.agenten[agent].dran()
        self._status(f"🤖 Du bist dran – als LLM von {agent} (in seinem Fenster).")

    # ------------------------------------------------------------------
    # Der Mensch (Hauptfenster)
    # ------------------------------------------------------------------
    def _mensch_freischalten(self, hinweis: str = "", agent: str | None = None):
        if hinweis:
            self._warte_auf = ("mensch", agent)
            if agent in self.agenten:
                self.agenten[agent].warten("⏳ wartet auf den Menschen (Hauptfenster)")
            # Hauptfenster nach vorn: Jetzt ist der Mensch dran, nicht das LLM
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        self.mensch_rahmen.configure(highlightbackground=FARBEN["aktiv"], highlightcolor=FARBEN["aktiv"])
        self.mensch_knopf.configure(state="normal")
        self.mensch_hinweis.configure(text=hinweis or "Schreibe deinen Auftrag an den Agenten.")
        self.mensch_eingabe.focus_set()
        self._status("👤 Der Mensch ist dran (Feld unten).")

    def _mensch_sperren(self):
        self.mensch_rahmen.configure(highlightbackground=FARBEN["inaktiv"], highlightcolor=FARBEN["inaktiv"])
        self.mensch_knopf.configure(state="disabled")
        self.mensch_hinweis.configure(text="")

    def _mensch_senden(self):
        text = self.mensch_eingabe.get("1.0", "end").strip()
        if not text:
            return
        if not self.lauf_aktiv:                                    # S1: neuer Auftrag
            self.mensch_eingabe.delete("1.0", "end")
            self._agenten_fenster_schliessen()
            self.verlauf.blase("links", "👤 Mensch: Auftrag", text, "mensch")
            self._lauf_starten(text)
        elif self._warte_auf and self._warte_auf[0] == "mensch":  # S3: Antwort auf eine Rückfrage
            self.mensch_eingabe.delete("1.0", "end")
            self.verlauf.blase("links", "👤 Mensch: Antwort auf die Rückfrage", text, "mensch")
            self._warte_auf = None
            self._mensch_sperren()
            self._status("⚙ Der Harness gibt die Antwort an das LLM weiter …")
            self._antworten.put(text)
        else:
            self._status("Der Mensch ist gerade nicht dran. Achte auf den gelben Rahmen.")

    def freigabe_dialog(self, agent: str, beschreibung: str):
        """S2: Ja/Nein-Dialog. Das Ergebnis geht über die Warteschlange zurück an den Harness."""
        if agent in self.agenten:
            self.agenten[agent].warten("⏳ wartet auf die Freigabe des Menschen")
        self.root.deiconify()
        self.root.lift()
        self._status("⚠ Der Harness fragt den Menschen um Erlaubnis …")
        erlaubt = messagebox.askyesno(
            "Freigabe nötig (S2)", f"{beschreibung}\n\nDieser Aufruf verändert Daten. Erlauben?",
            icon="warning", parent=self.root)
        grund = ""
        if not erlaubt:
            grund = simpledialog.askstring("Begründung", "Begründung für den Agenten (optional):",
                                           parent=self.root) or ""
        text = "Freigabe erteilt ✔" if erlaubt else f"Freigabe verweigert ✘ {grund}".strip()
        self.verlauf.blase("links", "👤 Mensch: Freigabe (S2)", text, "mensch")
        self._status("⚙ Der Harness macht weiter …")
        self._antworten.put((erlaubt, grund))

    # ------------------------------------------------------------------
    # Hilfe-Fenster
    # ------------------------------------------------------------------
    def hilfe_oeffnen(self):
        if self.hilfe_fenster and self.hilfe_fenster.winfo_exists():
            self.hilfe_fenster.destroy()  # neu aufbauen, damit "Deine Tools" aktuell ist
        fenster = tk.Toplevel(self.root)
        fenster.title("Hilfe – So spielst du das LLM")
        fenster.geometry(f"820x{min(760, int(self.root.winfo_screenheight() * 0.82))}")
        self.hilfe_fenster = fenster

        text = tk.Text(fenster, wrap="word", font=SCHRIFT, padx=16, pady=12, relief="flat")
        rollbalken = tk.Scrollbar(fenster, command=text.yview)
        text.configure(yscrollcommand=rollbalken.set)
        rollbalken.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)

        text.tag_configure("h1", font=("Segoe UI", 16, "bold"), foreground=FARBEN["llm_rand"], spacing3=8)
        text.tag_configure("h2", font=("Segoe UI", 12, "bold"), foreground=FARBEN["llm_rand"],
                           spacing1=14, spacing3=4)
        text.tag_configure("text", spacing3=4)
        text.tag_configure("code", font=MONO, background="#eef3fb", lmargin1=16, lmargin2=16,
                           spacing1=2, spacing3=2)
        text.tag_configure("hinweis", background="#fff8e1", lmargin1=8, lmargin2=8, spacing1=6, spacing3=6)

        for nummer, (art, inhalt) in enumerate(HILFE + self._hilfe_eigene_tools()):
            if art == "code":
                marke = f"code{nummer}"  # eigene Marke pro Zeile, damit jeder Klick weiß, was er einfügt
                text.insert("end", inhalt + "\n", ("code", marke))
                text.tag_bind(marke, "<Button-1>", lambda e, c=inhalt: self._beispiel_einfuegen(c))
                text.tag_bind(marke, "<Enter>", lambda e: text.configure(cursor="hand2"))
                text.tag_bind(marke, "<Leave>", lambda e: text.configure(cursor=""))
            elif art == "hinweis":
                text.insert("end", "💡 " + inhalt + "\n", "hinweis")
            else:
                text.insert("end", inhalt + "\n", art)
        text.configure(state="disabled")

    def _beispiel_einfuegen(self, code: str):
        if self.aktiver_agent in self.agenten:
            fenster = self.agenten[self.aktiver_agent]
            fenster.vorlage_einfuegen(code)
            fenster.fenster.lift()
            self._status(f"Beispiel ins LLM-Feld von {self.aktiver_agent} übernommen.")
        else:
            self._status("Starte zuerst einen Lauf – dann landet das Beispiel im LLM-Feld des Agenten.")

    def _hilfe_eigene_tools(self) -> list:
        """Zusätzlicher Abschnitt in der Hilfe: die Tools des Agenten, den du gerade spielst."""
        fenster = self.agenten.get(self.aktiver_agent)
        if not fenster or not fenster.tools:
            return [("h2", "Deine Tools in diesem Lauf"),
                    ("text", "Sobald ein Lauf gestartet ist, stehen hier die Tools des Agenten, den du gerade "
                             "spielst, mit ihrer vollständigen Beschreibung. Öffne die Hilfe dann einfach noch einmal.")]
        abschnitt = [("h2", f"Deine Tools als {fenster.name} (vollständige Beschreibung)")]
        for t in fenster.tools:
            schema = t["input_schema"].get("properties", {})
            argumente = "\n".join(f"      {name}: {info.get('type', '?')}"
                                  + (f" – {info['description']}" if info.get("description") else "")
                                  for name, info in schema.items()) or "      (keine Argumente)"
            abschnitt += [("text", f"\n{t['name']}\n{(t['description'] or '').strip()}\n   Argumente:\n{argumente}"),
                          ("code", tool_vorlage(t))]
        return abschnitt

    # ------------------------------------------------------------------
    # Knöpfe oben
    # ------------------------------------------------------------------
    def _agent_info_zeigen(self):
        try:
            self.agent_info.configure(text=lade_definition(self.agent_wahl.get()).beschreibung)
        except Exception:
            self.agent_info.configure(text="")

    def _zeilen_umschalten(self):
        self.harness_zeilen_zeigen = self.zeilen_var.get()

    def _abbrechen(self):
        """S4: Abbruch durch den Menschen. Der Harness bricht ab, sobald er das nächste Mal wartet."""
        if self.lauf_aktiv:
            self._antworten.put(ABBRUCH)
            self._status("⏹ Abbruch angefordert …")

    def _lauf_beendet(self):
        self.lauf_aktiv = False
        self._warte_auf = None
        for fenster in self.agenten.values():
            if not fenster.status.cget("text").startswith("✔"):  # wer nicht fertig wurde (z. B. Abbruch)
                fenster.warten("■ Lauf beendet")
        self.knopf_abbruch.configure(state="disabled")
        self.knopf_neu.configure(state="normal")
        self.knopf_weg.configure(state="normal" if self.weg_datei else "disabled")
        self.agent_wahl.configure(state="readonly")
        self.root.deiconify()
        self.root.lift()
        self._mensch_freischalten()
        self.mensch_hinweis.configure(text="Neuer Auftrag? Einfach hier eintippen (die Agenten-Fenster werden "
                                           "dann geschlossen) oder oben ↻ Neuer Lauf für einen leeren Chat.")
        self._status("Lauf beendet. 🗺 Weg anzeigen zeigt den Weg des Laufs als Diagramm.")

    def _neuer_lauf(self):
        if self.lauf_aktiv:
            return
        self.verlauf.leeren()
        self._agenten_fenster_schliessen()
        self._bereit_fuer_neuen_lauf()

    def _agenten_fenster_schliessen(self):
        for fenster in self.agenten.values():
            fenster.schliessen()
        self.agenten.clear()
        self.aktiver_agent = None

    def _bereit_fuer_neuen_lauf(self):
        self.weg_datei = None
        self.knopf_abbruch.configure(state="disabled")
        self.knopf_weg.configure(state="disabled")
        self.verlauf.kasten("Willkommen!",
                            "Wähle unten, an welchen Agenten dein Auftrag geht, und schreibe ihn darunter.\n"
                            "Für jeden Agenten öffnet sich dann ein eigenes Fenster – dort spielst du sein LLM.\n"
                            "❓ Hilfe erklärt alles mit Beispielen.", art="ergebnis")
        self._mensch_freischalten()
        if self.start_auftrag:  # Auftrag von der Kommandozeile
            self.mensch_eingabe.insert("1.0", self.start_auftrag)
            self.start_auftrag = None
            self._mensch_senden()

    def _weg_oeffnen(self):
        if self.weg_datei:
            webbrowser.open(Path(self.weg_datei).as_uri())

    def _status(self, text: str):
        self.status.configure(text=text)

    def _schliessen(self):
        if self.lauf_aktiv:
            self._antworten.put(ABBRUCH)
        self.root.destroy()


# ============================================================================
# 8. Start
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Du spielst das LLM – in Chat-Fenstern")
    parser.add_argument("auftrag", nargs="?", help="Auftrag an den Agenten (sonst im Fenster eintippen)")
    parser.add_argument("--agent", default="datenbank-analyst", help="an welchen Agenten der Auftrag geht (Name der Definitionsdatei ohne .md)")
    parser.add_argument("--alles-erlauben", action="store_true",
                        help="Keine Freigaben abfragen (lässt sich auch im Fenster umschalten)")
    args = parser.parse_args()

    if args.agent not in alle_definitionen():
        print(f"Unbekannter Agent '{args.agent}'. Vorhanden: {', '.join(alle_definitionen())}")
        sys.exit(1)

    root = tk.Tk()
    HauptFenster(root, args.agent, args.auftrag, args.alles_erlauben)
    root.mainloop()


if __name__ == "__main__":
    main()
