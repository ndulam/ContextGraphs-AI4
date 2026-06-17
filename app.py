import os
import time

import streamlit as st
from streamlit_agraph import agraph, Config

from agent import stream_ask_agent
from data import HOUSES, NODE_COLORS
import importlib
import demo_cache as _dm
importlib.reload(_dm)
CACHE = _dm.CACHE
from graph import ContextGraph, get_or_create_graph, GRAPH_PATH
from rag_agent import stream_ask_rag_agent

st.set_page_config(
    page_title="Context Graph Demo",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.story-divider {
    text-align: center;
    padding: 12px 0;
    margin: 8px 0;
    color: #27AE60;
    font-weight: 700;
    font-size: 14px;
    border-top: 1px solid #27AE60;
    border-bottom: 1px solid #27AE60;
    letter-spacing: 1px;
}
.time-note {
    text-align: center;
    padding: 6px 0;
    margin: 4px 0;
    color: #F39C12;
    font-size: 13px;
    font-style: italic;
}
/* Keep the graph panel fixed at the top of its column while chat scrolls */
div[data-testid="stHorizontalBlock"] > div:nth-child(2) > div[data-testid="stVerticalBlock"] {
    position: sticky;
    top: 60px;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
DEFAULT_DATE = "2026-03-10"
WEEK_LATER   = "2026-03-17"

def _init():
    defaults = {
        "story_phase":    "rag",
        "simulated_date": DEFAULT_DATE,
        "messages":       [],
        "rag_history":    [],
        "rag_house_d":    False,
        "cg_history":     [],
        "graph_events":   [],
        "graph":          None,
        "pending":        None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if st.session_state.graph is None:
        if os.path.exists(GRAPH_PATH):
            os.remove(GRAPH_PATH)
        st.session_state.graph = get_or_create_graph(DEFAULT_DATE)
    g = st.session_state.graph
    if not hasattr(g, "highlighted_nodes"):
        g.highlighted_nodes = set()
    if not hasattr(g, "path_description"):
        g.path_description = ""

_init()


def push(role, content, phase, avatar=None):
    st.session_state.messages.append(
        {"role": role, "content": content, "phase": phase, "avatar": avatar}
    )

def inject(message, action):
    st.session_state.pending = (message, action)
    st.rerun()

def stream_cached(text: str):
    """Yield a pre-written response word-by-word at ~60 wps — looks live, no API wait."""
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word + ("" if i == len(words) - 1 else " ")
        time.sleep(0.018)

def rag_houses():
    base = ["house_a", "house_b", "house_c"]
    return base + (["house_d"] if st.session_state.rag_house_d else [])


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏠 Home Buying Demo")
    st.caption("RAG vs Context Graph — same story, different outcomes")
    st.divider()

    st.markdown("### Demo Steps")
    st.caption("Run in order — RAG steps are instant")

    st.markdown("**Part 1: RAG — shows the problem**")
    if st.button("1. Compare Houses A, B, C", use_container_width=True, key="d1"):
        inject("Help me compare Houses A, B, and C.", "demo_rag_compare")
    if st.button("2. Remove House B (commute + HOA)", use_container_width=True, key="d2"):
        inject(
            "Let's remove House B from consideration. "
            "The commute is too long and the HOA fees are too high.",
            "demo_rag_remove_b",
        )
    if st.button("3. Compare House A and C", use_container_width=True, key="d3"):
        inject(
            "Compare House A and House C for me — what are the pros and cons of each?",
            "demo_rag_compare_a_c",
        )

    st.markdown('<div class="time-note">⏰ One week later — new chat session</div>', unsafe_allow_html=True)

    if st.button("4. Which houses are we considering?", use_container_width=True, key="d4"):
        inject("Which houses are we currently considering?", "demo_rag_which_houses")

    st.divider()
    if st.button("⚡ Switch to Context Graph →", use_container_width=True, key="d_switch", type="primary"):
        inject("", "transition")
    st.divider()

    st.markdown("**Part 2: Context Graph — solves it**")
    if st.button("5. Set our priorities", use_container_width=True, key="d5"):
        inject(
            "Before we decide, let me state our priorities: "
            "we want a short commute and low HOA fees. "
            "Please record these as our preferences.",
            "cg",
        )
    if st.button("6. Remove House B (commute + HOA)", use_container_width=True, key="d6"):
        inject(
            "Let's remove House B from consideration. "
            "The commute is too long and the HOA fees are too high.",
            "cg",
        )
    if st.button("7. Which houses are we considering?", use_container_width=True, key="d7"):
        inject("Which houses are we currently considering?", "cg")
    if st.button("8. Why did we reject House B?", use_container_width=True, key="d8"):
        inject("Why did we reject House B?", "cg")
    if st.button("9. Commute is no longer a concern", use_container_width=True, key="d9"):
        inject(
            "We've reconsidered — commute is no longer a top concern for us. "
            "Use the graph to analyze which past decisions were influenced by commute reasoning. "
            "What changes?",
            "cg",
        )
    if st.button("10. Which houses are we considering now?", use_container_width=True, key="d10"):
        inject(
            "Given that commute no longer matters, which houses are we now considering?",
            "cg",
        )

    st.divider()
    st.caption(f"Date: `{st.session_state.simulated_date}`")
    if st.button("🔄 Reset Demo", use_container_width=True, type="secondary"):
        if os.path.exists(GRAPH_PATH):
            os.remove(GRAPH_PATH)
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ── Main layout ────────────────────────────────────────────────────────────────
if st.session_state.story_phase == "context_graph":
    col_chat, col_graph = st.columns([2, 1.2], gap="medium")
else:
    col_chat = st.container()
    col_graph = None


# ── Chat column — rendering + streaming happens here ──────────────────────────
with col_chat:
    st.markdown("#### 💬 The Demo")

    chat_box = st.container(height=620, border=False)

    with chat_box:
        # ── Render saved messages ──────────────────────────────────────────────
        if not st.session_state.messages and not st.session_state.pending:
            st.info(
                "Use the **sidebar steps** to walk through the story.\n\n"
                "**Steps 1–4** (RAG): compare houses, remove one, then come back a week later "
                "and watch RAG forget your decision.\n\n"
                "**Steps 5–10** (Context Graph): state your priorities, replay the same story — "
                "every decision is remembered, traceable, and adapts when your priorities change."
            )

        for msg in st.session_state.messages:
            phase = msg.get("phase", "rag")
            role  = msg["role"]
            if phase == "transition":
                st.markdown(
                    '<div class="story-divider">⚡ CONTEXT GRAPH ACTIVATED</div>',
                    unsafe_allow_html=True,
                )
            elif phase == "system":
                st.markdown(
                    f'<div class="time-note">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            elif role == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant", avatar=msg.get("avatar", "🔍")):
                    st.markdown(msg["content"])

        # ── Process pending action — streaming renders at bottom of chat_box ───
        if st.session_state.pending:
            user_msg, action = st.session_state.pending
            st.session_state.pending = None

            # Transition between phases
            if action == "transition":
                # Reset graph so Part 2 always starts clean
                if os.path.exists(GRAPH_PATH):
                    os.remove(GRAPH_PATH)
                st.session_state.graph = get_or_create_graph(WEEK_LATER)
                st.session_state.graph_events = []
                st.session_state.cg_history = []
                st.markdown(
                    '<div class="story-divider">⚡ CONTEXT GRAPH ACTIVATED</div>',
                    unsafe_allow_html=True,
                )
                push("system", "CONTEXT GRAPH ACTIVATED", phase="transition")
                st.session_state.story_phase = "context_graph"
                st.session_state.simulated_date = WEEK_LATER
                st.rerun()

            # RAG session reset — simulate new session (one week later)
            elif action == "rag_reset":
                st.session_state.rag_history = []
                st.session_state.simulated_date = WEEK_LATER
                note = "⏰  One week later — new session started."
                st.markdown(f'<div class="time-note">{note}</div>', unsafe_allow_html=True)
                push("system", note, phase="system")
                action = "rag"

            # ── Demo: cached RAG responses (instant, no API call) ───────────
            elif action in ("demo_rag_compare", "demo_rag_remove_b", "demo_rag_compare_a_c", "demo_rag_which_houses"):
                cache_key = action.replace("demo_", "")
                if action == "demo_rag_which_houses":
                    # simulate new session — clear history, advance date
                    st.session_state.rag_history = []
                    st.session_state.simulated_date = WEEK_LATER
                    note = "⏰  New session — RAG has no memory of previous decisions."
                    st.markdown(f'<div class="time-note">{note}</div>', unsafe_allow_html=True)
                    push("system", note, phase="system")
                with st.chat_message("user"):
                    st.markdown(user_msg)
                with st.chat_message("assistant", avatar="🔍"):
                    reply = st.write_stream(stream_cached(CACHE[cache_key]))
                push("user", user_msg, phase="rag")
                push("assistant", reply, phase="rag", avatar="🔍")
                st.session_state.rag_history += [
                    {"role": "user",      "content": user_msg},
                    {"role": "assistant", "content": reply},
                ]
                st.rerun()

            # Enable House D in RAG document set
            if action == "rag_add_d":
                st.session_state.rag_house_d = True
                action = "rag"

            # Stream RAG response
            if action == "rag":
                with st.chat_message("user"):
                    st.markdown(user_msg)
                with st.chat_message("assistant", avatar="🔍"):
                    status_ph = st.empty()
                    def _rag_text():
                        for kind, val in stream_ask_rag_agent(
                            user_msg, st.session_state.rag_history, rag_houses()
                        ):
                            if kind == "tool_status":
                                status_ph.caption(val)
                            elif kind == "text":
                                yield val
                    reply = st.write_stream(_rag_text())
                    status_ph.empty()
                push("user", user_msg, phase="rag")
                push("assistant", reply, phase="rag", avatar="🔍")
                st.session_state.rag_history += [
                    {"role": "user",      "content": user_msg},
                    {"role": "assistant", "content": reply},
                ]
                st.rerun()

            # Add House D to Context Graph
            elif action == "cg_add_d":
                st.session_state.graph.add_house("house_d", st.session_state.simulated_date)
                action = "cg"

            # Stream Context Graph response
            if action == "cg":
                if hasattr(st.session_state.graph, "clear_highlighted_nodes"):
                    st.session_state.graph.clear_highlighted_nodes()
                else:
                    st.session_state.graph.highlighted_nodes = set()
                    st.session_state.graph.path_description = ""
                with st.chat_message("user"):
                    st.markdown(user_msg)
                new_graph_events: list[str] = []
                with st.chat_message("assistant", avatar="🔗"):
                    status_ph = st.empty()
                    def _cg_text():
                        for kind, val in stream_ask_agent(
                            user_msg,
                            st.session_state.graph,
                            st.session_state.cg_history,
                            st.session_state.simulated_date,
                        ):
                            if kind == "tool_status":
                                status_ph.caption(val)
                            elif kind == "graph_event":
                                new_graph_events.append(val)
                            elif kind == "text":
                                yield val
                    reply = st.write_stream(_cg_text())
                    status_ph.empty()
                push("user", user_msg, phase="context_graph")
                push("assistant", reply, phase="context_graph", avatar="🔗")
                st.session_state.cg_history += [
                    {"role": "user",      "content": user_msg},
                    {"role": "assistant", "content": reply},
                ]
                st.session_state.graph_events.extend(new_graph_events)
                st.rerun()

    # ── Free-type input ────────────────────────────────────────────────────────
    user_input = st.chat_input("Ask the assistant…")
    if user_input:
        action = "cg" if st.session_state.story_phase == "context_graph" else "rag"
        inject(user_input, action)


# ── Context Graph panel — only visible in Part 2 ──────────────────────────────
if col_graph is not None:
    with col_graph:
        st.markdown("#### 🔗 Context Graph")

        graph: ContextGraph = st.session_state.graph
        agraph_nodes, agraph_edges = graph.to_agraph_format()

        if agraph_nodes:
            config = Config(
                width=380,
                height=380,
                directed=True,
                physics=True,
                hierarchical=False,
                nodeHighlightBehavior=True,
                node={"labelProperty": "label", "fontSize": 11},
                link={"labelProperty": "label", "renderLabel": True, "fontSize": 9},
            )
            agraph(nodes=agraph_nodes, edges=agraph_edges, config=config)
        else:
            st.info("Graph nodes appear here as decisions are recorded.")

        st.markdown("**Legend**")
        pairs = [
            ("User", NODE_COLORS["User"]),
            ("House", NODE_COLORS["House"]),
            ("Rejected", NODE_COLORS["House_rejected"]),
            ("Decision", NODE_COLORS["Decision"]),
            ("Reason", NODE_COLORS["Reason"]),
            ("Preference", NODE_COLORS["Preference"]),
        ]
        c1, c2 = st.columns(2)
        for i, (label, color) in enumerate(pairs):
            (c1 if i % 2 == 0 else c2).markdown(
                f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;'
                f'background:{color};margin-right:5px;vertical-align:middle;"></span>'
                f'<span style="font-size:11px;">{label}</span>',
                unsafe_allow_html=True,
            )

        if graph.highlighted_nodes and graph.path_description:
            st.divider()
            st.markdown("**Reasoning Path Traversed**")
            st.info(f"✨ {graph.path_description}", icon=None)

        st.divider()
        st.markdown("**Timeline**")
        events = graph.events
        if not events:
            st.caption("No decisions recorded yet.")
        else:
            for ev in reversed(events[-8:]):
                ts  = ev.get("timestamp", "")[:10]
                msg = ev.get("message", "")
                st.markdown(
                    f'<div style="font-size:11px;color:#aaa;padding:3px 0;'
                    f'border-bottom:1px solid #2a2a3a;">'
                    f'<span style="color:#F39C12;">{ts}</span> {msg}</div>',
                    unsafe_allow_html=True,
                )

        if st.session_state.graph_events:
            st.divider()
            for ev in st.session_state.graph_events[-3:]:
                st.success(ev, icon="✅")
