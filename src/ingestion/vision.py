from __future__ import annotations

import base64
from pathlib import Path

from src.config import GROQ_VISION_MODEL
from src.llm import groq_client, parse_json_object

VISION_PROMPT = """Analyze this wardrobe or clothing image.
Return JSON only with this shape:
{
  "items": [
    {
      "type": "dress|shoes|bag|hat|top|bottom|accessory|other",
      "color": "main color",
      "style": "casual|formal|party|sport|minimalist|traditional",
      "material": "if visible",
      "occasion": "casual|formal|party|work|other",
      "season": "all-season|summer|winter|monsoon"
    }
  ],
  "dominant_colors": ["..."],
  "style_summary": "one sentence",
  "organization_notes": "short note"
}
"""


def analyze_image(image_path: Path) -> dict:
    suffix = image_path.suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix or 'png'}"
    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    response = groq_client().chat.completions.create(
        model=GROQ_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
        temperature=0.1,
        max_completion_tokens=2048,
        reasoning_effort="none",
    )
    parsed = parse_json_object(response.choices[0].message.content or "")
    parsed.setdefault("items", [])
    parsed.setdefault("source", image_path.name)
    return parsed
