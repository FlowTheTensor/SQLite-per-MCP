# Teil 2: Agenten & Multiagentensysteme

Im ersten Teil war **Claude Desktop** das Programm, das mit dem MCP-Server gesprochen hat.
In diesem Teil bauen wir dieses Programm – den **Harness** – selbst nach. So wird sichtbar, was sonst versteckt passiert:

- Was ist ein **Agent** – und was ist nur das **LLM**?
- Was macht der **Harness**?
- Wo greift der **Mensch** ein?
- Wie arbeiten **mehrere Agenten** zusammen?

## Lernpfad

| Kapitel | Inhalt |
|---|---|
| [1 · Begriffe](../docs/agenten/01_begriffe.md) | LLM, Tool, MCP, Agent, Harness, Workflow vs. Agent |
| [2 · Der Harness](../docs/agenten/02_harness.md) | Agenten-Schleife, Aufgaben des Harness, Rechte im Code |
| [3 · Mensch-Maschine-Schnittstellen](../docs/agenten/03_mensch_maschine.md) | S0–S5, Autonomiestufen, Verantwortung |
| [4 · Multiagentensysteme](../docs/agenten/04_multiagenten.md) | Koordinator & Spezialisten, Muster, Vor- und Nachteile |
| [5 · Aufgaben](../docs/agenten/05_aufgaben.md) | vom Rollenspiel bis zum eigenen Agenten-Team |
| [6 · Derselbe Agent in n8n](../docs/agenten/06_n8n.md) | n8n als zweiter Harness (Docker): Workflow vs. Agent, Freigabe per Formular |

## Schnellstart

Voraussetzung: Teil 1 ist eingerichtet (venv aktiv, `schule.db` erstellt). Es werden **keine weiteren Pakete** benötigt.

```powershell
# Welche Agenten gibt es?
python agenten/agent.py --liste

# 1) Du spielst selbst das LLM – kostenlos, ohne Internet
python agenten/agent.py --agent datenbank-analyst --modell mensch

# 2) Mit Claude (API-Key von console.anthropic.com)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python agenten/agent.py --agent datenbank-analyst --modell anthropic "Welche Klasse hat den besten Mathe-Schnitt?"

# 3) Mit einem lokalen Modell über Ollama (https://ollama.com)
ollama pull qwen2.5:7b
python agenten/agent.py --agent datenbank-analyst --modell ollama "Welche Klasse hat den besten Mathe-Schnitt?"

# Human-in-the-Loop: Noten eintragen nur mit Freigabe
python agenten/agent.py --agent notenverwalter --modell anthropic

# Multiagentensystem
python agenten/agent.py --agent koordinator --modell anthropic "Kurze Zwischenstand-Rückmeldung für die Klasse 10a in Informatik vor der nächsten Schulaufgabe"
```

Weitere Optionen:

| Option | Wirkung |
|---|---|
| `--modellname NAME` | anderes Modell, z. B. `claude-sonnet-5-5` oder `llama3.1:8b` |
| `--url URL` | anderer OpenAI-kompatibler Server (LM Studio, OpenAI, Schulserver …) |
| `--alles-erlauben` | keine Freigaben mehr (Autonomiestufe 3 – zum Ausprobieren) |
| `--leise` | `[HARNESS]`-Zeilen ausblenden |

## So liest du die Ausgabe

```
[MENSCH ] Auftrag: Wie viele Schüler hat die 7a?
[AGENT  ] ▶ Agent 'datenbank-analyst' startet (Gehirn: anthropic/claude-haiku-5-5)
[HARNESS] Schritt 1/10: sende 1 Nachricht(en) + 3 Tool(s) an das LLM …
[LLM    ] möchte Tool 'query_database' mit {"query": "SELECT COUNT(*) FROM schueler WHERE klasse='7a'"}
[MCP    ] tools/call → query_database
[MCP    ] Ergebnis: [{"COUNT(*)": 17}]
[HARNESS] Schritt 2/10: sende 3 Nachricht(en) + 3 Tool(s) an das LLM …
[LLM    ] Die Klasse 7a hat 17 Schüler.
[AGENT  ] ■ Agent 'datenbank-analyst' ist fertig (2 Schritt(e)).
```

Jede Zeile sagt dir, **wer** gerade handelt. Unteragenten erscheinen eingerückt mit `│`.
Das vollständige Protokoll (inkl. System-Prompts und ungekürzter Ergebnisse) liegt in `agenten/protokolle/`.

## Dateien

```
agenten/
├── agent.py               # Startprogramm (Kommandozeile)
├── minimal_agent.py       # der kleinste mögliche Agent – zum Vergleichen
├── definitionen/          # S0: Hier wird festgelegt, was jeder Agent ist und darf
│   ├── datenbank-analyst.md
│   ├── notenverwalter.md
│   ├── pruefer.md
│   ├── berichtsautor.md
│   └── koordinator.md
└── harness/               # Der Harness – jede Datei hat genau eine Aufgabe
    ├── harness.py         # die Agenten-Schleife, Rechteprüfung, Delegation
    ├── llm.py             # Verbindung zum LLM (Anthropic, Ollama, Mensch)
    ├── mcp_bruecke.py     # MCP-Client: tools/list und tools/call
    ├── mensch.py          # alle Mensch-Maschine-Schnittstellen an einem Ort
    ├── definition.py      # liest die Definitionsdateien
    └── protokoll.py       # farbige Ausgabe + JSONL-Protokoll
```

## Hinweise für Lehrkräfte

- **Ohne Budget:** Der Modus `--modell mensch` deckt alle Kernideen ab (Kontext, Schleife, Tools, Rechte, Freigabe, Delegation). Er eignet sich besonders als Einstieg, weil die Schülerinnen und Schüler das LLM *selbst spielen*.
- **Lokale Modelle:** Ollama mit `qwen2.5:7b` oder `llama3.1:8b` beherrscht Tool-Aufrufe und läuft auf Rechnern mit ca. 8 GB freiem Arbeitsspeicher. Einzelagenten funktionieren gut; das Multiagenten-Team ist für kleine Modelle oft zu anspruchsvoll – auch das ist ein guter Diskussionsanlass.
- **Kosten mit der API:** Ein Lauf des Einzelagenten kostet mit `claude-haiku-5-5` Bruchteile eines Cents bis wenige Cent; das Team ein Mehrfaches (siehe Token-Tabelle am Ende jedes Laufs). Ein Ausgabenlimit in der Anthropic-Konsole ist empfehlenswert.
- **Datenschutz:** Die Datenbank enthält ausschließlich erfundene Daten. Bei `--modell anthropic` werden Abfrageergebnisse an den Anbieter übertragen – mit echten Schülerdaten wäre das nicht zulässig. Guter Gesprächsanlass!
- **Datenbank zurücksetzen:** `add_grade` verändert `schule.db`. Mit `python create_database.py` wird sie neu erzeugt (mit neuen Zufallsnamen).
