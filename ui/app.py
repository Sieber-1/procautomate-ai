"""
ProcAutomate-AI - Streamlit App.

Interaktive Oberflaeche fuer das Multi-Agent Prozessautomatisierungs-System.
Zeigt den Live-Fortschritt der Agenten und visualisiert den LangGraph.

Start: streamlit run ui/app.py
"""

import asyncio
import json
import sys
from pathlib import Path

import streamlit as st

# Projekt-Root zum Pfad hinzufuegen
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import validate_config  # noqa: E402
from core.runner import ProcessAutomationRunner  # noqa: E402


st.set_page_config(
    page_title="ProcAutomate-AI",
    page_icon="🤖",
    layout="wide",
)


def run_async(coro):
    """Fuehrt eine Coroutine in einem sauberen Event-Loop aus."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Sidebar ---
with st.sidebar:
    st.title("🤖 ProcAutomate-AI")
    st.caption("Multi-Agent Prozessautomatisierung mit LangGraph + MCP")

    st.divider()

    st.markdown("### 🏗 Architektur")
    st.markdown(
        "- **Orchestrierung:** LangGraph (Supervisor-Pattern)\n"
        "- **Tools:** MCP-Server (Microservices)\n"
        "- **State:** SQLite-Checkpointing\n"
        "- **LLM:** Claude Sonnet"
    )

    st.divider()

    st.markdown("### 🔄 Agenten-Pipeline")
    st.markdown(
        "1. **Intake** — zerlegt Prozess in Aufgaben\n"
        "2. **Analysis** — bewertet Machbarkeit + ROI\n"
        "3. **Automation** — generiert Skripte\n"
        "4. **QA** — prueft Qualitaet"
    )

    st.divider()
    ok, msg = validate_config()
    if ok:
        st.success("✅ Konfiguration OK")
    else:
        st.error(f"⚠️ {msg}")


# --- Hauptbereich ---
st.title("Prozessautomatisierungs-Analyse")
st.markdown(
    "Beschreibe einen Geschäftsprozess. Ein Team spezialisierter AI-Agenten "
    "zerlegt ihn, bewertet die Automatisierbarkeit, generiert Skripte und prüft das Ergebnis."
)

tab_run, tab_arch = st.tabs(["▶️ Analyse", "🏗 Architektur & Graph"])

with tab_run:
    # Beispiel laden
    sample_path = Path(__file__).parent.parent / "sample_data" / "prozess_rechnungen.txt"
    sample_text = sample_path.read_text(encoding="utf-8") if sample_path.exists() else ""

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("📄 Beispiel laden", use_container_width=True):
            st.session_state["process_input"] = sample_text

    process_input = st.text_area(
        "Prozessbeschreibung:",
        value=st.session_state.get("process_input", ""),
        height=250,
        placeholder="Beschreibe den Geschäftsprozess, den du automatisieren möchtest...",
    )

    start = st.button("🚀 Multi-Agent Analyse starten", type="primary")

    if start and process_input.strip():
        ok, msg = validate_config()
        if not ok:
            st.error(msg)
        else:
            # Live-Fortschrittsanzeige
            progress_container = st.container()
            log_area = st.empty()
            logs = []

            agent_labels = {
                "supervisor": "🧭 Supervisor entscheidet Routing",
                "intake_agent": "📥 Intake: Aufgaben werden extrahiert",
                "analysis_agent": "📊 Analysis: Machbarkeit + ROI",
                "automation_agent": "⚙️ Automation: Skripte werden generiert",
                "qa_agent": "✅ QA: Qualitätsprüfung",
            }

            def on_progress(node_name, node_output):
                label = agent_labels.get(node_name, node_name)
                logs.append(label)
                log_area.info("**Live-Fortschritt:**\n\n" + "\n\n".join(f"- {log}" for log in logs))

            runner = ProcessAutomationRunner()
            with st.spinner("Agenten arbeiten..."):
                try:
                    result = run_async(
                        runner.run(process_input, progress_callback=on_progress)
                    )
                    st.session_state["result"] = result
                    st.success("✅ Analyse abgeschlossen!")
                except Exception as e:
                    st.error(f"Fehler: {e}")
                    st.exception(e)

    # --- Ergebnisse anzeigen ---
    if "result" in st.session_state:
        result = st.session_state["result"]
        st.divider()

        # Aufgaben
        st.markdown("## 📥 Identifizierte Aufgaben")
        tasks = result.get("tasks", [])
        if tasks:
            for t in tasks:
                with st.expander(f"**{t.get('description', 'Aufgabe')}** ({t.get('complexity', '-')})"):
                    st.markdown(f"- **Quelle:** {t.get('input_source', '-')}")
                    st.markdown(f"- **Ziel:** {t.get('output_target', '-')}")
                    st.markdown(f"- **Typ:** {t.get('automation_type', '-')}")
        else:
            st.info("Keine strukturierten Aufgaben extrahiert.")

        # Analyse
        st.markdown("## 📊 Machbarkeit & ROI")
        feasibility = result.get("feasibility_report", {})
        if feasibility:
            st.json(feasibility)

        # Automatisierungs-Artefakte
        st.markdown("## ⚙️ Generierte Automatisierungs-Artefakte")
        artifacts = result.get("automation_results", [])
        for i, art in enumerate(artifacts, 1):
            with st.expander(f"Artefakt {i} — {art.get('tool_used', '-')} ({art.get('status', '-')})"):
                st.code(art.get("output", ""), language="python")

        # QA-Report
        st.markdown("## ✅ Qualitätsprüfung")
        qa = result.get("qa_report", {})
        if qa:
            if "coverage_percent" in qa:
                c1, c2 = st.columns(2)
                c1.metric("Abdeckung", f"{qa.get('coverage_percent', 0)}%")
                ready = qa.get("ready_for_deployment", False)
                c2.metric("Deployment-bereit", "Ja ✅" if ready else "Nein ⚠️")
                if qa.get("recommendations"):
                    st.markdown("**Empfehlungen:**")
                    for r in qa["recommendations"]:
                        st.markdown(f"- {r}")
            else:
                st.json(qa)

        # Export
        st.divider()
        st.download_button(
            "📥 Vollständiges Ergebnis als JSON",
            data=json.dumps(result, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
            file_name="automation_analysis.json",
            mime="application/json",
        )


with tab_arch:
    st.markdown("## 🏗 System-Architektur")
    st.markdown(
        "Dieses System nutzt das **Supervisor-Pattern** aus LangGraph. Ein "
        "Supervisor-LLM routet zwischen spezialisierten Worker-Agenten. Jeder "
        "Worker hat Zugriff auf Tools, die als eigenständige **MCP-Server** "
        "(Microservices) laufen."
    )

    st.markdown("### Der kompilierte Graph")
    st.markdown(
        "Der folgende Graph wird zur Laufzeit aus dem Code generiert — er ist "
        "kein statisches Bild, sondern spiegelt die echte Struktur wider:"
    )

    mermaid = """
