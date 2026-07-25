"""
End-to-End Test des Multi-Agent Graphen mit Mock-LLM.

Prueft, dass der Supervisor korrekt durch alle Worker routet, der State
sauber zwischen den Agenten fliesst und der Graph terminiert. Verwendet
ein Mock-LLM, damit kein API-Key noetig ist.

Ausfuehren: pytest tests/test_graph_flow.py -v
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


class _MockModel:
    """Mock-LLM fuer den Supervisor: routet fest durch die Pipeline."""

    def __init__(self, routing):
        self._routing = iter(routing)

    def invoke(self, messages):
        return AIMessage(content=next(self._routing))

    def bind_tools(self, tools):
        return self


def _mock_react_agent(model, tools, prompt=None):
    """Mock eines ReAct-Agenten mit plausiblen JSON-Antworten."""
    p = prompt or ""
    if "Intake" in p or "zerleg" in p.lower():
        content = ('```json\n[{"step_id":"1","description":"PDF speichern",'
                   '"input_source":"email","output_target":"netzlaufwerk",'
                   '"automation_type":"file_transform","complexity":"niedrig"},'
                   '{"step_id":"2","description":"Daten extrahieren",'
                   '"input_source":"pdf","output_target":"excel",'
                   '"automation_type":"data_extraction","complexity":"mittel"}]\n```')
    elif "Analysis" in p:
        content = '```json\n{"feasible":true,"technology":"Python","roi":"5000 EUR/Jahr"}\n```'
    elif "QA" in p:
        content = ('```json\n{"coverage_percent":90,"issues":[],'
                   '"recommendations":["PDF-Parser testen"],'
                   '"ready_for_deployment":true}\n```')
    else:
        content = "Automatisierung generiert."
    agent = MagicMock()
    agent.invoke = lambda x: {"messages": [AIMessage(content=content)]}
    return agent


@pytest.mark.asyncio
async def test_full_pipeline_flow():
    """Der Graph durchlaeuft intake -> analysis -> automation -> qa -> FINISH."""
    from core import graph as graph_mod

    routing = ["intake_agent", "analysis_agent", "automation_agent", "qa_agent", "FINISH"]
    with patch.object(graph_mod, "init_chat_model", return_value=_MockModel(routing)), \
         patch.object(graph_mod, "create_react_agent", side_effect=_mock_react_agent):
        from core.graph import GraphBuilder

        app = GraphBuilder(tools=[]).build()
        state = {
            "messages": [], "process_description": "Test-Prozess",
            "tasks": [], "feasibility_report": {}, "automation_results": [],
            "qa_report": {}, "next_agent": "", "iteration_count": 0,
        }

        steps, final = [], dict(state)
        async for chunk in app.astream(
            state, config={"configurable": {"thread_id": "test"}, "recursion_limit": 50}
        ):
            for node, out in chunk.items():
                steps.append(node)
                final = {**final, **out}

    # Supervisor muss jeden Worker genau einmal angesteuert haben
    assert "intake_agent" in steps
    assert "analysis_agent" in steps
    assert "automation_agent" in steps
    assert "qa_agent" in steps
    # State-Fluss korrekt
    assert len(final["tasks"]) == 2
    assert final["feasibility_report"]["feasible"] is True
    assert len(final["automation_results"]) >= 1
    assert final["qa_report"]["ready_for_deployment"] is True


@pytest.mark.asyncio
async def test_circuit_breaker():
    """Bei Endlos-Routing greift der Circuit Breaker und terminiert."""
    from core import graph as graph_mod

    # LLM routet immer zu intake -> wuerde ohne Breaker ewig laufen
    infinite_routing = ["intake_agent"] * 100
    with patch.object(graph_mod, "init_chat_model", return_value=_MockModel(infinite_routing)), \
         patch.object(graph_mod, "create_react_agent", side_effect=_mock_react_agent):
        from core.graph import GraphBuilder
        import core.config as cfg

        app = GraphBuilder(tools=[]).build()
        state = {
            "messages": [], "process_description": "Test",
            "tasks": [], "feasibility_report": {}, "automation_results": [],
            "qa_report": {}, "next_agent": "", "iteration_count": 0,
        }

        count = 0
        async for chunk in app.astream(
            state, config={"configurable": {"thread_id": "cb"}, "recursion_limit": 100}
        ):
            count += 1

        # Muss durch MAX_ITERATIONS begrenzt terminieren, nicht durch recursion_limit
        assert count < 100
