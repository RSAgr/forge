import json
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
from app.services.routing_service import ROUTES

CATEGORIES = list(ROUTES)


def analyze_issue(description: str, image_bytes: bytes | None, mime_type: str | None, weather_context: dict[str, Any] | None = None) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY to analyze reports.")
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = f"""Analyze this civic issue. Return JSON: category (one of {CATEGORIES}), issue_description,
visible_damage_indicators (array), public_safety_risks (array), road_obstruction_level
(none/minor/partial/severe), confidence_score (0..1), explanation.
Do not infer facts not visible or stated. Recent weather context: {json.dumps(weather_context or {})}
Citizen description: {description}"""
    parts = [types.Part.from_text(text=prompt)]
    if image_bytes and mime_type:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    response = client.models.generate_content(
        model=settings.gemini_model, contents=parts,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty analysis.")
    result = json.loads(response.text)
    if result.get("category") not in CATEGORIES:
        result["category"] = "Other civic issues"
    return result
