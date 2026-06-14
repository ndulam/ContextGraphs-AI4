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
]


def _build_system_prompt(simulated_date: str) -> str:
    return f"""You are an AI home-buying assistant powered by a Context Graph.

The Context Graph is your persistent memory. It stores:
- Houses being evaluated (with all attributes)
- Decisions made (accept / reject / defer) with full reasoning
- Preferences the user has expressed
- The history and timeline of all interactions

Today's date: {simulated_date}

Your behavior rules:
1. ALWAYS call get_context_graph_state() at the start of each response to load current context.
2. When the user makes a decision about a house, call add_decision() immediately.
3. When the user expresses a preference, call add_preference().
4. When recommending a house, call add_recommendation() and cite the specific prior decision or preference that drives the recommendation.
5. Answer the three questions audiences care about:
   - "What happened?" → state decisions from the graph
   - "Why did it happen?" → cite stored reasons and rationale from the graph
   - "What should we do next?" → use stored preferences and decision history
6. Be concise but specific. Reference dates, house names, and stored reasons directly.
7. Never fabricate decisions or reasons — only cite what is in the graph.

This is a demonstration showing that AI agents fail not because information is missing, but because CONTEXT is missing. Show the power of the Context Graph in every response."""


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
    "get_context_graph_state": "📊 Reading context graph…",
    "get_active_candidates":   "🏠 Checking active houses…",
    "get_rejected_houses":     "🗂️ Looking up rejected houses…",
    "add_decision":            "✍️ Recording decision…",
    "add_preference":          "💡 Storing preference…",
    "add_recommendation":      "⭐ Recording recommendation…",
    "add_house_to_graph":      "➕ Adding house to graph…",
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
