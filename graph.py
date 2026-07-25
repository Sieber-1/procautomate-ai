"""
Der LangGraph Multi-Agent Graph.

Dies ist das Herzstueck des Systems. Es implementiert das Supervisor-Pattern:

    ┌──────────────┐
    │  supervisor  │◄──────────────┐
    └──────┬───────┘               │
           │ routet zu             │ zurueck nach jedem Worker
           ▼                       │
    ┌──────────────┐               │
    │ intake_agent │───────────────┤
    ├──────────────┤               │
    │analysis_agent│───────────────┤
    ├──────────────┤               │
    │automation_ag.│───────────────┤
    ├──────────────┤               │
    │   qa_agent   │───────────────┘
    └──────────────┘
           │ FINISH
           ▼
         END

Der Supervisor ist ein LLM, das nur routet. Jeder Worker ist ein ReAct-Agent
mit Zugriff auf MCP-Tools. Der State wird nach jedem Node in SQLite gecheckpointet.
"""

from __future__ import annotations

import json
import re

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from agents.prompts import (
    ANALYSIS_PROMPT,
    AUTOMATION_PROMPT,
    INTAKE_PROMPT,
    QA_PROMPT,
    SUPERVISOR_PROMPT,
)
from core.config import MAX_ITERATIONS, get_model_string
from core.state import AgentState


def _extract_json(text: str) -> dict | list | None:
    """Extrahiert das erste JSON-Objekt/Array aus einem Text (auch aus Codeblocks)."""
    # Versuche Codeblock ```json ... ```
    block = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", text, re.DOTALL)
    candidate = block.group(1) if block else None
    if candidate is None:
        # Fallback: erstes { ... } oder [ ... ]
        start = min(
            (text.find(c) for c in "{[" if text.find(c) >= 0),
            default=-1,
        )
        if start >= 0:
            candidate = text[start:]
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Greedy-Suche nach ausbalanciertem JSON
            for end in range(len(candidate), 0, -1):
                try:
                    return json.loads(candidate[:end])
                except json.JSONDecodeError:
                    continue
    return None


