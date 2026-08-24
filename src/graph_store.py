from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.config import GRAPH_DIR, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from src.storage import person_slug


def empty_graph(person: str) -> dict[str, Any]:
    return {
        "person": person,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": [],
        "relationships": [],
    }


def graph_path(person: str) -> Path:
    return GRAPH_DIR / f"{person_slug(person)}.json"


def load_graph(person: str) -> dict[str, Any]:
    path = graph_path(person)
    if not path.exists():
        return empty_graph(person)
    return json.loads(path.read_text(encoding="utf-8"))


def save_graph(graph: dict[str, Any]) -> Path:
    graph["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = graph_path(graph["person"])
    path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return path


def _node_id(label: str, name: str) -> str:
    return f"{label}:{name.strip().lower()}"


def upsert_node(graph: dict[str, Any], label: str, name: str, **properties: Any) -> str:
    name = name.strip()
    if not name:
        return ""
    node_id = properties.pop("id", None) or _node_id(label, name)
    for node in graph["nodes"]:
        if node["id"] == node_id:
            node["properties"].update({k: v for k, v in properties.items() if v not in (None, "")})
            return node_id
    graph["nodes"].append(
        {
            "id": node_id,
            "label": label,
            "properties": {"name": name, **{k: v for k, v in properties.items() if v not in (None, "")}},
        }
    )
    return node_id


def add_rel(
    graph: dict[str, Any],
    source_id: str,
    target_id: str,
    rel_type: str,
    **properties: Any,
) -> None:
    if not source_id or not target_id:
        return
    for rel in graph["relationships"]:
        if (
            rel["source"] == source_id
            and rel["target"] == target_id
            and rel["type"] == rel_type
        ):
            rel["properties"].update(properties)
            return
    graph["relationships"].append(
        {
            "id": str(uuid4()),
            "source": source_id,
            "target": target_id,
            "type": rel_type,
            "properties": properties,
        }
    )


def subgraph_for_query(graph: dict[str, Any], query: str, limit: int = 40) -> dict[str, Any]:
    terms = [term.lower() for term in query.split() if len(term) > 2]
    matched_ids: set[str] = set()
    for node in graph["nodes"]:
        blob = " ".join(
            [node["id"], node["label"], json.dumps(node["properties"]).lower()]
        )
        if not terms or any(term in blob for term in terms):
            matched_ids.add(node["id"])
    if not matched_ids:
        matched_ids = {node["id"] for node in graph["nodes"] if node["label"] == "User"}

    extra: set[str] = set()
    rels = []
    for rel in graph["relationships"]:
        if rel["source"] in matched_ids or rel["target"] in matched_ids:
            rels.append(rel)
            extra.add(rel["source"])
            extra.add(rel["target"])
    ids = matched_ids | extra
    nodes = [node for node in graph["nodes"] if node["id"] in ids][:limit]
    return {"nodes": nodes, "relationships": rels[:limit]}


def format_graph_context(subgraph: dict[str, Any]) -> str:
    if not subgraph["nodes"]:
        return "No graph facts found."
    id_to_name = {
        node["id"]: node["properties"].get("name", node["id"]) for node in subgraph["nodes"]
    }
    lines = ["Entities:"]
    for node in subgraph["nodes"]:
        props = {k: v for k, v in node["properties"].items() if k != "name"}
        extra = f" {props}" if props else ""
        lines.append(f"- ({node['label']}) {node['properties'].get('name')}{extra}")
    lines.append("Relationships:")
    for rel in subgraph["relationships"]:
        src = id_to_name.get(rel["source"], rel["source"])
        dst = id_to_name.get(rel["target"], rel["target"])
        evidence = rel["properties"].get("evidence", "")
        suffix = f" [evidence: {evidence}]" if evidence else ""
        lines.append(f"- {src} -[{rel['type']}]-> {dst}{suffix}")
    return "\n".join(lines)


def neo4j_enabled() -> bool:
    return bool(NEO4J_URI and NEO4J_PASSWORD and "your_neo4j_password" not in NEO4J_PASSWORD)


def sync_to_neo4j(graph: dict[str, Any]) -> str:
    if not neo4j_enabled():
        return "Local JSON graph only (Neo4j not configured)."
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            session.run(
                "MERGE (u:User {id: $id}) SET u.name = $name",
                id=_node_id("User", graph["person"]),
                name=graph["person"],
            )
            for node in graph["nodes"]:
                label = "".join(ch for ch in node["label"] if ch.isalnum())
                session.run(
                    f"MERGE (n:{label} {{id: $id}}) SET n += $props",
                    id=node["id"],
                    props=node["properties"],
                )
            for rel in graph["relationships"]:
                rel_type = "".join(ch for ch in rel["type"] if ch.isalnum() or ch == "_")
                session.run(
                    f"""
                    MATCH (a {{id: $src}}), (b {{id: $dst}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r += $props
                    """,
                    src=rel["source"],
                    dst=rel["target"],
                    props=rel["properties"],
                )
        return f"Synced to Neo4j at {NEO4J_URI}"
    finally:
        driver.close()