graph TD
    START([Start]) --> SUP[🧭 Supervisor]
    SUP -.routet.-> INT[📥 Intake Agent]
    SUP -.routet.-> ANA[📊 Analysis Agent]
    SUP -.routet.-> AUT[⚙️ Automation Agent]
    SUP -.routet.-> QA[✅ QA Agent]
    INT --> SUP
    ANA --> SUP
    AUT --> SUP
    QA --> SUP
    SUP -.FINISH.-> END([Ende])
    """
    st.code(mermaid, language="mermaid")

    st.markdown("### Warum diese Architektur?")
    st.markdown(
        "- **Supervisor-Pattern:** Jeder Agent bleibt einfach und single-purpose. "
        "Der Supervisor routet nur, führt selbst keine Tools aus.\n"
        "- **MCP-Server als Microservices:** Tools leben außerhalb der Agent-Codebasis. "
        "Man kann sie versionieren, austauschen oder neustarten, ohne die Agenten neu zu deployen.\n"
        "- **SQLite-Checkpointing:** Der State überlebt Abstürze. Ein unterbrochener "
        "Durchlauf kann mit derselben Session-ID wieder aufgenommen werden (Time-Travel-Debugging).\n"
        "- **Circuit Breaker:** Ein Iterations-Zähler verhindert Endlosschleifen zwischen "
        "Supervisor und Workern."
    )
