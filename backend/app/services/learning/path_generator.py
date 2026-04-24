"""Generate lightweight learning plans from gap analysis output."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from math import ceil
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    LearningPlan,
    LearningPlanItem,
    LearningPlanItemResource,
    LearningPlanItemSubSubtopic,
    LearningPlanItemSubtopic,
    WeekAssessment,
    WeekAssessmentAttempt,
    Resume,
    Role,
    Skill,
    SkillPrerequisite,
    User,
    UserSkillScore,
)
from app.schemas.learning import (
    DaySkillBlock,
    DeferredRoadmapItem,
    LearningDayPlan,
    LearningRoadmapResponse,
    LearningWeek,
    RoadmapBudgetSummary,
    ResourceSuggestion,
    SubSubtopic,
    Subtopic,
    WeekSkillNode,
)
from app.services.gap.gap_detector import GapResult, detect_and_store_gaps
from app.services.assessment_service import QUESTIONS_PER_ITEM, generate_assessment_questions
from app.services.catalog_service import get_resources_for_skill, is_url_reachable
from app.services.llm.llm_client import gemini_generate

log = logging.getLogger(__name__)


@dataclass
class PlanItem:
    order: int
    skill_id: str
    skill_name: str
    gap_type: str
    priority_score: float
    estimated_hours: int
    prerequisites: list[str]
    resources: list[dict]


@dataclass
class RoadmapSkillNode:
    skill_id: str
    skill_name: str
    gap_type: str
    priority_score: float
    total_hours: float
    subtopics: list[Subtopic]
    resources: list[ResourceSuggestion]
    prerequisites: list[str]
    level: int = 0
    importance: float = 0.0
    is_mandatory: bool = False
    skill_band: str = "Technical Skills"
    skill_rationale: str | None = None


CATALOG_LIMIT_PER_FORMAT = 2
MAX_CATALOG_RESOURCES_PER_SKILL = 4
WEEK_HOUR_CAP_DEFAULT = 10
RESOURCE_URL_VALIDATION_CONCURRENCY = 10

_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _assessment_level_from_gap_type(gap_type: str) -> str:
    return "intermediate" if str(gap_type or "").strip().lower() == "weak" else "beginner"


def _strip_json_fences(raw_text: str) -> str:
    raw = (raw_text or "").strip()
    if raw.startswith("```"):
        raw = raw[3:]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def _truncate_title(title: str, limit: int = 60) -> str:
    clean = " ".join((title or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _normalize_hours(total_hours: float, subtopics: list[dict]) -> list[dict]:
    total = float(total_hours or 0.0)
    if not subtopics or total <= 0:
        return subtopics

    # Distribute top-level hours proportionally based on sub_subtopic count as weight
    sub_counts = [max(len(st.get("sub_subtopics", []) or []), 1) for st in subtopics]
    total_weight = sum(sub_counts)

    result: list[dict] = []
    allocated = 0.0
    for i, st in enumerate(subtopics):
        if i == len(subtopics) - 1:
            st_hours = round(total - allocated, 2)
        else:
            st_hours = round((sub_counts[i] / total_weight) * total, 2)
        allocated += st_hours

        subs = st.get("sub_subtopics", []) or []
        sub_total = sum(float((s or {}).get("estimated_hours", 0) or 0.0) for s in subs if isinstance(s, dict))
        normalized_subs: list[dict] = []
        sub_allocated = 0.0
        for j, sub in enumerate(subs):
            if not isinstance(sub, dict):
                continue
            if j == len(subs) - 1:
                sub_hours = round(st_hours - sub_allocated, 2)
            else:
                ratio = (float(sub.get("estimated_hours", 0) or 0.0) / sub_total) if sub_total > 0 else (1 / len(subs))
                sub_hours = round(ratio * st_hours, 2)
            sub_allocated += sub_hours
            normalized_subs.append({**sub, "estimated_hours": sub_hours})

        result.append({**st, "estimated_hours": st_hours, "sub_subtopics": normalized_subs})
    return result


def _scale_week_skill_node(node: WeekSkillNode, factor: float) -> WeekSkillNode:
    """Shrink planned hours proportionally when total gap hours exceed the deadline budget.

    Keeps every gap in the roadmap instead of deferring optional skills entirely.
    """
    f = max(0.0, float(factor))
    if f >= 0.999999:
        return node.model_copy(deep=True)

    orig_total = float(node.total_hours or 0.0)
    new_total = round(orig_total * f, 2)
    if orig_total > 0 and new_total <= 0:
        new_total = round(max(0.5, orig_total * f), 2)

    subtopics_in = node.subtopics or []
    if not subtopics_in:
        return WeekSkillNode(
            skill_id=node.skill_id,
            item_id=node.item_id,
            item_status=node.item_status,
            skill_name=node.skill_name,
            skill_rationale=node.skill_rationale,
            gap_type=node.gap_type,
            priority_score=node.priority_score,
            skill_band=node.skill_band,
            total_hours=new_total,
            subtopics=[],
            resources=[
                ResourceSuggestion(
                    title=r.title,
                    provider=r.provider,
                    url=r.url,
                    resource_type=r.resource_type,
                    estimated_hours=round(float(r.estimated_hours or 0.0) * f, 2),
                    why=r.why,
                )
                for r in (node.resources or [])
            ],
        )

    sub_dump: list[dict] = []
    for st in subtopics_in:
        subs_list = []
        for ss in st.sub_subtopics or []:
            subs_list.append(
                {
                    "title": ss.title,
                    "estimated_hours": float(ss.estimated_hours or 0.0) * f,
                }
            )
        sub_dump.append(
            {
                "title": st.title,
                "estimated_hours": float(st.estimated_hours or 0.0) * f,
                "sub_subtopics": subs_list,
            }
        )

    normalized = _normalize_hours(new_total, sub_dump)
    new_subtopics: list[Subtopic] = []
    for st in normalized:
        if not isinstance(st, dict):
            continue
        norm_ss = []
        for ss in st.get("sub_subtopics") or []:
            if isinstance(ss, dict):
                norm_ss.append(
                    SubSubtopic(
                        title=str(ss.get("title", "")),
                        estimated_hours=float(ss.get("estimated_hours", 0.0) or 0.0),
                    )
                )
        new_subtopics.append(
            Subtopic(
                title=str(st.get("title", "")),
                estimated_hours=float(st.get("estimated_hours", 0.0) or 0.0),
                sub_subtopics=norm_ss,
            )
        )

    scaled_resources = [
        ResourceSuggestion(
            title=r.title,
            provider=r.provider,
            url=r.url,
            resource_type=r.resource_type,
            estimated_hours=round(float(r.estimated_hours or 0.0) * f, 2),
            why=r.why,
        )
        for r in (node.resources or [])
    ]

    return WeekSkillNode(
        skill_id=node.skill_id,
        item_id=node.item_id,
        item_status=node.item_status,
        skill_name=node.skill_name,
        skill_rationale=node.skill_rationale,
        gap_type=node.gap_type,
        priority_score=node.priority_score,
        skill_band=node.skill_band,
        total_hours=new_total,
        subtopics=new_subtopics,
        resources=scaled_resources,
    )


def _fallback_structure(skill_name: str, total_hours: float) -> list[Subtopic]:
    subtopic_titles = [
        f"{skill_name} Fundamentals",
        f"{skill_name} Applied",
        f"{skill_name} Advanced",
    ]
    subtopic_hours = total_hours / 3 if total_hours else 0.0
    sub_sub_hours = subtopic_hours / 2 if subtopic_hours else 0.0

    return [
        Subtopic(
            title=title,
            estimated_hours=subtopic_hours,
            sub_subtopics=[
                SubSubtopic(title="Core concepts", estimated_hours=sub_sub_hours),
                SubSubtopic(title="Hands-on practice", estimated_hours=sub_sub_hours),
            ],
        )
        for title in subtopic_titles
    ]


def _fallback_resources(skill_name: str, hours: int) -> list[dict]:
    suggested_hours = max(1.0, float(hours or 4) / 3.0)
    return [
        {
            "title": f"{skill_name} Documentation Essentials",
            "provider": "Official Docs",
            "url": f"https://www.google.com/search?q={skill_name.replace(' ', '+')}+official+documentation",
            "resource_type": "docs",
            "estimated_hours": round(suggested_hours, 1),
            "why": "Start with canonical concepts and terminology.",
        },
        {
            "title": f"{skill_name} Practical Exercises",
            "provider": "Hands-on Labs",
            "url": f"https://www.google.com/search?q={skill_name.replace(' ', '+')}+practice+exercises",
            "resource_type": "practice",
            "estimated_hours": round(suggested_hours, 1),
            "why": "Convert theory into repeatable implementation skill.",
        },
        {
            "title": f"{skill_name} Applied Course",
            "provider": "Online Learning Platform",
            "url": f"https://www.google.com/search?q={skill_name.replace(' ', '+')}+project+based+course",
            "resource_type": "course",
            "estimated_hours": round(suggested_hours, 1),
            "why": "Use a structured sequence to reach job-ready fluency.",
        },
    ]


def _deserialize_subtopics(raw: str | None) -> list[Subtopic]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [
            Subtopic(
                title=st["title"],
                estimated_hours=float(st.get("estimated_hours", 0.0)),
                sub_subtopics=[
                    SubSubtopic(
                        title=ss["title"],
                        estimated_hours=float(ss.get("estimated_hours", 0.0)),
                    )
                    for ss in st.get("sub_subtopics", [])
                ],
            )
            for st in data
            if isinstance(st, dict) and st.get("title")
        ]
    except Exception:
        return []


def _deserialize_learning_content(raw: str | None) -> tuple[list[Subtopic], list[ResourceSuggestion]]:
    """
    Backward-compatible loader for LearningPlanItem.subtopics_json.
    Supported formats:
    1) Legacy list: [<subtopic>, ...]
    2) Wrapper object: {"subtopics": [...], "resources": [...]}.
    """
    if not raw:
        return [], []

    try:
        payload = json.loads(raw)
    except Exception:
        return [], []

    if isinstance(payload, list):
        return _deserialize_subtopics(raw), []

    if not isinstance(payload, dict):
        return [], []

    subtopics = _deserialize_subtopics(json.dumps(payload.get("subtopics", [])))
    resources_raw = payload.get("resources", [])
    resources: list[ResourceSuggestion] = []
    allowed_resource_types = {"video", "article", "course", "practice", "docs"}
    if isinstance(resources_raw, list):
        for item in resources_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            provider = str(item.get("provider", "")).strip()
            url = str(item.get("url", "")).strip()
            resource_type = str(item.get("resource_type", "article")).strip().lower() or "article"
            if resource_type not in allowed_resource_types:
                resource_type = "article"
            why = str(item.get("why", "")).strip()
            if not title or not provider or not url or not why:
                continue
            try:
                estimated_hours = float(item.get("estimated_hours", 0.0) or 0.0)
            except Exception:
                estimated_hours = 0.0
            if estimated_hours <= 0:
                continue

            resources.append(
                ResourceSuggestion(
                    title=title,
                    provider=provider,
                    url=url,
                    resource_type=resource_type,
                    estimated_hours=estimated_hours,
                    why=why,
                )
            )

    return subtopics, resources


def _serialize_learning_content(subtopics: list[Subtopic], resources: list[ResourceSuggestion]) -> str | None:
    if not subtopics and not resources:
        return None

    subtopics_payload = [
        {
            "title": st.title,
            "estimated_hours": st.estimated_hours,
            "sub_subtopics": [
                {"title": ss.title, "estimated_hours": ss.estimated_hours}
                for ss in st.sub_subtopics
            ],
        }
        for st in subtopics
    ]
    resources_payload = [
        {
            "title": rs.title,
            "provider": rs.provider,
            "url": rs.url,
            "resource_type": rs.resource_type,
            "estimated_hours": rs.estimated_hours,
            "why": rs.why,
        }
        for rs in resources
    ]

    # Store wrapper form to preserve legacy compatibility while persisting resources.
    return json.dumps({"subtopics": subtopics_payload, "resources": resources_payload})


async def _generate_skill_breakdown(
    skill_name: str,
    target_role: str,
    gap_type: str,
    time_to_learn_hours: float,
    user_skill_profile: list[tuple[str, str]] | None = None,
) -> list[Subtopic]:
    profile_list = user_skill_profile or []
    profile_text = ", ".join([f"{name} - {level}" for name, level in profile_list]) if profile_list else "None"

    profile_summary = (
        f"Already proficient in: {profile_text}" if profile_text else "No prior related skills."
    )

    prompt = f"""
