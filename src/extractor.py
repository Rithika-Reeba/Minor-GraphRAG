from __future__ import annotations

from src.llm import chat_text, parse_json_object

DOC_PROMPT = """Extract a personal knowledge graph from this resume/document for "{person}".
Return ONLY a JSON object with these keys:
- summary: string
- skills: array of objects {{"name": "...", "level": ""}}
- projects: array of objects {{"name": "...", "description": "...", "technologies": []}}
- education: array of objects {{"name": "...", "details": "..."}}
- experience: array of objects {{"title": "...", "organization": "...", "details": "...", "technologies": []}}
- certifications: array of strings
- languages: array of strings
- interests: array of strings
- goals: array of strings
- technologies: array of strings

Extract ALL jobs, skills, projects, schools, certifications, languages, and interests present in the text.
Empty arrays are allowed only when that section is missing.

Document:
{text}
"""

FALLBACK_PROMPT = """From this resume for "{person}", return JSON with keys:
skills, projects, education, experience, certifications, languages, interests, technologies.
Include every item you can find. skills/projects/education/experience should be objects with name/title fields.

Document:
{text}
"""


def _normalize(data: dict) -> dict:
    keys = (
        "skills",
        "projects",
        "education",
        "experience",
        "certifications",
        "languages",
        "interests",
        "goals",
        "technologies",
    )
    for key in keys:
        data.setdefault(key, [])
    data.setdefault("summary", "")
    return data


def _has_signal(data: dict) -> bool:
    return any(data.get(key) for key in (
        "skills", "projects", "education", "experience",
        "certifications", "languages", "interests", "technologies",
    ))


def extract_document_entities(person: str, text: str) -> dict:
    excerpt = text[:14000]
    system = "You extract structured personal knowledge. Reply with one JSON object only."

    data = _normalize(parse_json_object(
        chat_text(
            DOC_PROMPT.format(person=person, text=excerpt),
            system=system,
            temperature=0.1,
            max_completion_tokens=8192,
        )
    ))

    if text.strip() and not _has_signal(data):
        data = _normalize(parse_json_object(
            chat_text(
                FALLBACK_PROMPT.format(person=person, text=excerpt),
                system=system,
                temperature=0.0,
                max_completion_tokens=8192,
            )
        ))
    return data
