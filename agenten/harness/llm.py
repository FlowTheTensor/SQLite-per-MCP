"""
LLM-Adapter – die Verbindung zum Sprachmodell.

WICHTIG FÜR DAS VERSTÄNDNIS:
Ein LLM ist (von außen betrachtet) nur eine Funktion:

        Text + Toolliste  ──►  LLM  ──►  Text  ODER  Wunsch nach einem Tool-Aufruf

Das LLM führt NIE selbst ein Tool aus. Es schreibt nur auf, welches Tool es
gerne mit welchen Argumenten aufrufen würde. Ausführen tut das der Harness.

Hier gibt es drei austauschbare "Gehirne":

    AnthropicLLM   – Claude über die Anthropic-API (API-Key nötig)
    OpenAIKompatibelLLM – alles, was die OpenAI-Schnittstelle spricht:
                     Ollama (lokal & kostenlos), LM Studio, OpenAI, ...
    MenschLLM      – DU spielst das Sprachmodell! Du siehst genau das, was
                     ein LLM sehen würde, und tippst die Antwort selbst.

Alle drei verwenden dasselbe neutrale Nachrichtenformat (siehe unten), damit
der Harness nicht wissen muss, welches Modell dahintersteckt.

Neutrales Nachrichtenformat
---------------------------
    {"role": "user",      "content": "Frage des Menschen"}
    {"role": "assistant", "text": "...", "tool_calls": [{"id": "...", "name": "...", "arguments": {...}}]}
    {"role": "tool",      "tool_call_id": "...", "name": "...", "content": "Ergebnis als Text"}

Neutrales Tool-Format
---------------------
    {"name": "query_database", "description": "...", "input_schema": {JSON-Schema}}

Antwort jedes Adapters
----------------------
    {"text": "...", "tool_calls": [...], "verbrauch": {"eingabe": int, "ausgabe": int}}
"""

import json
import os
import re
import urllib.error
import urllib.request
import uuid


def _http_post(url: str, daten: dict, kopfzeilen: dict) -> dict:
    """Schickt JSON per HTTP POST und liefert die JSON-Antwort.
    (Ja – ein LLM-Aufruf ist am Ende nur eine HTTP-Anfrage.)"""
    anfrage = urllib.request.Request(
        url,
        data=json.dumps(daten).encode("utf-8"),
        headers={"content-type": "application/json", **kopfzeilen},
        method="POST",
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=300) as antwort:
            return json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP-Fehler {e.code} von {url}: {text}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Keine Verbindung zu {url}: {e.reason}") from None


