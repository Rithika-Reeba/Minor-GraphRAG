from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.config import GRAPH_DIR, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from src.storage import load_chunks as load_local_chunks
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


def subgraph_for_query(graph: dict[str, Any], query: str, limit: int = 200) -> dict[str, Any]:
    # A personal graph this size fits in the LLM context; send all facts.
    if len(graph["nodes"]) <= 150:
        return {"nodes": graph["nodes"], "relationships": graph["relationships"]}

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


def _neo4j_node_to_dict(node: Any) -> dict[str, Any] | None:
    if node is None:
        return None
    labels = list(node.labels)
    label = labels[0] if labels else "Entity"
    props = {k: v for k, v in dict(node).items() if v is not None}
    name = props.get("name") or props.get("id") or label
    node_id = props.get("id") or _node_id(label, str(name))
    return {"id": node_id, "label": label, "properties": props}


def load_graph_from_neo4j(person: str) -> dict[str, Any] | None:
    """Load the signed-in person's neighborhood from Neo4j."""
    if not neo4j_enabled():
        return None
    from neo4j import GraphDatabase

    user_id = _node_id("User", person)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    nodes: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []
    seen_rels: set[tuple[str, str, str]] = set()

    def add_node(raw: Any) -> str:
        parsed = _neo4j_node_to_dict(raw)
        if not parsed or parsed["label"] == "Chunk":
            return ""
        nodes[parsed["id"]] = parsed
        return parsed["id"]

    def add_rel(raw_rel: Any, source_id: str, target_id: str) -> None:
        if raw_rel is None or not source_id or not target_id:
            return
        rel_type = raw_rel.type
        key = (source_id, target_id, rel_type)
        if key in seen_rels:
            return
        seen_rels.add(key)
        relationships.append(
            {
                "id": str(uuid4()),
                "source": source_id,
                "target": target_id,
                "type": rel_type,
                "properties": dict(raw_rel),
            }
        )

    try:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (u:User)
                WHERE toLower(coalesce(u.name, '')) = toLower($name)
                   OR u.id = $uid
                OPTIONAL MATCH (u)-[r1]->(a)
                OPTIONAL MATCH (a)-[r2]->(b)
                RETURN u, r1, a, r2, b
                """,
                name=person,
                uid=user_id,
            )
            for record in rows:
                uid = add_node(record["u"])
                aid = add_node(record["a"])
                bid = add_node(record["b"])
                add_rel(record["r1"], uid, aid)
                add_rel(record["r2"], aid, bid)
        if not nodes:
            return None
        return {
            "person": person,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "nodes": list(nodes.values()),
            "relationships": relationships,
            "source": "neo4j",
        }
    except Exception:
        return None
    finally:
        driver.close()


def load_graph_for_retrieval(person: str) -> dict[str, Any]:
    """Prefer Neo4j for chat retrieval; fall back to local JSON."""
    neo4j_graph = load_graph_from_neo4j(person)
    if neo4j_graph and neo4j_graph.get("nodes"):
        return neo4j_graph
    graph = load_graph(person)
    graph["source"] = "json"
    return graph


def sync_chunks_to_neo4j(person: str, chunks: list[dict[str, Any]] | None = None) -> str:
    if not neo4j_enabled():
        return "Chunks kept locally (Neo4j not configured)."
    from neo4j import GraphDatabase

    payload = chunks if chunks is not None else load_local_chunks(person)
    if not payload:
        return "No document chunks to sync."

    user_id = _node_id("User", person)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            session.run(
                "MERGE (u:User {id: $id}) SET u.name = $name",
                id=user_id,
                name=person,
            )
            for chunk in payload:
                session.run(
                    """
                    MATCH (u:User {id: $uid})
                    MERGE (c:Chunk {id: $cid})
                    SET c.text = $text,
                        c.source = $source,
                        c.kind = $kind,
                        c.person = $person,
                        c.created_at = $created_at
                    MERGE (u)-[:HAS_CHUNK]->(c)
                    """,
                    uid=user_id,
                    cid=chunk.get("id") or str(uuid4()),
                    text=chunk.get("text", ""),
                    source=chunk.get("source", ""),
                    kind=chunk.get("kind", "document"),
                    person=person,
                    created_at=chunk.get("created_at", ""),
                )
        return f"Synced {len(payload)} chunks to Neo4j."
    finally:
        driver.close()


def load_chunks_from_neo4j(person: str) -> list[dict[str, Any]]:
    if not neo4j_enabled():
        return []
    from neo4j import GraphDatabase

    user_id = _node_id("User", person)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (u:User)-[:HAS_CHUNK]->(c:Chunk)
                WHERE toLower(coalesce(u.name, '')) = toLower($name)
                   OR u.id = $uid
                RETURN c.id AS id, c.text AS text, c.source AS source,
                       c.kind AS kind, c.person AS person, c.created_at AS created_at
                """,
                name=person,
                uid=user_id,
            )
            chunks = []
            for record in rows:
                chunks.append(
                    {
                        "id": record["id"],
                        "text": record["text"] or "",
                        "source": record["source"] or "",
                        "kind": record["kind"] or "document",
                        "person": record["person"] or person,
                        "created_at": record["created_at"] or "",
                    }
                )
            return chunks
    except Exception:
        return []
    finally:
        driver.close()


def load_chunks_for_retrieval(person: str) -> tuple[list[dict[str, Any]], str]:
    """Load document snippets from Neo4j. Migrate local JSON chunks if Neo4j is empty."""
    chunks = load_chunks_from_neo4j(person)
    if chunks:
        return chunks, "neo4j"
    local = load_local_chunks(person)
    if local and neo4j_enabled():
        try:
            sync_chunks_to_neo4j(person, local)
            migrated = load_chunks_from_neo4j(person)
            if migrated:
                return migrated, "neo4j"
        except Exception:
            pass
    return local, "json"


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
