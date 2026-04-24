"""Gap detection service for comparing user skills against role requirements."""
import json
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Role, RoleSkillRequirement, Skill, SkillGap, SkillPrerequisite, User, UserSkillScore


PROFICIENCY_ORDER = ["beginner", "intermediate", "advanced"]
PROFICIENCY_TO_SCORE = {
    "beginner": 0.25,
    "intermediate": 0.5,
    "advanced": 0.75,
}

# Priority scoring weights (sum to 1.0 including mandatory bonus max).
GAP_WEIGHT = 0.50
IMPORTANCE_WEIGHT = 0.30
PREREQ_WEIGHT = 0.15
MANDATORY_BONUS = 0.05
# Keep score magnitudes compatible with existing downstream rerank/display behavior.
# This scales the bounded weighted score without changing relative ranking.
PRIORITY_SCORE_SCALE = 0.05


@dataclass
class GapItem:
    skill_id: str
    skill_name: str
    gap_type: str
    priority_score: float
    current_proficiency: str | None
    required_proficiency: str
    time_to_learn_hours: int
    importance: float
    is_mandatory: bool
    prerequisites: list[str]
    prerequisite_coverage: float
    skill_band: str = "Technical Skills"


@dataclass
class GapResult:
    user_id: str
    role_id: str
    role_name: str
    readiness_score: float
    missing_skills: int
    weak_skills: int
    total_gaps: int
    total_learning_hours: int
    gaps: list[GapItem]


def _safe_json_list(text_value: str | None) -> list[str]:
    if not text_value:
        return []
    try:
        value = json.loads(text_value)
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
    except Exception:
        return []
    return []


def _proficiency_to_score(proficiency: str | None) -> float:
    if not proficiency:
        return 0.0
    return PROFICIENCY_TO_SCORE.get(proficiency.lower(), 0.0)


def _required_threshold(required_proficiency: str) -> float:
    return _proficiency_to_score(required_proficiency)


def _score_to_proficiency(score: float) -> str:
    if score >= 0.75:
        return "advanced"
    if score >= 0.5:
        return "intermediate"
    return "beginner"


def _calc_prereq_coverage(prereq_skill_ids: list[str], user_skill_scores_by_id: dict[str, float]) -> float:
    if not prereq_skill_ids:
        return 1.0
    hit = 0
    for skill_id in prereq_skill_ids:
        if user_skill_scores_by_id.get(skill_id, 0.0) >= 0.25:
            hit += 1
    return hit / len(prereq_skill_ids)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _proficiency_distance(required_score: float, current_score: float) -> float:
    denom = max(float(required_score or 0.0), 1e-6)
    distance = (float(required_score or 0.0) - float(current_score or 0.0)) / denom
    return _clamp01(distance)


def _importance_normalized(importance: float, max_importance: float) -> float:
    denom = max(float(max_importance or 0.0), 1e-6)
    return _clamp01(float(importance or 0.0) / denom)


def _prerequisite_depth_scores(gap_prereqs_by_skill_id: dict[str, list[str]]) -> dict[str, float]:
    """Compute normalized dependent-count centrality for skills in current gaps."""
    gap_skill_ids = {str(skill_id).strip() for skill_id in gap_prereqs_by_skill_id if str(skill_id).strip()}
    dependent_counts: dict[str, int] = {skill_id: 0 for skill_id in gap_skill_ids}

    for gap_skill_id, prereq_ids in gap_prereqs_by_skill_id.items():
        _ = gap_skill_id
        seen_for_gap: set[str] = set()
        for prereq_id in prereq_ids or []:
            pid = str(prereq_id).strip()
            if not pid or pid not in gap_skill_ids or pid in seen_for_gap:
                continue
            dependent_counts[pid] = dependent_counts.get(pid, 0) + 1
            seen_for_gap.add(pid)

    max_dependents = max(dependent_counts.values(), default=0)
    if max_dependents <= 0:
        return {skill_id: 0.0 for skill_id in gap_skill_ids}

    return {
        skill_id: round(dependent_counts.get(skill_id, 0) / max_dependents, 6)
        for skill_id in gap_skill_ids
    }


def _priority_score(
    proficiency_distance: float,
    importance_normalized: float,
    prerequisite_depth_score: float,
    is_mandatory: bool,
) -> float:
    raw = (
        GAP_WEIGHT * _clamp01(proficiency_distance)
        + IMPORTANCE_WEIGHT * _clamp01(importance_normalized)
        + PREREQ_WEIGHT * _clamp01(prerequisite_depth_score)
        + MANDATORY_BONUS * (1.0 if is_mandatory else 0.0)
    )
    # Keep score bounded and legacy-scale so related flows using priority remain stable.
    return round(_clamp01(raw) * PRIORITY_SCORE_SCALE, 6)


