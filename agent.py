import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from data import HOUSES
from graph import ContextGraph

load_dotenv(Path(__file__).parent / ".env")

MODEL = "claude-sonnet-4-6"

TOOLS = [
    {
        "name": "get_context_graph_state",
        "description": (
            "Read the full current state of the Context Graph, including active houses, "
            "rejected houses with reasons, all decisions made, and stored preferences. "
            "Always call this first before answering any question about the evaluation."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_active_candidates",
        "description": "Returns only the houses currently under active consideration.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_rejected_houses",
        "description": "Returns houses that were rejected, with the reasons and decision date.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_decision",
        "description": (
            "Record a decision about a house in the Context Graph. Use this whenever the user "
            "accepts, rejects, or defers a house. This preserves the decision and reasoning "
            "for future sessions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "house_id": {
                    "type": "string",
                    "description": "The house ID (e.g. 'house_a', 'house_b', 'house_c', 'house_d')",
                },
                "decision": {
                    "type": "string",
                    "enum": ["REJECT", "ACCEPT", "DEFER"],
                    "description": "The decision outcome",
                },
                "reasons": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of specific reasons driving this decision",
                },
                "rationale": {
                    "type": "string",
                    "description": "A brief narrative explaining the trade-offs behind this decision",
                },
            },
            "required": ["house_id", "decision", "reasons", "rationale"],
        },
    },
    {
        "name": "add_preference",
        "description": (
            "Store a user preference in the Context Graph so it can inform future evaluations. "
            "Call this when the user expresses what they value (e.g. 'good commute', 'low HOA')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "preference_text": {
                    "type": "string",
                    "description": "The preference to record (e.g. 'Commute under 30 min')",
                }
            },
            "required": ["preference_text"],
        },
    },
    {
        "name": "add_recommendation",
        "description": "Record a recommendation for a house, linked to the decision that generated it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "house_id": {"type": "string"},
                "based_on_decision_id": {
                    "type": "string",
                    "description": "The decision node ID this recommendation derives from (optional)",
                },
            },
            "required": ["house_id"],
        },
    },
    {
        "name": "add_house_to_graph",
        "description": "Add a new house to the Context Graph for evaluation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "house_id": {
                    "type": "string",
                    "description": "The house ID to add (e.g. 'house_d')",
                }
            },
            "required": ["house_id"],
        },
    },
    {
        "name": "highlight_reasoning_path",
        "description": (
            "Visually highlight the specific nodes and edges in the Context Graph that form "
            "the reasoning chain behind your answer. Call this AFTER determining your answer, "
            "passing the node IDs you actually traversed. The audience will see exactly which "
            "graph nodes lit up — making the difference between graph traversal and flat memory lookup visible. "
            "Use node IDs from the graph state: 'user', 'house_a/b/c/d', and the 'id' fields "
            "from decision_history, preferences, and recommendations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Node IDs that form the reasoning path (e.g. ['user', 'pref_1', 'decision_1', 'house_b', 'rec_1', 'house_d'])",
                },
                "path_description": {
                    "type": "string",
                    "description": "Human-readable description of the traversal path shown to the audience (e.g. 'User → PREFERS Low HOA → REJECT House B → GENERATED FROM → Recommend House D')",
                },
            },
            "required": ["node_ids", "path_description"],
        },
    },
    {
        "name": "analyze_preference_impact",
        "description": (
            "Analyze what changes in the graph if a preference is dropped or deprioritized. "
            "Traverses the graph to find all Reason nodes matching the keyword, then walks up "
            "to the Decision nodes that were BASED_ON those reasons, and identifies which "
            "houses might need reconsideration. Automatically highlights the affected subgraph. "
            "Call this when the user asks 'what if X no longer matters' or 'we changed our mind about X'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "preference_keyword": {
                    "type": "string",
                    "description": "Keyword to search in reason/preference nodes (e.g. 'commute', 'HOA', 'schools')",
                }
            },
            "required": ["preference_keyword"],
        },
    },
]


