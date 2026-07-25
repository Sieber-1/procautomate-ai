"""
Runner: Verbindet MCP-Server, baut den Graphen und fuehrt Analysen aus.

Dieses Modul kapselt die gesamte Orchestrierung:
1. MCP-Server als Microservices anbinden (via MultiServerMCPClient)
2. Tools laden und in LangChain-Tools konvertieren
3. Graph mit SQLite-Checkpointing bauen
4. Prozessbeschreibung durch den Multi-Agent-Graphen laufen lassen

Alles ist async, weil MCP-Kommunikation async ist.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator, Callable

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from core.config import CHECKPOINT_DB
from core.graph import GraphBuilder
from core.state import AgentState


# Absolute Pfade zu den MCP-Server-Skripten
_BASE = Path(__file__).parent.parent
_DATA_SERVER = str(_BASE / "mcp_servers" / "data_tools_server.py")
_AUTO_SERVER = str(_BASE / "mcp_servers" / "automation_tools_server.py")


def _mcp_server_config() -> dict:
    """
    Konfiguration der MCP-Server als eigenstaendige stdio-Prozesse.

    Jeder Server laeuft als separater Python-Prozess. LangGraph spricht mit
    ihnen ueber das MCP-Protokoll (JSON-RPC 2.0 ueber stdio).
    """
    return {
        "data_tools": {
            "command": "python",
            "args": [_DATA_SERVER],
            "transport": "stdio",
        },
        "automation_tools": {
            "command": "python",
            "args": [_AUTO_SERVER],
            "transport": "stdio",
        },
    }


class ProcessAutomationRunner:
    """Hauptklasse zur Ausfuehrung der Prozessautomatisierungs-Analyse."""

    def __init__(self):
        self.client: MultiServerMCPClient | None = None
        self.tools: list = []

    async def _load_tools(self) -> list:
        """Startet die MCP-Server und laedt ihre Tools."""
        self.client = MultiServerMCPClient(_mcp_server_config())
        self.tools = await self.client.get_tools()
        return self.tools

    async def run(
        self,
        process_description: str,
        session_id: str = "default",
        progress_callback: Callable[[str, dict], None] | None = None,
    ) -> dict:
        """
        Fuehrt die vollstaendige Analyse aus.

        Args:
            process_description: Die zu analysierende Prozessbeschreibung.
            session_id: Eindeutige ID fuer Checkpointing (ermoeglicht Resume).
            progress_callback: Wird nach jedem Node mit (node_name, state) aufgerufen.

        Returns:
            Der finale State mit allen Ergebnissen.
        """
        tools = await self._load_tools()

        # SQLite-Checkpointer: State ueberlebt Abstuerze, erlaubt Time-Travel
        async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB) as checkpointer:
            builder = GraphBuilder(tools, checkpointer=checkpointer)
            app = builder.build()

            initial_state: AgentState = {
                "messages": [],
                "process_description": process_description,
                "tasks": [],
                "feasibility_report": {},
                "automation_results": [],
                "qa_report": {},
                "next_agent": "",
                "iteration_count": 0,
            }

            config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}

            final_state = initial_state
            # astream liefert nach jedem Node ein Update
            async for chunk in app.astream(initial_state, config=config):
                for node_name, node_output in chunk.items():
                    if progress_callback:
                        progress_callback(node_name, node_output)
                    # State-Updates akkumulieren
                    final_state = {**final_state, **node_output}

            return final_state

    async def get_graph_visualization(self) -> bytes | None:
        """Gibt eine PNG-Visualisierung des Graphen zurueck (falls Graphviz verfuegbar)."""
        tools = await self._load_tools()
        builder = GraphBuilder(tools)
        app = builder.build()
        try:
            return app.get_graph().draw_mermaid_png()
        except Exception:
            return None

    async def get_mermaid_diagram(self) -> str:
        """Gibt den Graphen als Mermaid-Text zurueck (immer verfuegbar)."""
        tools = await self._load_tools()
        builder = GraphBuilder(tools)
        app = builder.build()
        return app.get_graph().draw_mermaid()
