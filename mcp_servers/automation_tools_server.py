"""
MCP Server: Automation Tools.

Stellt Werkzeuge bereit, die Automatisierungs-Artefakte generieren:
lauffaehige Python-Skripte und PowerShell-Skripte fuer typische
RPA-Aufgaben (Datei-Handling, Datenextraktion, Reporting).

Wie data_tools_server ein eigenstaendiger MCP-Microservice.

Start: python mcp_servers/automation_tools_server.py
"""

import json

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("automation-tools")


@mcp.tool()
def generate_python_automation(task_description: str, input_type: str, output_type: str) -> str:
    """
    Generiert ein lauffaehiges Python-Skript-Geruest fuer eine Automatisierungsaufgabe.

    Args:
        task_description: Was das Skript tun soll.
        input_type: Eingabeformat (z.B. "csv", "excel", "email", "pdf").
        output_type: Ausgabeformat (z.B. "json", "excel", "database").

    Returns:
        JSON mit dem generierten Skript und Metadaten.
    """
    templates = {
        "csv": "import pandas as pd\ndf = pd.read_csv(input_path)",
        "excel": "import pandas as pd\ndf = pd.read_excel(input_path)",
        "json": "import json\nwith open(input_path) as f:\n    data = json.load(f)",
        "email": "import email\nfrom email import policy\nmsg = email.message_from_file(open(input_path), policy=policy.default)",
    }
    output_templates = {
        "json": "df.to_json(output_path, orient='records', force_ascii=False)",
        "excel": "df.to_excel(output_path, index=False)",
        "database": "df.to_sql('table_name', engine, if_exists='append', index=False)",
    }

    read_code = templates.get(input_type, "# Input laden")
    write_code = output_templates.get(output_type, "# Output schreiben")

    script = f'''"""
Automatisierungsskript: {task_description}
Generiert von ProcAutomate-AI.
"""
import sys


def automate(input_path: str, output_path: str):
    # 1. Eingabe laden
    {read_code}

    # 2. Verarbeitung
    # TODO: Geschaeftslogik fuer: {task_description}

    # 3. Ausgabe schreiben
    {write_code}
    print(f"Verarbeitet: {{input_path}} -> {{output_path}}")


if __name__ == "__main__":
    automate(sys.argv[1], sys.argv[2])
'''
    return json.dumps(
        {
            "language": "python",
            "script": script,
            "input_type": input_type,
            "output_type": output_type,
            "dependencies": ["pandas", "openpyxl"] if "excel" in (input_type, output_type) else ["pandas"],
        },
        ensure_ascii=False,
    )


@mcp.tool()
def generate_powershell_automation(task_description: str) -> str:
    """
    Generiert ein PowerShell-Skript-Geruest fuer Datei- und Systemautomatisierung.

    Args:
        task_description: Was das Skript tun soll.

    Returns:
        JSON mit dem generierten PowerShell-Skript.
    """
    script = f'''<#
.SYNOPSIS
    {task_description}
    Generiert von ProcAutomate-AI.
#>

param(
    [Parameter(Mandatory=$true)][string]$SourcePath,
    [Parameter(Mandatory=$true)][string]$TargetPath
)

# Aufgabe: {task_description}
try {{
    # TODO: Automatisierungslogik
    Get-ChildItem -Path $SourcePath | ForEach-Object {{
        # Verarbeitung pro Datei
        Write-Host "Verarbeite: $($_.Name)"
    }}
    Write-Host "Fertig." -ForegroundColor Green
}} catch {{
    Write-Error "Fehler: $_"
    exit 1
}}
'''
    return json.dumps(
        {"language": "powershell", "script": script}, ensure_ascii=False
    )


@mcp.tool()
def estimate_automation_roi(
    manual_minutes_per_run: int, runs_per_month: int, hourly_cost_eur: float
) -> str:
    """
    Berechnet den ROI einer Automatisierung.

    Args:
        manual_minutes_per_run: Wie lange der manuelle Prozess pro Durchlauf dauert.
        runs_per_month: Anzahl Durchlaeufe pro Monat.
        hourly_cost_eur: Stundensatz der bearbeitenden Person.

    Returns:
        JSON mit ROI-Kennzahlen.
    """
    manual_hours_month = manual_minutes_per_run * runs_per_month / 60
    monthly_saving = round(manual_hours_month * hourly_cost_eur, 2)
    annual_saving = round(monthly_saving * 12, 2)

    return json.dumps(
        {
            "manual_hours_per_month": round(manual_hours_month, 1),
            "monthly_saving_eur": monthly_saving,
            "annual_saving_eur": annual_saving,
            "runs_per_month": runs_per_month,
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
