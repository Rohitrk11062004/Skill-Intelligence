"""Learning plan endpoints."""
import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.db.session import get_db
from app.models.models import (
    LearningPlan,
    LearningPlanItem,
    LearningPlanItemSubSubtopic,
    LearningPlanItemSubtopic,
    Role,
    RoleSkillRequirement,
    Skill,
    SkillPrerequisite,
    User,
)
from app.schemas.learning import (
    AssessmentFeedbackRequest,
    AssessmentFeedbackResponse,
    LearningPlanItemResponse,
    LearningPlanResponse,
    LearningModuleProgressResponse,
    LearningResource,
    LearningRoadmapResponse,
)
from app.services.gap.gap_detector import detect_and_store_gaps
from app.services.learning.path_generator import (
    _generate_assessment_breakdown,
    _deserialize_learning_content,
    _serialize_learning_content,
    build_learning_plan,
    compute_pacing_signal,
    delete_learning_plans_by_ids,
    generate_roadmap,
)
from app.api.v1.endpoints.week_assessments import ensure_week_assessment_generated_background

router = APIRouter(prefix="/users/me", tags=["learning"])
logger = logging.getLogger(__name__)


class LearningModuleProgressUpdate(BaseModel):
    status: Literal["not_started", "in_progress", "completed", "needs_review"]


class ManualSkillInput(BaseModel):
    skill_name: str


class ManualAnalysisRequest(BaseModel):
    skills: list[ManualSkillInput] = []
    target_role: str | None = None