async def detect_and_store_gaps(db: AsyncSession, user: User, role: Role) -> GapResult:
    req_stmt = (
        select(RoleSkillRequirement, Skill)
        .join(Skill, Skill.id == RoleSkillRequirement.skill_id)
        .where(RoleSkillRequirement.role_id == role.id)
    )
    req_rows = (await db.execute(req_stmt)).all()

    score_stmt = (
        select(UserSkillScore, Skill)
        .join(Skill, Skill.id == UserSkillScore.skill_id)
        .where(UserSkillScore.user_id == user.id)
    )
    score_rows = (await db.execute(score_stmt)).all()

    user_scores_by_skill_id: dict[str, tuple[str, float]] = {}
    user_scores_numeric_by_skill_id: dict[str, float] = {}
    for score, skill in score_rows:
        numeric = score.proficiency_score if score.proficiency_score is not None else _proficiency_to_score(score.proficiency)
        label = score.proficiency or _score_to_proficiency(numeric)
        user_scores_by_skill_id[skill.id] = (label, numeric)
        user_scores_numeric_by_skill_id[skill.id] = numeric

    # Normalized prerequisites (skill_id -> [prerequisite_skill_id...]) for skills in this role.
    role_skill_ids = [skill.id for _, skill in req_rows]
    prereq_stmt = select(SkillPrerequisite).where(SkillPrerequisite.skill_id.in_(role_skill_ids))
    prereq_rows = (await db.execute(prereq_stmt)).scalars().all()
    prereq_by_skill_id: dict[str, list[str]] = {}
    for row in prereq_rows:
        prereq_by_skill_id.setdefault(row.skill_id, []).append(row.prerequisite_skill_id)

    max_role_importance = max((float(req.importance or 0.0) for req, _skill in req_rows), default=0.0)
    total_importance = 0.0
    matched_importance = 0.0

    pending_gap_rows: list[dict] = []
    for req, skill in req_rows:
        importance = float(req.importance or 0.0)
        total_importance += importance

        required_prof = req.min_proficiency or "intermediate"
        required_score = _required_threshold(required_prof)

        user_entry = user_scores_by_skill_id.get(skill.id)
        if user_entry is None:
            current_label = None
            current_score = 0.0
            gap_type = "missing"
        else:
            current_label, current_score = user_entry
            gap_type = "weak" if current_score < required_score else ""

        met_ratio = min(1.0, current_score / required_score) if required_score > 0 else 1.0
        matched_importance += importance * met_ratio

        if gap_type:
            prereq_ids = prereq_by_skill_id.get(skill.id)
            if prereq_ids is None:
                # Backward-compatible fallback until all prereqs are normalized.
                prereq_names = _safe_json_list(getattr(skill, "prerequisites", None))
                prereq_ids = []
                if prereq_names:
                    resolved = (
                        await db.execute(select(Skill.id, Skill.name).where(Skill.name.in_(prereq_names)))
                    ).all()
                    name_to_id = {name.lower(): sid for sid, name in resolved}
                    prereq_ids = [name_to_id.get(p.lower(), "") for p in prereq_names]
                    prereq_ids = [pid for pid in prereq_ids if pid]

            prereq_coverage = _calc_prereq_coverage(prereq_ids, user_scores_numeric_by_skill_id)
            ttl_hours = int(getattr(skill, "time_to_learn_hours", None) or 80)

            pending_gap_rows.append(
                {
                    "skill_id": skill.id,
                    "skill_name": skill.name,
                    "gap_type": gap_type,
                    "current_label": current_label,
                    "current_score": float(current_score or 0.0),
                    "required_prof": required_prof,
                    "required_score": float(required_score or 0.0),
                    "ttl_hours": ttl_hours,
                    "importance": importance,
                    "is_mandatory": bool(req.is_mandatory),
                    "skill_band": str(getattr(skill, "skill_band", None) or "Technical Skills"),
                    "prereq_ids": prereq_ids,
                    "prereq_coverage": round(prereq_coverage, 3),
                }
            )

    depth_scores = _prerequisite_depth_scores(
        {
            str(row["skill_id"]): list(row.get("prereq_ids", []))
            for row in pending_gap_rows
        }
    )

    gaps: list[GapItem] = []
    for row in pending_gap_rows:
        skill_id = str(row["skill_id"])
        gaps.append(
            GapItem(
                skill_id=skill_id,
                skill_name=row["skill_name"],
                gap_type=row["gap_type"],
                priority_score=_priority_score(
                    proficiency_distance=_proficiency_distance(
                        required_score=float(row["required_score"]),
                        current_score=float(row["current_score"]),
                    ),
                    importance_normalized=_importance_normalized(
                        importance=float(row["importance"]),
                        max_importance=max_role_importance,
                    ),
                    prerequisite_depth_score=depth_scores.get(skill_id, 0.0),
                    is_mandatory=bool(row["is_mandatory"]),
                ),
                current_proficiency=row["current_label"],
                required_proficiency=row["required_prof"],
                time_to_learn_hours=int(row["ttl_hours"]),
                importance=float(row["importance"]),
                is_mandatory=bool(row["is_mandatory"]),
                skill_band=row["skill_band"],
                prerequisites=list(row.get("prereq_ids", [])),
                prerequisite_coverage=float(row["prereq_coverage"]),
            )
        )

    readiness = 0.0 if total_importance == 0 else round(matched_importance / total_importance, 4)
    gaps.sort(key=lambda x: (x.priority_score, x.importance, x.is_mandatory), reverse=True)

    # Duplicate RoleSkillRequirement rows for the same skill produce duplicate GapItems and
    # violate SkillGap's unique (user_id, skill_id, role_id). Keep the highest-priority gap per skill.
    _seen_skill_ids: set[str] = set()
    _deduped: list[GapItem] = []
    for g in gaps:
        sid = str(g.skill_id).strip()
        if sid in _seen_skill_ids:
            continue
        _seen_skill_ids.add(sid)
        _deduped.append(g)
    gaps = _deduped

    # Persist gaps idempotently.
    #
    # We must tolerate concurrent requests (e.g., dashboard + learning roadmap loading together).
    # Using delete+insert can race:
    # - Req A deletes
    # - Req B deletes, inserts
    # - Req A inserts -> unique violation
    #
    # So we UPSERT on (user_id, skill_id, role_id) and only delete gaps that are no longer present.
    current_skill_ids = [str(g.skill_id).strip() for g in gaps if str(g.skill_id).strip()]

    if current_skill_ids:
        await db.execute(
            delete(SkillGap).where(
                SkillGap.user_id == user.id,
                SkillGap.role_id == role.id,
                ~SkillGap.skill_id.in_(current_skill_ids),
            )
        )
    else:
        await db.execute(delete(SkillGap).where(SkillGap.user_id == user.id, SkillGap.role_id == role.id))

    rows = [
        {
            "user_id": user.id,
            "skill_id": str(g.skill_id).strip(),
            "role_id": role.id,
            "gap_type": g.gap_type,
            "priority_score": float(g.priority_score or 0.0),
            "time_to_learn_hours": int(g.time_to_learn_hours) if g.time_to_learn_hours is not None else None,
            "current_proficiency": g.current_proficiency,
            "required_proficiency": g.required_proficiency,
        }
        for g in gaps
        if str(g.skill_id).strip()
    ]

    if rows:
        bind_name = (db.bind.dialect.name if db.bind and db.bind.dialect else "").lower()
        insert_stmt = None
        if "postgres" in bind_name:
            insert_stmt = pg_insert(SkillGap).values(rows)
        elif "sqlite" in bind_name:
            insert_stmt = sqlite_insert(SkillGap).values(rows)
        else:
            # Fallback: keep prior behavior (best-effort) if dialect is unexpected.
            insert_stmt = None

        if insert_stmt is not None:
            upsert = insert_stmt.on_conflict_do_update(
                index_elements=["user_id", "skill_id", "role_id"],
                set_={
                    "gap_type": insert_stmt.excluded.gap_type,
                    "priority_score": insert_stmt.excluded.priority_score,
                    "time_to_learn_hours": insert_stmt.excluded.time_to_learn_hours,
                    "current_proficiency": insert_stmt.excluded.current_proficiency,
                    "required_proficiency": insert_stmt.excluded.required_proficiency,
                },
            )
            await db.execute(upsert)
        else:
            # Dialect fallback: try insert in a loop (may still race on unique, but keeps service usable).
            for row in rows:
                db.add(SkillGap(**row))

    await db.flush()

    return GapResult(
        user_id=user.id,
        role_id=role.id,
        role_name=role.name,
        readiness_score=readiness,
        missing_skills=sum(1 for g in gaps if g.gap_type == "missing"),
        weak_skills=sum(1 for g in gaps if g.gap_type == "weak"),
        total_gaps=len(gaps),
        total_learning_hours=sum(g.time_to_learn_hours for g in gaps),
        gaps=gaps,
    )
