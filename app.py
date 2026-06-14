import os

import streamlit as st
from streamlit_agraph import agraph, Config

from agent import stream_ask_agent
from data import HOUSES, NODE_COLORS
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

def rag_houses():
    base = ["house_a", "house_b", "house_c"]
    return base + (["house_d"] if st.session_state.rag_house_d else [])


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏠 Home Buying Demo")
    st.caption("RAG vs Context Graph — same story, different outcomes")
    st.divider()

    st.markdown("### 🔍 Phase 1 — RAG Agent")

    if st.button("1. Compare Houses A, B, C", use_container_width=True):
        inject("Help me compare Houses A, B, and C.", "rag")

    if st.button("2. Remove House B — commute too long, HOA too high", use_container_width=True):
        inject(
            "Let's remove House B from consideration. "
            "The commute is too long and the HOA fees are too high.",
            "rag",
        )

    st.markdown('<div class="time-note">⏰ One week passes…</div>', unsafe_allow_html=True)

    if st.button("3. Which houses are we still considering?", use_container_width=True):
        inject("Which houses are we currently considering?", "rag_reset")

    if st.button("4. Why did we reject House B?", use_container_width=True):
        inject("Why did we reject House B?", "rag")

    if st.button("5. Add House D to our list", use_container_width=True):
        inject(
            "A new house just came on the market — House D, $435,000. "
            "Schools 4/5, Commute 5/5, Taxes 4/5, Crime Rate 4/5, "
            "Resale Value 5/5, HOA 4/5. Can we add it to our consideration?",
            "rag_add_d",
        )

    if st.button("6. Why are you recommending House D?", use_container_width=True):
        inject("Why are you recommending House D?", "rag")

    st.divider()

    if st.button("⚡ Switch to Context Graph →", use_container_width=True, type="primary"):
        inject("", "transition")

    st.divider()

    st.markdown("### 🔗 Phase 2 — Context Graph")

    if st.button("1. Compare Houses A, B, C", use_container_width=True, key="cg_1"):
        inject("Help me compare Houses A, B, and C.", "cg")

    if st.button("2. Remove House B — commute too long, HOA too high", use_container_width=True, key="cg_2"):
        inject(
            "Let's remove House B from consideration. "
            "The commute is too long and the HOA fees are too high.",
            "cg",
        )

    if st.button("3. Which houses are we still considering?", use_container_width=True, key="cg_3"):
        inject("Which houses are we currently considering?", "cg")

    if st.button("4. Why did we reject House B?", use_container_width=True, key="cg_4"):
        inject("Why did we reject House B?", "cg")

    if st.button("5. Add House D to our list", use_container_width=True, key="cg_5"):
        inject(
            "A new house just came on the market — House D, $435,000. "
            "Schools 4/5, Commute 5/5, Taxes 4/5, Crime Rate 4/5, "
            "Resale Value 5/5, HOA 4/5. Can we add it to our consideration?",
            "cg_add_d",
        )

    if st.button("6. Why are you recommending House D?", use_container_width=True, key="cg_6"):
        inject("Why are you recommending House D?", "cg")

    st.markdown("---")
    st.markdown("**Graph Traversal Demo**")

    if st.button("7. What if commute is no longer a priority?", use_container_width=True, key="cg_7"):
        inject(
            "We've reconsidered our priorities — commute is no longer a top concern for us. "
            "Use the graph to analyze which past decisions were influenced by commute-related reasoning. "
            "What changes? Which decisions might need to be revisited?",
            "cg",
        )

    if st.button("8. Trace: how exactly did we end up with House D?", use_container_width=True, key="cg_8"):
        inject(
            "Trace the complete reasoning path in the Context Graph that led to recommending House D. "
            "Walk me through every node — from our stored preferences, through the rejection decision, "
            "to the final recommendation. Show the full chain.",
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
col_chat, col_graph = st.columns([2, 1.2], gap="medium")


# ── Chat column — rendering + streaming happens here ──────────────────────────
with col_chat:
    st.markdown("#### 💬 The Demo")

    chat_box = st.container(height=620, border=False)

    with chat_box:
        # ── Render saved messages ──────────────────────────────────────────────
        if not st.session_state.messages and not st.session_state.pending:
            st.info(
                "Use the **sidebar steps** to walk through the story.\n\n"
                "Start with **Phase 1** (RAG Agent) — run all 6 steps to see where "
                "retrieval alone falls short. Then click **Switch to Context Graph** "
                "and run the same 6 steps to see full context preserved."
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


# ── Context Graph panel ────────────────────────────────────────────────────────
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
        st.caption("Graph builds as decisions are recorded in Phase 2.")
        st.info("Switch to the Context Graph phase — nodes appear here in real time.")

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
