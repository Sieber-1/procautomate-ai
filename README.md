# 🤖 ProcAutomate-AI

**Ein Multi-Agent-System, das Geschäftsprozesse analysiert und Automatisierungslösungen generiert — gebaut mit LangGraph, MCP und dem Supervisor-Pattern.**

Beschreibe einen manuellen Geschäftsprozess in natürlicher Sprache. Ein Team spezialisierter AI-Agenten zerlegt ihn in automatisierbare Aufgaben, bewertet Machbarkeit und ROI, generiert lauffähige Automatisierungs-Skripte (Python/PowerShell) und prüft das Ergebnis auf Qualität.

---

## 🎯 Das Problem

Unternehmen automatisieren tausende Prozesse (RPA, ETL, Skripting). Der teuerste Schritt ist nicht das Programmieren — es ist die **Analyse**: Welche Schritte lohnt es zu automatisieren? Mit welcher Technologie? Was ist der ROI? Diese Vorarbeit macht heute ein Mensch manuell für jeden einzelnen Use Case.

ProcAutomate-AI automatisiert diese Analyse selbst. Aus einer Prozessbeschreibung entsteht in unter zwei Minuten ein strukturierter Automatisierungs-Vorschlag mit Skript-Gerüsten und ROI-Rechnung.

## 🏗 Architektur

Das System nutzt das **Supervisor-Pattern** aus LangGraph — dieselbe Architektur, die u.a. LinkedIn 2026 für seine AI-Workflows dokumentiert hat.

```
                    ┌─────────────────┐
        ┌──────────►│   Supervisor    │◄──────────┐
        │           │  (LLM, routet)  │           │
        │           └────────┬────────┘           │
        │                    │                     │
        │      ┌─────────────┼─────────────┐       │
        │      ▼             ▼             ▼       │
   ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌──────┐│
   │ Intake  │ │ Analysis │ │Automation │ │  QA  ││
   │ Agent   │ │  Agent   │ │  Agent    │ │Agent ││
   └────┬────┘ └────┬─────┘ └─────┬─────┘ └───┬──┘│
        └───────────┴─────────────┴───────────┴───┘
                    │
              ┌─────┴──────┐         ┌──────────────────┐
              │ MCP Server │         │   MCP Server     │
              │ data-tools │         │ automation-tools │
              │(Microservice)        │  (Microservice)  │
              └────────────┘         └──────────────────┘
```

**Vier spezialisierte Agenten:**

1. **Intake Agent** — zerlegt die Prozessbeschreibung in strukturierte, einzeln automatisierbare Aufgaben
2. **Analysis Agent** — bewertet technische Machbarkeit und berechnet den ROI (via MCP-Tool)
3. **Automation Agent** — generiert lauffähige Python- und PowerShell-Skript-Gerüste
4. **QA Agent** — prüft Abdeckung, Qualität und Deployment-Bereitschaft

**Der Supervisor** ist ein LLM, das ausschließlich routet — es führt selbst keine Tools aus. Nach jedem Worker kehrt der Fluss zum Supervisor zurück, der über den nächsten Schritt entscheidet.

## 🔑 Zentrale technische Konzepte

Diese vier Dinge unterscheiden das Projekt von einem einfachen Agent-Loop:

**1. Supervisor-Pattern mit LangGraph**
Statt einer linearen Kette wird der Workflow als **gerichteter Graph** modelliert. Nodes sind Agenten, Edges sind Übergänge. Der Graph unterstützt Zyklen (Worker → Supervisor → Worker), konditionales Routing und paralleles Fan-out.

**2. MCP-Server als Microservices**
Die Tools (`extract_structured_data`, `generate_python_automation`, `estimate_automation_roi` etc.) leben in **eigenständigen MCP-Servern**, nicht im Agent-Code. Kommunikation über das Model Context Protocol (JSON-RPC 2.0 über stdio). Vorteil: Tools können versioniert, ausgetauscht oder neugestartet werden, ohne die Agenten neu zu deployen — exakt das Prinzip, das Enterprise-Plattformen wie UiPath, KNIME und Dify mit MCP/A2A verfolgen.

**3. State-Checkpointing (SQLite)**
Der gemeinsame State wird nach **jedem** Node in SQLite gecheckpointet. Ein abgestürzter Durchlauf überlebt und kann mit derselben Session-ID wieder aufgenommen werden. Das ist der Unterschied zwischen einem Prototyp und einem produktionstauglichen System.

**4. Circuit Breaker**
Ein Iterations-Zähler im State verhindert Endlosschleifen zwischen Supervisor und Workern — eine praktische Notwendigkeit bei zyklischen Agent-Graphen.

## 🛠 Tech Stack

