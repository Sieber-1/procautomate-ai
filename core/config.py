"""
Zentrale Konfiguration.

Alle einstellbaren Parameter an einem Ort. Werte werden aus
Umgebungsvariablen gelesen, mit sinnvollen Defaults.
"""

import os

from dotenv import load_dotenv

load_dotenv()


# --- LLM Konfiguration ---
# Anthropic Claude als Standard. Ueber init_chat_model auch OpenAI moeglich.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0"))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# --- Agent Konfiguration ---
# Maximale Anzahl Supervisor-Durchlaeufe (Circuit Breaker gegen Endlosschleifen)
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "12"))

# --- Checkpointing ---
# SQLite-Datei fuer State-Persistenz. Ermoeglicht Pause/Resume/Time-Travel.
CHECKPOINT_DB = os.environ.get("CHECKPOINT_DB", "checkpoints.sqlite")

# --- MCP Server ---
# Die Tool-Server laufen als eigenstaendige Prozesse (Microservices).
# Kommunikation ueber stdio (lokal) oder HTTP (verteilt).
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")


def get_model_string() -> str:
    """Baut den Modell-String fuer init_chat_model."""
    return f"{LLM_PROVIDER}:{LLM_MODEL}"


def validate_config() -> tuple[bool, str]:
    """Prueft, ob die noetigen API Keys gesetzt sind."""
    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        return False, "ANTHROPIC_API_KEY fehlt. Bitte in .env setzen."
    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        return False, "OPENAI_API_KEY fehlt. Bitte in .env setzen."
    return True, "OK"
