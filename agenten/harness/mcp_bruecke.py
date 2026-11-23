"""
MCP-Brücke – der Harness als MCP-CLIENT.

Im ersten Teil des Projekts war Claude Desktop der MCP-Client.
Jetzt übernimmt unser eigener Harness diese Rolle:

    Harness (MCP-Client)  ──stdio / JSON-RPC──►  src/index.py (MCP-Server)  ──SQL──►  schule.db

Es werden genau die zwei MCP-Methoden verwendet, die du schon kennst:
    tools/list  -> welche Werkzeuge gibt es?
    tools/call  -> ein Werkzeug ausführen
"""

import sys
import warnings
from pathlib import Path

# Veraltungs-Warnungen aus Bibliotheken beim Import "einsammeln", damit die Konsole lesbar bleibt
with warnings.catch_warnings(record=True):
    from fastmcp import Client
    from fastmcp.client.transports import PythonStdioTransport

SERVER_SKRIPT = Path(__file__).resolve().parents[2] / "src" / "index.py"


class MCPBruecke:
    def __init__(self, server_skript: Path = SERVER_SKRIPT):
        # Der Server wird als eigener Prozess gestartet; Harness und Server sprechen
        # über stdin/stdout miteinander (stdio-Transport, Nachrichten im JSON-RPC-Format).
        log_ordner = Path(__file__).resolve().parent.parent / "protokolle"
        log_ordner.mkdir(exist_ok=True)
        transport = PythonStdioTransport(
            script_path=str(server_skript),
            python_cmd=sys.executable,
            env={"FASTMCP_SHOW_CLI_BANNER": "false", "FASTMCP_LOG_LEVEL": "WARNING", "PYTHONIOENCODING": "utf-8"},
            log_file=log_ordner / "mcp_server.log",  # Meldungen des Servers landen hier statt in der Konsole
        )
        self.client = Client(transport)
        self.tools: list[dict] = []

    async def __aenter__(self):
        await self.client.__aenter__()
        await self.lade_tools()
        return self

    async def __aexit__(self, *args):
        await self.client.__aexit__(*args)

    async def lade_tools(self) -> list[dict]:
        """MCP-Methode tools/list"""
        roh = await self.client.list_tools()
        self.tools = [
            {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
            for t in roh
        ]
        return self.tools

    async def rufe_auf(self, name: str, argumente: dict) -> str:
        """MCP-Methode tools/call – liefert das Ergebnis als Text."""
        ergebnis = await self.client.call_tool(name, argumente, raise_on_error=False)
        teile = []
        for inhalt in ergebnis.content:
            teile.append(getattr(inhalt, "text", None) or str(inhalt))
        text = "\n".join(teile)
        if ergebnis.is_error:
            return f"Fehler vom MCP-Server: {text}"
        return text
