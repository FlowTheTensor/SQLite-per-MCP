# TODO

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
