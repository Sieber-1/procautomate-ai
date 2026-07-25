"""
Tests fuer die MCP-Tool-Logik.

Diese Tests pruefen die Rechen- und Extraktionslogik der MCP-Server-Tools
ohne LLM. Sie starten die MCP-Server als echte Subprozesse und rufen die
Tools ueber das MCP-Protokoll auf.

Ausfuehren: pytest tests/test_mcp_tools.py -v
"""

import json
from pathlib import Path

import pytest
from langchain_mcp_adapters.client import MultiServerMCPClient


_BASE = Path(__file__).parent.parent


def _unwrap(result):
    """MCP-Tools geben Content-Bloecke zurueck; extrahiere das JSON."""
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return json.loads(result[0]["text"])
    return json.loads(result)


async def _get_tools():
    client = MultiServerMCPClient({
        "data_tools": {
            "command": "python",
            "args": [str(_BASE / "mcp_servers" / "data_tools_server.py")],
            "transport": "stdio",
        },
        "automation_tools": {
            "command": "python",
            "args": [str(_BASE / "mcp_servers" / "automation_tools_server.py")],
            "transport": "stdio",
        },
    })
    return {t.name: t for t in await client.get_tools()}


@pytest.mark.asyncio
async def test_roi_calculation():
    """ROI: 200 Rechnungen x 4 Min x 15 EUR/h = 200 EUR/Monat."""
    tools = await _get_tools()
    roi = _unwrap(await tools["estimate_automation_roi"].ainvoke(
        {"manual_minutes_per_run": 4, "runs_per_month": 200, "hourly_cost_eur": 15.0}))
    assert roi["monthly_saving_eur"] == 200.0
    assert roi["annual_saving_eur"] == 2400.0


@pytest.mark.asyncio
async def test_structured_extraction():
    """Feld-Extraktion aus unstrukturiertem Text."""
    tools = await _get_tools()
    ext = _unwrap(await tools["extract_structured_data"].ainvoke(
        {"text": "Rechnungsnummer: RE-2024-001\nBetrag: 1500 EUR",
         "fields": ["Rechnungsnummer", "Betrag"]}))
    assert ext["Rechnungsnummer"] == "RE-2024-001"
    assert ext["Betrag"] == "1500 EUR"


@pytest.mark.asyncio
async def test_data_quality_validation():
    """Datenqualitaet: ein leeres Feld von vier -> 75% Score."""
    tools = await _get_tools()
    qual = _unwrap(await tools["validate_data_quality"].ainvoke(
        {"json_data": '[{"name":"A","betrag":100},{"name":"","betrag":200}]',
         "required_fields": ["name", "betrag"]}))
    assert qual["quality_score"] == 75.0
    assert qual["valid"] is False
    assert len(qual["issues"]) == 1


@pytest.mark.asyncio
async def test_python_generation():
    """Python-Skript-Generierung enthaelt passende Imports."""
    tools = await _get_tools()
    py = _unwrap(await tools["generate_python_automation"].ainvoke(
        {"task_description": "CSV nach JSON", "input_type": "csv", "output_type": "json"}))
    assert "pandas" in py["script"]
    assert py["language"] == "python"


@pytest.mark.asyncio
async def test_powershell_generation():
    """PowerShell-Skript-Generierung erzeugt gueltiges Geruest."""
    tools = await _get_tools()
    ps = _unwrap(await tools["generate_powershell_automation"].ainvoke(
        {"task_description": "Dateien verschieben"}))
    assert "param(" in ps["script"]
    assert ps["language"] == "powershell"
