# Architektur-Vertiefung & Interview-Vorbereitung

Dieses Dokument erklärt die technischen Entscheidungen im Detail. Es dient auch als deine Vorbereitung: Wenn dich jemand im Interview zu diesem Projekt fragt, findest du hier die Antworten — aber verstehe sie, lerne sie nicht auswendig.

---

## Warum LangGraph und nicht nur LangChain?

**Kurz:** LangChain ist die Werkzeugschicht (Prompts, Modelle, Tools). LangGraph ist die Orchestrierungsschicht darüber.

Ein einfacher LangChain-Agent ist im Kern eine Schleife: reasoning → tool call → observation → reasoning. Das reicht für einen einzelnen Agenten. Sobald man aber **mehrere Agenten** koordinieren, den Zustand **persistieren** oder **konditional verzweigen** will, muss man diese Logik selbst bauen — fehleranfällig und schwer zu debuggen.

LangGraph modelliert den Workflow als **gerichteten Graphen**: Nodes sind Berechnungsschritte, Edges sind Übergänge. Zyklen (Worker → Supervisor → Worker) sind nativ möglich. Der State wird automatisch gemerged und gecheckpointet.

**Die Kernfrage, die du beantworten können musst:** "Warum nicht einfach ein großer Prompt oder eine lineare Kette?"
→ Weil echte Automatisierungs-Analysen mehrere unterschiedliche Kompetenzen brauchen (Extraktion, Bewertung, Generierung, Prüfung), die man sauber trennen will. Getrennte Agenten sind einfacher zu testen, zu debuggen und einzeln zu verbessern. Und weil man Zwischenzustände persistieren will, um bei Fehlern nicht von vorne zu beginnen.

## Warum das Supervisor-Pattern?

Es gibt mehrere Multi-Agent-Muster:

- **Supervisor** (dieses Projekt): Ein zentraler Router entscheidet, welcher Agent als nächstes arbeitet. Jeder Worker ist einfach und single-purpose.
- **Swarm/Netzwerk**: Agenten geben direkt aneinander ab, ohne zentrale Instanz.
- **Hierarchisch**: Supervisoren von Supervisoren.

Ich habe **Supervisor** gewählt, weil der Kontrollfluss dadurch explizit und nachvollziehbar bleibt. Man sieht zu jedem Zeitpunkt, wer warum arbeitet. Für einen linearen Prozess (Analyse → Generierung → Prüfung) mit optionalen Rücksprüngen ist das die klarste Wahl.

**Wichtig:** Der Supervisor führt selbst **keine** Tools aus. Er routet nur. Das hält die Verantwortlichkeiten sauber getrennt.

## Warum MCP-Server statt einfacher Python-Funktionen?

Das ist der Teil, der am meisten auffällt — und den du besonders gut verstehen solltest.

Man könnte die Tools einfach als `@tool`-dekorierte Python-Funktionen im Agent-Code definieren. Das funktioniert und ist für kleine Projekte oft die bessere Wahl.

Ich habe sie stattdessen als **MCP-Server** (Model Context Protocol) gebaut. Das bedeutet: Die Tools laufen als **eigenständige Prozesse** und kommunizieren mit dem Agenten über ein standardisiertes Protokoll (JSON-RPC 2.0 über stdio oder HTTP).

**Vorteile:**
- Tools leben außerhalb der Agent-Codebasis → unabhängig versionierbar
- Ein Tool-Server kann neugestartet oder ausgetauscht werden, ohne die Agenten neu zu deployen
- Dasselbe Tool kann von mehreren Agenten (auch aus anderen Frameworks) genutzt werden
- Es ist genau das Muster, das Enterprise-Plattformen (UiPath, KNIME, Dify) mit MCP/A2A verfolgen

**Ehrlicher Trade-off, den du nennen solltest:** MCP fügt Komplexität und etwas Latenz hinzu (Prozess-Kommunikation statt direktem Funktionsaufruf). Für ein Solo-Skript wäre `@tool` schneller. MCP lohnt sich, wenn Tools geteilt, unabhängig deployed oder über Sprach-/Framework-Grenzen hinweg genutzt werden. Die offizielle Doku sagt sogar explizit: "do you actually need MCP? or can you get away with a simple `@tool`?" — Ich habe MCP bewusst gewählt, weil das Projekt die geteilte, service-orientierte Tool-Architektur demonstrieren soll, die dem Enterprise-Kontext entspricht.