| Bereich | Technologie |
|---|---|
| Orchestrierung | LangGraph 1.2 (Supervisor-Pattern) |
| Tool-Integration | MCP (langchain-mcp-adapters) |
| LLM | Claude Sonnet (Anthropic) — via `init_chat_model` auch OpenAI |
| State-Persistenz | LangGraph SQLite Checkpointer |
| UI | Streamlit |
| Tests | pytest + pytest-asyncio |

## 🚀 Setup

```bash
# 1. Repository klonen
git clone https://github.com/Sieber-1/procautomate-ai.git
cd procautomate-ai

# 2. Virtuelle Umgebung
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Abhängigkeiten
pip install -r requirements.txt

# 4. API Key konfigurieren
cp .env.example .env
# .env öffnen und ANTHROPIC_API_KEY eintragen
```

API Key anfordern: [console.anthropic.com](https://console.anthropic.com/)

## 📖 Nutzung

### Streamlit-UI (empfohlen)

```bash
streamlit run ui/app.py
```

Öffnet sich unter `http://localhost:8501`. Beispielprozess laden, Analyse starten, Live-Fortschritt der Agenten verfolgen.

### Command Line

```bash
# Analyse aus Datei
python cli.py --file sample_data/prozess_rechnungen.txt

# Analyse aus Text
python cli.py --text "Beschreibung des Prozesses..."

# Nur den Graphen anzeigen (kein API-Key nötig)
python cli.py --graph
```

## 🧪 Tests

```bash
pytest tests/ -v
```

Die Tests decken ab:
- **Graph-Flow** — der Supervisor routet korrekt durch alle vier Worker, der State fließt sauber, der Graph terminiert (mit Mock-LLM, kein API-Key nötig)
- **Circuit Breaker** — bei fehlerhaftem Endlos-Routing greift die Iterations-Begrenzung
- **MCP-Tools** — ROI-Berechnung, Datenextraktion, Qualitätsprüfung und Skript-Generierung mit echten Werten

Alle 7 Tests laufen ohne API-Key (MCP-Server werden als echte Subprozesse gestartet).

## 📁 Projektstruktur

```
procautomate-ai/
├── core/
│   ├── state.py         # Gemeinsamer State (TypedDict + Reducer)
│   ├── graph.py         # LangGraph Supervisor-Graph  ← Herzstück
│   ├── runner.py        # MCP-Anbindung + Ausführung
│   └── config.py        # Konfiguration
├── agents/
│   └── prompts.py       # System-Prompts pro Agent
├── mcp_servers/
│   ├── data_tools_server.py        # MCP-Server: Datenverarbeitung
│   └── automation_tools_server.py  # MCP-Server: Code-Generierung
├── ui/
│   └── app.py           # Streamlit-Oberfläche
├── tests/
│   ├── test_graph_flow.py   # End-to-End Graph-Tests
│   └── test_mcp_tools.py    # MCP-Tool-Tests
├── sample_data/
│   └── prozess_rechnungen.txt
├── cli.py               # Command-Line-Interface
└── requirements.txt
```

## 🎓 Was dieses Projekt demonstriert

- **LangGraph über Tutorial-Niveau** — nicht nur ein linearer Agent, sondern das zyklische Supervisor-Pattern mit konditionalem Routing und Checkpointing
- **MCP-Integration** — Tools als eigenständige Microservices, nicht als hartcodierte Funktionen
- **Produktionsdenken** — State-Persistenz, Circuit Breaker, Fehlerbehandlung, Tests
- **Business-Kontext** — angewandt auf einen realen RPA/Automatisierungs-Use-Case mit ROI-Quantifizierung
- **Sauberer Code** — klare Modul-Trennung, Single-Responsibility-Agenten, Typannotationen

## 🚧 Mögliche Erweiterungen

- [ ] MCP-Server über HTTP statt stdio (echte verteilte Microservices)
- [ ] A2A-Protokoll für Agent-zu-Agent-Kommunikation
- [ ] Human-in-the-Loop-Gate vor der Skript-Generierung (LangGraph unterstützt das nativ via `interrupt`)
- [ ] Anbindung echter Datenquellen (Snowflake, SQL Server) als zusätzliche MCP-Server
- [ ] PDF-Parsing im Intake (aktuell Text-Input)
- [ ] LangSmith-Tracing für Observability
- [ ] Export der generierten Skripte als lauffähige Dateien

## 📝 Hinweise

- Das Beispieldokument (Rechnungsverarbeitung) ist fiktiv.
- Die generierten Skripte sind **Gerüste** — die Geschäftslogik muss angepasst werden. Das ist bewusst so: der Agent liefert das Skelett, der Mensch füllt die domänenspezifische Logik.
- API-Kosten pro vollständiger Analyse: ca. $0.10–$0.30.

## 📄 Lizenz

MIT

---

