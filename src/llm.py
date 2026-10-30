import json
import re
from typing import Any

from groq import Groq

from src.config import GROQ_API_KEY, GROQ_TEXT_MODEL


def groq_client() -> Groq:
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Copy .env.example to .env and add your key."
        )
    return Groq(api_key=GROQ_API_KEY)


def parse_json_object(text: str) -> dict[str, Any]:
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def chat_text(
    prompt: str,
    system: str = "",
    temperature: float = 0.2,
    json_mode: bool = False,
    max_completion_tokens: int = 4096,
) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    kwargs = {
        "model": GROQ_TEXT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_completion_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = groq_client().chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""
