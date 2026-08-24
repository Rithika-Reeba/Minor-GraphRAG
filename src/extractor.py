from __future__ import annotations

from src.llm import chat_text, parse_json_object

DOC_PROMPT = """Extract a personal knowledge graph from this document for person "{person}".
Return JSON only:
{{
  "skills": [{{"name": "", "level": ""}}],
  "projects": [{{"name": "", "description": "", "technologies": []}}],
  "education": [{{"name": "", "details": ""}}],
  "interests": [],
  "goals": [],
  "technologies": []
}}
Use only facts present in the text. Empty arrays are allowed.

Document:
{text}
"""


def extract_document_entities(person: str, text: str) -> dict:
    raw = chat_text(
        DOC_PROMPT.format(person=person, text=text[:12000]),
        system="You extract structured personal knowledge. Return JSON only.",
    )
    data = parse_json_object(raw)
    for key in ("skills", "projects", "education", "interests", "goals", "technologies"):
        data.setdefault(key, [])
    return data
