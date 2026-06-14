# Context Graph Demo

An interactive demo showing how **Context Graphs** enable AI agents to preserve, traverse, and reason over decisions — contrasted with what traditional RAG cannot do.

> "AI agents do not fail because information is missing. They fail because **context** is missing."

## What This Demo Shows

| Traditional RAG | Context Graph |
|---|---|
| Retrieves house descriptions, school info, tax records | Does all of that **plus** |
| Cannot recall why a house was rejected | Remembers the decision and reasons |
| Cannot explain what influenced a recommendation | Traces reasoning back to prior decisions |
| Loses context between sessions | Persists decisions, preferences, and history |
| Cannot answer "what if this preference changes?" | Traverses the graph to find all affected decisions |
| Memory is opaque — no way to inspect it | Graph traversal is visible — every path is shown |

## Scenario

A user evaluates homes with an AI assistant that:
- Stores preferences, decisions, and reasoning as a live graph
- Recalls which houses were rejected and **why**
- Traces multi-hop paths from preferences through decisions to recommendations
- Analyzes the impact of changing a preference across the entire decision history

---

## Prerequisites

- Python 3.9+
- An [Anthropic API key](https://console.anthropic.com/)

---

## Setup

**1. Clone / navigate to the project folder**

```bash
cd "ContextGraphs-AI4"
```

**2. Create a virtual environment (recommended)**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Add your API key**

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Open `.env` and set:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

---

## Run the App

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**

---

## Demo Walkthrough

The demo tells a single story in one chat window. **Phase 1** runs 6 steps with a RAG agent to expose the gaps. **Phase 2** runs the same 6 steps with a Context Graph agent to show them solved — then adds 2 graph-traversal steps that no flat memory system can replicate.

Click sidebar steps in order. The story unfolds in the chat.

---

### Phase 1 — RAG Agent

The RAG agent searches property listings and answers from documents. It has no persistent memory of decisions, preferences, or history.

**Step 1 — Compare Houses A, B, C**
The agent retrieves all three listings and compares them. RAG works well here — this is pure information retrieval.

**Step 2 — Remove House B** *(commute too long, HOA too high)*
The agent acknowledges the request but writes nothing down. No record of this decision exists anywhere.

**Step 3 — Which houses are we still considering?** *(one week later)*
Simulates a new session — RAG conversation history is cleared. The agent goes back to the documents and confidently lists all three houses including House B, completely unaware it was removed. This is the failure.

**Step 4 — Why did we reject House B?**
The agent has no record of the rejection. It retrieves House B's listing and describes its attributes — missing the question entirely.

**Step 5 — Add House D to our list**
House D's listing is introduced. The agent adds it to the comparison but has no stored preferences to evaluate it against — just raw scores.

**Step 6 — Why are you recommending House D?**
The agent gives a generic answer based on attribute scores alone. It cannot explain that House D was chosen because it avoids the specific problems that caused House B's rejection — that reasoning was never stored.

---

### Switching to Context Graph

Click **"Switch to Context Graph"** in the sidebar. A transition marker appears in the chat. The same 6 steps now run with an agent that reads and writes a persistent graph of decisions, reasons, and preferences.

---

### Phase 2 — Context Graph Agent

**Step 1 — Compare Houses A, B, C**
The agent retrieves the listings and records each house as a node in the Context Graph. Same answer as RAG — but now the evaluation is stored as graph structure.

**Step 2 — Remove House B** *(commute too long, HOA too high)*
The agent records a Decision node linked to House B, with Reason nodes for commute and HOA. The graph updates live. Rejected nodes turn red.

**Step 3 — Which houses are we still considering?**
The agent reads the graph. It immediately recalls that House B was rejected with specific reasons and a date. Returns House A and House C as active — no re-explaining required.

**Step 4 — Why did we reject House B?**
The agent traces `Decision → BASED_ON → Reason` nodes in the graph and gives the full explanation: the specific reasons, the rationale, and when the decision was made.

**Step 5 — Add House D to our list**
House D is added to the graph. The agent evaluates it against stored preferences derived from the House B rejection — good commute, lower HOA, strong resale — not just raw scores.

**Step 6 — Why are you recommending House D?**
The agent cites the prior rejection of House B as the explicit source of its evaluation criteria. The reasoning is traceable, explainable, and grounded in stored context.

---

### Graph Traversal Demo — Steps 7 & 8

These two steps show what Context Graphs can do that **no flat memory system can replicate**.

**Step 7 — What if commute is no longer a priority?**
The agent calls `analyze_preference_impact("commute")` — a graph traversal that:
1. Finds all Reason nodes containing "commute"
2. Walks up to the Decision nodes that were `BASED_ON` those reasons
3. Checks whether other reasons alone would still justify each decision
4. Reports which decisions might need revisiting

The affected nodes light up gold in the graph. This is structured impact analysis — not possible with unstructured memory.

**Step 8 — Trace: how exactly did we end up with House D?**
The agent traces the full multi-hop reasoning chain and highlights it in the graph:

```
User → PREFERS → [stored preferences]
     → influenced → Decision: REJECT House B
     → BASED_ON  → Reason: Commute too long
                 → Reason: HOA too high
     → GENERATED_FROM → Recommendation: House D
     → FOR_HOUSE → House D (Commute 5/5, HOA 4/5)
```

Every node in the chain glows gold simultaneously. The graph panel shows the "Reasoning Path Traversed" description below the visualization. This is graph traversal made visible — the key differentiator from ChatGPT-style memory.

---

### The contrast

Steps 3, 4, and 6 show memory working. Steps 7 and 8 show **structured reasoning over a graph** — something impossible with flat memory or vector search. Same question, fundamentally different architecture.

Use **Reset Demo** in the sidebar to clear all state and start fresh.

---

## Project Structure

```
app.py                  # Streamlit UI — chat + live graph panel
agent.py                # Claude agent: 9 graph-aware tools, streaming
rag_agent.py            # Stateless RAG agent for Phase 1 contrast
graph.py                # ContextGraph engine (NetworkX + JSON persistence)
data.py                 # House data definitions (A, B, C, D) + node colors
requirements.txt        # Python dependencies
.env.example            # API key template
context_graph.json      # Auto-created — persists graph state across sessions
```

---

## Context Graph Model

**Entity types:** `House`, `User`, `Decision`, `Reason`, `Preference`, `Recommendation`

**Relationships:**
```
User           ──EVALUATED──────► House
User           ──REJECTED────────► House (status changes to rejected, node turns red)
User           ──PREFERS─────────► Preference
Decision       ──CONSIDERED──────► House
Decision       ──BASED_ON────────► Reason
Recommendation ──FOR_HOUSE───────► House
Recommendation ──GENERATED_FROM──► Decision
```

**Agent tools (9 total):**

| Tool | Purpose |
|------|---------|
| `get_context_graph_state` | Read full graph — active houses, decisions, preferences, recommendations with node IDs |
| `get_active_candidates` | List houses still under consideration |
| `get_rejected_houses` | List rejected houses with reasons and dates |
| `add_decision` | Record accept / reject / defer with reasons and rationale |
| `add_preference` | Store a user preference linked to the User node |
| `add_recommendation` | Record a recommendation linked to the decision that generated it |
| `add_house_to_graph` | Add a new house node for evaluation |
| `highlight_reasoning_path` | Mark specific node IDs as the active reasoning chain — they glow gold in the graph |
| `analyze_preference_impact` | Traverse graph to find all decisions affected by removing a preference keyword |

---

## UI Layout

```
┌────────────────────┬─────────────────────────┐
│  Sidebar           │  Story Chat              │
│                    │  (fixed-height,          │
│  Phase 1 steps     │   auto-scrolling)        │
│  → Switch          │                          │
│  Phase 2 steps     ├─────────────────────────┤
│  Graph Traversal   │  Context Graph Panel     │
│  steps 7 & 8       │  (sticky — always        │
│                    │   visible while chat     │
│  Reset Demo        │   scrolls)               │
│                    │                          │
│                    │  · Force-directed graph  │
│                    │  · Gold = active path    │
│                    │  · Reasoning Path box    │
│                    │  · Timeline              │
└────────────────────┴─────────────────────────┘
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude AI agent with streaming tool use |
| `streamlit` | Web UI framework |
| `streamlit-agraph` | Force-directed graph visualization |
| `networkx` | In-memory graph engine |
| `python-dotenv` | Load `.env` API key |
