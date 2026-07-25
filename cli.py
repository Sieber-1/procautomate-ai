"""
ProcAutomate-AI - Command Line Interface.

Ermoeglicht die Ausfuehrung der Analyse direkt aus dem Terminal,
ohne Streamlit. Nuetzlich fuer Automatisierung und CI.

Nutzung:
    python cli.py --file sample_data/prozess_rechnungen.txt
    python cli.py --text "Beschreibung des Prozesses..."
    python cli.py --graph   # zeigt nur den Graphen
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from core.config import validate_config
from core.runner import ProcessAutomationRunner


def _print_header(text: str):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


async def run_analysis(process_text: str):
    """Fuehrt die Analyse aus und gibt die Ergebnisse formatiert aus."""
    runner = ProcessAutomationRunner()

    def on_progress(node_name: str, _output: dict):
        labels = {
            "supervisor": "🧭 Supervisor routet...",
            "intake_agent": "📥 Intake extrahiert Aufgaben...",
            "analysis_agent": "📊 Analysis bewertet Machbarkeit + ROI...",
            "automation_agent": "⚙️  Automation generiert Skripte...",
            "qa_agent": "✅ QA prueft Qualitaet...",
        }
        print(f"   {labels.get(node_name, node_name)}")

    _print_header("Multi-Agent Analyse laeuft")
    result = await runner.run(process_text, progress_callback=on_progress)

    _print_header("Ergebnisse")

    tasks = result.get("tasks", [])
    print(f"\n📥 Identifizierte Aufgaben: {len(tasks)}")
    for t in tasks:
        print(f"   - {t.get('description', '?')} "
              f"[{t.get('automation_type', '?')}, {t.get('complexity', '?')}]")

    feasibility = result.get("feasibility_report", {})
    if feasibility:
        print("\n📊 Machbarkeit & ROI:")
        print("   " + json.dumps(feasibility, ensure_ascii=False, indent=2).replace("\n", "\n   "))

    artifacts = result.get("automation_results", [])
    print(f"\n⚙️  Generierte Artefakte: {len(artifacts)}")
    for a in artifacts:
        print(f"   - {a.get('tool_used', '?')} ({a.get('status', '?')})")

    qa = result.get("qa_report", {})
    if qa:
        print("\n✅ QA-Report:")
        if "coverage_percent" in qa:
            print(f"   Abdeckung: {qa.get('coverage_percent')}%")
            print(f"   Deployment-bereit: {qa.get('ready_for_deployment')}")
        for rec in qa.get("recommendations", []):
            print(f"   Empfehlung: {rec}")

    # Ergebnis speichern
    out_path = Path("automation_analysis.json")
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"\n💾 Vollstaendiges Ergebnis gespeichert: {out_path}")


async def show_graph():
    """Zeigt den Mermaid-Graphen."""
    runner = ProcessAutomationRunner()
    _print_header("LangGraph Struktur")
    print(await runner.get_mermaid_diagram())


def main():
    parser = argparse.ArgumentParser(description="ProcAutomate-AI CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=str, help="Pfad zu einer Prozessbeschreibungs-Datei")
    group.add_argument("--text", type=str, help="Prozessbeschreibung als Text")
    group.add_argument("--graph", action="store_true", help="Nur den Graphen anzeigen")
    args = parser.parse_args()

    if args.graph:
        asyncio.run(show_graph())
        return

    ok, msg = validate_config()
    if not ok:
        print(f"Konfigurationsfehler: {msg}", file=sys.stderr)
        sys.exit(1)

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = args.text

    asyncio.run(run_analysis(text))


if __name__ == "__main__":
    main()
