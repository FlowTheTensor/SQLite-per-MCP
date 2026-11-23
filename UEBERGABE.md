# Übergabe (Stand: 23.11.2026, abends)

Arbeitsnotiz für die nächste Sitzung. Nach Abschluss der offenen Punkte löschen.

## Kontext

- Unterrichtsprojekt zu MCP mit einer SQLite-Schul-Datenbank, Zielgruppe Schülerinnen und Schüler.
- Alle Texte, Kommentare und Doku **auf Deutsch**, einfach und klar. Plattform: Windows + PowerShell.
- Branch `agenten-erweiterung`: Teil 2 (eigener Harness, Kapitel 1–5) und Kapitel 6 (n8n).

## Stand Kapitel 6 (n8n)

- `n8n/docker-compose.yml`: MCP-Server (`src/index.py --http`) + n8n 2.48.8. Port 8000 nur lokal (keine Anmeldung am MCP-Server). `N8N_PORT` und `N8N_URL` einstellbar.
- `docs/agenten/06_n8n.md` geschrieben, Verweise in `agenten/README.md`, `README.md`, Kapitel 1.
- **Getestet:** Workflow A und C komplett über die Formulare (inkl. Mehrfachtreffer, SQL-Injection-Eingabe, Freigabe Ja/Nein).
- **Erkenntnis:** Der n8n-Knoten *MCP Client* liefert in `content[0].text` bei JSON-Text schon eine **umgewandelte Liste**, bei normalem Text einen **String**. Die Workflows prüfen das mit `typeof`.
- **Erkenntnis:** Ohne `WEBHOOK_URL`/`N8N_EDITOR_BASE_URL` baut n8n Chat- und Formular-Links mit Port 5678 → „Failed to receive response“ bei abweichendem Port oder auf einem Server.

## Offen

1. **Workflow B mit echtem LLM testen.** Bis zum LLM-Aufruf geprüft (Chat → Verlauf → Agent → Anthropic). Anthropic lehnte nur wegen fehlendem API-Guthaben ab. Geplant: Ollama lokal (`ollama pull qwen2.5:7b`), in B auf den Ollama-Knoten umstecken, Credential-URL `http://host.docker.internal:11434`. Dabei prüfen, ob die Tool-Auswahl (nur lesende Tools) wirkt und die Logs gut zu lesen sind. Kapitel 6 ggf. anpassen.
2. Danach diese Datei löschen und einen PR nach `main` erstellen.
