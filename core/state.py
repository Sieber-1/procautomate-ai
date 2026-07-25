"""
Gemeinsamer State fuer das Multi-Agent System.

In LangGraph teilen sich alle Nodes (Agenten) ein einziges State-Objekt.
Jeder Node liest aus dem State und schreibt Updates zurueck. LangGraph
merged diese Updates automatisch (Reducer-Pattern) und checkpointet den
State nach jedem Node-Durchlauf.

Das ist der zentrale Unterschied zu einem simplen Agent-Loop: Der State
ueberlebt Abstuerze, kann pausiert und wieder aufgenommen werden, und
ist zu jedem Zeitpunkt inspizierbar (Time-Travel-Debugging).
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage


# Die einzelnen Prozessschritte, die der Supervisor ansteuern kann
AgentName = Literal[
    "supervisor",
    "intake_agent",
    "analysis_agent",
    "automation_agent",
    "qa_agent",
    "FINISH",
]


class ProcessTask(TypedDict):
    """Eine einzelne identifizierte Automatisierungs-Aufgabe."""

    step_id: str
    description: str
    input_source: str
    output_target: str
    automation_type: str  # z.B. "data_extraction", "email", "file_transform"
    complexity: str  # "niedrig" | "mittel" | "hoch"


class AutomationResult(TypedDict):
    """Ergebnis eines automatisierten Schrittes."""

    step_id: str
    status: str  # "success" | "failed" | "skipped"
    output: str
    tool_used: str


class AgentState(TypedDict):
    """
    Der geteilte State fuer das gesamte Multi-Agent System.

    Annotated[..., operator.add] bedeutet: Updates an diesem Feld werden
    ANGEHAENGT statt ueberschrieben (Reducer-Pattern). So koennen mehrere
    Agenten unabhaengig Nachrichten/Ergebnisse beisteuern, ohne sich
    gegenseitig zu ueberschreiben.
    """

    # Konversations-Historie (append-only)
    messages: Annotated[list[BaseMessage], operator.add]

    # Roh-Input: die Prozessbeschreibung
    process_description: str

    # Vom intake_agent extrahierte, strukturierte Aufgaben
    tasks: list[ProcessTask]

    # Vom analysis_agent bewertete Machbarkeit / ROI
    feasibility_report: dict

    # Vom automation_agent generierte Automatisierungs-Artefakte
    automation_results: Annotated[list[AutomationResult], operator.add]

    # Vom qa_agent erstellte Qualitaetspruefung
    qa_report: dict

    # Routing-Feld: welcher Agent kommt als naechstes?
    next_agent: str

    # Zaehler, um Endlosschleifen zu verhindern (Circuit Breaker)
    iteration_count: int
