"""Assessment generation, submission, and admin monitoring endpoints."""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.admin import require_admin
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.learning import _apply_failed_assessment_remediation
from app.db.session import AsyncSessionLocal, get_db
from app.models.models import (
    Assessment,
    AssessmentAttempt,
    LearningPlan,
    LearningPlanItem,
    Role,
    Skill,
    User,
    WeekAssessmentAttempt,
)
from app.services.assessment_service import QUESTIONS_PER_ITEM, generate_assessment_questions
from app.services.learning.path_generator import WEEK_HOUR_CAP_DEFAULT, _load_roadmap_from_db

router = APIRouter(prefix="/assessments", tags=["assessments"])
admin_router = APIRouter(prefix="/admin/assessments", tags=["admin-assessments"])

PASS_THRESHOLD = 0.7
logger = logging.getLogger(__name__)

class UserAssessmentSummaryResponse(BaseModel):
    assessments_completed: int
    average_score: float
    skills_assessed: int
    proficiency_level: str | None = None
    week_assessments_completed: int
    week_assessments_avg_score: float
    item_attempts_total: int
    item_attempts_accuracy: float


class GenerateAssessmentRequest(BaseModel):
    skill_name: str
    difficulty: str = "intermediate"
    question_type: str = "mcq"
    num_questions: int = Field(default=5, ge=1, le=20)


class AssessmentSubmissionItem(BaseModel):
    assessment_id: str
    answer: str
    time_taken_seconds: int = 0


class SubmitAssessmentRequest(BaseModel):
    submissions: list[AssessmentSubmissionItem]


class SubmitItemAssessmentRequest(BaseModel):
    answers: list[int]


class SubmitItemAssessmentResult(BaseModel):
    index: int
    correct: bool
    correct_index: int
    explanation: str
    selected_index: int
    selected_option: str
    correct_option: str


class SubmitItemAssessmentResponse(BaseModel):
    score: float
    passed: bool
    correct_count: int
    total: int
    results: list[SubmitItemAssessmentResult]
    item_status: str
    remediation_feedback: list[dict]


class UpdateMasteryRequest(BaseModel):
    skill_id: str
    question_id: str
    is_correct: bool
    time_taken_seconds: int = 0


