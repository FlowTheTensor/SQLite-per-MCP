#!/usr/bin/env python3
"""
Generiert die Claude Desktop Konfiguration mit absoluten Pfaden
"""

import json
from pathlib import Path

# Aktuelles Projektverzeichnis
project_dir = Path(__file__).parent.resolve()

# Pfade
python_exe = project_dir / "venv" / "Scripts" / "python.exe"
index_py = project_dir / "src" / "index.py"

# Konfiguration erstellen
config = {
    "mcpServers": {
        "sqlite-schule": {
            "command": str(python_exe),
            "args": [str(index_py)]
        }
    }
}

# Ausgeben
print("Füge folgende Konfiguration in %APPDATA%\\Claude\\claude_desktop_config.json ein:")
print()
print(json.dumps(config, indent=2))

# Optional: In Datei speichern
output_file = project_dir / "claude_desktop_config.json"
with open(output_file, 'w') as f:
    json.dump(config, f, indent=2)

print()
print(f"✓ Konfiguration wurde auch gespeichert in: {output_file}")
