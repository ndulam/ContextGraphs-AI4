import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from data import HOUSES

load_dotenv(Path(__file__).parent / ".env")

MODEL = "claude-sonnet-4-6"

RAG_DOCUMENTS = {
    house_id: (
        f"{h['name']} — Listed at ${h['price']:,}. "
        f"Schools: {h['attributes']['Schools']}/5. "
        f"Commute: {h['attributes']['Commute']}/5. "
        f"Property Taxes: {h['attributes']['Taxes']}/5. "
        f"Crime Rate: {h['attributes']['Crime Rate']}/5. "
        f"Resale Value: {h['attributes']['Resale Value']}/5. "
        f"HOA: {h['attributes']['HOA']}/5."
    )
    for house_id, h in HOUSES.items()
}

TOOLS = [
    {
        "name": "search_listings",
        "description": (
            "Search the property listings database. Returns house attributes: "
            "price, schools, commute, taxes, crime rate, resale value, HOA."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (e.g. 'all houses', 'House B details', 'commute scores')",
                }
            },
            "required": ["query"],
        },
    }
]

SYSTEM_PROMPT = """You are a helpful real estate assistant. You help users search and compare property listings.

For every question:
1. Call search_listings() to retrieve the relevant property data
2. Answer based only on what you find in the listings database
3. Be helpful, confident, and specific — cite actual scores and prices

You work with the property documents in front of you. You do not have access to meeting notes, \
decision logs, or records of what preferences were discussed in other sessions. \
When asked about status, comparisons, or options — retrieve the listings and answer from there."""


def _search(query: str, available_houses: list[str]) -> str:
    q = query.lower()
    docs = {k: v for k, v in RAG_DOCUMENTS.items() if k in available_houses}
    results = []
    for house_id, doc in docs.items():
        if (
            house_id.replace("_", " ") in q
            or HOUSES[house_id]["name"].lower() in q
            or any(w in q for w in ["all", "houses", "list", "compar", "option", "consider", "active", "current"])
        ):
            results.append(doc)
    if not results:
        results = list(docs.values())
    return "\n\n".join(results)


def ask_rag_agent(
    user_message: str,
    history: list[dict],
    available_houses: list[str] | None = None,
) -> str:
    """available_houses controls which listings are searchable. Defaults to A, B, C only."""
    if available_houses is None:
        available_houses = ["house_a", "house_b", "house_c"]

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    messages = history + [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": _search(block.input.get("query", ""), available_houses),
                    })
            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ]
        else:
            return "".join(b.text for b in response.content if hasattr(b, "text"))


def stream_ask_rag_agent(
    user_message: str,
    history: list[dict],
    available_houses: list[str] | None = None,
):
    """
    Generator yielding (kind, value) tuples:
      ("tool_status", str)  — shown while searching
      ("text", str)         — token from the streamed response
    """
    if available_houses is None:
        available_houses = ["house_a", "house_b", "house_c"]

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    messages = history + [{"role": "user", "content": user_message}]

    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
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
                    yield ("tool_status", "🔍 Searching property listings…")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": _search(block.input.get("query", ""), available_houses),
                    })
            messages = messages + [
                {"role": "assistant", "content": final.content},
                {"role": "user", "content": tool_results},
            ]
        else:
            break
