"""Week-level assessment question generation and validation helpers."""

from __future__ import annotations

import json
import math
from typing import Any

from app.services.llm.llm_client import gemini_generate

MIN_WEEK_QUESTIONS = 8
MAX_WEEK_QUESTIONS = 20
BASE_WEEK_QUESTIONS = 8
MAX_DISTRIBUTION_RETRIES = 2


def clamp_question_count(question_count: int) -> int:
    return max(MIN_WEEK_QUESTIONS, min(MAX_WEEK_QUESTIONS, int(question_count)))


def compute_week_question_count(*, total_subtopics: int, week_hours: float) -> int:
    extra = int(math.ceil(max(0, int(total_subtopics)) / 3)) + int(math.ceil(max(0.0, float(week_hours)) / 5.0))
    return clamp_question_count(BASE_WEEK_QUESTIONS + extra)


def _strip_json_fences(raw_text: str) -> str:
    raw = (raw_text or "").strip()
    if raw.startswith("```"):
        raw = raw[3:]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def _normalize_tag(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_edge_case_question(tags: list[str], question: str) -> bool:
    if any("edge" in tag or "failure" in tag for tag in tags):
        return True
    return "edge case" in question.lower() or "failure mode" in question.lower()


def _is_scenario_question(tags: list[str], question: str) -> bool:
    if any("scenario" in tag or "applied" in tag for tag in tags):
        return True
    lowered = question.lower()
    return lowered.startswith("you are") or "scenario" in lowered or "in production" in lowered


def _validate_week_question(item: Any) -> dict | None:
    if not isinstance(item, dict):
        return None

    question = str(item.get("question", "")).strip()
    explanation = str(item.get("explanation", "")).strip()
    options = item.get("options", [])
    correct_index = item.get("correct_index")
    tags = item.get("tags", [])

    if not question or not explanation or not isinstance(options, list) or len(options) != 4:
        return None

    normalized_options = [str(opt).strip() for opt in options]
    if any(not opt for opt in normalized_options):
        return None

    if not isinstance(correct_index, int) or correct_index < 0 or correct_index > 3:
        return None

    if not isinstance(tags, list) or not tags:
        return None

    normalized_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    if not normalized_tags:
        return None

    return {
        "question": question,
        "options": normalized_options,
        "correct_index": correct_index,
        "explanation": explanation,
        "tags": normalized_tags,
    }


def _best_effort_distribution_ok(questions: list[dict], question_count: int) -> bool:
    if not questions or question_count <= 0:
        return False

    min_edge_cases = max(2, int(math.ceil(question_count * 0.2)))
    min_scenarios = int(math.ceil(question_count * 0.5))

    edge_count = 0
    scenario_count = 0
    for row in questions:
        tags = [_normalize_tag(tag) for tag in row.get("tags", [])]
        question = str(row.get("question", ""))
        if _is_edge_case_question(tags, question):
            edge_count += 1
        if _is_scenario_question(tags, question):
            scenario_count += 1

    return edge_count >= min_edge_cases and scenario_count >= min_scenarios


def _distribution_counts(questions: list[dict]) -> tuple[int, int]:
    edge_count = 0
    scenario_count = 0
    for row in questions:
        tags = [_normalize_tag(tag) for tag in row.get("tags", [])]
        question = str(row.get("question", ""))
        if _is_edge_case_question(tags, question):
            edge_count += 1
        if _is_scenario_question(tags, question):
            scenario_count += 1
    return edge_count, scenario_count


def _base_generation_prompt(
    *,
    week_number: int,
    week_hours: float,
    normalized_skills: list[str],
    normalized_subtopics: list[str],
    normalized_count: int,
    min_edge_cases: int,
    min_scenarios: int,
) -> str:
    skills_csv = ", ".join(normalized_skills)
    subtopics_csv_or_fallback = ", ".join(normalized_subtopics) if normalized_subtopics else "General applied concepts"
    week_hours_value = float(week_hours)
    return f"""
You are generating a WEEK assessment for a learner based on the content scheduled for this week.

Week:
- week_number: {int(week_number)}
- week_hours: {week_hours_value}
Skills (from week.skills[*].skill_name):
{skills_csv}

Subtopics (from week.skills[*].subtopics[*].title and sub_subtopics[*].title):
{subtopics_csv_or_fallback}

OUTPUT (STRICT):
Return ONLY valid JSON (no markdown, no prose), an array of exactly {normalized_count} objects.

Each object MUST have exactly these keys:
- "question" (string)
- "options" (array of exactly 4 strings)
- "correct_index" (integer 0..3)
- "explanation" (string, non-empty)
- "tags" (array of strings)

Schema example (do not include extra keys):
{{
  "question": "string",
  "options": ["A","B","C","D"],
  "correct_index": 0,
  "explanation": "string",
  "tags": ["skill:<skill name>", "subtopic:<subtopic>", "type:<scenario|edge_case|concept_check>"]
}}

COVERAGE REQUIREMENTS:
- Cover ALL skills listed above. Include at least 1 question per skill where possible.
- Cover major subtopic clusters across the provided subtopics/sub-subtopics (avoid overfocusing on one skill).
- Questions should reflect applied understanding, not trivia.

DISTRIBUTION (MUST SATISFY):
- At least {min_scenarios} scenario-based questions (>= 50% of total).
  Tag each as "type:scenario".
  Each scenario question must include real constraints and ask for the best action/decision:
  - debugging a failing pipeline / evaluation
  - prompt failures and mitigation
  - retrieval/RAG quality issues
  - hallucination & safety/guardrails
  - latency/cost trade-offs
  - data privacy and leakage
  - fine-tuning vs RAG decision-making
  - monitoring and drift

- At least {min_edge_cases} questions tagged as edge_case (edge-case / failure-mode) (>= 20% of total, min 2).
  Tag each as "type:edge_case".
  These must focus on subtle failure modes, misleading metrics, corner cases, security/privacy pitfalls, or prompt injection.

- Remaining questions may be "type:concept_check" but keep them practical and decision-oriented.

QUALITY RULES:
- Exactly 4 options; only one correct option.
- Options must be plausible and mutually exclusive.
- Avoid "All of the above" / "None of the above".
- Do not repeat the same question with minor rewording.
- No URLs.
- Use concise but clear explanations.

IMPORTANT:
Return JSON only. The array length must be exactly {normalized_count}.
""".strip()


def _retry_distribution_prompt(
    *,
    base_prompt: str,
    attempt: int,
    expected_edge_cases: int,
    expected_scenarios: int,
    found_edge_cases: int,
    found_scenarios: int,
) -> str:
    return (
        f"{base_prompt}\n\n"
        f"Previous output failed distribution constraints on attempt {attempt}.\n"
        f"Required edge-case count: >= {expected_edge_cases}; found: {found_edge_cases}.\n"
        f"Required scenario count: >= {expected_scenarios}; found: {found_scenarios}.\n"
        "Regenerate the full JSON array from scratch and satisfy all constraints exactly.\n"
        "Return strict JSON only."
    )


async def generate_week_assessment_questions(
    *,
    week_number: int,
    week_hours: float = 0.0,
    skills: list[str],
    subtopics: list[str],
    question_count: int,
) -> list[dict]:
    normalized_skills = [str(skill).strip() for skill in (skills or []) if str(skill).strip()]
    normalized_subtopics = [str(topic).strip() for topic in (subtopics or []) if str(topic).strip()]
    normalized_count = clamp_question_count(question_count)

    if not normalized_skills:
        return []

    min_edge_cases = max(2, int(math.ceil(normalized_count * 0.2)))
    min_scenarios = int(math.ceil(normalized_count * 0.5))

    prompt = _base_generation_prompt(
        week_number=week_number,
        week_hours=week_hours,
        normalized_skills=normalized_skills,
        normalized_subtopics=normalized_subtopics,
        normalized_count=normalized_count,
        min_edge_cases=min_edge_cases,
        min_scenarios=min_scenarios,
    )

    for attempt in range(MAX_DISTRIBUTION_RETRIES + 1):
        try:
            response_text = await gemini_generate(
                purpose="week_assessment_questions",
                prompt=prompt,
            )
            raw = _strip_json_fences(response_text or "")
            payload = json.loads(raw)
        except Exception:
            payload = None

        if isinstance(payload, list) and len(payload) == normalized_count:
            normalized: list[dict] = []
            for item in payload:
                parsed = _validate_week_question(item)
                if not parsed:
                    normalized = []
                    break
                normalized.append(parsed)

            if normalized:
                if _best_effort_distribution_ok(normalized, normalized_count):
                    return normalized
                if attempt < MAX_DISTRIBUTION_RETRIES:
                    found_edge_cases, found_scenarios = _distribution_counts(normalized)
                    prompt = _retry_distribution_prompt(
                        base_prompt=prompt,
                        attempt=attempt + 1,
                        expected_edge_cases=min_edge_cases,
                        expected_scenarios=min_scenarios,
                        found_edge_cases=found_edge_cases,
                        found_scenarios=found_scenarios,
                    )
                    continue

        if attempt < MAX_DISTRIBUTION_RETRIES:
            prompt = _retry_distribution_prompt(
                base_prompt=prompt,
                attempt=attempt + 1,
                expected_edge_cases=min_edge_cases,
                expected_scenarios=min_scenarios,
                found_edge_cases=0,
                found_scenarios=0,
            )

    return []