You are a senior technical curriculum designer building a personalized learning plan.

Skill to learn: "{skill_name}"
Target role: {target_role}
Gap type: {"MISSING — learner has never used this skill" if gap_type == "missing" else "WEAK — learner has surface-level exposure but needs depth"}
Total hours allocated for this skill: {time_to_learn_hours}h
Learner context: {profile_summary}

Your task: Break "{skill_name}" into 3–6 specific, sequenced subtopics a professional would actually study to become job-ready in this skill for the {target_role} role.

Requirements:
- Stay strictly focused on "{skill_name}" — subtopics must teach that skill only. Do not substitute generic communication, teamwork, or presentation topics unless "{skill_name}" itself is clearly a soft-skill or communication skill.
- Subtopic titles must be concrete and specific (e.g. "Sprint ceremonies and velocity tracking" not "Agile basics")
- Each subtopic must have 2–5 sub-subtopics that are equally specific
- Sub-subtopic titles should name the exact concept or technique (e.g. "Writing user stories with acceptance criteria" not "Practice")
- If gap_type is weak, skip foundational theory — go straight to applied, advanced, or edge-case topics
- Skip any subtopic that is already covered by the learner's existing skills: {profile_summary}
- Hours must be realistic for a working professional — bias toward applied practice over theory
- Total estimated_hours across ALL subtopics must sum to exactly {time_to_learn_hours}

