# Übergabe an Claude Code (Stand: 23.11.2026)

Diese Datei fasst den Stand einer Arbeitssitzung zusammen, damit Claude Code nahtlos weitermachen kann.
Nach Abschluss der Arbeiten kann sie gelöscht werden.

## Kontext

- Repo: `FlowTheTensor/SQLite-per-MCP`, Unterrichtsprojekt (Schule) zu MCP mit einer SQLite-Schul-Datenbank.
- Zielgruppe: Schülerinnen und Schüler. Alle Texte, Kommentare, Variablennamen und Doku **auf Deutsch**, einfach und klar.
- Plattform der Schüler: **Windows + PowerShell**, Python-venv, Claude Desktop.
- Ziel der Erweiterung: Schülern sehr deutlich machen, **was ein Agent ist, was ein Harness ist, wo die Mensch-Maschine-Schnittstellen sind** und wie Multiagentensysteme funktionieren.

## Erledigt (Commit „Teil 2: Agenten, Harness, …“ auf Branch `agenten-erweiterung`)

| Bereich | Dateien |
|---|---|
| Eigener, lesbarer Agenten-Harness (MCP-Client per stdio) | `agenten/harness/*.py` |
| LLM-Adapter: `anthropic`, `ollama`/`openai` (OpenAI-kompatibel), `mensch` (Schüler spielen das LLM) – nur `urllib`, keine neuen Pakete | `agenten/harness/llm.py` |
| Agenten-Definitionen als Markdown mit Kopfbereich (`tools`, `tools_mit_freigabe`, `mensch_fragen`, `delegiert_an`, `max_schritte`) | `agenten/definitionen/*.md` |
| Agenten: `datenbank-analyst`, `notenverwalter` (HITL), `koordinator` + `pruefer` + `berichtsautor` (Multiagent) | ebd. |
| Alle Mensch-Schnittstellen S0–S5 an einem Ort | `agenten/harness/mensch.py` |
| CLI + Minimal-Agent zum Vergleich | `agenten/agent.py`, `agenten/minimal_agent.py` |
| Neues schreibendes MCP-Tool `add_grade` | `src/index.py` |
| Unterrichtsmaterial Kapitel 1–5 | `docs/agenten/01…05_*.md`, `agenten/README.md` |
| Haupt-README: Verweis auf Teil 2, Datenbankbeschreibung an echtes Schema angepasst | `README.md` |

Getestet: Harness-Schleife, Rechteprüfung, Freigabe, Rückfrage, Delegation (mit Skript-LLM), beide HTTP-Adapter gegen einen Fake-Server, `mensch`-Modus per stdin. **Noch nicht** mit echtem Claude-API-Key oder echtem Ollama getestet.

## In Arbeit: n8n-Erweiterung („Kapitel 6 – Derselbe Agent in n8n“)

### Idee
n8n (im Docker-Container) als **zweiter Harness** für denselben MCP-Server. Didaktischer Kern: **Workflow vs. Agent** direkt nebeneinander sehen, und „derselbe MCP-Server, anderer Harness“.

### Schon erledigt (noch nicht committet → zweiter Commit)
1. **`src/index.py` hat einen HTTP-Modus:** `python src/index.py --http` → MCP-Endpunkt `http://<host>:8000/mcp` (Streamable HTTP). stdio bleibt Standard. ✅ getestet (tools/list + tools/call über HTTP).
2. **Drei n8n-Workflows** in `n8n/workflows/` (MCP-URL darin: `http://mcp-server:8000/mcp` = Docker-Service-Name):
   - `A_fester_workflow.json` – Form Trigger (Klasse, Fach als Dropdown) → **MCP Client** (`query_database`, feste SQL) → Form-Abschlussseite. Kein LLM.
   - `B_agent_datenbank_analyst.json` – Chat Trigger → **AI Agent** (System-Prompt aus `datenbank-analyst.md`, maxIterations 10) + Anthropic-Chat-Model (`claude-haiku-5-5`) + **MCP Client Tool** (Include = Selected: nur `list_tables`, `describe_table`, `query_database` → `add_grade` unsichtbar) + Window-Memory. Ein Ollama-Knoten liegt unverbunden daneben zum Umstecken. Sticky Notes beschriften Harness / LLM / Tools / Mensch / Verlauf.
   - `C_workflow_mit_freigabe.json` – Form (Klasse, Nachname, Fach, Note, Art) → MCP `query_database` sucht Schüler + Kurs → Code-Knoten wertet aus → If „genau ein Treffer?“ → **Form-Seite „Freigabe“ mit Namen statt ids** → If „Ja?“ → MCP `add_grade` → Abschlussseite. Zeigt S2 (Freigabe) mit verständlicher Anzeige – löst das in Kapitel 3 diskutierte Problem „ids statt Namen“.
   - Import in n8n 2.48.8 per `n8n import:workflow --separate --input=…` ✅ erfolgreich. **Ausgeführt wurden sie noch nicht.**