## Warum State-Checkpointing?

Der State wird nach jedem Node in SQLite gespeichert. Warum?

- **Crash-Recovery:** Stürzt der Prozess in Schritt 3 ab, kann man mit derselben `thread_id` genau dort weitermachen — die ersten beiden Schritte müssen nicht wiederholt werden (spart Zeit und API-Kosten).
- **Human-in-the-Loop:** Man kann den Graphen pausieren, einen Menschen entscheiden lassen und dann fortsetzen.
- **Time-Travel-Debugging:** Man kann den State zu jedem vergangenen Zeitpunkt inspizieren.

Ein naiver `for`-Loop verliert bei einem Absturz alles. Genau das macht LangGraph zu einem Produktions-Tool statt einem Prototyp.

## Der State im Detail

Der State ist ein `TypedDict`. Ein Feld ist besonders:

```python
messages: Annotated[list[BaseMessage], operator.add]
```

Das `operator.add` ist ein **Reducer**. Es sagt LangGraph: Wenn ein Node dieses Feld aktualisiert, hänge die neuen Werte an, statt sie zu überschreiben. So können mehrere Agenten unabhängig Nachrichten beisteuern, ohne sich gegenseitig zu überschreiben. Felder ohne Reducer (wie `tasks`) werden hingegen ersetzt.

## Der Circuit Breaker

Zyklische Graphen haben ein Risiko: Endlosschleifen. Wenn der Supervisor immer wieder zum selben Worker routet, läuft das System ewig.

Lösung: Ein `iteration_count` im State, der bei jedem Supervisor-Durchlauf erhöht wird. Übersteigt er `MAX_ITERATIONS`, erzwingt der Supervisor `FINISH`. LangGraph hat zusätzlich ein `recursion_limit` als zweites Sicherheitsnetz.

## Fragen, auf die du vorbereitet sein solltest

1. **"Was passiert, wenn ein Agent fehlerhaftes JSON zurückgibt?"**
   → Die `_extract_json`-Funktion hat mehrere Fallback-Stufen: erst Codeblock-Extraktion, dann Suche nach balanciertem JSON, dann greedy Parsing. Schlägt alles fehl, wird der Rohtext gespeichert statt zu crashen.

2. **"Wie würdest du das auf 100 Prozesse gleichzeitig skalieren?"**
   → MCP-Server auf HTTP umstellen (verteilt deploybar), PostgreSQL statt SQLite als Checkpointer (concurrency-sicher), und die Analysen als separate Threads/Sessions parallel laufen lassen.

3. **"Warum Claude und nicht GPT?"**
   → Über `init_chat_model` ist der Provider austauschbar (eine Zeile in `.env`). Claude Sonnet liefert gute Ergebnisse für deutsche Fachsprache und strukturierte Outputs. Die Architektur ist provider-agnostisch.

4. **"Was ist der schwächste Teil des Systems?"**
   → Die Skript-Generierung liefert Gerüste, keine fertige Geschäftslogik. Und die Extraktions-Tools nutzen Regex-Heuristiken, die bei stark abweichenden Formaten versagen können. Beides bewusste Scope-Entscheidungen, aber ehrlich zu benennen.

## Ehrliche Grenzen des Projekts

- Die generierten Skripte sind **Startpunkte**, keine deploybare Software.
- Die MCP-Server nutzen stdio (lokal), nicht HTTP (verteilt) — für echte Microservices wäre HTTP der nächste Schritt.
- Kein echtes RAG — bei sehr langen Dokumenten würde der Kontext knapp.
- Die Regex-Extraktion ist simpel. Produktiv würde man hier ein spezialisiertes Extraktionsmodell einsetzen.

Diese Grenzen zu kennen und zu benennen ist wichtiger, als das Projekt größer zu reden als es ist.