@router.get("/summary", response_model=UserAssessmentSummaryResponse)
async def my_assessments_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregated assessment metrics for the logged-in user.

    - Week assessments: derived from `week_assessment_attempts` (score is 0..1)
    - Item assessments: derived from `assessment_attempts` (is_correct / total)
    """
    # Week assessments
    week_completed = int(
        await db.scalar(
            select(func.count(func.distinct(WeekAssessmentAttempt.week_assessment_id))).where(
                WeekAssessmentAttempt.user_id == current_user.id,
                WeekAssessmentAttempt.passed.is_(True),
            )
        )
        or 0
    )
    week_avg = float(
        await db.scalar(
            select(func.avg(WeekAssessmentAttempt.score)).where(WeekAssessmentAttempt.user_id == current_user.id)
        )
        or 0.0
    )

    # Item assessments
    item_total = int(
        await db.scalar(select(func.count(AssessmentAttempt.id)).where(AssessmentAttempt.user_id == current_user.id))
        or 0
    )
    item_correct = int(
        await db.scalar(
            select(func.count(AssessmentAttempt.id)).where(
                AssessmentAttempt.user_id == current_user.id,
                AssessmentAttempt.is_correct.is_(True),
            )
        )
        or 0
    )
    item_accuracy = (item_correct / item_total) if item_total else 0.0

    skills_assessed = int(
        await db.scalar(
            select(func.count(func.distinct(Assessment.skill_name)))
            .select_from(AssessmentAttempt)
            .join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
            .where(AssessmentAttempt.user_id == current_user.id)
        )
        or 0
    )

    # Overall average score: blend week assessments (0..1) with item assessment correctness (0..1).
    completed = int(week_completed + (1 if item_total else 0))
    average_score = float((week_avg + item_accuracy) / (2 if item_total else 1)) if completed else 0.0

    return UserAssessmentSummaryResponse(
        assessments_completed=int(week_completed),
        average_score=float(average_score),
        skills_assessed=int(skills_assessed),
        proficiency_level=getattr(current_user, "seniority_level", None),
        week_assessments_completed=int(week_completed),
        week_assessments_avg_score=float(week_avg),
        item_attempts_total=int(item_total),
        item_attempts_accuracy=float(item_accuracy),
    )


def _assessment_marker(item_id: str) -> str:
    return f"plan_item:{item_id}"


def _assessment_level_for_item(item: LearningPlanItem) -> str:
    return "intermediate" if str(item.resource_type or "").strip().lower() == "weak" else "beginner"


def _extract_subtopic_titles(subtopics_json: str | None) -> list[str]:
    if not subtopics_json:
        return []
    try:
        payload = json.loads(subtopics_json)
    except Exception:
        return []

    if isinstance(payload, dict):
        raw_subtopics = payload.get("subtopics", [])
    elif isinstance(payload, list):
        raw_subtopics = payload
    else:
        return []

    if not isinstance(raw_subtopics, list):
        return []

    titles: list[str] = []
    for st in raw_subtopics:
        if not isinstance(st, dict):
            continue
        title = str(st.get("title", "")).strip()
        if title:
            titles.append(title)
    return titles


def _parse_questions(raw_questions: str | None) -> list[dict]:
    if not raw_questions:
        return []
    try:
        payload = json.loads(raw_questions)
    except Exception:
        return []
    if not isinstance(payload, list) or len(payload) != QUESTIONS_PER_ITEM:
        return []

    normalized: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            return []
        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        explanation = str(item.get("explanation", "")).strip()
        correct_index = item.get("correct_index")
        if (
            not question
            or not explanation
            or not isinstance(options, list)
            or len(options) != 4
            or not isinstance(correct_index, int)
            or correct_index < 0
            or correct_index > 3
        ):
            return []
        normalized_options = [str(opt).strip() for opt in options]
        if any(not opt for opt in normalized_options):
            return []

        normalized.append(
            {
                "question": question,
                "options": normalized_options,
                "correct_index": int(correct_index),
                "explanation": explanation,
            }
        )

    return normalized


async def _get_user_plan_item(db: AsyncSession, user_id: str, item_id: str) -> tuple[LearningPlan, LearningPlanItem]:
    row = (
        await db.execute(
            select(LearningPlanItem, LearningPlan)
            .join(LearningPlan, LearningPlan.id == LearningPlanItem.plan_id)
            .where(
                LearningPlanItem.id == item_id,
                LearningPlan.user_id == user_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Learning plan item not found")
    item, plan = row
    return plan, item


async def _ensure_item_questions(db: AsyncSession, item: LearningPlanItem) -> tuple[list[dict], str, bool, bool, float]:
    level = _assessment_level_for_item(item)
    parsed = _parse_questions(item.assessment_questions)
    if parsed:
        return parsed, level, False, True, 0.0

    llm_started = time.monotonic()
    generated = await generate_assessment_questions(
        skill_name=item.title,
        level=level,
        subtopics=_extract_subtopic_titles(item.subtopics_json),
    )
    llm_ms = (time.monotonic() - llm_started) * 1000

    if len(generated) == QUESTIONS_PER_ITEM:
        # Double-check in case another concurrent request already persisted questions.
        await db.refresh(item, attribute_names=["assessment_questions"])
        refreshed = _parse_questions(item.assessment_questions)
        if refreshed:
            return refreshed, level, False, True, llm_ms

        item.assessment_questions = json.dumps(generated)
        db.add(item)
        await db.flush()
        return generated, level, True, False, llm_ms

    return [], level, False, False, llm_ms


def _mask_assessment_questions(questions: list[dict]) -> list[dict]:
    return [
        {
            "index": idx,
            "question": q["question"],
            "options": q["options"],
        }
        for idx, q in enumerate(questions)
    ]


def _is_completed_status(status: str | None) -> bool:
    return str(status or "").strip().lower() == "completed"


def _quick_tip_for_mistake(question_index: int, correct_index: int) -> str:
    return (
        f"Revisit Q{question_index + 1}: eliminate weak options first, then justify why "
        f"option {correct_index + 1} is the best fit before your next attempt."
    )


async def _resolve_item_week_context(
    db: AsyncSession,
    plan: LearningPlan,
    item: LearningPlanItem,
) -> tuple[int | None, list[str], list[str]]:
    role = await db.scalar(select(Role).where(Role.id == plan.role_id))
    role_name = role.name if role else "Target Role"
    roadmap = await _load_roadmap_from_db(
        db=db,
        plan=plan,
        role_name=role_name,
        hours_per_week=int(WEEK_HOUR_CAP_DEFAULT),
        readiness_score=0.0,
    )

    current_week_number: int | None = None
    current_week_item_ids: list[str] = []
    next_week_item_ids: list[str] = []

    week_to_item_ids: dict[int, list[str]] = {}
    for week in roadmap.weeks:
        seen: set[str] = set()
        item_ids: list[str] = []
        for skill in week.skills:
            candidate_item_id = str(skill.item_id or "").strip()
            if candidate_item_id and candidate_item_id not in seen:
                seen.add(candidate_item_id)
                item_ids.append(candidate_item_id)
        week_to_item_ids[int(week.week_number)] = item_ids

    for week_number, item_ids in week_to_item_ids.items():
        if item.id in item_ids:
            current_week_number = int(week_number)
            current_week_item_ids = item_ids
            break

    if current_week_number is not None:
        next_week_item_ids = week_to_item_ids.get(int(current_week_number) + 1, [])

    return current_week_number, current_week_item_ids, next_week_item_ids


async def _is_week_complete(
    db: AsyncSession,
    plan_id: str,
    week_item_ids: list[str],
    status_overrides: dict[str, str] | None = None,
) -> bool:
    if not week_item_ids:
        return False

    rows = (
        await db.execute(
            select(LearningPlanItem.id, LearningPlanItem.status)
            .where(
                LearningPlanItem.plan_id == plan_id,
                LearningPlanItem.id.in_(week_item_ids),
            )
        )
    ).all()
    status_by_item_id = {str(row[0]): str(row[1] or "") for row in rows}
    for override_item_id, override_status in (status_overrides or {}).items():
        status_by_item_id[str(override_item_id)] = str(override_status or "")

    for row_item_id in week_item_ids:
        if not _is_completed_status(status_by_item_id.get(str(row_item_id))):
            return False
    return True


async def _generate_week_item_questions_background(plan_id: str, item_ids: list[str]) -> None:
    if not item_ids:
        return

    async with AsyncSessionLocal() as db:
        try:
            rows = (
                await db.execute(
                    select(LearningPlanItem)
                    .where(
                        LearningPlanItem.plan_id == plan_id,
                        LearningPlanItem.id.in_(item_ids),
                    )
                    .order_by(LearningPlanItem.order)
                )
            ).scalars().all()

            did_persist = False
            for row in rows:
                if _parse_questions(row.assessment_questions):
                    continue

                generated = await generate_assessment_questions(
                    skill_name=row.title,
                    level=_assessment_level_for_item(row),
                    subtopics=_extract_subtopic_titles(row.subtopics_json),
                )
                if len(generated) != QUESTIONS_PER_ITEM:
                    continue

                # Double-check under concurrency before persisting generated payload.
                await db.refresh(row, attribute_names=["assessment_questions"])
                if _parse_questions(row.assessment_questions):
                    continue

                row.assessment_questions = json.dumps(generated)
                db.add(row)
                did_persist = True

            if did_persist:
                await db.commit()
        except Exception:
            await db.rollback()
            logger.exception(
                "assessment_next_week_generation_failed",
                extra={"plan_id": plan_id, "item_count": len(item_ids)},
            )


async def _get_or_create_item_assessment(db: AsyncSession, item: LearningPlanItem, level: str) -> Assessment:
    marker = _assessment_marker(item.id)
    existing = await db.scalar(
        select(Assessment).where(
            Assessment.question_type == "item_quiz",
            Assessment.question_text == marker,
        )
    )
    if existing:
        return existing

    assessment = Assessment(
        skill_name=item.title,
        difficulty=level,
        question_type="item_quiz",
        question_text=marker,
        options={"item_id": item.id},
        correct_option="N/A",
    )
    db.add(assessment)
    await db.flush()
    return assessment


def _template_question(skill_name: str, difficulty: str, idx: int) -> dict:
    variants = [
        {
            "question_text": f"Which practice is most important when working with {skill_name}?",
            "options": [
                f"Applying {skill_name} through hands-on projects",
                "Skipping tests to save time",
                "Avoiding code reviews",
                "Ignoring documentation",
            ],
            "correct_option": f"Applying {skill_name} through hands-on projects",
        },
        {
            "question_text": f"For {difficulty} level {skill_name}, what should you prioritize first?",
            "options": [
                "Fundamentals and repeatable workflows",
                "Random trial and error",
                "Only memorizing definitions",
                "Copying solutions without understanding",
            ],
            "correct_option": "Fundamentals and repeatable workflows",
        },
        {
            "question_text": f"How do you improve proficiency in {skill_name} most effectively?",
            "options": [
                "Practice + feedback + iteration",
                "One-time reading only",
                "Avoiding mistakes by not building",
                "Ignoring peer input",
            ],
            "correct_option": "Practice + feedback + iteration",
        },
    ]
    return variants[idx % len(variants)]


@router.post("/generate")
async def generate_assessment(
    payload: GenerateAssessmentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    questions = []
    for idx in range(payload.num_questions):
        q = _template_question(payload.skill_name, payload.difficulty, idx)
        record = Assessment(
            skill_name=payload.skill_name,
            difficulty=payload.difficulty,
            question_type=payload.question_type,
            question_text=q["question_text"],
            options=q["options"],
            correct_option=q["correct_option"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()

        questions.append(
            {
                "id": record.id,
                "question_text": record.question_text,
                "options": record.options,
                "difficulty": record.difficulty,
                "skill_name": record.skill_name,
            }
        )

    return questions


@router.post("/submit")
async def submit_assessment(
    payload: SubmitAssessmentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    if not payload.submissions:
        raise HTTPException(status_code=400, detail="No submissions provided")

    ids = [row.assessment_id for row in payload.submissions]
    assessment_rows = (
        await db.execute(select(Assessment).where(Assessment.id.in_(ids)))
    ).scalars().all()
    assessment_map = {a.id: a for a in assessment_rows}

    results = []
    total_score = 0
    total_max_score = 0

    for row in payload.submissions:
        assessment = assessment_map.get(row.assessment_id)
        if not assessment:
            continue

        is_correct = (row.answer or "").strip() == (assessment.correct_option or "").strip()
        score = 1 if is_correct else 0
        max_score = 1

        db.add(
            AssessmentAttempt(
                user_id=current_user.id,
                assessment_id=assessment.id,
                answer=row.answer,
                is_correct=is_correct,
                score=score,
                max_score=max_score,
                time_taken_seconds=max(0, int(row.time_taken_seconds or 0)),
                submitted_at=datetime.now(timezone.utc),
            )
        )

        total_score += score
        total_max_score += max_score
        results.append({"assessment_id": assessment.id, "is_correct": is_correct})

    if total_max_score == 0:
        raise HTTPException(status_code=400, detail="No valid assessment IDs submitted")

    percentage = round((total_score / total_max_score) * 100, 2)
    await db.flush()

    return {
        "percentage": percentage,
        "total_score": total_score,
        "total_max_score": total_max_score,
        "results": results,
    }


@router.post("/mastery/update")
async def update_mastery(
    _: UpdateMasteryRequest,
    __: Annotated[User, Depends(get_current_user)],
):
    return {"ok": True}


@router.get("/items/{item_id}")
async def get_item_assessment(
    item_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    total_started = time.monotonic()
    llm_ms = 0.0
    commit_ms = 0.0
    had_cached_questions = False

    db_started = time.monotonic()
    _, item = await _get_user_plan_item(db=db, user_id=current_user.id, item_id=item_id)
    db_ms = (time.monotonic() - db_started) * 1000

    questions, level, did_persist, had_cached_questions, llm_ms = await _ensure_item_questions(db=db, item=item)
    if did_persist:
        commit_started = time.monotonic()
        await db.commit()
        commit_ms = (time.monotonic() - commit_started) * 1000

    if not questions:
        total_ms = (time.monotonic() - total_started) * 1000
        logger.info(
            "assessment_get_timing: %s",
            {
                "item_id": item_id,
                "had_cached_questions": had_cached_questions,
                "db_ms": round(db_ms, 2),
                "llm_ms": round(llm_ms, 2),
                "commit_ms": round(commit_ms, 2),
                "serialize_ms": 0.0,
                "total_ms": round(total_ms, 2),
            },
        )
        raise HTTPException(status_code=503, detail="Assessment generation failed. Please retry.")

    serialize_started = time.monotonic()
    masked_questions = _mask_assessment_questions(questions)
    serialize_ms = (time.monotonic() - serialize_started) * 1000
    total_ms = (time.monotonic() - total_started) * 1000
    logger.info(
        "assessment_get_timing: %s",
        {
            "item_id": item_id,
            "had_cached_questions": had_cached_questions,
            "db_ms": round(db_ms, 2),
            "llm_ms": round(llm_ms, 2),
            "commit_ms": round(commit_ms, 2),
            "serialize_ms": round(serialize_ms, 2),
            "total_ms": round(total_ms, 2),
        },
    )

    return {
        "item_id": item.id,
        "skill_name": item.title,
        "level": level,
        "questions": masked_questions,
        "attempts": int(item.assessment_attempts or 0),
        "last_score": item.assessment_score,
    }


@router.post("/items/{item_id}/submit", response_model=SubmitItemAssessmentResponse)
async def submit_item_assessment(
    item_id: str,
    payload: SubmitItemAssessmentRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    plan, item = await _get_user_plan_item(db=db, user_id=current_user.id, item_id=item_id)

    answers = list(payload.answers or [])
    if len(answers) != QUESTIONS_PER_ITEM or any((not isinstance(v, int) or v < 0 or v > 3) for v in answers):
        raise HTTPException(
            status_code=400,
            detail=f"answers must contain exactly {QUESTIONS_PER_ITEM} integers in range 0..3",
        )

    questions, level, _, _, _ = await _ensure_item_questions(db=db, item=item)
    if not questions:
        await db.commit()
        raise HTTPException(status_code=503, detail="Assessment generation failed. Please retry.")

    results = []
    correct_count = 0
    failed_areas: list[str] = []
    for idx, (question, selected) in enumerate(zip(questions, answers)):
        options = question.get("options")
        if not isinstance(options, list) or len(options) != 4:
            raise HTTPException(status_code=503, detail="Assessment question options are invalid. Please retry.")

        normalized_options = [str(opt).strip() for opt in options]
        if any(not opt for opt in normalized_options):
            raise HTTPException(status_code=503, detail="Assessment question options are invalid. Please retry.")

        correct_index = int(question["correct_index"])
        if correct_index < 0 or correct_index >= len(normalized_options):
            raise HTTPException(status_code=503, detail="Assessment question options are invalid. Please retry.")

        selected_index = int(selected)
        if selected_index < 0 or selected_index >= len(normalized_options):
            raise HTTPException(status_code=400, detail="Selected answer index is out of range.")

        is_correct = int(selected) == correct_index
        if is_correct:
            correct_count += 1
        else:
            failed_areas.append(str(question.get("question", "")).strip())
        results.append(
            {
                "index": idx,
                "correct": is_correct,
                "correct_index": correct_index,
                "explanation": str(question.get("explanation", "")).strip(),
                "selected_index": selected_index,
                "selected_option": normalized_options[selected_index],
                "correct_option": normalized_options[correct_index],
            }
        )

    score = float(correct_count / QUESTIONS_PER_ITEM)
    passed = score >= PASS_THRESHOLD
    remediation_feedback: list[dict] = []
    for idx, (question, selected) in enumerate(zip(questions, answers)):
        correct_index = int(question["correct_index"])
        if int(selected) == correct_index:
            continue
        remediation_feedback.append(
            {
                "question_index": idx,
                "user_answer": int(selected),
                "correct_index": correct_index,
                "explanation": str(question.get("explanation", "")).strip(),
                "quick_tip": _quick_tip_for_mistake(idx, correct_index),
            }
        )

    assessment_row = await _get_or_create_item_assessment(db=db, item=item, level=level)
    db.add(
        AssessmentAttempt(
            user_id=current_user.id,
            assessment_id=assessment_row.id,
            answer=json.dumps(answers),
            is_correct=passed,
            score=correct_count,
            max_score=QUESTIONS_PER_ITEM,
            time_taken_seconds=0,
            submitted_at=datetime.now(timezone.utc),
        )
    )

    item.assessment_score = score
    item.assessment_attempts = int(item.assessment_attempts or 0) + 1
    current_week_number: int | None = None
    next_week_item_ids: list[str] = []

    now = datetime.now(timezone.utc)
    if passed:
        item.status = "completed"
        item.completed_at = now
        logger.info(
            "assessment_pass_with_mistakes",
            extra={"item_id": item.id, "mistake_count": len(remediation_feedback)},
        )
        current_week_number, current_week_item_ids, next_week_item_ids = await _resolve_item_week_context(
            db=db,
            plan=plan,
            item=item,
        )
        if not await _is_week_complete(
            db=db,
            plan_id=plan.id,
            week_item_ids=current_week_item_ids,
            status_overrides={item.id: item.status},
        ):
            next_week_item_ids = []
    else:
        skill = await db.scalar(select(Skill).where(Skill.id == item.skill_id))
        role = await db.scalar(select(Role).where(Role.id == plan.role_id))
        if not skill or not role:
            raise HTTPException(status_code=404, detail="Role or skill not found")
        await _apply_failed_assessment_remediation(
            db=db,
            item=item,
            skill=skill,
            target_role=role,
            failed_areas=failed_areas or [f"{item.title} remediation"],
        )
        item.status = "needs_review"
        item.completed_at = None

    db.add(item)
    await db.flush()

    all_items = (
        await db.execute(select(LearningPlanItem).where(LearningPlanItem.plan_id == plan.id))
    ).scalars().all()
    if all_items and all(str(i.status or "").lower() == "completed" for i in all_items):
        plan.status = "completed"
        plan.completed_at = now
    else:
        plan.status = "in_progress"
        plan.completed_at = None
    plan.updated_at = now
    db.add(plan)
    await db.flush()
    await db.commit()

    if passed and next_week_item_ids:
        background_tasks.add_task(
            _generate_week_item_questions_background,
            plan.id,
            next_week_item_ids,
        )
        logger.info(
            "assessment_next_week_generation_scheduled",
            extra={
                "plan_id": plan.id,
                "current_week": current_week_number,
                "next_week": (current_week_number + 1) if current_week_number is not None else None,
                "item_count": len(next_week_item_ids),
            },
        )

    return {
        "score": score,
        "passed": passed,
        "correct_count": correct_count,
        "total": QUESTIONS_PER_ITEM,
        "results": results,
        "item_status": item.status,
        "remediation_feedback": remediation_feedback,
    }


@router.get("/items/{item_id}/history")
async def get_item_assessment_history(
    item_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    _, item = await _get_user_plan_item(db=db, user_id=current_user.id, item_id=item_id)
    marker = _assessment_marker(item.id)

    rows = (
        await db.execute(
            select(AssessmentAttempt)
            .join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
            .where(
                Assessment.question_type == "item_quiz",
                Assessment.question_text == marker,
                AssessmentAttempt.user_id == current_user.id,
            )
            .order_by(AssessmentAttempt.submitted_at.desc())
        )
    ).scalars().all()

    attempts = []
    for row in rows:
        try:
            selected_answers = json.loads(row.answer or "[]")
        except Exception:
            selected_answers = []
        attempts.append(
            {
                "attempt_id": row.id,
                "score": row.score,
                "max_score": row.max_score,
                "passed": bool(row.is_correct),
                "selected_answers": selected_answers,
                "submitted_at": row.submitted_at,
            }
        )

    return {
        "item_id": item.id,
        "skill_name": item.title,
        "attempts": attempts,
    }


@admin_router.get("")
async def admin_list_assessments(
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
    skill: str = Query(default=""),
):
    stmt = (
        select(AssessmentAttempt, Assessment, User)
        .join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .join(User, User.id == AssessmentAttempt.user_id)
        .order_by(AssessmentAttempt.submitted_at.desc())
    )

    s = skill.strip().lower()
    if s:
        stmt = stmt.where(func.lower(Assessment.skill_name).contains(s))

    rows = (await db.execute(stmt)).all()
    return [
        {
            "attempt_id": attempt.id,
            "user_name": user.full_name,
            "user_email": user.email,
            "skill_name": assessment.skill_name,
            "question_type": assessment.question_type,
            "difficulty": assessment.difficulty,
            "score": attempt.score,
            "max_score": attempt.max_score,
            "is_correct": attempt.is_correct,
            "time_taken_seconds": attempt.time_taken_seconds,
            "submitted_at": attempt.submitted_at,
        }
        for attempt, assessment, user in rows
    ]


@admin_router.get("/summary")
async def admin_assessments_summary(
    _: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    total_attempts = int(await db.scalar(select(func.count(AssessmentAttempt.id))) or 0)
    correct_attempts = int(
        await db.scalar(select(func.count(AssessmentAttempt.id)).where(AssessmentAttempt.is_correct.is_(True))) or 0
    )
    users_assessed = int(await db.scalar(select(func.count(func.distinct(AssessmentAttempt.user_id)))) or 0)
    accuracy_rate = (correct_attempts / total_attempts) if total_attempts else 0.0

    return {
        "total_attempts": total_attempts,
        "correct_attempts": correct_attempts,
        "accuracy_rate": accuracy_rate,
        "users_assessed": users_assessed,
    }