def _parse_prerequisites(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        value = json.loads(raw_value)
    except Exception:
        return []

    if not isinstance(value, list):
        return []

    return [str(item).strip().lower() for item in value if str(item).strip()]


async def _normalized_prerequisites_for_skill(db: AsyncSession, skill_id: str) -> list[str]:
    rows = (
        await db.execute(
            select(SkillPrerequisite.prerequisite_skill_id).where(SkillPrerequisite.skill_id == skill_id)
        )
    ).scalars().all()
    return [str(x) for x in rows if str(x).strip()]


def _rerank_priority(importance: float, hours: float, is_mandatory: bool, coverage: float) -> float:
    mandatory_weight = 1.5 if is_mandatory else 1.0
    clamped_coverage = max(0.0, min(1.0, float(coverage)))
    return float(importance or 0.0) * (1.0 / max(1.0, float(hours or 1.0))) * mandatory_weight * clamped_coverage


async def _rerank_remaining_items(
    db: AsyncSession,
    plan: LearningPlan,
    completed_skill_name: str,
) -> bool:
    rows = (
        await db.execute(
            select(LearningPlanItem, Skill)
            .join(Skill, Skill.id == LearningPlanItem.skill_id)
            .where(LearningPlanItem.plan_id == plan.id)
        )
    ).all()

    requirements = (
        await db.execute(
            select(RoleSkillRequirement).where(RoleSkillRequirement.role_id == plan.role_id)
        )
    ).scalars().all()
    requirement_by_skill_id = {req.skill_id: req for req in requirements}

    completed_skill_ids = {
        str(item.skill_id).strip()
        for item, _skill in rows
        if str(item.status or "").lower() == "completed"
    }

    incomplete_items: list[tuple[LearningPlanItem, float]] = []
    reranked = False

    for item, skill in rows:
        if str(item.status or "").lower() == "completed":
            continue

        current_priority = float(item.priority_score or 0.0)
        prereq_ids = await _normalized_prerequisites_for_skill(db, skill.id)
        if not prereq_ids:
            # fallback for legacy JSON
            prereq_names = _parse_prerequisites(getattr(skill, "prerequisites", None))
            if prereq_names:
                resolved = (
                    await db.execute(select(Skill.id).where(func.lower(Skill.name).in_(prereq_names)))
                ).scalars().all()
                prereq_ids = [str(x) for x in resolved if str(x).strip()]

        if completed_skill_ids and prereq_ids:
            total_prereqs = len(prereq_ids)
            satisfied_prereqs = sum(1 for prereq in prereq_ids if prereq in completed_skill_ids)
            prereq_coverage = (satisfied_prereqs / total_prereqs) if total_prereqs else 1.0
            requirement = requirement_by_skill_id.get(skill.id)
            importance = float(requirement.importance or 0.0) if requirement else 0.0
            is_mandatory = bool(requirement.is_mandatory) if requirement else False
            hours = float(item.estimated_hours or skill.time_to_learn_hours or 1.0 or 1.0)
            current_priority = _rerank_priority(importance, hours, is_mandatory, prereq_coverage)
            item.priority_score = current_priority
            reranked = True

        incomplete_items.append((item, current_priority))

    incomplete_items.sort(
        key=lambda pair: (
            -pair[1],
            pair[0].order,
            pair[0].title.lower(),
        )
    )

    next_order = max((item.order for item, _skill in rows if str(item.status or "").lower() == "completed"), default=0) + 1
    for index, (item, _priority) in enumerate(incomplete_items, start=next_order):
        if item.order != index:
            item.order = index
            reranked = True

    return reranked


async def _apply_failed_assessment_remediation(
    db: AsyncSession,
    item: LearningPlanItem,
    skill: Skill,
    target_role: Role,
    failed_areas: list[str],
):
    _, existing_resources = _deserialize_learning_content(item.subtopics_json)
    updated_subtopics = await _generate_assessment_breakdown(
        skill_name=skill.name,
        target_role=target_role.name,
        failed_areas=failed_areas,
        time_to_learn_hours=float(item.estimated_hours or skill.time_to_learn_hours or 0.0),
    )
    item.subtopics_json = _serialize_learning_content(updated_subtopics, existing_resources)
    item.status = "needs_review"
    db.add(item)
    await db.flush()

    existing_subtopic_ids = (
        await db.execute(
            select(LearningPlanItemSubtopic.id).where(LearningPlanItemSubtopic.item_id == item.id)
        )
    ).scalars().all()
    if existing_subtopic_ids:
        await db.execute(
            delete(LearningPlanItemSubSubtopic).where(
                LearningPlanItemSubSubtopic.subtopic_id.in_(existing_subtopic_ids)
            )
        )
    await db.execute(delete(LearningPlanItemSubtopic).where(LearningPlanItemSubtopic.item_id == item.id))
    await db.flush()

    new_subtopic_rows: list[LearningPlanItemSubtopic] = []
    for st_idx, st in enumerate(updated_subtopics or []):
        new_subtopic_rows.append(
            LearningPlanItemSubtopic(
                item_id=item.id,
                order_index=st_idx,
                title=st.title,
                estimated_hours=float(st.estimated_hours or 0.0),
                focus=False,
            )
        )
    db.add_all(new_subtopic_rows)
    await db.flush()

    subtopic_id_by_index = {(row.order_index): row.id for row in new_subtopic_rows}
    new_sub_sub_rows: list[LearningPlanItemSubSubtopic] = []
    for st_idx, st in enumerate(updated_subtopics or []):
        subtopic_id = subtopic_id_by_index.get(st_idx)
        if not subtopic_id:
            continue
        for ss_idx, ss in enumerate(st.sub_subtopics or []):
            new_sub_sub_rows.append(
                LearningPlanItemSubSubtopic(
                    subtopic_id=subtopic_id,
                    order_index=ss_idx,
                    title=ss.title,
                    estimated_hours=float(ss.estimated_hours or 0.0),
                )
            )
    db.add_all(new_sub_sub_rows)
    await db.flush()

    return updated_subtopics


@router.get("/learning-plan", response_model=LearningPlanResponse)
async def get_learning_plan(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    daily_hours: float | None = Query(default=None, gt=0, le=24),
    study_days_per_week: int = Query(default=7, ge=1, le=7),
    deadline_weeks: int | None = Query(default=None, gt=0, le=104),
):
    if not current_user.target_role_id:
        raise HTTPException(status_code=400, detail="Target role not set. Use POST /api/v1/users/me/target-role")

    role = await db.scalar(select(Role).where(Role.id == current_user.target_role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Target role not found")

    gap_result = await detect_and_store_gaps(db, current_user, role)
    total_hours, items = build_learning_plan(
        gap_result,
        daily_hours=daily_hours,
        deadline_weeks=deadline_weeks,
        study_days_per_week=study_days_per_week,
    )

    return LearningPlanResponse(
        user_id=gap_result.user_id,
        role_id=gap_result.role_id,
        role_name=gap_result.role_name,
        readiness_score=gap_result.readiness_score,
        total_hours_estimate=total_hours,
        item_count=len(items),
        items=[
            LearningPlanItemResponse(
                order=i.order,
                skill_id=i.skill_id,
                skill_name=i.skill_name,
                skill_rationale=None,
                gap_type=i.gap_type,
                priority_score=i.priority_score,
                estimated_hours=i.estimated_hours,
                prerequisites=i.prerequisites,
                resources=[LearningResource(**r) for r in i.resources],
            )
            for i in items
        ],
    )


@router.get("/learning-roadmap", response_model=LearningRoadmapResponse)
async def get_learning_roadmap(
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    hours_per_week: int = Query(default=10, ge=1, le=168),
    daily_hours: float | None = Query(default=None, gt=0, le=24),
    study_days_per_week: int = Query(default=7, ge=1, le=7),
    deadline_weeks: int | None = Query(default=None, gt=0, le=104),
    force_regenerate: bool = Query(default=False),
):
    effective_hours_per_week = hours_per_week
    current_user_id = str(current_user.id)
    if daily_hours is not None:
        effective_hours_per_week = max(1, int(round(float(daily_hours) * float(study_days_per_week))))

    roadmap = await generate_roadmap(
        user_id=current_user_id,
        db=db,
        hours_per_week=effective_hours_per_week,
        daily_hours=daily_hours,
        deadline_weeks=deadline_weeks,
        force_regenerate=force_regenerate,
        study_days_per_week=study_days_per_week,
    )

    # Generate week-1 assessment questions after responding so roadmap GET returns quickly.
    if roadmap.plan_id:
        background_tasks.add_task(
            ensure_week_assessment_generated_background,
            current_user_id,
            roadmap.plan_id,
            1,
        )

    return roadmap


@router.delete("/learning-plan/{plan_id}")
async def delete_learning_plan(
    plan_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    plan = await db.scalar(
        select(LearningPlan).where(
            LearningPlan.id == plan_id,
            LearningPlan.user_id == current_user.id,
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Learning plan not found")

    await delete_learning_plans_by_ids(db, [plan_id])
    await db.commit()
    return {"ok": True, "deleted_plan_id": plan_id}


@router.patch("/learning-plan/{plan_id}/items/{item_id}/progress", response_model=LearningModuleProgressResponse)
async def update_learning_module_progress(
    plan_id: str,
    item_id: str,
    payload: LearningModuleProgressUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    plan = await db.scalar(
        select(LearningPlan).where(
            LearningPlan.id == plan_id,
            LearningPlan.user_id == current_user.id,
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Learning plan not found")

    item = await db.scalar(
        select(LearningPlanItem)
        .where(LearningPlanItem.id == item_id, LearningPlanItem.plan_id == plan_id)
    )

    if not item:
        raise HTTPException(status_code=404, detail="Learning plan item not found")

    current_status = (item.status or "not_started").lower()
    next_status = payload.status

    if current_status == "completed" and next_status != "completed":
        raise HTTPException(status_code=400, detail="Cannot revert a completed item")

    allowed_transitions = {
        "not_started": {"in_progress", "completed", "not_started", "needs_review"},
        "in_progress": {"completed", "not_started", "in_progress", "needs_review"},
        "needs_review": {"in_progress", "completed", "needs_review"},
        "completed": {"completed", "needs_review"},
    }
    if next_status not in allowed_transitions.get(current_status, set()):
        raise HTTPException(status_code=400, detail="Cannot revert a completed item")

    if (
        next_status == "completed"
        and str(item.assessment_questions or "").strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="This item requires assessment submission before completion.",
        )

    item.status = next_status
    if next_status == "completed":
        item.completed_at = datetime.now(timezone.utc)
    else:
        item.completed_at = None

    db.add(item)
    await db.flush()

    completed_skill = await db.scalar(select(Skill).where(Skill.id == item.skill_id))

    all_items = (
        await db.execute(
            select(LearningPlanItem).where(LearningPlanItem.plan_id == plan_id)
        )
    ).scalars().all()

    reranked = False
    if next_status == "completed":
        reranked = await _rerank_remaining_items(
            db=db,
            plan=plan,
            completed_skill_name=(completed_skill.name if completed_skill else item.title),
        )

    if all_items and all(i.status == "completed" for i in all_items):
        plan.status = "completed"
        plan.completed_at = datetime.now(timezone.utc)
    else:
        plan.status = "in_progress"
        plan.completed_at = None

    plan.updated_at = datetime.now(timezone.utc)
    db.add(plan)
    await db.flush()
    await db.commit()

    return {
        "ok": True,
        "item_id": item.id,
        "status": item.status,
        "completed_at": item.completed_at,
        "plan_status": plan.status,
        "plan_completed_at": plan.completed_at,
        "reranked": reranked,
    }


@router.post("/learning-plan/{plan_id}/items/{item_id}/assessment-feedback", response_model=AssessmentFeedbackResponse)
async def submit_assessment_feedback(
    plan_id: str,
    item_id: str,
    payload: AssessmentFeedbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    plan = await db.scalar(
        select(LearningPlan).where(
            LearningPlan.id == plan_id,
            LearningPlan.user_id == current_user.id,
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Learning plan not found")

    item = await db.scalar(
        select(LearningPlanItem).where(
            LearningPlanItem.id == item_id,
            LearningPlanItem.plan_id == plan_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Learning plan item not found")

    if str(item.title or "").strip().lower() != str(payload.skill_name or "").strip().lower():
        raise HTTPException(status_code=400, detail="skill_name does not match the learning plan item")

    target_role = await db.scalar(select(Role).where(Role.id == plan.role_id))
    skill = await db.scalar(select(Skill).where(Skill.id == item.skill_id))
    if not target_role or not skill:
        raise HTTPException(status_code=404, detail="Role or skill not found")

    item.completed_at = None
    reranked_remaining = False

    if float(payload.score) >= 0.75:
        item.resource_type = "weak"
        db.add(item)
        await db.flush()
        action_taken = "upgraded_to_weak"
        updated_subtopics = None
    else:
        updated_subtopics = await _apply_failed_assessment_remediation(
            db=db,
            item=item,
            skill=skill,
            target_role=target_role,
            failed_areas=payload.failed_areas,
        )

        action_taken = "subtopics_regenerated"

    plan.updated_at = datetime.now(timezone.utc)
    db.add(plan)
    await db.flush()
    await db.commit()

    return AssessmentFeedbackResponse(
        action_taken=action_taken,
        updated_subtopics=updated_subtopics,
        reranked_remaining=reranked_remaining,
    )


@router.get("/learning-plan/progress")
async def get_learning_plan_progress_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    plan = await db.scalar(
        select(LearningPlan)
        .where(
            LearningPlan.user_id == current_user.id,
            LearningPlan.status.in_(["active", "in_progress", "completed"]),
        )
        .order_by(LearningPlan.updated_at.desc())
        .limit(1)
    )

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="No active learning plan found. Generate one via GET /api/v1/users/me/learning-roadmap",
        )

    all_items = (
        await db.execute(
            select(LearningPlanItem).where(LearningPlanItem.plan_id == plan.id)
        )
    ).scalars().all()

    total_items = len(all_items)
    completed_items = sum(1 for item in all_items if item.status == "completed")
    in_progress_items = sum(1 for item in all_items if item.status == "in_progress")
    not_started_items = sum(1 for item in all_items if item.status == "not_started")

    percent_complete = round((completed_items / total_items) * 100, 1) if total_items > 0 else 0.0

    total_hours = sum(float(item.estimated_hours or 0.0) for item in all_items)
    hours_completed = sum(
        float(item.estimated_hours or 0.0)
        for item in all_items
        if item.status == "completed"
    )
    hours_remaining = total_hours - hours_completed

    role = await db.scalar(select(Role).where(Role.id == plan.role_id))
    pacing = await compute_pacing_signal(plan_id=plan.id, db=db)

    return {
        "plan_id": plan.id,
        "plan_status": plan.status,
        "target_role": role.name if role else "Unknown",
        "total_items": total_items,
        "completed_items": completed_items,
        "in_progress_items": in_progress_items,
        "not_started_items": not_started_items,
        "percent_complete": percent_complete,
        "total_hours_estimate": total_hours,
        "hours_completed": hours_completed,
        "hours_remaining": hours_remaining,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "completed_at": plan.completed_at,
        "pacing_signal": pacing["pacing_signal"],
        "expected_skills_done_by_now": pacing["expected_skills_done_by_now"],
        "actual_skills_done": pacing["actual_skills_done"],
    }


@router.post("/manual-analysis")
async def manual_skill_analysis(
    payload: ManualAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    target_role_id = current_user.target_role_id

    if payload.target_role:
        role = await db.scalar(select(Role).where(func.lower(Role.name) == payload.target_role.lower()))
        if not role:
            raise HTTPException(status_code=404, detail="Target role not found")
        target_role_id = role.id

    if not target_role_id:
        raise HTTPException(status_code=400, detail="Target role is required")

    role = await db.scalar(select(Role).where(Role.id == target_role_id))
    required = (
        await db.execute(
            select(RoleSkillRequirement, Skill)
            .join(Skill, Skill.id == RoleSkillRequirement.skill_id)
            .where(RoleSkillRequirement.role_id == target_role_id)
        )
    ).all()

    submitted = {s.skill_name.strip().lower() for s in payload.skills if s.skill_name and s.skill_name.strip()}
    detected_skills = [
        {"skill_name": s.skill_name.strip(), "source": "manual", "proficiency_score": 0.5}
        for s in payload.skills
        if s.skill_name and s.skill_name.strip()
    ]

    skill_gaps = []
    for req, skill in required:
        if skill.name.lower() in submitted:
            continue
        skill_gaps.append(
            {
                "skill_id": skill.id,
                "skill_name": skill.name,
                "gap_type": "missing",
                "priority_score": req.importance,
                "time_to_learn_hours": skill.time_to_learn_hours or 20,
            }
        )

    matched = max(0, len(required) - len(skill_gaps))
    readiness = (matched / len(required)) if required else 0
    role_name = role.name if role else "target role"

    return {
        "detected_skills": detected_skills,
        "skill_gaps": skill_gaps,
        "analysis_summary": f"Readiness {round(readiness * 100)}% for {role_name} with {len(skill_gaps)} gaps identified",
    }