Return ONLY valid JSON:
{{
  "subtopics": [
    {{
      "title": "<specific subtopic name>",
      "estimated_hours": <float>,
      "sub_subtopics": [
        {{
          "title": "<specific concept or technique>",
          "estimated_hours": <float>
        }}
      ]
    }}
  ]
}}
""".strip()

    try:
        response_text = await gemini_generate(
            purpose="roadmap_subtopics",
            prompt=prompt,
        )
        raw = _strip_json_fences(response_text or "")
        data = json.loads(raw)

        subtopics_raw = data.get("subtopics", []) if isinstance(data, dict) else []
        if not isinstance(subtopics_raw, list) or not subtopics_raw:
            raise ValueError("Gemini response missing subtopics list")

        normalized_subtopics: list[dict] = []
        for item in subtopics_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            sub_subtopics_raw = item.get("sub_subtopics", [])
            normalized_sub_subtopics: list[dict] = []
            if isinstance(sub_subtopics_raw, list):
                for sub_item in sub_subtopics_raw:
                    if not isinstance(sub_item, dict):
                        continue
                    sub_title = str(sub_item.get("title", "")).strip()
                    if not sub_title:
                        continue
                    normalized_sub_subtopics.append(
                        {
                            "title": sub_title,
                            "estimated_hours": float(sub_item.get("estimated_hours", 0.0) or 0.0),
                        }
                    )

            normalized_subtopics.append(
                {
                    "title": title,
                    "estimated_hours": float(item.get("estimated_hours", 0.0) or 0.0),
                    "sub_subtopics": normalized_sub_subtopics,
                }
            )

        if len(normalized_subtopics) < 3:
            raise ValueError("Gemini returned too few subtopics")

        normalized_subtopics = normalized_subtopics[:6]
        for st in normalized_subtopics:
            if not st.get("sub_subtopics"):
                raise ValueError(
                    f"Subtopic '{st.get('title')}' returned no valid sub-subtopics from Gemini"
                )
        normalized_subtopics = _normalize_hours(float(time_to_learn_hours or 0.0), normalized_subtopics)
        return [Subtopic(**item) for item in normalized_subtopics]
    except Exception as exc:
        log.warning("Falling back to placeholder roadmap structure for %s: %s", skill_name, exc)
        return _fallback_structure(skill_name, float(time_to_learn_hours or 0.0))


async def _generate_assessment_breakdown(
    skill_name: str,
    target_role: str,
    failed_areas: list[str],
    time_to_learn_hours: float,
) -> list[Subtopic]:
    failed_titles = [
        str(area).replace("_", " ").strip().title()
        for area in failed_areas
        if str(area).strip()
    ]
    if not failed_titles:
        failed_titles = [f"{skill_name} Focus Areas"]

    prompt = f'''
You are revising a learning breakdown after an assessment.
Skill: "{skill_name}"
Target role: "{target_role}"
Failed areas: {", ".join(failed_titles)}
Total time available for this skill: {time_to_learn_hours} hours

Return ONLY valid JSON, no markdown and no explanation:
{{
  "subtopics": [
    {{
      "title": "<subtopic title>",
      "estimated_hours": <float>,
      "sub_subtopics": [
        {{
          "title": "<sub-subtopic title>",
          "estimated_hours": <float>
        }}
      ]
    }}
  ]
}}

Rules:
- Focus on the failed areas listed above.
- Titles should map the failed area names into user-friendly titles.
- Return 3 to 5 subtopics.
- Total estimated_hours across all subtopics must equal {time_to_learn_hours}.
- Prefer applied practice and remediation over broad fundamentals.
'''.strip()

    try:
        response_text = await gemini_generate(
            purpose="roadmap_assessment_remediation_subtopics",
            prompt=prompt,
        )
        raw = _strip_json_fences(response_text or "")
        data = json.loads(raw)

        subtopics_raw = data.get("subtopics", []) if isinstance(data, dict) else []
        if not isinstance(subtopics_raw, list) or not subtopics_raw:
            raise ValueError("Gemini response missing subtopics list")

        normalized_subtopics: list[dict] = []
        for item in subtopics_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            sub_subtopics_raw = item.get("sub_subtopics", [])
            normalized_sub_subtopics: list[dict] = []
            if isinstance(sub_subtopics_raw, list):
                for sub_item in sub_subtopics_raw:
                    if not isinstance(sub_item, dict):
                        continue
                    sub_title = str(sub_item.get("title", "")).strip()
                    if not sub_title:
                        continue
                    normalized_sub_subtopics.append(
                        {
                            "title": sub_title,
                            "estimated_hours": float(sub_item.get("estimated_hours", 0.0) or 0.0),
                        }
                    )

            normalized_subtopics.append(
                {
                    "title": title,
                    "estimated_hours": float(item.get("estimated_hours", 0.0) or 0.0),
                    "sub_subtopics": normalized_sub_subtopics or [
                        {"title": "Core concepts", "estimated_hours": 0.0},
                        {"title": "Applied practice", "estimated_hours": 0.0},
                    ],
                }
            )

        if len(normalized_subtopics) < 3:
            raise ValueError("Gemini returned too few remediation subtopics")

        normalized_subtopics = normalized_subtopics[:5]
        normalized_subtopics = _normalize_hours(float(time_to_learn_hours or 0.0), normalized_subtopics)
        return [Subtopic(**item) for item in normalized_subtopics]
    except Exception as exc:
        log.warning("Falling back to assessment roadmap structure for %s: %s", skill_name, exc)
        return _fallback_structure(skill_name, float(time_to_learn_hours or 0.0))


def _band_rank(skill_band: str | None) -> int:
    band = (skill_band or "").strip().lower()
    if band == "beginner":
        return 0
    if band == "intermediate":
        return 1
    if band == "advanced":
        return 2
    return 1


def _domain_schedule_rank(skill_band: str | None, skill_name: str | None) -> int:
    """Order gaps within the same topological level: technical/engineering before soft skills.

    `skill_band` in the DB is usually a domain (e.g. Technical Skills, Soft Skills), not
    proficiency. The old `_band_rank` compared against beginner/intermediate/advanced, so almost
    every gap tied and ordering collapsed to secondary keys — often surfacing communication-heavy
    weeks first. Lower = earlier in the schedule.
    """
    band = (skill_band or "").strip().lower()
    name = (skill_name or "").strip().lower()
    blob = f"{band} {name}"

    soft_markers = (
        "soft skill",
        "soft skills",
        "communication",
        "leadership",
        "interpersonal",
        "presentation skills",
        "public speaking",
        "collaboration",
        "teamwork",
        "negotiation",
        "emotional intelligence",
    )
    tech_markers = (
        "technical",
        "backend",
        "frontend",
        "full stack",
        "devops",
        "sre",
        "cloud",
        "data engineer",
        "data science",
        "security",
        "network",
        "database",
        "kubernetes",
        "docker",
        "programming",
        "software",
        "qa",
        "testing",
        "machine learning",
        "analytics",
        "api",
        "microservice",
    )

    if "soft" in band or any(m in blob for m in soft_markers):
        return 2
    if "technical" in band or any(m in blob for m in tech_markers):
        return 0
    return 1


def _extract_base_skill_name(skill_name: str) -> str:
    marker = " — Part "
    idx = skill_name.rfind(marker)
    if idx == -1:
        return skill_name
    return skill_name[:idx]


def _resolve_skill_id(skill_name: str, skill_id_by_name: dict[str, str]) -> str:
    direct = skill_id_by_name.get(skill_name)
    if direct:
        return direct
    return skill_id_by_name.get(_extract_base_skill_name(skill_name), "")


async def _load_user_intermediate_or_advanced_skills(
    db: AsyncSession,
    user_id: str,
) -> list[tuple[str, str]]:
    rows = (
        await db.execute(
            select(UserSkillScore, Skill)
            .join(Skill, Skill.id == UserSkillScore.skill_id)
            .where(UserSkillScore.user_id == user_id)
        )
    ).all()

    profile: list[tuple[str, str]] = []
    for score, skill in rows:
        level = (score.proficiency or "beginner").lower().strip()
        numeric = float(score.proficiency_score or 0.0)
        if level in {"intermediate", "advanced"} or numeric >= 0.5:
            normalized = level if level in {"intermediate", "advanced"} else "intermediate"
            profile.append((skill.name, normalized))

    profile.sort(key=lambda item: item[0].lower())
    return profile


async def _gemini_resources(
    skill_name: str,
    target_role: str,
    gap_type: str,
    hours: int,
) -> list[ResourceSuggestion]:
    prompt = f'''
You are recommending learning resources for one skill.
Skill: "{skill_name}"
Target role: "{target_role}"
Gap type: "{gap_type}"
Total learning hours for this skill: {hours}

Return ONLY valid JSON, no markdown and no explanation.
The JSON must be an array with 3 to 4 objects and each object must contain:
- title (string)
- provider (string)
- url (string)
- resource_type (one of: video, article, course, practice, docs)
- estimated_hours (number)
- why (string)

Rules:
- Include practical, non-placeholder resources.
- Keep each "why" concise and skill-specific.
- Estimated hours should sum approximately to {max(1, int(hours))}.
'''.strip()

    try:
        response_text = await gemini_generate(
            purpose="catalog_fallback_resources",
            prompt=prompt,
        )
        raw = _strip_json_fences(response_text or "")
        data = json.loads(raw)
        resources_raw = data if isinstance(data, list) else data.get("resources", [])

        if not isinstance(resources_raw, list):
            raise ValueError("Gemini resources payload is not a list")

        output: list[ResourceSuggestion] = []
        allowed_types = {"video", "article", "course", "practice", "docs"}

        for item in resources_raw[:4]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            provider = str(item.get("provider", "")).strip()
            url = str(item.get("url", "")).strip()
            why = str(item.get("why", "")).strip()
            r_type = str(item.get("resource_type", "article")).strip().lower() or "article"
            if r_type not in allowed_types:
                r_type = "article"

            try:
                estimated_hours = float(item.get("estimated_hours", 0.0) or 0.0)
            except Exception:
                estimated_hours = 0.0

            if not title or not provider or not url or not why or estimated_hours <= 0:
                continue

            output.append(
                ResourceSuggestion(
                    title=title,
                    provider=provider,
                    url=url,
                    resource_type=r_type,
                    estimated_hours=round(estimated_hours, 1),
                    why=why,
                )
            )

        if len(output) < 3:
            raise ValueError("Gemini resources payload did not contain at least 3 valid entries")

        return output[:4]
    except Exception as exc:
        log.warning("Falling back to safe stub resources for %s: %s", skill_name, exc)
        fallback = _fallback_resources(skill_name, hours)
        return [
            ResourceSuggestion(
                title=str(item.get("title", "")).strip() or f"{skill_name} resource",
                provider=str(item.get("provider", "")).strip() or "Internal",
                url=str(item.get("url", "")).strip() or "https://www.google.com",
                resource_type=str(item.get("resource_type", "article")).strip().lower() or "article",
                estimated_hours=float(item.get("estimated_hours", 1.0) or 1.0),
                why=str(item.get("why", "")).strip() or f"Supports {skill_name} improvement.",
            )
            for item in fallback
        ]


def _map_gap_to_catalog_level(gap_type: str, skill_band: str | None = None) -> str:
    # Deterministic default: missing -> beginner, weak -> intermediate, with optional skill-band bump.
    base = "intermediate" if str(gap_type or "").strip().lower() == "weak" else "beginner"
    band = str(skill_band or "").strip().lower()
    if "advanced" in band:
        return "advanced" if base == "intermediate" else "intermediate"
    if "beginner" in band:
        return "beginner"
    return base


def _catalog_format_to_resource_type(resource_format: str | None) -> str:
    normalized = str(resource_format or "").strip().lower()
    if normalized == "doc":
        return "docs"
    if normalized in {"video", "article", "course", "practice", "docs"}:
        return normalized
    return "article"


def _estimated_hours_from_duration(duration_minutes: object) -> float:
    try:
        minutes = float(duration_minutes or 0.0)
    except (TypeError, ValueError):
        minutes = 0.0
    if minutes > 0:
        return max(0.1, round(minutes / 60.0, 2))
    return 0.5


def _rationale_cache_key(skill_name: str, target_role: str, gap_type: str) -> tuple[str, str, str]:
    return (
        str(skill_name or "").strip().lower(),
        str(target_role or "").strip().lower(),
        str(gap_type or "").strip().lower(),
    )


async def _gemini_skill_rationale(
    skill_name: str,
    target_role: str,
    gap_type: str,
    rationale_cache: dict[tuple[str, str, str], str] | None = None,
) -> str:
    cache_key = _rationale_cache_key(skill_name, target_role, gap_type)
    if rationale_cache is not None and cache_key in rationale_cache:
        return rationale_cache[cache_key]

    prompt = f'''
Write 1-2 concise sentences explaining why improving "{skill_name}" matters for the "{target_role}" role.
Gap type: "{gap_type}".

Rules:
- Plain text only
- No links or resource lists
- Focus on practical job impact
'''.strip()

    try:
        response_text = await gemini_generate(
            purpose="roadmap_rationale",
            prompt=prompt,
        )
        rationale = " ".join((response_text or "").split()).strip()
        if rationale:
            value = rationale[:280]
            if rationale_cache is not None:
                rationale_cache[cache_key] = value
            return value
    except Exception as exc:
        log.warning("Using fallback rationale for %s: %s", skill_name, exc)

    value = f"Improving {skill_name} strengthens delivery quality and role readiness for {target_role}."
    if rationale_cache is not None:
        rationale_cache[cache_key] = value
    return value


async def _gemini_skill_rationale_batch(
    target_role: str,
    skill_items: list[tuple[str, str]],
    rationale_cache: dict[tuple[str, str, str], str],
) -> dict[tuple[str, str, str], str]:
    """Batch rationale generation for one role to reduce duplicate LLM round-trips."""
    if not skill_items:
        return {}

    payload = [
        {"skill_name": skill_name, "gap_type": gap_type}
        for skill_name, gap_type in skill_items
    ]
    prompt = f'''
You are generating concise skill-gap rationales for a learning roadmap.
Target role: "{target_role}"

Input items:
{json.dumps(payload, ensure_ascii=True)}

Return ONLY valid JSON with this exact shape:
{{
  "items": [
    {{"skill_name": "...", "gap_type": "...", "rationale": "1-2 sentences"}}
  ]
}}

Rules:
- Plain text only, no markdown
- No links and no resource suggestions
- Keep each rationale concise (max ~280 chars)
'''.strip()

    try:
        response_text = await gemini_generate(
            purpose="roadmap_rationale_batch",
            prompt=prompt,
        )
        raw = _strip_json_fences(response_text or "")
        data = json.loads(raw)
        items = data.get("items", []) if isinstance(data, dict) else []
        if not isinstance(items, list):
            raise ValueError("Batch rationale payload missing items list")

        output: dict[tuple[str, str, str], str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            skill_name = str(item.get("skill_name", "")).strip()
            gap_type = str(item.get("gap_type", "")).strip()
            rationale = " ".join(str(item.get("rationale", "")).split()).strip()
            if not skill_name or not gap_type or not rationale:
                continue
            rationale = rationale[:280]
            key = _rationale_cache_key(skill_name, target_role, gap_type)
            output[key] = rationale

        rationale_cache.update(output)
        return output
    except Exception as exc:
        log.warning("Batch rationale generation failed for role %s: %s", target_role, exc)
        return {}


async def _catalog_or_fallback_resources_for_node(
    db: AsyncSession,
    node: RoadmapSkillNode,
    target_role: str,
    rationale_cache: dict[tuple[str, str, str], str],
    catalog_payload: dict | None = None,
) -> tuple[list[ResourceSuggestion], str | None]:
    catalog_level = _map_gap_to_catalog_level(node.gap_type, node.skill_band)
    if catalog_payload is None:
        catalog_payload = await get_resources_for_skill(
            db=db,
            skill_name=node.skill_name,
            level=catalog_level,
            limit_per_format=CATALOG_LIMIT_PER_FORMAT,
        )

    video_rows = catalog_payload.get("video", []) if isinstance(catalog_payload, dict) else []
    article_rows = catalog_payload.get("article", []) if isinstance(catalog_payload, dict) else []

    if not video_rows and not article_rows:
        log.warning("No catalog resources found for skill: %s, falling back to LLM", node.skill_name)
        return await _gemini_resources(
            skill_name=node.skill_name,
            target_role=target_role,
            gap_type=node.gap_type,
            hours=max(1, int(round(node.total_hours or 1.0))),
        ), None

    rationale = await _gemini_skill_rationale(
        skill_name=node.skill_name,
        target_role=target_role,
        gap_type=node.gap_type,
        rationale_cache=rationale_cache,
    )

    # Preserve deterministic order: all video/course entries first, then article/doc.
    selected_rows = (list(video_rows) + list(article_rows))[:MAX_CATALOG_RESOURCES_PER_SKILL]
    resources: list[ResourceSuggestion] = []
    for row in selected_rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "")).strip()
        url = str(row.get("url", "")).strip()
        provider = str(row.get("provider", "")).strip() or "Catalog"
        if not title or not url:
            continue

        resource_type = _catalog_format_to_resource_type(row.get("format"))
        estimated_hours = _estimated_hours_from_duration(row.get("duration_minutes"))
        resources.append(
            ResourceSuggestion(
                title=title,
                provider=provider,
                url=url,
                resource_type=resource_type,
                estimated_hours=estimated_hours,
                why=rationale,
            )
        )

    return resources, rationale


async def _generate_resources_for_nodes(
    db: AsyncSession,
    nodes: list[RoadmapSkillNode],
    target_role: str,
) -> None:
    if not nodes:
        return

    batch_size = 5
    rationale_cache: dict[tuple[str, str, str], str] = {}
    for start in range(0, len(nodes), batch_size):
        chunk = nodes[start:start + batch_size]

        catalog_payloads = await asyncio.gather(
            *[
                get_resources_for_skill(
                    db=db,
                    skill_name=node.skill_name,
                    level=_map_gap_to_catalog_level(node.gap_type, node.skill_band),
                    limit_per_format=CATALOG_LIMIT_PER_FORMAT,
                )
                for node in chunk
            ]
        )

        batch_inputs: list[tuple[str, str]] = []
        seen_batch_keys: set[tuple[str, str, str]] = set()
        for node, payload in zip(chunk, catalog_payloads):
            video_rows = payload.get("video", []) if isinstance(payload, dict) else []
            article_rows = payload.get("article", []) if isinstance(payload, dict) else []
            if not video_rows and not article_rows:
                continue
            key = _rationale_cache_key(node.skill_name, target_role, node.gap_type)
            if key in rationale_cache or key in seen_batch_keys:
                continue
            seen_batch_keys.add(key)
            batch_inputs.append((node.skill_name, node.gap_type))

        if batch_inputs:
            await _gemini_skill_rationale_batch(
                target_role=target_role,
                skill_items=batch_inputs,
                rationale_cache=rationale_cache,
            )

        results = await asyncio.gather(
            *[
                _catalog_or_fallback_resources_for_node(
                    db=db,
                    node=node,
                    target_role=target_role,
                    rationale_cache=rationale_cache,
                    catalog_payload=payload,
                )
                for node, payload in zip(chunk, catalog_payloads)
            ]
        )

        for node, (resources, skill_rationale) in zip(chunk, results):
            node.resources = resources
            # Persist only catalog-path skill rationale; fallback resource-level rationale remains on rows.
            node.skill_rationale = skill_rationale

    await _validate_resources_for_nodes(nodes)


async def _load_roadmap_from_db(
    db: AsyncSession,
    plan: LearningPlan,
    role_name: str,
    hours_per_week: int,
    readiness_score: float,
    *,
    daily_hours: float | None = None,
    study_days_per_week: int = 7,
) -> LearningRoadmapResponse:
    items = (
        await db.execute(
            select(LearningPlanItem)
            .where(LearningPlanItem.plan_id == plan.id)
            .order_by(LearningPlanItem.order)
        )
    ).scalars().all()

    item_ids = [item.id for item in items]
    subtopics_rows = []
    resources_rows = []
    sub_sub_rows = []
    if item_ids:
        subtopics_rows = (
            await db.execute(
                select(LearningPlanItemSubtopic)
                .where(LearningPlanItemSubtopic.item_id.in_(item_ids))
                .order_by(LearningPlanItemSubtopic.item_id, LearningPlanItemSubtopic.order_index)
            )
        ).scalars().all()

        resources_rows = (
            await db.execute(
                select(LearningPlanItemResource)
                .where(LearningPlanItemResource.item_id.in_(item_ids))
                .order_by(LearningPlanItemResource.item_id, LearningPlanItemResource.rank)
            )
        ).scalars().all()

        subtopic_ids = [st.id for st in subtopics_rows]
        if subtopic_ids:
            sub_sub_rows = (
                await db.execute(
                    select(LearningPlanItemSubSubtopic)
                    .where(LearningPlanItemSubSubtopic.subtopic_id.in_(subtopic_ids))
                    .order_by(LearningPlanItemSubSubtopic.subtopic_id, LearningPlanItemSubSubtopic.order_index)
                )
            ).scalars().all()

    subtopic_rows_by_item: dict[str, list[LearningPlanItemSubtopic]] = {}
    for row in subtopics_rows:
        subtopic_rows_by_item.setdefault(row.item_id, []).append(row)

    sub_sub_by_subtopic: dict[str, list[LearningPlanItemSubSubtopic]] = {}
    for row in sub_sub_rows:
        sub_sub_by_subtopic.setdefault(row.subtopic_id, []).append(row)

    resources_by_item: dict[str, list[LearningPlanItemResource]] = {}
    for row in resources_rows:
        resources_by_item.setdefault(row.item_id, []).append(row)

    all_skill_nodes: list[WeekSkillNode] = []
    for item in items:
        subtopics: list[Subtopic] = []
        resources: list[ResourceSuggestion] = []

        normalized_subtopics = subtopic_rows_by_item.get(item.id, [])
        if normalized_subtopics:
            for st_row in normalized_subtopics:
                ss_rows = sub_sub_by_subtopic.get(st_row.id, [])
                subtopics.append(
                    Subtopic(
                        title=st_row.title,
                        estimated_hours=float(st_row.estimated_hours or 0.0),
                        sub_subtopics=[
                            SubSubtopic(
                                title=ss_row.title,
                                estimated_hours=float(ss_row.estimated_hours or 0.0),
                            )
                            for ss_row in ss_rows
                        ],
                    )
                )
        else:
            subtopics, resources = _deserialize_learning_content(item.subtopics_json)

        normalized_resources = resources_by_item.get(item.id, [])
        if normalized_resources:
            resources = [
                ResourceSuggestion(
                    title=r.title,
                    provider=r.provider,
                    url=r.url,
                    resource_type=str(r.resource_type or "article").strip().lower() or "article",
                    estimated_hours=float(r.estimated_hours or 0.0),
                    why=r.why,
                )
                for r in normalized_resources
                if r.title and r.provider and r.url and r.why
            ]
        elif not resources:
            _sub, resources = _deserialize_learning_content(item.subtopics_json)
        all_skill_nodes.append(
            WeekSkillNode(
                skill_id=item.skill_id,
                item_id=item.id,
                item_status=str(item.status or "not_started"),
                skill_name=item.title,
                skill_rationale=item.skill_rationale,
                gap_type=item.resource_type or "missing",
                priority_score=float(item.priority_score or 0.0),
                skill_band=item.skill_band or "Technical Skills",
                total_hours=float(item.estimated_hours or 0.0),
                subtopics=subtopics,
                resources=resources,
            )
        )

    weeks = _pack_ordered_skill_nodes_into_weeks(all_skill_nodes, int(hours_per_week or WEEK_HOUR_CAP_DEFAULT))
    weeks = _finalize_weeks_with_daily_plans(
        weeks,
        daily_hours=daily_hours,
        study_days_per_week=study_days_per_week,
        hours_per_week=int(hours_per_week or WEEK_HOUR_CAP_DEFAULT),
    )

    return LearningRoadmapResponse(
        plan_id=plan.id,
        target_role=role_name,
        readiness_score=readiness_score,
        total_weeks=len(weeks),
        estimated_total_weeks=len(weeks),
        total_hours_estimate=round(sum(node.total_hours for node in all_skill_nodes), 2),
        hours_per_week=int(hours_per_week),
        daily_hours=daily_hours,
        study_days_per_week=study_days_per_week,
        weeks=weeks,
        deferred_items=[],
        budget=RoadmapBudgetSummary(
            daily_hours=daily_hours,
            weekly_hours=int(hours_per_week),
            total_budget_hours=None,
            scheduled_hours=round(sum(node.total_hours for node in all_skill_nodes), 2),
            overflow_hours_estimate=0.0,
        ),
    )


def _build_dependency_levels(gaps) -> list[list]:
    nodes = {gap.skill_id: gap for gap in gaps}
    adjacency: dict[str, set[str]] = {key: set() for key in nodes}
    indegree: dict[str, int] = {key: 0 for key in nodes}

    for gap in gaps:
        node_key = gap.skill_id
        prereq_ids = {
            str(prereq).strip()
            for prereq in getattr(gap, "prerequisites", [])
            if str(prereq).strip()
        }
        prereq_ids = {pr for pr in prereq_ids if pr in nodes and pr != node_key}
        for prereq_id in prereq_ids:
            adjacency[prereq_id].add(node_key)
            indegree[node_key] += 1

    remaining = set(nodes)
    levels: list[list] = []

    while remaining:
        frontier = [name for name in remaining if indegree[name] == 0]
        if not frontier:
            cycle_name = max(
                remaining,
                key=lambda name: (
                    nodes[name].priority_score,
                    nodes[name].importance,
                    nodes[name].is_mandatory,
                    name,
                ),
            )
            indegree[cycle_name] = 0
            frontier = [cycle_name]

        frontier.sort(
            key=lambda name: (
                -nodes[name].priority_score,
                -nodes[name].importance,
                not nodes[name].is_mandatory,
                name,
            )
        )

        current_level: list = []
        for name in frontier:
            if name not in remaining:
                continue
            remaining.remove(name)
            current_level.append(nodes[name])

        if not current_level:
            break

        levels.append(current_level)

        for name in frontier:
            for dependent in adjacency[name]:
                indegree[dependent] = max(0, indegree[dependent] - 1)

    return levels


def _pack_week_titles(skill_names: list[str]) -> str:
    title = " + ".join(skill_names)
    return _truncate_title(title, 60)


def _pick_focus_title(unit: WeekSkillNode) -> str:
    subs = unit.subtopics or []
    if subs:
        t = str(subs[0].title or unit.skill_name).strip()
        if t:
            return t
    return unit.skill_name


def _split_week_into_day_plans(
    skills: list[WeekSkillNode],
    *,
    daily_cap: float,
    study_days: int,
) -> list[LearningDayPlan]:
    """Distribute week skill units into Mon–Sun slots, up to `daily_cap` on the first `study_days` days."""
    sd = max(1, min(7, int(study_days)))
    dc = max(0.25, float(daily_cap))
    caps = [dc if d < sd else 0.0 for d in range(7)]
    used = [0.0] * 7
    blocks_by_day: list[list[DaySkillBlock]] = [[] for _ in range(7)]

    def available(d: int) -> float:
        return max(0.0, caps[d] - used[d])

    def add_block(d: int, unit: WeekSkillNode, hours: float) -> None:
        blocks_by_day[d].append(
            DaySkillBlock(
                skill_id=str(unit.skill_id or ""),
                item_id=str(unit.item_id or ""),
                skill_name=unit.skill_name,
                estimated_hours=round(float(hours), 2),
                focus_title=_pick_focus_title(unit),
            )
        )
        used[d] += hours

    for unit in skills:
        h_remain = float(unit.total_hours or 0.0)
        while h_remain > 1e-6:
            placed = False
            for d in range(7):
                sp = available(d)
                if sp > 1e-6:
                    take = min(h_remain, sp)
                    add_block(d, unit, take)
                    h_remain -= take
                    placed = True
                    break
            if placed:
                continue
            for d in range(sd, 7):
                if caps[d] <= 0:
                    caps[d] = dc
            placed_inner = False
            for d in range(7):
                sp = available(d)
                if sp > 1e-6:
                    take = min(h_remain, sp)
                    add_block(d, unit, take)
                    h_remain -= take
                    placed_inner = True
                    break
            if placed_inner:
                continue
            ld = max(0, sd - 1)
            add_block(ld, unit, h_remain)
            h_remain = 0

    days_out: list[LearningDayPlan] = []
    est_by_d = [round(sum(b.estimated_hours for b in blocks_by_day[d]), 2) for d in range(7)]
    for d in range(7):
        est = est_by_d[d]
        cap_display = dc if (d < sd or (est > 1e-6 and caps[d] > 0)) else 0.0
        days_out.append(
            LearningDayPlan(
                day_index=d,
                day_name=_DAY_NAMES[d],
                capacity_hours=round(cap_display, 2),
                estimated_hours=est,
                skills=blocks_by_day[d],
            )
        )
    return days_out


def _finalize_weeks_with_daily_plans(
    weeks: list[LearningWeek],
    *,
    daily_hours: float | None,
    study_days_per_week: int,
    hours_per_week: int,
) -> list[LearningWeek]:
    sd = max(1, min(7, int(study_days_per_week)))
    if daily_hours is not None:
        daily_cap = float(daily_hours)
    else:
        daily_cap = float(hours_per_week or WEEK_HOUR_CAP_DEFAULT) / float(sd)

    out: list[LearningWeek] = []
    for w in weeks:
        days_plan = _split_week_into_day_plans(w.skills, daily_cap=daily_cap, study_days=sd)
        out.append(
            LearningWeek(
                week_number=w.week_number,
                week_title=w.week_title,
                total_hours=w.total_hours,
                skills=w.skills,
                days=days_plan,
            )
        )
    return out


def _subtopic_units_for_skill(node: WeekSkillNode, hours_per_week: int) -> list[WeekSkillNode]:
    """Split a skill into week-packable subtopic units without splitting a subtopic."""
    subtopics = list(node.subtopics or [])
    total_hours = float(node.total_hours or 0.0)

    if not subtopics:
        fallback_total = total_hours if total_hours > 0 else 3.0
        unit_hours = round(fallback_total / 3.0, 2)
        subtopics = [
            Subtopic(
                title=f"{node.skill_name} Segment {idx + 1}",
                estimated_hours=unit_hours,
                sub_subtopics=[
                    SubSubtopic(title="Core concepts", estimated_hours=round(unit_hours / 2.0, 2)),
                    SubSubtopic(title="Applied practice", estimated_hours=round(unit_hours / 2.0, 2)),
                ],
            )
            for idx in range(3)
        ]

    if any(float(st.estimated_hours or 0.0) <= 0 for st in subtopics):
        basis = total_hours if total_hours > 0 else float(len(subtopics))
        per_subtopic = round(max(0.1, basis / max(1, len(subtopics))), 2)
        normalized: list[Subtopic] = []
        for st in subtopics:
            normalized.append(
                Subtopic(
                    title=st.title,
                    estimated_hours=per_subtopic,
                    sub_subtopics=st.sub_subtopics,
                )
            )
        subtopics = normalized

    units: list[WeekSkillNode] = []
    segment_count = max(1, len(subtopics))

    def _resources_for_segment(segment_index: int) -> list[ResourceSuggestion]:
        resources = list(node.resources or [])
        if not resources:
            return []
        if segment_count == 1:
            return resources

        chunk_size = max(1, ceil(len(resources) / segment_count))
        start = segment_index * chunk_size
        end = min(len(resources), start + chunk_size)

        if start < len(resources):
            return resources[start:end]

        # More segments than resources: keep at least one resource visible per segment.
        return [resources[segment_index % len(resources)]]

    for idx, st in enumerate(subtopics):
        st_hours = float(st.estimated_hours or 0.0)
        if st_hours <= 0:
            st_hours = 0.1

        resources = _resources_for_segment(idx)
        units.append(
            WeekSkillNode(
                skill_id=node.skill_id,
                item_id=node.item_id,
                item_status=node.item_status,
                skill_name=node.skill_name,
                skill_rationale=node.skill_rationale,
                gap_type=node.gap_type,
                priority_score=node.priority_score,
                skill_band=node.skill_band,
                total_hours=st_hours,
                subtopics=[st],
                resources=resources,
            )
        )

    return units


def _pack_ordered_skill_nodes_into_weeks(
    ordered_nodes: list[WeekSkillNode],
    hours_per_week: int,
) -> list[LearningWeek]:
    weeks: list[LearningWeek] = []
    week_number = 1
    budget = float(hours_per_week or WEEK_HOUR_CAP_DEFAULT)

    current_week_skills: list[WeekSkillNode] = []
    current_week_hours = 0.0

    def flush_current() -> None:
        nonlocal week_number, current_week_skills, current_week_hours
        if not current_week_skills:
            return
        weeks.append(
            LearningWeek(
                week_number=week_number,
                week_title=_pack_week_titles([node.skill_name for node in current_week_skills]),
                total_hours=round(current_week_hours, 2),
                skills=current_week_skills,
            )
        )
        week_number += 1
        current_week_skills = []
        current_week_hours = 0.0

    for node in ordered_nodes:
        for unit in _subtopic_units_for_skill(node, int(budget)):
            unit_hours = float(unit.total_hours or 0.0)

            if unit_hours > budget:
                flush_current()
                weeks.append(
                    LearningWeek(
                        week_number=week_number,
                        week_title=_pack_week_titles([unit.skill_name]),
                        total_hours=round(unit_hours, 2),
                        skills=[unit],
                    )
                )
                week_number += 1
                continue

            if current_week_skills and current_week_hours + unit_hours > budget:
                flush_current()

            current_week_skills.append(unit)
            current_week_hours += unit_hours

    flush_current()
    return weeks


def _pack_levels_into_weeks(levels: list[list], hours_per_week: int) -> list[WeekSkillNode]:
    budget = float(hours_per_week or WEEK_HOUR_CAP_DEFAULT)
    planned_skill_ids = {
        str(node.skill_id).strip()
        for level in levels
        for node in level
        if str(node.skill_id).strip()
    }
    scheduled_skill_ids: set[str] = set()
    ordered_nodes: list[WeekSkillNode] = []

    for level in levels:
        sorted_level = sorted(
            level,
            key=lambda gap: (
                _domain_schedule_rank(
                    getattr(gap, "skill_band", None),
                    getattr(gap, "skill_name", None),
                ),
                _band_rank(getattr(gap, "skill_band", None)),
                -gap.priority_score,
                -gap.importance,
                not gap.is_mandatory,
                gap.skill_name.lower(),
            ),
        )

        pending = list(sorted_level)
        while pending:
            progressed = False
            next_pending = []

            for gap in pending:
                prereq_ids = {
                    str(prereq).strip()
                    for prereq in getattr(gap, "prerequisites", [])
                    if str(prereq).strip()
                }
                required_internal = {pr for pr in prereq_ids if pr in planned_skill_ids}
                if any(pr not in scheduled_skill_ids for pr in required_internal):
                    next_pending.append(gap)
                    continue

                skill_hours = float(gap.total_hours or 0.0)
                node = WeekSkillNode(
                    skill_id=gap.skill_id,
                    skill_name=gap.skill_name,
                    skill_rationale=getattr(gap, "skill_rationale", None),
                    item_status="not_started",
                    gap_type=gap.gap_type,
                    priority_score=gap.priority_score,
                    skill_band=gap.skill_band,
                    total_hours=skill_hours,
                    subtopics=gap.subtopics,
                    resources=gap.resources,
                )

                ordered_nodes.append(node)

                scheduled_skill_ids.add(gap.skill_id.strip())
                progressed = True

            if not progressed:
                # Defensive fallback for cyclic or malformed prerequisite graphs.
                for gap in next_pending:
                    skill_hours = float(gap.total_hours or 0.0)
                    node = WeekSkillNode(
                        skill_id=gap.skill_id,
                        skill_name=gap.skill_name,
                        skill_rationale=getattr(gap, "skill_rationale", None),
                        item_status="not_started",
                        gap_type=gap.gap_type,
                        priority_score=gap.priority_score,
                        skill_band=gap.skill_band,
                        total_hours=skill_hours,
                        subtopics=gap.subtopics,
                        resources=gap.resources,
                    )
                    ordered_nodes.append(node)
                    scheduled_skill_ids.add(gap.skill_id.strip())
                break

            pending = next_pending

    return ordered_nodes


def _select_nodes_with_budget(
    ordered_nodes: list[WeekSkillNode],
    *,
    hours_per_week: int,
    deadline_weeks: int | None,
    daily_hours: float | None,
) -> tuple[list[WeekSkillNode], list[WeekSkillNode], RoadmapBudgetSummary]:
    if deadline_weeks is None:
        scheduled_hours = round(sum(float(n.total_hours or 0.0) for n in ordered_nodes), 2)
        return ordered_nodes, [], RoadmapBudgetSummary(
            daily_hours=daily_hours,
            weeks=None,
            weekly_hours=int(hours_per_week),
            total_budget_hours=None,
            scheduled_hours=scheduled_hours,
            overflow_hours_estimate=0.0,
        )

    total_budget_hours = float(hours_per_week) * float(deadline_weeks)
    sum_hours = round(sum(float(n.total_hours or 0.0) for n in ordered_nodes), 4)

    if sum_hours <= total_budget_hours + 1e-6:
        summary = RoadmapBudgetSummary(
            daily_hours=daily_hours,
            weeks=int(deadline_weeks),
            weekly_hours=int(hours_per_week),
            total_budget_hours=round(total_budget_hours, 2),
            scheduled_hours=sum_hours,
            overflow_hours_estimate=0.0,
        )
        return ordered_nodes, [], summary

    # Fit ALL gaps into the horizon by scaling hours down proportionally (breadth-first roadmap).
    factor = total_budget_hours / sum_hours if sum_hours > 0 else 1.0
    scaled = [_scale_week_skill_node(n, factor) for n in ordered_nodes]
    scheduled = round(sum(float(n.total_hours or 0.0) for n in scaled), 2)
    trimmed = round(max(0.0, sum_hours - total_budget_hours), 2)

    summary = RoadmapBudgetSummary(
        daily_hours=daily_hours,
        weeks=int(deadline_weeks),
        weekly_hours=int(hours_per_week),
        total_budget_hours=round(total_budget_hours, 2),
        scheduled_hours=scheduled,
        overflow_hours_estimate=trimmed,
    )
    return scaled, [], summary


def _default_resources(skill_name: str, hours: int) -> list[dict]:
    legacy_resources: list[dict] = []
    for item in _fallback_resources(skill_name, hours):
        legacy_resources.append(
            {
                "type": str(item.get("resource_type", "article")).strip().lower() or "article",
                "title": str(item.get("title", "")).strip() or f"{skill_name} resource",
                "provider": str(item.get("provider", "")).strip() or "Internal",
                "search_query": str(item.get("title", "")).strip() or skill_name,
                "url": str(item.get("url", "")).strip() or None,
                "estimated_hours": int(round(float(item.get("estimated_hours", 1.0) or 1.0))),
            }
        )
    return legacy_resources


def _fallback_resource_suggestions(skill_name: str, hours: int) -> list[ResourceSuggestion]:
    return [
        ResourceSuggestion(
            title=str(item.get("title", "")).strip() or f"{skill_name} resource",
            provider=str(item.get("provider", "")).strip() or "Internal",
            url=str(item.get("url", "")).strip() or "https://www.google.com",
            resource_type=str(item.get("resource_type", "article")).strip().lower() or "article",
            estimated_hours=float(item.get("estimated_hours", 1.0) or 1.0),
            why=str(item.get("why", "")).strip() or f"Supports {skill_name} improvement.",
        )
        for item in _fallback_resources(skill_name, hours)
    ]


async def _validate_resources_for_nodes(nodes: list[RoadmapSkillNode]) -> None:
    if not nodes:
        return

    unique_urls = {
        str(resource.url or "").strip()
        for node in nodes
        for resource in (node.resources or [])
        if str(resource.url or "").strip()
    }

    url_reachability: dict[str, bool] = {}
    if unique_urls:
        semaphore = asyncio.Semaphore(RESOURCE_URL_VALIDATION_CONCURRENCY)

        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:

            async def _check(url: str) -> tuple[str, bool]:
                async with semaphore:
                    return url, await is_url_reachable(client, url)

            results = await asyncio.gather(*[_check(url) for url in unique_urls])
            url_reachability = {url: ok for url, ok in results}

    for node in nodes:
        filtered_resources = [
            resource
            for resource in (node.resources or [])
            if url_reachability.get(str(resource.url or "").strip(), False)
        ]
        if filtered_resources:
            node.resources = filtered_resources
            continue

        node.resources = _fallback_resource_suggestions(
            skill_name=node.skill_name,
            hours=max(1, int(round(node.total_hours or 1.0))),
        )


def build_learning_plan(
    gap_result: GapResult,
    max_items: int = 48,
    daily_hours: Optional[float] = None,
    deadline_weeks: Optional[int] = None,
    study_days_per_week: int = 7,
) -> tuple[int, list[PlanItem]]:
    levels = _build_dependency_levels(gap_result.gaps)
    ordered = [gap for level in levels for gap in level]

    candidates = ordered[:max_items]

    hour_budget: Optional[float] = None
    if daily_hours is not None and deadline_weeks is not None:
        hour_budget = float(daily_hours) * float(study_days_per_week) * float(deadline_weeks)

    selected = []
    running_hours = 0
    for gap in candidates:
        est = int(gap.time_to_learn_hours or 40)
        if hour_budget is not None and selected and running_hours + est > hour_budget:
            continue
        selected.append(gap)
        running_hours += est

    if not selected and candidates:
        selected = [candidates[0]]

    items: list[PlanItem] = []
    total_hours = 0

    for idx, g in enumerate(selected, start=1):
        est = int(g.time_to_learn_hours or 40)
        total_hours += est
        items.append(
            PlanItem(
                order=idx,
                skill_id=g.skill_id,
                skill_name=g.skill_name,
                gap_type=g.gap_type,
                priority_score=g.priority_score,
                estimated_hours=est,
                prerequisites=g.prerequisites,
                resources=_default_resources(g.skill_name, est),
            )
        )

    return total_hours, items


async def delete_learning_plans_by_ids(db: AsyncSession, plan_ids: list[str]) -> None:
    """Remove learning plans and normalized descendants (same order as roadmap regeneration)."""
    if not plan_ids:
        return

    wa_ids = (
        await db.execute(select(WeekAssessment.id).where(WeekAssessment.plan_id.in_(plan_ids)))
    ).scalars().all()
    if wa_ids:
        await db.execute(
            delete(WeekAssessmentAttempt).where(WeekAssessmentAttempt.week_assessment_id.in_(wa_ids))
        )

    await db.execute(delete(WeekAssessment).where(WeekAssessment.plan_id.in_(plan_ids)))

    old_item_ids = (
        await db.execute(select(LearningPlanItem.id).where(LearningPlanItem.plan_id.in_(plan_ids)))
    ).scalars().all()
    if old_item_ids:
        old_subtopic_ids = (
            await db.execute(
                select(LearningPlanItemSubtopic.id).where(LearningPlanItemSubtopic.item_id.in_(old_item_ids))
            )
        ).scalars().all()
        if old_subtopic_ids:
            await db.execute(
                delete(LearningPlanItemSubSubtopic).where(
                    LearningPlanItemSubSubtopic.subtopic_id.in_(old_subtopic_ids)
                )
            )
        await db.execute(delete(LearningPlanItemSubtopic).where(LearningPlanItemSubtopic.item_id.in_(old_item_ids)))
        await db.execute(delete(LearningPlanItemResource).where(LearningPlanItemResource.item_id.in_(old_item_ids)))

    await db.execute(delete(LearningPlanItem).where(LearningPlanItem.plan_id.in_(plan_ids)))
    await db.execute(delete(LearningPlan).where(LearningPlan.id.in_(plan_ids)))
    await db.flush()


async def generate_roadmap(
    user_id: str,
    db: AsyncSession,
    hours_per_week: int = 10,
    daily_hours: float | None = None,
    deadline_weeks: int | None = None,
    force_regenerate: bool = False,
    study_days_per_week: int = 7,
) -> LearningRoadmapResponse:
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.target_role_id:
        raise HTTPException(status_code=400, detail="Target role not set. Use POST /api/v1/users/me/target-role")

    role = await db.scalar(select(Role).where(Role.id == user.target_role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Target role not found")

    # Use the latest *completed* resume. Ordering only by created_at can pick a newer row that is
    # still uploading/parsing while an older row is already complete — which incorrectly returns 400.
    completed_status_lower = ("complete", "completed", "processed")
    resume = await db.scalar(
        select(Resume)
        .where(
            Resume.user_id == user_id,
            func.lower(func.coalesce(Resume.status, "")).in_(completed_status_lower),
        )
        .order_by(Resume.created_at.desc())
    )
    if not resume:
        raise HTTPException(status_code=400, detail="Resume not yet processed. Process a resume before generating a roadmap.")

    gap_result = await detect_and_store_gaps(db, user, role)
    user_skill_profile = await _load_user_intermediate_or_advanced_skills(db=db, user_id=user.id)

    existing_plan = None
    if deadline_weeks is not None:
        # Deadline-constrained roadmap is request-specific; regenerate to enforce current budget.
        force_regenerate = True

    if not force_regenerate:
        existing_plan = await db.scalar(
            select(LearningPlan)
            .where(
                LearningPlan.user_id == user.id,
                LearningPlan.role_id == role.id,
                LearningPlan.status.in_(["active", "in_progress", "completed"]),
            )
            .order_by(LearningPlan.updated_at.desc())
        )
        if existing_plan:
            first_item = await db.scalar(
                select(LearningPlanItem)
                .where(LearningPlanItem.plan_id == existing_plan.id)
                .limit(1)
            )
            normalized_subtopic_exists = False
            if first_item:
                normalized_subtopic_exists = bool(
                    await db.scalar(
                        select(LearningPlanItemSubtopic.id)
                        .where(LearningPlanItemSubtopic.item_id == first_item.id)
                        .limit(1)
                    )
                )
            has_subtopics = bool(first_item and (normalized_subtopic_exists or first_item.subtopics_json is not None))

            if not has_subtopics:
                force_regenerate = True
            else:
                return await _load_roadmap_from_db(
                    db,
                    existing_plan,
                    role.name,
                    hours_per_week,
                    gap_result.readiness_score,
                    daily_hours=daily_hours,
                    study_days_per_week=study_days_per_week,
                )

    roadmap_nodes: list[RoadmapSkillNode] = []

    prereq_rows = (
        await db.execute(
            select(SkillPrerequisite).where(SkillPrerequisite.skill_id.in_([g.skill_id for g in gap_result.gaps]))
        )
    ).scalars().all()
    prereq_by_skill_id: dict[str, list[str]] = {}
    for row in prereq_rows:
        prereq_by_skill_id.setdefault(row.skill_id, []).append(row.prerequisite_skill_id)

    async def _breakdown_for_gap(gap) -> list[Subtopic]:
        try:
            return await _generate_skill_breakdown(
                skill_name=gap.skill_name,
                target_role=role.name,
                gap_type=gap.gap_type,
                time_to_learn_hours=float(gap.time_to_learn_hours or 0.0),
                user_skill_profile=user_skill_profile,
            )
        except Exception as exc:
            log.warning("Skill breakdown failed for %s: %s", gap.skill_name, exc)
            return _fallback_structure(gap.skill_name, float(gap.time_to_learn_hours or 20.0))

    breakdown_results = await asyncio.gather(*[_breakdown_for_gap(g) for g in gap_result.gaps])

    for gap, subtopics in zip(gap_result.gaps, breakdown_results):
        resolved_subtopics = subtopics if isinstance(subtopics, list) and subtopics else _fallback_structure(
            gap.skill_name, float(gap.time_to_learn_hours or 20.0)
        )
        roadmap_nodes.append(
            RoadmapSkillNode(
                skill_id=gap.skill_id,
                skill_name=gap.skill_name,
                gap_type=gap.gap_type,
                priority_score=gap.priority_score,
                skill_band=getattr(gap, "skill_band", "Technical Skills"),
                total_hours=float(gap.time_to_learn_hours or 0.0),
                subtopics=resolved_subtopics,
                resources=[],
                prerequisites=prereq_by_skill_id.get(gap.skill_id, getattr(gap, "prerequisites", [])),
                level=0,
                importance=gap.importance,
                is_mandatory=gap.is_mandatory,
            )
        )

    await _generate_resources_for_nodes(db, roadmap_nodes, role.name)

    levels = _build_dependency_levels(roadmap_nodes)

    level_index = 0
    for level in levels:
        for node in level:
            node.level = level_index
        level_index += 1

    ordered_nodes = _pack_levels_into_weeks(levels, hours_per_week)
    selected_nodes, deferred_nodes, budget_summary = _select_nodes_with_budget(
        ordered_nodes,
        hours_per_week=hours_per_week,
        deadline_weeks=deadline_weeks,
        daily_hours=daily_hours,
    )
    weeks = _pack_ordered_skill_nodes_into_weeks(selected_nodes, hours_per_week)
    weeks = _finalize_weeks_with_daily_plans(
        weeks,
        daily_hours=daily_hours,
        study_days_per_week=study_days_per_week,
        hours_per_week=hours_per_week,
    )
    total_hours_estimate = round(sum(node.total_hours for node in selected_nodes), 2)

    existing_plan_ids = (
        await db.execute(
            select(LearningPlan.id).where(
                LearningPlan.user_id == user.id,
                LearningPlan.role_id == role.id,
                LearningPlan.status.in_(["active", "in_progress", "completed"]),
            )
        )
    ).scalars().all()

    if existing_plan_ids:
        await delete_learning_plans_by_ids(db, list(existing_plan_ids))

    plan = LearningPlan(
        user_id=user.id,
        role_id=role.id,
        total_hours_estimate=int(round(total_hours_estimate)),
        status="active",
    )
    db.add(plan)
    await db.flush()

    skill_rationale_by_id = {
        str(node.skill_id).strip(): node.skill_rationale
        for node in selected_nodes
        if str(node.skill_id).strip()
    }
    roadmap_node_by_skill_id = {
        str(node.skill_id).strip(): node
        for node in selected_nodes
        if str(node.skill_id).strip()
    }

    assessment_questions_by_node_index: list[str | None] = []
    question_tasks = [
        generate_assessment_questions(
            skill_name=node.skill_name,
            level=_assessment_level_from_gap_type(node.gap_type),
            subtopics=[st.title for st in (node.subtopics or []) if str(st.title or "").strip()],
        )
        for node in selected_nodes
    ]
    if question_tasks:
        generated_questions = await asyncio.gather(*question_tasks, return_exceptions=True)
        for questions in generated_questions:
            if isinstance(questions, list) and len(questions) == QUESTIONS_PER_ITEM:
                assessment_questions_by_node_index.append(json.dumps(questions))
            else:
                assessment_questions_by_node_index.append(None)

    flat_items = []
    order = 1
    for idx, node in enumerate(selected_nodes):
        resolved_skill_id = str(node.skill_id or "").strip()
        if not resolved_skill_id:
            raise ValueError(f"Missing skill_id for roadmap skill '{node.skill_name}'")
        flat_items.append(
            LearningPlanItem(
                plan_id=plan.id,
                skill_id=resolved_skill_id,
                order=order,
                priority_score=float(node.priority_score or 0.0),
                resource_type=node.gap_type,
                title=node.skill_name,
                url=None,
                provider=None,
                skill_rationale=skill_rationale_by_id.get(resolved_skill_id),
                assessment_questions=(
                    assessment_questions_by_node_index[idx]
                    if idx < len(assessment_questions_by_node_index)
                    else None
                ),
                assessment_score=None,
                assessment_attempts=0,
                skill_band=node.skill_band,
                subtopics_json=_serialize_learning_content(node.subtopics, node.resources),
                estimated_hours=int(round(node.total_hours)),
                status="not_started",
            )
        )
        order += 1

    db.add_all(flat_items)
    await db.flush()

    item_id_by_skill_id = {str(item.skill_id).strip(): item.id for item in flat_items if str(item.skill_id).strip()}
    for week in weeks:
        for skill in week.skills:
            sid = str(skill.skill_id or "").strip()
            skill.item_id = item_id_by_skill_id.get(sid, "")
            skill.item_status = "not_started"
            if sid in roadmap_node_by_skill_id and not skill.skill_rationale:
                skill.skill_rationale = roadmap_node_by_skill_id[sid].skill_rationale

    normalized_subtopics_rows: list[LearningPlanItemSubtopic] = []
    normalized_sub_sub_rows: list[LearningPlanItemSubSubtopic] = []
    normalized_resource_rows: list[LearningPlanItemResource] = []
    for item in flat_items:
        item_id = item.id
        if not item_id:
            continue
        persisted_node = roadmap_node_by_skill_id.get(str(item.skill_id or "").strip())
        if persisted_node is None:
            continue
        for st_idx, st in enumerate(persisted_node.subtopics or []):
            normalized_subtopics_rows.append(
                LearningPlanItemSubtopic(
                    item_id=item_id,
                    order_index=st_idx,
                    title=st.title,
                    estimated_hours=float(st.estimated_hours or 0.0),
                    focus=False,
                )
            )

        for r_idx, r in enumerate(persisted_node.resources or []):
            normalized_resource_rows.append(
                LearningPlanItemResource(
                    item_id=item_id,
                    rank=r_idx,
                    title=r.title,
                    provider=r.provider,
                    url=r.url,
                    resource_type=str(r.resource_type).strip().lower() or "article",
                    estimated_hours=float(r.estimated_hours or 0.0),
                    why=r.why,
                )
            )

    db.add_all(normalized_subtopics_rows)
    db.add_all(normalized_resource_rows)
    await db.flush()

    subtopic_id_by_item_and_index: dict[tuple[str, int], str] = {
        (row.item_id, row.order_index): row.id for row in normalized_subtopics_rows
    }

    for item in flat_items:
        item_id = item.id
        if not item_id:
            continue
        persisted_node = roadmap_node_by_skill_id.get(str(item.skill_id or "").strip())
        if persisted_node is None:
            continue
        for st_idx, st in enumerate(persisted_node.subtopics or []):
            subtopic_id = subtopic_id_by_item_and_index.get((item_id, st_idx))
            if not subtopic_id:
                continue
            for ss_idx, ss in enumerate(st.sub_subtopics or []):
                normalized_sub_sub_rows.append(
                    LearningPlanItemSubSubtopic(
                        subtopic_id=subtopic_id,
                        order_index=ss_idx,
                        title=ss.title,
                        estimated_hours=float(ss.estimated_hours or 0.0),
                    )
                )

    db.add_all(normalized_sub_sub_rows)
    await db.flush()

    await db.commit()

    return LearningRoadmapResponse(
        plan_id=plan.id,
        target_role=role.name,
        readiness_score=gap_result.readiness_score,
        total_weeks=len(weeks),
        estimated_total_weeks=len(weeks),
        total_hours_estimate=total_hours_estimate,
        hours_per_week=int(hours_per_week),
        daily_hours=daily_hours,
        study_days_per_week=study_days_per_week,
        weeks=weeks,
        deferred_items=[
            DeferredRoadmapItem(
                skill_id=str(node.skill_id or ""),
                skill_name=node.skill_name,
                gap_type=node.gap_type,
                priority_score=float(node.priority_score or 0.0),
                estimated_hours=float(node.total_hours or 0.0),
                is_mandatory=bool(getattr(node, "is_mandatory", False)),
            )
            for node in deferred_nodes
        ],
        budget=budget_summary,
    )


async def compute_pacing_signal(plan_id: str, db: AsyncSession) -> dict:
    plan = await db.scalar(select(LearningPlan).where(LearningPlan.id == plan_id))
    if not plan:
        return {
            "pacing_signal": "not_started",
            "expected_skills_done_by_now": 0,
            "actual_skills_done": 0,
        }

    items = (
        await db.execute(
            select(LearningPlanItem)
            .where(LearningPlanItem.plan_id == plan_id)
            .order_by(LearningPlanItem.order)
        )
    ).scalars().all()

    total_skills = len(items)
    if total_skills == 0:
        return {
            "pacing_signal": "not_started",
            "expected_skills_done_by_now": 0,
            "actual_skills_done": 0,
        }

    completed_items = [item for item in items if str(item.status or "").lower() == "completed"]
    actual_done = len(completed_items)

    total_hours = float(plan.total_hours_estimate or 0.0)
    if total_hours <= 0:
        total_hours = float(sum(item.estimated_hours or 0 for item in items))

    deadline_weeks = max(1, int(ceil(total_hours / 10.0)) if total_hours > 0 else int(ceil(total_skills / 2.0)))
    expected_rate = total_skills / max(1.0, float(deadline_weeks * 7))

    now = datetime.now(timezone.utc)
    created_at = plan.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    elapsed_days = max(1, int((now - created_at).total_seconds() // 86400) + 1)

    expected_done_by_now = int(min(total_skills, max(0, round(expected_rate * elapsed_days))))

    if actual_done <= 0:
        pacing = "not_started"
    else:
        actual_rate = actual_done / float(elapsed_days)
        if actual_rate >= expected_rate * 1.15:
            pacing = "ahead"
        elif actual_rate < expected_rate * 0.85:
            pacing = "behind"
        else:
            pacing = "on_track"

    return {
        "pacing_signal": pacing,
        "expected_skills_done_by_now": expected_done_by_now,
        "actual_skills_done": actual_done,
    }