### Erkenntnisse aus der Recherche/Tests
- n8n-Version beim Test: **2.48.8**. Braucht **Node ≥ 24** (bei Docker egal).
- In n8n 2.x heißt „Aktivieren“ jetzt **Publish** (CLI: `n8n publish:workflow --id=…`). Doku entsprechend formulieren.
- n8n spricht MCP **nur über HTTP** (SSE oder Streamable HTTP), nicht stdio → deshalb `--http`.
- Knoten-Typen/Versionen in den JSONs: `formTrigger` 2.3, `form` 1, `mcpClient` 1.1, `mcpClientTool` 1.2, `agent` 2.2, `lmChatAnthropic` 1.3, `lmChatOllama` 1, `memoryBufferWindow` 1.3, `chatTrigger` 1.1, `if` 2.2, `code` 2.
- n8n hat eingebaute HITL-Funktionen vor allem über Messenger („send and wait“, z. B. Slack). Für die Schule ist die Form-basierte Freigabe (Workflow C) einfacher.
- Credentials (Anthropic-Key, Ollama-URL) sind **nicht** in den Workflows – müssen in n8n angelegt werden. Ollama aus dem Container: `http://host.docker.internal:11434`.

### ⚠️ Unsichere Annahme – zuerst prüfen
Die Workflows A und C lesen das Ergebnis des **MCP Client**-Knotens mit `$json.content?.[0]?.text ?? $json.result`. Das echte Ausgabeformat des Knotens ist **nicht verifiziert**. Nach dem ersten Testlauf im n8n-Editor die Ausgabe ansehen und die Ausdrücke in „Ergebnis anzeigen“, „Treffer auswerten“ und „Fertig“ ggf. anpassen. Ebenso prüfen: Wird `jsonInput` mit `JSON.stringify(...)`-Ausdruck korrekt akzeptiert?

## Offene Aufgaben (Reihenfolge)

1. **`n8n/docker-compose.yml`** schreiben:
   - Service `mcp-server`: `python:3.12-slim`, Projektordner nach `/app` mounten, `pip install -r requirements.txt`, `schule.db` erzeugen falls fehlend, `python src/index.py --http`, Port 8000.
   - Service `n8n`: Image `docker.n8n.io/n8nio/n8n`, Port 5678, Volume `n8n_data:/home/node/.n8n`, `./workflows:/workflows:ro`, `GENERIC_TIMEZONE`/`TZ=Europe/Berlin`, `N8N_SECURE_COOKIE=false` (Zugriff per http im Schulnetz), `extra_hosts: host.docker.internal:host-gateway` (Ollama), `depends_on: mcp-server`.
   - Import-Befehl dokumentieren: `docker compose exec n8n n8n import:workflow --separate --input=/workflows`.
2. Stack starten, alle drei Workflows **wirklich ausführen** (siehe ⚠️), Workflow B mit echtem LLM testen.
3. **`docs/agenten/06_n8n.md`** schreiben (Stil wie Kapitel 1–5: Leitfrage, Tabellen, Mermaid, Kontrollfragen):
   - Warum n8n? Workflow vs. Agent (A vs. B), Harness-Teile im n8n-Canvas finden, Tool-Auswahl = S0, Freigabe in C = S2, Vergleich eigener Harness ↔ Claude Desktop ↔ n8n.
   - Hinweise: Docker unter Windows braucht WSL2 + Adminrechte → evtl. ein zentraler n8n-Container auf Lehrer-/Schulserver. AI-Agent-Knoten ist wieder eine Blackbox → n8n erst **nach** dem eigenen Harness einsetzen.
   - Aufgaben: A und B mit derselben Frage vergleichen; in B `add_grade` freischalten und diskutieren; C mit Mehrfachtreffer testen; SQL-Injection-Diskussion (Nachname-Feld in C wird escaped, Dropdowns in A).
   - Ausblick: **MCP Server Trigger** – n8n selbst als MCP-Server, z. B. „Elternbrief per Mail“ als Tool für den eigenen Harness (dafür müsste `agenten/harness/mcp_bruecke.py` auch eine URL statt Skriptpfad akzeptieren).
4. Verlinkungen ergänzen: `agenten/README.md` (Lernpfad-Tabelle), Haupt-`README.md` (Projektstruktur: `n8n/`), Kapitel 1 Tabelle „Workflow oder Agent?“ → Verweis auf Kapitel 6.
5. `.gitignore` prüfen, committen, PR erstellen.

## Vorschlag für den ersten Prompt in Claude Code

> Lies `UEBERGABE.md`. Mach mit den offenen Aufgaben 1–4 weiter. Prüf zuerst das Ausgabeformat des n8n-MCP-Client-Knotens, bevor du Kapitel 6 schreibst. Alles auf Deutsch, Zielgruppe Schüler, Windows/PowerShell.
