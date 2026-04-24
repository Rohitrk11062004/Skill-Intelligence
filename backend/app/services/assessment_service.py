"""Assessment question generation helpers."""

from __future__ import annotations

import json
from typing import Any

from app.services.llm.llm_client import gemini_generate

QUESTIONS_PER_ITEM = 5


def _strip_json_fences(raw_text: str) -> str:
    raw = (raw_text or "").strip()
    if raw.startswith("```"):
        raw = raw[3:]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def _validate_question_item(item: Any) -> dict | None:
    if not isinstance(item, dict):
        return None

    question = str(item.get("question", "")).strip()
    explanation = str(item.get("explanation", "")).strip()
    options = item.get("options", [])
    correct_index = item.get("correct_index")

    if not question or not explanation or not isinstance(options, list) or len(options) != 4:
        return None

    normalized_options = [str(opt).strip() for opt in options]
    if any(not opt for opt in normalized_options):
        return None

    if not isinstance(correct_index, int) or correct_index < 0 or correct_index > 3:
        return None

    return {
        "question": question,
        "options": normalized_options,
        "correct_index": correct_index,
        "explanation": explanation,
    }


async def generate_assessment_questions(skill_name: str, level: str, subtopics: list[str]) -> list[dict]:
    """Generate exactly five quiz questions for a learning plan item.

    Returns an empty list when generation/parsing fails so callers can store null and retry later.
    """
    normalized_skill = str(skill_name or "").strip()
    normalized_level = str(level or "intermediate").strip().lower() or "intermediate"
    subtopic_list = [str(topic).strip() for topic in (subtopics or []) if str(topic).strip()]

    if not normalized_skill:
        return []

    subtopics_text = ", ".join(subtopic_list) if subtopic_list else "General applied concepts"

    prompt = f'''
You are generating a quiz-only assessment.
Skill: "{normalized_skill}"
Level: "{normalized_level}"
Subtopics: {subtopics_text}

Return ONLY valid JSON (no markdown), as an array with exactly {QUESTIONS_PER_ITEM} objects.
Each object must match:
{{
  "question": "string",
  "options": ["A", "B", "C", "D"],
  "correct_index": 0,
  "explanation": "string"
}}

Rules:
- Exactly {QUESTIONS_PER_ITEM} questions.
- Exactly 4 options per question.
- correct_index must be an integer from 0 to 3.
- No URLs.
- No resource suggestions.
'''.strip()

    try:
        response_text = await gemini_generate(
            purpose="assessment_questions",
            prompt=prompt,
        )
        raw = _strip_json_fences(response_text or "")
        payload = json.loads(raw)

        if not isinstance(payload, list) or len(payload) != QUESTIONS_PER_ITEM:
            return []

        normalized: list[dict] = []
        for item in payload:
            parsed = _validate_question_item(item)
            if not parsed:
                return []
            normalized.append(parsed)

        return normalized
    except Exception:
        return []
