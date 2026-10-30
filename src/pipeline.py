from __future__ import annotations

from pathlib import Path

from src.graph_store import (
    add_rel,
    load_graph,
    save_graph,
    sync_chunks_to_neo4j,
    sync_to_neo4j,
    upsert_node,
)
from src.ingestion.documents import chunk_text, extract_pdf_text
from src.ingestion.vision import analyze_image
from src.extractor import extract_document_entities
from src.storage import load_chunks, make_chunk, save_chunks


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
DOC_SUFFIXES = {".pdf", ".txt", ".md"}


def _ensure_user(graph: dict, person: str) -> str:
    return upsert_node(graph, "User", person)


def ingest_image(person: str, image_path: Path) -> dict:
    analysis = analyze_image(image_path)
    graph = load_graph(person)
    user_id = _ensure_user(graph, person)
    evidence = image_path.name
    chunks = []

    for item in analysis.get("items", []):
        item_name = " ".join(
            part for part in [item.get("color"), item.get("type")] if part
        ) or "clothing item"
        item_id = upsert_node(
            graph,
            "ClothingItem",
            item_name,
            type=item.get("type"),
            color=item.get("color"),
            style=item.get("style"),
            material=item.get("material"),
            occasion=item.get("occasion"),
            season=item.get("season"),
            source=evidence,
        )
        add_rel(graph, user_id, item_id, "OWNS", evidence=evidence)
        if item.get("color"):
            color_id = upsert_node(graph, "Color", item["color"])
            add_rel(graph, item_id, color_id, "HAS_COLOR", evidence=evidence)
        if item.get("style"):
            style_id = upsert_node(graph, "Style", item["style"])
            add_rel(graph, item_id, style_id, "HAS_STYLE", evidence=evidence)
            add_rel(graph, user_id, style_id, "HAS_STYLE", evidence=evidence)

    summary = analysis.get("style_summary") or f"Wardrobe analysis of {evidence}"
    chunks.append(make_chunk(person, evidence, summary, "image"))
    if analysis.get("items"):
        item_lines = ", ".join(
            f"{i.get('color', '')} {i.get('type', '')}".strip()
            for i in analysis["items"]
        )
        chunks.append(make_chunk(person, evidence, f"Wardrobe items: {item_lines}", "image"))

    save_chunks(person, chunks)
    save_graph(graph)
    neo4j_status = sync_to_neo4j(graph)
    sync_chunks_to_neo4j(person, chunks)
    return {"analysis": analysis, "graph": graph, "neo4j": neo4j_status}


