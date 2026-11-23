# TODO

## MCP Apps (Teil 1b) in Claude Desktop testen

Die Apps sind mit einem selbstgebauten Test-Host im Browser geprüft (Anzeige, Klassenwechsel, Freigabe mit Auswahl). In Claude Desktop selbst sind sie noch nicht getestet.

- [ ] venv aktualisieren: `pip install -r requirements.txt` (FastMCP 3.4.11)
- [ ] Claude Desktop ganz beenden und neu starten
- [ ] „Zeig mir die Notenübersicht der 7a in Mathematik.“ → erscheint die Oberfläche? Funktioniert der Klassenwechsel?
- [ ] „Trage für Werner aus der 7a eine 2 in Mathe ein.“ → Freigabe-App mit Auswahl, nach Klick steht die Note in der Datenbank
- [ ] Prüfen, ob Claude nach dem Klassenwechsel weiß, welche Klasse man sieht (`updateModelContext`)
- [ ] Falls keine Oberfläche erscheint: Medientyp und CSP prüfen; notfalls die Bibliothek `ext-apps` direkt in die HTML-Seite einbetten statt vom CDN zu laden
- [ ] `docs/mcp-apps.md` anpassen, falls Claude Desktop sich anders verhält als beschrieben

## Workflow B (n8n-Agent) mit echtem LLM testen

Workflow B ist bis zum LLM-Aufruf geprüft. Es fehlt nur noch eine Antwort von einem echten Modell.

- [ ] Ollama installieren (https://ollama.com) und `ollama pull qwen2.5:7b` ausführen
- [ ] In n8n bei Workflow B die Verbindung vom Knoten *Claude* auf den Knoten *Ollama* umstecken (Eingang *Chat Model* des Agenten)
- [ ] Ollama-Credential anlegen mit Base URL `http://host.docker.internal:11434`
- [ ] Testfrage im Chat stellen, z. B. „Welche Klasse hat den besten Durchschnitt in Mathematik?“
- [ ] Prüfen, ob der Agent nur die lesenden Tools sieht (`add_grade` darf nicht auftauchen)
- [ ] Prüfen, ob die Logs unter dem Chat für Schüler verständlich sind
- [ ] `docs/agenten/06_n8n.md` anpassen, falls sich beim Test etwas anders verhält als beschrieben

## Abschluss

- [ ] Pull Request von `agenten-erweiterung` nach `main` erstellen
- [ ] Test-Stack aufräumen: `docker compose -f n8n/docker-compose.yml down -v` (löscht auch die Test-Workflows mit „TEST“ im Namen)
- [ ] `schule.db` neu erzeugen (`python create_database.py`), denn sie enthält eine Testnote
- [ ] Diese Datei löschen, wenn alles erledigt ist