class GraphBuilder:
    """Baut den kompilierten LangGraph mit MCP-Tools."""

    def __init__(self, tools: list, checkpointer=None):
        """
        Args:
            tools: Liste von LangChain-Tools (typischerweise aus MCP geladen).
            checkpointer: Optionaler LangGraph-Checkpointer fuer State-Persistenz.
        """
        self.model = init_chat_model(get_model_string(), temperature=0)
        self.tools = tools
        self.checkpointer = checkpointer

        # Data-Tools fuer intake, Automation-Tools fuer automation
        self.data_tools = [t for t in tools if t.name in
                           ("extract_structured_data", "csv_to_json", "validate_data_quality")]
        self.automation_tools = [t for t in tools if t.name in
                                ("generate_python_automation", "generate_powershell_automation",
                                 "estimate_automation_roi")]

    # --- Supervisor Node ---
    def supervisor_node(self, state: AgentState) -> dict:
        """Der Supervisor entscheidet ueber das naechste Routing."""
        iteration = state.get("iteration_count", 0) + 1

        # Circuit Breaker: verhindert Endlosschleifen
        if iteration > MAX_ITERATIONS:
            return {"next_agent": "FINISH", "iteration_count": iteration}

        # Kontext fuer den Supervisor: was ist bereits passiert?
        context = self._build_supervisor_context(state)
        messages = [
            SystemMessage(content=SUPERVISOR_PROMPT),
            HumanMessage(content=context),
        ]
        response = self.model.invoke(messages)
        decision = response.content.strip()

        # Robustes Parsing des Routing-Ziels
        valid = ["intake_agent", "analysis_agent", "automation_agent", "qa_agent", "FINISH"]
        next_agent = "FINISH"
        for agent in valid:
            if agent in decision:
                next_agent = agent
                break

        return {"next_agent": next_agent, "iteration_count": iteration}

    def _build_supervisor_context(self, state: AgentState) -> str:
        """Fasst den aktuellen Fortschritt fuer den Supervisor zusammen."""
        parts = [f"Prozessbeschreibung liegt vor: {'ja' if state.get('process_description') else 'nein'}"]
        parts.append(f"Aufgaben extrahiert: {len(state.get('tasks', []))}")
        parts.append(f"Analyse vorhanden: {'ja' if state.get('feasibility_report') else 'nein'}")
        parts.append(f"Automatisierungs-Artefakte: {len(state.get('automation_results', []))}")
        parts.append(f"QA abgeschlossen: {'ja' if state.get('qa_report') else 'nein'}")
        return "Aktueller Stand:\n" + "\n".join(parts) + "\n\nWelcher Agent kommt als naechstes?"

    # --- Worker Nodes ---
    def intake_node(self, state: AgentState) -> dict:
        """Zerlegt die Prozessbeschreibung in strukturierte Aufgaben."""
        agent = create_react_agent(self.model, self.data_tools, prompt=INTAKE_PROMPT)
        result = agent.invoke({
            "messages": [HumanMessage(content=
                f"Prozessbeschreibung:\n\n{state['process_description']}\n\n"
                "Zerlege dies in strukturierte, automatisierbare Aufgaben.")]
        })
        last = result["messages"][-1]
        parsed = _extract_json(last.content)
        tasks = parsed if isinstance(parsed, list) else []

        return {
            "tasks": tasks,
            "messages": [AIMessage(content=f"[Intake] {len(tasks)} Aufgaben identifiziert.")],
        }

    def analysis_node(self, state: AgentState) -> dict:
        """Bewertet Machbarkeit und ROI."""
        agent = create_react_agent(self.model, self.automation_tools, prompt=ANALYSIS_PROMPT)
        tasks_json = json.dumps(state.get("tasks", []), ensure_ascii=False)
        result = agent.invoke({
            "messages": [HumanMessage(content=
                f"Identifizierte Aufgaben:\n{tasks_json}\n\n"
                "Bewerte Machbarkeit und ROI. Nutze das ROI-Tool.")]
        })
        last = result["messages"][-1]
        parsed = _extract_json(last.content)
        report = parsed if isinstance(parsed, dict) else {"raw": last.content}

        return {
            "feasibility_report": report,
            "messages": [AIMessage(content="[Analysis] Machbarkeit und ROI bewertet.")],
        }

    def automation_node(self, state: AgentState) -> dict:
        """Generiert Automatisierungs-Artefakte."""
        agent = create_react_agent(self.model, self.automation_tools, prompt=AUTOMATION_PROMPT)
        tasks_json = json.dumps(state.get("tasks", []), ensure_ascii=False)
        result = agent.invoke({
            "messages": [HumanMessage(content=
                f"Aufgaben:\n{tasks_json}\n\n"
                "Generiere fuer jede automatisierbare Aufgabe ein Skript. Nutze die Code-Gen-Tools.")]
        })
        last = result["messages"][-1]

        # Sammle die generierten Artefakte aus den Tool-Aufrufen
        results = []
        for msg in result["messages"]:
            if hasattr(msg, "name") and msg.name in (
                "generate_python_automation", "generate_powershell_automation"):
                artifact = _extract_json(msg.content) or {}
                results.append({
                    "step_id": f"auto_{len(results)+1}",
                    "status": "success",
                    "output": artifact.get("script", "")[:500],
                    "tool_used": msg.name,
                })

        # Falls keine Tool-Calls erfasst: mindestens die Zusammenfassung speichern
        if not results:
            results.append({
                "step_id": "auto_1",
                "status": "success",
                "output": last.content[:500],
                "tool_used": "llm_direct",
            })

        return {
            "automation_results": results,
            "messages": [AIMessage(content=f"[Automation] {len(results)} Artefakte generiert.")],
        }

    def qa_node(self, state: AgentState) -> dict:
        """Prueft die generierten Artefakte."""
        agent = create_react_agent(self.model, [], prompt=QA_PROMPT)
        summary = {
            "tasks": len(state.get("tasks", [])),
            "artifacts": len(state.get("automation_results", [])),
            "results": state.get("automation_results", []),
        }
        result = agent.invoke({
            "messages": [HumanMessage(content=
                f"Zu pruefende Ergebnisse:\n{json.dumps(summary, ensure_ascii=False)}\n\n"
                "Erstelle einen QA-Report.")]
        })
        last = result["messages"][-1]
        parsed = _extract_json(last.content)
        report = parsed if isinstance(parsed, dict) else {"raw": last.content}

        return {
            "qa_report": report,
            "messages": [AIMessage(content="[QA] Qualitaetspruefung abgeschlossen.")],
        }

    # --- Routing ---
    def route_from_supervisor(self, state: AgentState) -> str:
        """Bestimmt die Kante vom Supervisor zum naechsten Node."""
        next_agent = state.get("next_agent", "FINISH")
        return END if next_agent == "FINISH" else next_agent

    # --- Graph Assembly ---
    def build(self):
        """Baut und kompiliert den Graphen."""
        graph = StateGraph(AgentState)

        # Nodes registrieren
        graph.add_node("supervisor", self.supervisor_node)
        graph.add_node("intake_agent", self.intake_node)
        graph.add_node("analysis_agent", self.analysis_node)
        graph.add_node("automation_agent", self.automation_node)
        graph.add_node("qa_agent", self.qa_node)

        # Einstieg: immer zum Supervisor
        graph.add_edge(START, "supervisor")

        # Supervisor routet konditional zu einem Worker oder END
        graph.add_conditional_edges(
            "supervisor",
            self.route_from_supervisor,
            {
                "intake_agent": "intake_agent",
                "analysis_agent": "analysis_agent",
                "automation_agent": "automation_agent",
                "qa_agent": "qa_agent",
                END: END,
            },
        )

        # Jeder Worker kehrt zum Supervisor zurueck (Supervisor-Pattern)
        for worker in ["intake_agent", "analysis_agent", "automation_agent", "qa_agent"]:
            graph.add_edge(worker, "supervisor")

        return graph.compile(checkpointer=self.checkpointer)