def _build_system_prompt(simulated_date: str) -> str:
    return f"""You are an AI home-buying assistant powered by a Context Graph.

The Context Graph is your persistent memory. It stores:
- Houses being evaluated (with all attributes)
- Decisions made (accept / reject / defer) with full reasoning
- Preferences the user has expressed
- Recommendations with traceable links to the decisions that generated them
- The full timeline of interactions

Today's date: {simulated_date}

Your behavior rules:
1. ALWAYS call get_context_graph_state() first to load current context. Note the 'id' fields — you need them for highlighting.
2. When the user makes a decision about a house, call add_decision() immediately.
3. When the user expresses a preference, call add_preference().
4. When recommending a house, call add_recommendation() and cite the specific prior decision or preference that drives it.
5. Answer the three questions audiences care about:
   - "What happened?" → state decisions from the graph
   - "Why did it happen?" → cite stored reasons and rationale from the graph
   - "What should we do next?" → use stored preferences and decision history
6. Be concise but specific. Reference dates, house names, and stored reasons directly.
7. Never fabricate decisions or reasons — only cite what is in the graph.
8. ALWAYS call highlight_reasoning_path() before your final answer, passing the specific node IDs you traversed to reach your answer. This makes graph traversal visible to the audience — it is what distinguishes a Context Graph from flat memory. Include 'user', relevant house IDs, decision IDs, reason IDs, preference IDs, and recommendation IDs from the graph state.
9. When the user asks "what if X no longer matters" or changes a preference, call analyze_preference_impact() with the relevant keyword. The tool automatically traverses the graph, finds every rejection decision based on that preference, and reactivates any house whose ONLY rejection reason was that preference. Report which houses were reactivated and why.

This is a demonstration showing that AI agents fail not because information is missing, but because CONTEXT is missing. Every response should visibly demonstrate graph traversal."""


def _execute_tool(tool_name: str, tool_input: dict, graph: ContextGraph, simulated_date: str) -> tuple[str, list[str]]:
    """Execute a tool call and return (result_json, list_of_graph_event_labels)."""
    events = []

    if tool_name == "get_context_graph_state":
        result = graph.to_summary_dict()
        return json.dumps(result, indent=2), events

    if tool_name == "get_active_candidates":
        return json.dumps(graph.get_active_houses(), indent=2), events

    if tool_name == "get_rejected_houses":
        return json.dumps(graph.get_rejected_houses(), indent=2), events

    if tool_name == "add_decision":
        node_id = graph.record_decision(
            house_id=tool_input["house_id"],
            decision=tool_input["decision"],
            reasons=tool_input["reasons"],
            rationale=tool_input["rationale"],
            simulated_date=simulated_date,
        )
        house_name = HOUSES.get(tool_input["house_id"], {}).get("name", tool_input["house_id"])
        events.append(f"Decision recorded: {tool_input['decision']} {house_name}")
        return json.dumps({"status": "ok", "decision_id": node_id}), events

    if tool_name == "add_preference":
        node_id = graph.add_preference(tool_input["preference_text"], simulated_date)
        events.append(f"Preference stored: {tool_input['preference_text']}")
        return json.dumps({"status": "ok", "preference_id": node_id}), events

    if tool_name == "add_recommendation":
        node_id = graph.add_recommendation(
            house_id=tool_input["house_id"],
            based_on_decision_id=tool_input.get("based_on_decision_id", ""),
            simulated_date=simulated_date,
        )
        house_name = HOUSES.get(tool_input["house_id"], {}).get("name", tool_input["house_id"])
        events.append(f"Recommendation: {house_name}")
        return json.dumps({"status": "ok", "recommendation_id": node_id}), events

    if tool_name == "add_house_to_graph":
        graph.add_house(tool_input["house_id"], simulated_date)
        house_name = HOUSES.get(tool_input["house_id"], {}).get("name", tool_input["house_id"])
        events.append(f"Added to graph: {house_name}")
        return json.dumps({"status": "ok"}), events

    if tool_name == "highlight_reasoning_path":
        node_ids = tool_input.get("node_ids", [])
        description = tool_input.get("path_description", "")
        graph.set_highlighted_nodes(node_ids, description)
        events.append(f"Path: {description}")
        return json.dumps({"status": "ok", "highlighted_count": len(graph.highlighted_nodes)}), events

    if tool_name == "analyze_preference_impact":
        keyword = tool_input.get("preference_keyword", "").lower()

        matching_reasons = [
            (nid, attrs) for nid, attrs in graph.g.nodes(data=True)
            if attrs.get("node_type") == "Reason"
            and keyword in attrs.get("text", "").lower()
        ]

        affected_decisions = []
        seen_decisions = set()
        for reason_id, _ in matching_reasons:
            for src, _ in graph.g.in_edges(reason_id):
                if src in seen_decisions:
                    continue
                if graph.g.nodes[src].get("node_type") == "Decision":
                    seen_decisions.add(src)
                    dec_attrs = graph.g.nodes[src]
                    all_reasons = [
                        graph.g.nodes[r].get("text", "")
                        for _, r in graph.g.out_edges(src)
                        if graph.g.nodes[r].get("node_type") == "Reason"
                    ]
                    other_reasons = [r for r in all_reasons if keyword not in r.lower()]
                    affected_decisions.append({
                        "id": src,
                        "house": dec_attrs.get("house", ""),
                        "house_name": HOUSES.get(dec_attrs.get("house", ""), {}).get("name", ""),
                        "decision_type": dec_attrs.get("decision_type", ""),
                        "all_reasons": all_reasons,
                        "other_reasons_still_valid": other_reasons,
                        "decision_would_change": len(other_reasons) == 0,
                    })

        # Auto-reactivate any REJECT decision where dropping this preference
        # removes ALL rejection reasons — generic across any number of houses.
        reactivated = []
        for d in affected_decisions:
            if d["decision_type"] == "REJECT" and d["decision_would_change"] and d["house"]:
                graph.reactivate_house(d["house"], simulated_date)
                reactivated.append(d["house_name"] or d["house"])
                events.append(f"Reconsidering: {d['house_name'] or d['house']}")

        highlight_ids = (
            [r[0] for r in matching_reasons]
            + [d["id"] for d in affected_decisions]
            + [d["house"] for d in affected_decisions if d["house"]]
            + ["user"]
        )
        graph.set_highlighted_nodes(
            highlight_ids,
            f"Dropping '{keyword}': {len(reactivated)} house(s) back in consideration"
            if reactivated else
            f"Impact of removing '{keyword}': {len(affected_decisions)} decision(s) affected"
        )
        events.append(f"Impact analysis: '{keyword}' affects {len(affected_decisions)} decision(s)")

        return json.dumps({
            "keyword": keyword,
            "matching_reason_nodes": [{"id": r[0], "text": r[1].get("text")} for r in matching_reasons],
            "affected_decisions": affected_decisions,
            "reactivated_houses": reactivated,
            "summary": (
                f"{len(matching_reasons)} reason node(s) found for '{keyword}'. "
                f"{len(affected_decisions)} decision(s) affected. "
                f"{len(reactivated)} house(s) moved back to active consideration: {reactivated}."
            ),
        }, indent=2), events

    return json.dumps({"error": f"Unknown tool: {tool_name}"}), events


