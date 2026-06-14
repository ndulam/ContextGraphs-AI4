import json
import os
from datetime import datetime

import networkx as nx
from streamlit_agraph import Node, Edge

from data import HOUSES, INITIAL_HOUSES, NODE_COLORS

GRAPH_PATH = "context_graph.json"


class ContextGraph:
    def __init__(self):
        self.g = nx.DiGraph()
        self.events: list[dict] = []
        self._node_counter = 0

    def _next_id(self, prefix: str) -> str:
        self._node_counter += 1
        return f"{prefix}_{self._node_counter}"

    def add_node(self, node_id: str, node_type: str, label: str = "", **attrs) -> str:
        color = NODE_COLORS.get(node_type, "#AAAAAA")
        self.g.add_node(
            node_id,
            node_type=node_type,
            label=label or node_id,
            color=color,
            **attrs,
        )
        return node_id

    def add_edge(self, src: str, dst: str, relationship: str):
        self.g.add_edge(src, dst, relationship=relationship)

    def log_event(self, message: str):
        self.events.append(
            {"timestamp": datetime.now().isoformat(), "message": message}
        )

    # --- Domain helpers ---

    def initialize(self, simulated_date: str):
        self.add_node("user", "User", label="HomeSeeker")
        for house_id in INITIAL_HOUSES:
            h = HOUSES[house_id]
            self.add_node(
                house_id,
                "House",
                label=h["name"],
                price=h["price"],
                status="active",
                **{k: v for k, v in h["attributes"].items()},
            )
            self.add_edge("user", house_id, "EVALUATED")
        self.log_event(f"[{simulated_date}] Session started — evaluating House A, B, C")
        self.save()

    def add_house(self, house_id: str, simulated_date: str):
        if house_id in self.g.nodes:
            return
        h = HOUSES[house_id]
        self.add_node(
            house_id,
            "House_new",
            label=h["name"],
            price=h["price"],
            status="active",
            **{k: v for k, v in h["attributes"].items()},
        )
        self.add_edge("user", house_id, "EVALUATED")
        self.log_event(f"[{simulated_date}] New house added: {h['name']}")
        self.save()

    def record_decision(
        self,
        house_id: str,
        decision: str,
        reasons: list[str],
        rationale: str,
        simulated_date: str,
    ) -> str:
        decision_id = self._next_id("decision")
        self.add_node(
            decision_id,
            "Decision",
            label=f"{decision}: {HOUSES.get(house_id, {}).get('name', house_id)}",
            decision_type=decision,
            house=house_id,
            rationale=rationale,
            date=simulated_date,
        )
        self.add_edge(decision_id, house_id, "CONSIDERED")
        self.add_edge("user", decision_id, f"{decision}")

        for reason_text in reasons:
            reason_id = self._next_id("reason")
            self.add_node(reason_id, "Reason", label=reason_text, text=reason_text)
            self.add_edge(decision_id, reason_id, "BASED_ON")

        if decision == "REJECT":
            if house_id in self.g.nodes:
                self.g.nodes[house_id]["status"] = "rejected"
                self.g.nodes[house_id]["color"] = NODE_COLORS["House_rejected"]
                self.g.nodes[house_id]["node_type"] = "House_rejected"
            self.add_edge("user", house_id, "REJECTED")

        house_name = HOUSES.get(house_id, {}).get("name", house_id)
        self.log_event(
            f"[{simulated_date}] Decision: {decision} {house_name} — {', '.join(reasons)}"
        )
        self.save()
        return decision_id

    def add_preference(self, preference_text: str, simulated_date: str) -> str:
        pref_id = self._next_id("pref")
        self.add_node(pref_id, "Preference", label=preference_text, text=preference_text)
        self.add_edge("user", pref_id, "PREFERS")
        self.log_event(f"[{simulated_date}] Preference noted: {preference_text}")
        self.save()
        return pref_id

    def add_recommendation(
        self, house_id: str, based_on_decision_id: str, simulated_date: str
    ) -> str:
        rec_id = self._next_id("rec")
        house_name = HOUSES.get(house_id, {}).get("name", house_id)
        self.add_node(rec_id, "Recommendation", label=f"Recommend: {house_name}")
        self.add_edge(rec_id, house_id, "FOR_HOUSE")
        if based_on_decision_id and based_on_decision_id in self.g.nodes:
            self.add_edge(rec_id, based_on_decision_id, "GENERATED_FROM")
        self.log_event(f"[{simulated_date}] Recommendation: {house_name}")
        self.save()
        return rec_id

    # --- Query methods ---

    def get_active_houses(self) -> list[dict]:
        result = []
        for node_id, attrs in self.g.nodes(data=True):
            if attrs.get("node_type") in ("House", "House_new") and attrs.get("status") == "active":
                result.append({"id": node_id, **attrs})
        return result

    def get_rejected_houses(self) -> list[dict]:
        result = []
        for node_id, attrs in self.g.nodes(data=True):
            if attrs.get("status") == "rejected":
                reasons = []
                for _, reason_id, edge_attrs in self.g.out_edges(
                    [n for n, a in self.g.nodes(data=True)
                     if a.get("node_type") == "Decision" and a.get("house") == node_id],
                    data=True,
                ):
                    if self.g.nodes[reason_id].get("node_type") == "Reason":
                        reasons.append(self.g.nodes[reason_id].get("text", ""))
                decision_date = ""
                for n, a in self.g.nodes(data=True):
                    if a.get("node_type") == "Decision" and a.get("house") == node_id:
                        decision_date = a.get("date", "")
                result.append(
                    {
                        "id": node_id,
                        "name": attrs.get("label", node_id),
                        "reasons": reasons,
                        "date": decision_date,
                    }
                )
        return result

    def get_decision_history(self) -> list[dict]:
        decisions = []
        for node_id, attrs in self.g.nodes(data=True):
            if attrs.get("node_type") == "Decision":
                reasons = []
                for _, reason_id in self.g.out_edges(node_id):
                    if self.g.nodes[reason_id].get("node_type") == "Reason":
                        reasons.append(self.g.nodes[reason_id].get("text", ""))
                decisions.append(
                    {
                        "id": node_id,
                        "decision_type": attrs.get("decision_type"),
                        "house": attrs.get("house"),
                        "rationale": attrs.get("rationale", ""),
                        "reasons": reasons,
                        "date": attrs.get("date", ""),
                    }
                )
        return decisions

    def get_preferences(self) -> list[str]:
        return [
            attrs.get("text", "")
            for _, attrs in self.g.nodes(data=True)
            if attrs.get("node_type") == "Preference"
        ]

    def to_summary_dict(self) -> dict:
        active = [
            {"id": n, "name": a.get("label"), "price": a.get("price"), "attributes": {
                k: a[k] for k in ["Schools","Commute","Taxes","Crime Rate","Resale Value","HOA"] if k in a
            }}
            for n, a in self.g.nodes(data=True)
            if a.get("node_type") in ("House", "House_new") and a.get("status") == "active"
        ]
        rejected = self.get_rejected_houses()
        decisions = self.get_decision_history()
        preferences = self.get_preferences()
        return {
            "active_houses": active,
            "rejected_houses": rejected,
            "decision_history": decisions,
            "preferences": preferences,
        }

    # --- streamlit-agraph serialization ---

    def to_agraph_format(self) -> tuple[list[Node], list[Edge]]:
        nodes = []
        for node_id, attrs in self.g.nodes(data=True):
            nodes.append(
                Node(
                    id=node_id,
                    label=attrs.get("label", node_id),
                    color=attrs.get("color", "#AAAAAA"),
                    size=20 if attrs.get("node_type") in ("House", "House_new", "House_rejected") else 15,
                    font={"size": 11},
                )
            )
        edges = []
        for src, dst, attrs in self.g.edges(data=True):
            edges.append(
                Edge(
                    source=src,
                    target=dst,
                    label=attrs.get("relationship", ""),
                    font={"size": 9, "align": "middle"},
                )
            )
        return nodes, edges

    # --- Persistence ---

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {"id": n, **{k: v for k, v in a.items()}}
                for n, a in self.g.nodes(data=True)
            ],
            "edges": [
                {"src": s, "dst": d, **a}
                for s, d, a in self.g.edges(data=True)
            ],
            "events": self.events,
            "_node_counter": self._node_counter,
        }

    def save(self, path: str = GRAPH_PATH):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str = GRAPH_PATH) -> "ContextGraph":
        cg = cls()
        with open(path) as f:
            data = json.load(f)
        for node in data["nodes"]:
            node_id = node.pop("id")
            cg.g.add_node(node_id, **node)
        for edge in data["edges"]:
            src, dst = edge.pop("src"), edge.pop("dst")
            cg.g.add_edge(src, dst, **edge)
        cg.events = data.get("events", [])
        cg._node_counter = data.get("_node_counter", 0)
        return cg


def get_or_create_graph(simulated_date: str) -> ContextGraph:
    if os.path.exists(GRAPH_PATH):
        return ContextGraph.load(GRAPH_PATH)
    cg = ContextGraph()
    cg.initialize(simulated_date)
    return cg