def ingest_document(person: str, doc_path: Path) -> dict:
    if doc_path.suffix.lower() == ".pdf":
        text = extract_pdf_text(doc_path)
    else:
        text = doc_path.read_text(encoding="utf-8", errors="ignore")

    entities = extract_document_entities(person, text)
    graph = load_graph(person)
    user_id = _ensure_user(graph, person)
    evidence = doc_path.name

    for skill in entities.get("skills", []):
        name = skill.get("name") if isinstance(skill, dict) else str(skill)
        level = skill.get("level") if isinstance(skill, dict) else ""
        if not name:
            continue
        skill_id = upsert_node(graph, "Skill", name, level=level)
        add_rel(graph, user_id, skill_id, "HAS_SKILL", evidence=evidence, level=level)

    for project in entities.get("projects", []):
        if not isinstance(project, dict) or not project.get("name"):
            continue
        project_id = upsert_node(
            graph,
            "Project",
            project["name"],
            description=project.get("description", ""),
        )
        add_rel(graph, user_id, project_id, "WORKED_ON", evidence=evidence)
        for tech in project.get("technologies", []) or []:
            tech_id = upsert_node(graph, "Technology", str(tech))
            add_rel(graph, project_id, tech_id, "USES", evidence=evidence)
            add_rel(graph, user_id, tech_id, "USES", evidence=evidence)

    for edu in entities.get("education", []):
        name = edu.get("name") if isinstance(edu, dict) else str(edu)
        if not name:
            continue
        edu_id = upsert_node(
            graph,
            "Education",
            name,
            details=edu.get("details") if isinstance(edu, dict) else "",
        )
        add_rel(graph, user_id, edu_id, "STUDIED_AT", evidence=evidence)

    for job in entities.get("experience", []):
        if not isinstance(job, dict):
            continue
        title = (job.get("title") or "").strip()
        organization = (job.get("organization") or "").strip()
        if not title and not organization:
            continue
        job_name = " at ".join(part for part in [title, organization] if part)
        job_id = upsert_node(
            graph,
            "Experience",
            job_name,
            title=title,
            organization=organization,
            details=job.get("details", ""),
        )
        add_rel(graph, user_id, job_id, "WORKED_AS", evidence=evidence)
        if organization:
            org_id = upsert_node(graph, "Organization", organization)
            add_rel(graph, user_id, org_id, "WORKED_AT", evidence=evidence)
            add_rel(graph, job_id, org_id, "AT_ORGANIZATION", evidence=evidence)
        for tech in job.get("technologies", []) or []:
            tech_id = upsert_node(graph, "Technology", str(tech))
            add_rel(graph, job_id, tech_id, "USES", evidence=evidence)
            add_rel(graph, user_id, tech_id, "USES", evidence=evidence)

    for cert in entities.get("certifications", []):
        name = cert.get("name") if isinstance(cert, dict) else str(cert)
        if not name:
            continue
        cert_id = upsert_node(graph, "Certification", name)
        add_rel(graph, user_id, cert_id, "EARNED", evidence=evidence)

    for language in entities.get("languages", []):
        name = language.get("name") if isinstance(language, dict) else str(language)
        if not name:
            continue
        lang_id = upsert_node(graph, "Language", name)
        add_rel(graph, user_id, lang_id, "SPEAKS", evidence=evidence)

    for interest in entities.get("interests", []):
        interest_id = upsert_node(graph, "Interest", str(interest))
        add_rel(graph, user_id, interest_id, "INTERESTED_IN", evidence=evidence)

    for goal in entities.get("goals", []):
        goal_id = upsert_node(graph, "Goal", str(goal))
        add_rel(graph, user_id, goal_id, "HAS_GOAL", evidence=evidence)

    for tech in entities.get("technologies", []):
        tech_id = upsert_node(graph, "Technology", str(tech))
        add_rel(graph, user_id, tech_id, "USES", evidence=evidence)

    if entities.get("summary"):
        summary_id = upsert_node(graph, "Summary", "Professional Summary", text=entities["summary"])
        add_rel(graph, user_id, summary_id, "HAS_SUMMARY", evidence=evidence)

    chunks = [
        make_chunk(person, evidence, piece, "document")
        for piece in chunk_text(text)
    ]
    save_chunks(person, chunks)
    save_graph(graph)
    neo4j_status = sync_to_neo4j(graph)
    sync_chunks_to_neo4j(person, chunks)

    entity_count = sum(
        len(entities.get(key, []) or [])
        for key in ("skills", "projects", "education", "experience", "certifications", "languages", "interests", "technologies")
    )
    if text.strip() and entity_count == 0:
        raise RuntimeError(
            f"PDF text was read from {doc_path.name}, but no entities were extracted. "
            "Try Extract and build graph again."
        )

    return {"entities": entities, "graph": graph, "neo4j": neo4j_status}


def build_graph_from_files(person: str, file_paths: list[Path]) -> dict:
    summaries = []
    last_graph = load_graph(person)
    _ensure_user(last_graph, person)
    save_graph(last_graph)

    for path in file_paths:
        suffix = path.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            result = ingest_image(person, path)
            summaries.append(f"Image {path.name}: {len(result['analysis'].get('items', []))} items")
            last_graph = result["graph"]
        elif suffix in DOC_SUFFIXES:
            result = ingest_document(person, path)
            summaries.append(f"Document {path.name}: extracted skills/projects")
            last_graph = result["graph"]
        else:
            summaries.append(f"Skipped {path.name}: unsupported type")

    neo4j_status = sync_to_neo4j(last_graph)
    chunk_status = sync_chunks_to_neo4j(person, load_chunks(person))
    if chunk_status:
        neo4j_status = f"{neo4j_status} {chunk_status}"
    return {
        "person": person,
        "summaries": summaries,
        "nodes": len(last_graph["nodes"]),
        "relationships": len(last_graph["relationships"]),
        "neo4j": neo4j_status,
        "graph": last_graph,
    }
