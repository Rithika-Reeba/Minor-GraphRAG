from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.config import CHUNK_DIR


def person_slug(name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "user"


def save_chunks(person: str, chunks: list[dict[str, Any]]) -> Path:
    path = CHUNK_DIR / f"{person_slug(person)}.json"
    existing: list[dict[str, Any]] = []
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    existing.extend(chunks)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return path


def load_chunks(person: str) -> list[dict[str, Any]]:
    path = CHUNK_DIR / f"{person_slug(person)}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def make_chunk(
    person: str,
    source: str,
    text: str,
    kind: str,
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "person": person,
        "source": source,
        "kind": kind,
        "text": text.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def score_chunks(query: str, chunks: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    terms = {term.lower() for term in query.split() if len(term) > 2}
    ranked: list[tuple[int, dict[str, Any]]] = []
    for chunk in chunks:
        haystack = chunk.get("text", "").lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if ranked:
        return [chunk for _, chunk in ranked[:limit]]
    return chunks[-limit:]