# ---------------------------------------------------------------------------
# 1) Claude über die Anthropic-API
# ---------------------------------------------------------------------------
class AnthropicLLM:
    def __init__(self, modell: str | None = None):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Kein ANTHROPIC_API_KEY gesetzt.\n"
                "PowerShell:  $env:ANTHROPIC_API_KEY = \"sk-ant-...\"\n"
                "Alternativ:  --modell ollama   oder   --modell mensch"
            )
        self.modell = modell or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
        self.basis_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
        self.name = f"anthropic/{self.modell}"

    def antworte(self, system: str, nachrichten: list, tools: list) -> dict:
        daten = {
            "model": self.modell,
            "max_tokens": 2048,
            "system": system,
            "messages": self._umwandeln(nachrichten),
        }
        if tools:
            daten["tools"] = [
                {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
                for t in tools
            ]
        roh = _http_post(
            f"{self.basis_url}/v1/messages",
            daten,
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
        )
        text, aufrufe = [], []
        for block in roh.get("content", []):
            if block["type"] == "text":
                text.append(block["text"])
            elif block["type"] == "tool_use":
                aufrufe.append({"id": block["id"], "name": block["name"], "arguments": block["input"]})
        nutzung = roh.get("usage", {})
        return {
            "text": "\n".join(text),
            "tool_calls": aufrufe,
            "verbrauch": {"eingabe": nutzung.get("input_tokens", 0), "ausgabe": nutzung.get("output_tokens", 0)},
        }

    @staticmethod
    def _umwandeln(nachrichten: list) -> list:
        """Neutrales Format -> Anthropic-Format (Tool-Ergebnisse sind dort 'user'-Nachrichten)."""
        ergebnis = []
        for n in nachrichten:
            if n["role"] == "user":
                ergebnis.append({"role": "user", "content": n["content"]})
            elif n["role"] == "assistant":
                bloecke = []
                if n.get("text"):
                    bloecke.append({"type": "text", "text": n["text"]})
                for a in n.get("tool_calls", []):
                    bloecke.append({"type": "tool_use", "id": a["id"], "name": a["name"], "input": a["arguments"]})
                ergebnis.append({"role": "assistant", "content": bloecke or [{"type": "text", "text": "…"}]})
            elif n["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": n["tool_call_id"], "content": n["content"]}
                # Mehrere Tool-Ergebnisse hintereinander gehören in EINE user-Nachricht
                if ergebnis and ergebnis[-1]["role"] == "user" and isinstance(ergebnis[-1]["content"], list):
                    ergebnis[-1]["content"].append(block)
                else:
                    ergebnis.append({"role": "user", "content": [block]})
        return ergebnis


# ---------------------------------------------------------------------------
# 2) Alles mit OpenAI-kompatibler Schnittstelle (Standard: lokales Ollama)
# ---------------------------------------------------------------------------
class OpenAIKompatibelLLM:
    def __init__(self, modell: str | None = None, basis_url: str | None = None):
        self.basis_url = (basis_url or os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")).rstrip("/")
        self.modell = modell or os.environ.get("OPENAI_MODEL", "qwen2.5:7b")
        self.api_key = os.environ.get("OPENAI_API_KEY", "ollama")  # Ollama ignoriert den Key
        self.name = f"openai-kompatibel/{self.modell} @ {self.basis_url}"

    def antworte(self, system: str, nachrichten: list, tools: list) -> dict:
        daten = {
            "model": self.modell,
            "messages": [{"role": "system", "content": system}] + self._umwandeln(nachrichten),
        }
        if tools:
            daten["tools"] = [
                {"type": "function",
                 "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
                for t in tools
            ]
        roh = _http_post(f"{self.basis_url}/chat/completions", daten, {"authorization": f"Bearer {self.api_key}"})
        nachricht = roh["choices"][0]["message"]
        aufrufe = []
        for a in nachricht.get("tool_calls") or []:
            argumente = a["function"].get("arguments") or {}
            if isinstance(argumente, str):
                try:
                    argumente = json.loads(argumente) if argumente.strip() else {}
                except json.JSONDecodeError:
                    argumente = {"_unlesbar": argumente}
            aufrufe.append({"id": a.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                            "name": a["function"]["name"], "arguments": argumente})
        nutzung = roh.get("usage") or {}
        return {
            "text": nachricht.get("content") or "",
            "tool_calls": aufrufe,
            "verbrauch": {"eingabe": nutzung.get("prompt_tokens", 0), "ausgabe": nutzung.get("completion_tokens", 0)},
        }

    @staticmethod
    def _umwandeln(nachrichten: list) -> list:
        ergebnis = []
        for n in nachrichten:
            if n["role"] == "user":
                ergebnis.append({"role": "user", "content": n["content"]})
            elif n["role"] == "assistant":
                eintrag = {"role": "assistant", "content": n.get("text") or ""}
                if n.get("tool_calls"):
                    eintrag["tool_calls"] = [
                        {"id": a["id"], "type": "function",
                         "function": {"name": a["name"], "arguments": json.dumps(a["arguments"], ensure_ascii=False)}}
                        for a in n["tool_calls"]
                    ]
                ergebnis.append(eintrag)
            elif n["role"] == "tool":
                ergebnis.append({"role": "tool", "tool_call_id": n["tool_call_id"], "content": n["content"]})
        return ergebnis


# ---------------------------------------------------------------------------
# 3) Der Mensch als Sprachmodell ("Du bist das LLM")
# ---------------------------------------------------------------------------
class MenschLLM:
    """Zeigt dir genau den Kontext, den ein echtes LLM bekäme – und du antwortest.

    Eingabe-Möglichkeiten:
        Einfach Text tippen               -> fertige Antwort an den Menschen (Schleife endet)
        tool NAME {"arg": "wert"}         -> Wunsch, ein Tool aufzurufen
        Beispiel:  tool query_database {"query": "SELECT COUNT(*) FROM schueler"}
    """

    BLAU = "\033[94m"
    RESET = "\033[0m"

    def __init__(self):
        self.name = "mensch (du bist das LLM)"
        self._gesehen = {}       # pro Agent: wie viele Nachrichten schon gezeigt wurden
        self._letzter = None     # welcher Agent zuletzt dran war

    def antworte(self, system: str, nachrichten: list, tools: list) -> dict:
        b, r = self.BLAU, self.RESET
        treffer = re.search(r"Du bist der Agent '([^']+)'", system)
        agent = treffer.group(1) if treffer else "agent"
        print(f"\n{b}╔══════════ DAS SIEHT DAS LLM  (du spielst: {agent}) ══════════{r}")
        if agent not in self._gesehen:
            print(f"{b}║ SYSTEM-PROMPT:{r}")
            for zeile in system.splitlines():
                print(f"{b}║{r}   {zeile}")
            print(f"{b}║ VERFÜGBARE TOOLS:{r}")
            for t in tools:
                parameter = ", ".join(t["input_schema"].get("properties", {}).keys())
                beschreibung = (t["description"] or "").strip().splitlines()[0] if t["description"] else ""
                print(f"{b}║{r}   • {t['name']}({parameter}) – {beschreibung}")
            self._gesehen[agent] = 0
        elif len(nachrichten) < self._gesehen[agent]:
            print(f"{b}║ ('{agent}' startet NEU – mit leerem Verlauf. Er erinnert sich an nichts von vorhin!){r}")
            self._gesehen[agent] = 0
        elif agent != self._letzter:
            print(f"{b}║ (Du bist wieder '{agent}'. System-Prompt und Tools wie vorhin.){r}")
        self._letzter = agent
        print(f"{b}║ NEUE NACHRICHTEN:{r}")
        for n in nachrichten[self._gesehen[agent]:]:
            if n["role"] == "user":
                print(f"{b}║{r}   [user]   {n['content']}")
            elif n["role"] == "assistant":
                for a in n.get("tool_calls", []):
                    print(f"{b}║{r}   [du]     tool {a['name']} {json.dumps(a['arguments'], ensure_ascii=False)}")
            elif n["role"] == "tool":
                inhalt = n["content"] if len(n["content"]) < 1500 else n["content"][:1500] + " …"
                print(f"{b}║{r}   [tool-ergebnis {n['name']}]")
                for zeile in inhalt.splitlines():
                    print(f"{b}║{r}       {zeile}")
        self._gesehen[agent] = len(nachrichten) + 1  # +1: deine eigene Antwort gleich
        print(f"{b}╚═══════════════════════════════════════════════{r}")
        print("Antworte als LLM:  Text  ODER  tool NAME {json-argumente}")

        while True:
            eingabe = input(f"{b}LLM> {r}").strip()
            if not eingabe:
                continue
            zerlegt = zerlege_llm_eingabe(eingabe)
            if zerlegt["art"] == "fehler":
                print(f"  {zerlegt['meldung']} Beispiel: tool describe_table {{\"table_name\": \"noten\"}}")
                continue
            return als_llm_antwort(zerlegt)


# ---------------------------------------------------------------------------
# Wie wird das, was ein Mensch als "LLM" tippt, gelesen?
# Diese Regel benutzen BEIDE Oberflächen: das Terminal (MenschLLM oben) und das
# Chat-Fenster (agenten/llm_spielen.py). So gilt überall dasselbe.
# ---------------------------------------------------------------------------
def zerlege_llm_eingabe(eingabe: str) -> dict:
    """Liest eine Eingabe und sagt, was sie ist.

        "tool NAME {json}"   -> {"art": "tool", "name": NAME, "argumente": {...}}
        anderer Text         -> {"art": "text", "text": ...}       (= Endantwort)
        kaputtes JSON        -> {"art": "fehler", "meldung": ...}

    Der Harness rät nicht: Nur die FORM entscheidet, ob es ein Tool-Aufruf ist.
    """
    eingabe = eingabe.strip()
    if not eingabe.lower().startswith("tool "):
        return {"art": "text", "text": eingabe}

    # "tool" abschneiden, dann am ersten Leerzeichen/Zeilenumbruch trennen: NAME | JSON
    teile = eingabe[5:].strip().split(maxsplit=1)
    name = teile[0]
    if len(teile) == 1:
        return {"art": "tool", "name": name, "argumente": {}}
    try:
        argumente = json.loads(teile[1])
    except json.JSONDecodeError as e:
        return {"art": "fehler", "meldung": f"Ungültiges JSON ({e})."}
    if not isinstance(argumente, dict):
        return {"art": "fehler", "meldung": "Die Argumente müssen ein JSON-Objekt in {…} sein."}
    return {"art": "tool", "name": name, "argumente": argumente}


def als_llm_antwort(zerlegt: dict) -> dict:
    """Macht aus dem Ergebnis von zerlege_llm_eingabe die Antwort im neutralen Format
    (siehe oben: {"text", "tool_calls", "verbrauch"}) – genau wie bei Claude oder Ollama."""
    if zerlegt["art"] == "tool":
        aufruf = {"id": f"call_{uuid.uuid4().hex[:8]}", "name": zerlegt["name"], "arguments": zerlegt["argumente"]}
        return {"text": "", "tool_calls": [aufruf], "verbrauch": {}}
    return {"text": zerlegt["text"], "tool_calls": [], "verbrauch": {}}


def erstelle_llm(art: str, modell: str | None = None, basis_url: str | None = None):
    art = art.lower()
    if art == "anthropic":
        return AnthropicLLM(modell)
    if art in ("ollama", "openai"):
        return OpenAIKompatibelLLM(modell, basis_url)
    if art == "mensch":
        return MenschLLM()
    raise ValueError(f"Unbekanntes Modell '{art}'. Erlaubt: anthropic, ollama, openai, mensch")