def ask_agent(
    user_message: str,
    graph: ContextGraph,
    conversation_history: list[dict],
    simulated_date: str,
) -> tuple[str, list[str]]:
    """
    Send a message to the Claude agent and handle tool use in a loop.
    Returns (assistant_text, list_of_graph_event_labels).
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    messages = conversation_history + [{"role": "user", "content": user_message}]
    all_graph_events: list[str] = []

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=_build_system_prompt(simulated_date),
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_text, events = _execute_tool(
                        block.name, block.input, graph, simulated_date
                    )
                    all_graph_events.extend(events)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        }
                    )

            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ]

        else:
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            return text, all_graph_events


TOOL_STATUS_LABELS = {
    "get_context_graph_state":    "📊 Reading context graph…",
    "get_active_candidates":      "🏠 Checking active houses…",
    "get_rejected_houses":        "🗂️ Looking up rejected houses…",
    "add_decision":               "✍️ Recording decision…",
    "add_preference":             "💡 Storing preference…",
    "add_recommendation":         "⭐ Recording recommendation…",
    "add_house_to_graph":         "➕ Adding house to graph…",
    "highlight_reasoning_path":   "✨ Highlighting reasoning path…",
    "analyze_preference_impact":  "🔍 Analyzing impact on graph…",
}


def stream_ask_agent(
    user_message: str,
    graph: ContextGraph,
    conversation_history: list[dict],
    simulated_date: str,
):
    """
    Generator yielding (kind, value) tuples:
      ("tool_status", str)  — label shown while a tool runs
      ("graph_event", str)  — graph mutation label
      ("text", str)         — token from the final streamed response
    Tool calls run non-streaming; the final text response streams.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    messages = conversation_history + [{"role": "user", "content": user_message}]
    system = _build_system_prompt(simulated_date)

    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=system,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for text_chunk in stream.text_stream:
                yield ("text", text_chunk)
            final = stream.get_final_message()

        if final.stop_reason == "tool_use":
            tool_results = []
            for block in final.content:
                if block.type == "tool_use":
                    yield ("tool_status", TOOL_STATUS_LABELS.get(block.name, f"🔧 {block.name}…"))
                    result_text, events = _execute_tool(block.name, block.input, graph, simulated_date)
                    for ev in events:
                        yield ("graph_event", ev)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    })
            messages = messages + [
                {"role": "assistant", "content": final.content},
                {"role": "user", "content": tool_results},
            ]
        else:
            break
