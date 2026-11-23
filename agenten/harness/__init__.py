"""Ein kleiner, lesbarer Agenten-Harness für den Unterricht."""

from .definition import alle_definitionen, lade_definition
from .harness import Harness
from .llm import erstelle_llm
from .mcp_bruecke import MCPBruecke
from .mensch import Mensch
from .protokoll import Protokoll

__all__ = ["Harness", "MCPBruecke", "Mensch", "Protokoll", "erstelle_llm", "lade_definition", "alle_definitionen"]
