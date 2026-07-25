"""
MCP Server: Data Tools.

Dieser Server stellt Werkzeuge zur Datenverarbeitung als eigenstaendigen
Microservice bereit. Er kommuniziert ueber das Model Context Protocol (MCP)
per stdio oder HTTP.

Der entscheidende Vorteil: Diese Tools leben AUSSERHALB der Agent-Codebasis.
Man kann sie unabhaengig versionieren, austauschen oder neustarten, ohne den
Agenten neu zu deployen. Genau das Pattern, das moderne Enterprise-Setups
(UiPath, KNIME, Dify) mit MCP/A2A anstreben.

Start: python mcp_servers/data_tools_server.py
"""

import csv
import io
import json
import re

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("data-tools")


@mcp.tool()
def extract_structured_data(text: str, fields: list[str]) -> str:
    """
    Extrahiert benannte Felder aus unstrukturiertem Text mittels Regex-Heuristiken.

    Args:
        text: Der Rohtext (z.B. eine E-Mail oder ein Formular).
        fields: Liste der zu extrahierenden Feldnamen.

    Returns:
        JSON-String mit den extrahierten Feld-Wert-Paaren.
    """
    result = {}
    for field in fields:
        # Heuristik: Suche nach "Feldname: Wert" oder "Feldname = Wert"
        pattern = rf"{re.escape(field)}\s*[:=]\s*(.+?)(?:\n|$)"
        match = re.search(pattern, text, re.IGNORECASE)
        result[field] = match.group(1).strip() if match else None
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def csv_to_json(csv_text: str) -> str:
    """
    Konvertiert CSV-Text in eine JSON-Liste von Objekten.

    Args:
        csv_text: CSV-Inhalt als String (mit Header-Zeile).

    Returns:
        JSON-String einer Liste von Dicts.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    return json.dumps(rows, ensure_ascii=False)


@mcp.tool()
def validate_data_quality(json_data: str, required_fields: list[str]) -> str:
    """
    Prueft einen JSON-Datensatz auf Vollstaendigkeit und Qualitaet.

    Args:
        json_data: JSON-String (Liste von Objekten oder einzelnes Objekt).
        required_fields: Felder, die vorhanden und nicht leer sein muessen.

    Returns:
        JSON-Report mit Fehlern und Qualitaets-Score.
    """
    try:
        data = json.loads(json_data)
    except json.JSONDecodeError:
        return json.dumps({"valid": False, "error": "Ungueltiges JSON"})

    records = data if isinstance(data, list) else [data]
    issues = []
    total_checks = 0
    passed_checks = 0

    for idx, record in enumerate(records):
        for field in required_fields:
            total_checks += 1
            value = record.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                issues.append(f"Datensatz {idx}: Feld '{field}' fehlt oder leer")
            else:
                passed_checks += 1

    score = round(passed_checks / total_checks * 100, 1) if total_checks else 100.0
    return json.dumps(
        {
            "valid": len(issues) == 0,
            "quality_score": score,
            "record_count": len(records),
            "issues": issues,
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
