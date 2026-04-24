"""Week-based assessment endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.db.session import AsyncSessionLocal, get_db
from app.models.models import LearningPlan, Role, User, WeekAssessment, WeekAssessmentAttempt
from app.services.learning.path_generator import WEEK_HOUR_CAP_DEFAULT, _load_roadmap_from_db
from app.services.week_assessment_service import compute_week_question_count, generate_week_assessment_questions

router = APIRouter(prefix="/assessments/weeks", tags=["assessments"])

PASS_THRESHOLD = 0.7
logger = logging.getLogger(__name__)
_WEEK_GENERATION_LOCKS: dict[str, asyncio.Lock] = {}
_WEEK_GENERATION_CACHE: dict[str, list[dict]] = {}


def _build_week_assessment_report(
    *,
    plan_id: str,
    week_number: int,
    score: float,
    passed: bool,
    correct_count: int,
    total: int,
    results: list[dict],
) -> dict:
    """Lightweight persisted report for assessment results page."""
    wrong = [r for r in results if not r.get("correct")]
    tag_counts: dict[str, int] = {}
    for r in wrong:
        for t in (r.get("tags") or []):
            tag = str(t or "").strip()
            if not tag:
                continue
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_weak = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "plan_id": plan_id,
        "week_number": int(week_number),
        "score": float(score),
        "passed": bool(passed),
        "correct_count": int(correct_count),
        "total": int(total),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weak_areas": [{"tag": k, "missed": v} for k, v in top_weak],
        # keep only the essentials for storage size
        "incorrect_questions": [
            {
                "index": int(r["index"]),
                "selected_index": r.get("selected_index"),
                "correct_index": r.get("correct_index"),
                "tags": r.get("tags", []),
            }
            for r in wrong
        ],
    }


def _build_week_assessment_report_with_answers(
    *,
    plan_id: str,
    week_number: int,
    score: float,
    passed: bool,
    correct_count: int,
    total: int,
    questions: list[dict],
    results: list[dict],
) -> dict:
    """
    Persisted report including question text, correct answers, and explanations.
    This is stored only after submission (not returned by GET /weeks/{plan}/{week}).
    """
    by_index = {int(r["index"]): r for r in results if isinstance(r, dict) and "index" in r}
    rendered = []
    for idx, q in enumerate(questions):
        r = by_index.get(idx, {})
        options = q.get("options", [])
        correct_index = int(q.get("correct_index", 0))
        selected_index = r.get("selected_index")
        rendered.append(
            {
                "index": idx,
                "question": q.get("question"),
                "options": options,
                "selected_index": selected_index,
                "selected_option": r.get("selected_option"),
                "correct_index": correct_index,
                "correct_option": options[correct_index] if isinstance(options, list) and len(options) > correct_index else None,
                "correct": bool(r.get("correct")),
                "explanation": q.get("explanation") or r.get("explanation"),
                "tags": q.get("tags", []) or r.get("tags", []),
            }
        )

    return {
        "plan_id": plan_id,
        "week_number": int(week_number),
        "score": float(score),
        "passed": bool(passed),
        "correct_count": int(correct_count),
        "total": int(total),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "questions": rendered,
    }


class SubmitWeekAssessmentRequest(BaseModel):
    answers: list[int | None]


def _generation_lock_key(user_id: str, plan_id: str, week_number: int) -> str:
    return f"{user_id}:{plan_id}:{int(week_number)}"


def _parse_week_questions(raw_questions: str | None) -> list[dict]:
    if not raw_questions:
        return []
    try:
        payload = json.loads(raw_questions)
    except Exception:
        return []

    if not isinstance(payload, list):
        return []

    normalized: list[dict] = []
    for row in payload:
        if not isinstance(row, dict):
            return []

        question = str(row.get("question", "")).strip()
        explanation = str(row.get("explanation", "")).strip()
        options = row.get("options", [])
        correct_index = row.get("correct_index")
        tags = row.get("tags", [])

        if (
            not question
            or not explanation
            or not isinstance(options, list)
            or len(options) != 4
            or not isinstance(correct_index, int)
            or correct_index < 0
            or correct_index > 3
            or not isinstance(tags, list)
            or not tags
        ):
            return []

        normalized_options = [str(opt).strip() for opt in options]
        if any(not opt for opt in normalized_options):
            return []

        normalized_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
        if not normalized_tags:
            return []

        normalized.append(
            {
                "question": question,
                "options": normalized_options,
                "correct_index": int(correct_index),
                "explanation": explanation,
                "tags": normalized_tags,
            }
        )

    return normalized


def _mask_week_questions(questions: list[dict]) -> list[dict]:
    return [
        {
            "index": idx,
            "question": row["question"],
            "options": row["options"],
            "tags": row.get("tags", []),
        }
        for idx, row in enumerate(questions)
    ]


async def _get_user_plan(db: AsyncSession, user_id: str, plan_id: str) -> LearningPlan:
    plan = await db.scalar(
        select(LearningPlan).where(
            LearningPlan.id == plan_id,
            LearningPlan.user_id == user_id,
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Learning plan not found")
    return plan


async def _get_week_scope(
    db: AsyncSession,
    *,
    plan: LearningPlan,
    week_number: int,
) -> tuple[list[str], list[str], float, int]:
    role = await db.scalar(select(Role).where(Role.id == plan.role_id))
    role_name = role.name if role else "Target Role"

    roadmap = await _load_roadmap_from_db(
        db=db,
        plan=plan,
        role_name=role_name,
        hours_per_week=int(WEEK_HOUR_CAP_DEFAULT),
        readiness_score=0.0,
    )

    week = next((row for row in roadmap.weeks if int(row.week_number) == int(week_number)), None)
    if not week:
        raise HTTPException(status_code=404, detail="Week not found in roadmap")

    skills = [str(skill.skill_name).strip() for skill in week.skills if str(skill.skill_name or "").strip()]
    subtopics: list[str] = []
    for skill in week.skills:
        for subtopic in skill.subtopics or []:
            title = str(subtopic.title or "").strip()
            if title:
                subtopics.append(title)
            for sub_subtopic in subtopic.sub_subtopics or []:
                sub_subtitle = str(sub_subtopic.title or "").strip()
                if sub_subtitle:
                    subtopics.append(sub_subtitle)

    total_subtopics = len(subtopics)
    week_hours = float(week.total_hours or 0.0)
    question_count = compute_week_question_count(total_subtopics=total_subtopics, week_hours=week_hours)
    return skills, subtopics, week_hours, question_count


async def _get_or_create_week_assessment(
    db: AsyncSession,
    *,
    user_id: str,
    plan_id: str,
    week_number: int,
    question_count: int,
) -> WeekAssessment:
    existing = await db.scalar(
        select(WeekAssessment).where(
            WeekAssessment.user_id == user_id,
            WeekAssessment.plan_id == plan_id,
            WeekAssessment.week_number == week_number,
        )
    )
    if existing:
        if int(existing.question_count or 0) != int(question_count):
            existing.question_count = int(question_count)
            db.add(existing)
            await db.flush()
        return existing

    row = WeekAssessment(
        plan_id=plan_id,
        user_id=user_id,
        week_number=int(week_number),
        question_count=int(question_count),
        status="pending",
    )
    db.add(row)
    try:
        await db.flush()
        return row
    except IntegrityError:
        await db.rollback()
        refreshed = await db.scalar(
            select(WeekAssessment).where(
                WeekAssessment.user_id == user_id,
                WeekAssessment.plan_id == plan_id,
                WeekAssessment.week_number == week_number,
            )
        )
        if not refreshed:
            raise
        if int(refreshed.question_count or 0) != int(question_count):
            refreshed.question_count = int(question_count)
            db.add(refreshed)
            await db.flush()
        return refreshed


async def _ensure_week_questions(
    db: AsyncSession,
    *,
    plan: LearningPlan,
    row: WeekAssessment,
    user_id: str,
    week_number: int,
    week_hours: float,
    skills: list[str],
    subtopics: list[str],
) -> list[dict]:
    parsed = _parse_week_questions(row.questions_json)
    if parsed and len(parsed) == int(row.question_count):
        if row.status != "completed":
            row.status = "ready"
            db.add(row)
            await db.flush()
        return parsed

    generation_lock = _WEEK_GENERATION_LOCKS.setdefault(
        _generation_lock_key(user_id=user_id, plan_id=row.plan_id, week_number=week_number),
        asyncio.Lock(),
    )
    lock_key = _generation_lock_key(user_id=user_id, plan_id=row.plan_id, week_number=week_number)

    async with generation_lock:
        lock_stmt = select(WeekAssessment).where(
            WeekAssessment.id == row.id,
            WeekAssessment.user_id == user_id,
        )
        if db.get_bind().dialect.name == "postgresql":
            lock_stmt = lock_stmt.with_for_update()
        locked_row = await db.scalar(lock_stmt)
        if not locked_row:
            return []

        parsed_after_lock = _parse_week_questions(locked_row.questions_json)
        if parsed_after_lock and len(parsed_after_lock) == int(locked_row.question_count):
            if locked_row.status != "completed":
                locked_row.status = "ready"
                db.add(locked_row)
                await db.flush()
            return parsed_after_lock

        generated = _WEEK_GENERATION_CACHE.get(lock_key, [])
        if len(generated) != int(locked_row.question_count):
            generation_kwargs = {
                "week_number": int(week_number),
                "week_hours": float(week_hours),
                "skills": skills,
                "subtopics": subtopics,
                "question_count": int(locked_row.question_count),
            }
            try:
                generated = await generate_week_assessment_questions(**generation_kwargs)
            except TypeError as exc:
                # Keep compatibility with test monkeypatches or legacy callables.
                if "week_hours" not in str(exc):
                    raise
                generation_kwargs.pop("week_hours", None)
                generated = await generate_week_assessment_questions(**generation_kwargs)
            if len(generated) == int(locked_row.question_count):
                _WEEK_GENERATION_CACHE[lock_key] = generated
        if len(generated) != int(locked_row.question_count):
            return []

        locked_row.questions_json = json.dumps(generated)
        if locked_row.status != "completed":
            locked_row.status = "ready"
        db.add(locked_row)
        await db.flush()
        return generated


async def ensure_week_assessment_generated(
    db: AsyncSession,
    *,
    user_id: str,
    plan_id: str,
    week_number: int,
    generate_questions: bool,
) -> WeekAssessment | None:
    plan = await _get_user_plan(db=db, user_id=user_id, plan_id=plan_id)
    skills, subtopics, week_hours, question_count = await _get_week_scope(
        db=db,
        plan=plan,
        week_number=week_number,
    )

    row = await _get_or_create_week_assessment(
        db=db,
        user_id=user_id,
        plan_id=plan_id,
        week_number=week_number,
        question_count=question_count,
    )

    if not generate_questions:
        return row

    generated = await _ensure_week_questions(
        db=db,
        plan=plan,
        row=row,
        user_id=user_id,
        week_number=week_number,
        week_hours=week_hours,
        skills=skills,
        subtopics=subtopics,
    )
    if not generated:
        return row

    return row


async def ensure_week_assessment_generated_background(user_id: str, plan_id: str, week_number: int) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await ensure_week_assessment_generated(
                db=db,
                user_id=user_id,
                plan_id=plan_id,
                week_number=week_number,
                generate_questions=True,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception(
                "week_assessment_background_generation_failed",
                extra={"plan_id": plan_id, "week_number": week_number, "user_id": user_id},
            )


@router.get("/{plan_id}/{week_number}")
async def get_week_assessment(
    plan_id: str,
    week_number: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    if week_number < 1:
        raise HTTPException(status_code=400, detail="week_number must be >= 1")

    row = await ensure_week_assessment_generated(
        db=db,
        user_id=current_user.id,
        plan_id=plan_id,
        week_number=week_number,
        generate_questions=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Week assessment not found")

    questions = _parse_week_questions(row.questions_json)
    if not questions or len(questions) != int(row.question_count):
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Week assessment generation failed and can be retried. Please retry.",
        )

    attempts_count = int(
        await db.scalar(
            select(func.count(WeekAssessmentAttempt.id)).where(
                WeekAssessmentAttempt.week_assessment_id == row.id,
                WeekAssessmentAttempt.user_id == current_user.id,
            )
        )
        or 0
    )

    last_attempt = await db.scalar(
        select(WeekAssessmentAttempt)
        .where(
            WeekAssessmentAttempt.week_assessment_id == row.id,
            WeekAssessmentAttempt.user_id == current_user.id,
        )
        .order_by(desc(WeekAssessmentAttempt.attempted_at))
        .limit(1)
    )

    await db.commit()

    return {
        "plan_id": plan_id,
        "week_number": int(week_number),
        "question_count": int(row.question_count),
        "status": row.status,
        "questions": _mask_week_questions(questions),
        "attempts": attempts_count,
        "last_score": float(last_attempt.score) if last_attempt else None,
    }


@router.post("/{plan_id}/{week_number}/submit")
async def submit_week_assessment(
    plan_id: str,
    week_number: int,
    payload: SubmitWeekAssessmentRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    if week_number < 1:
        raise HTTPException(status_code=400, detail="week_number must be >= 1")

    row = await ensure_week_assessment_generated(
        db=db,
        user_id=current_user.id,
        plan_id=plan_id,
        week_number=week_number,
        generate_questions=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Week assessment not found")

    if row.status == "completed":
        raise HTTPException(status_code=409, detail="Week assessment already completed; retakes are not allowed.")

    last_attempt = await db.scalar(
        select(WeekAssessmentAttempt)
        .where(
            WeekAssessmentAttempt.week_assessment_id == row.id,
            WeekAssessmentAttempt.user_id == current_user.id,
        )
        .order_by(desc(WeekAssessmentAttempt.attempted_at))
        .limit(1)
    )
    if last_attempt and bool(last_attempt.passed):
        raise HTTPException(status_code=409, detail="Week assessment already completed; retakes are not allowed.")

    questions = _parse_week_questions(row.questions_json)
    if not questions or len(questions) != int(row.question_count):
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Week assessment generation failed and can be retried. Please retry.",
        )

    answers = list(payload.answers or [])
    if len(answers) != int(row.question_count):
        raise HTTPException(
            status_code=400,
            detail=f"answers must contain exactly {int(row.question_count)} values (integers 0..3 or null)",
        )
    if any((answer is not None and (not isinstance(answer, int) or answer < 0 or answer > 3)) for answer in answers):
        raise HTTPException(status_code=400, detail="All answer indices must be integers in range 0..3 or null")

    results: list[dict] = []
    correct_count = 0
    for idx, (question, selected_index) in enumerate(zip(questions, answers)):
        options = [str(opt).strip() for opt in question.get("options", [])]
        correct_index = int(question["correct_index"])
        selected_index_value = selected_index if isinstance(selected_index, int) else None

        is_correct = selected_index_value == correct_index
        if is_correct:
            correct_count += 1

        if selected_index_value is None:
            selected_option = "-"
        else:
            selected_option = options[selected_index_value]

        results.append(
            {
                "index": idx,
                "correct": is_correct,
                "selected_index": selected_index_value,
                "selected_option": selected_option,
                "correct_index": correct_index,
                "correct_option": options[correct_index],
                "explanation": str(question.get("explanation", "")).strip(),
                "tags": question.get("tags", []),
            }
        )

    total = int(row.question_count)
    score = float(correct_count / total) if total > 0 else 0.0
    passed = score >= PASS_THRESHOLD

    now = datetime.now(timezone.utc)
    attempt = WeekAssessmentAttempt(
        week_assessment_id=row.id,
        user_id=current_user.id,
        score=score,
        answers_json=json.dumps(answers),
        passed=passed,
        attempted_at=now,
    )
    # Persist report for both pass/fail. Includes correct answers and explanations.
    report = _build_week_assessment_report_with_answers(
        plan_id=plan_id,
        week_number=int(week_number),
        score=score,
        passed=passed,
        correct_count=correct_count,
        total=total,
        questions=questions,
        results=results,
    )
    attempt.report_json = json.dumps(report)
    attempt.report_generated_at = now
    db.add(attempt)

    row.status = "completed" if passed else "ready"
    row.updated_at = now
    db.add(row)
    await db.flush()

    if not passed:
        # Regenerate a fresh set of questions for the same week so the user doesn't retake the same assessment.
        skills, subtopics, week_hours, question_count = await _get_week_scope(
            db=db,
            plan=await _get_user_plan(db=db, user_id=current_user.id, plan_id=plan_id),
            week_number=week_number,
        )
        # Ensure question_count stays consistent with row.question_count.
        row.question_count = int(question_count)
        generation_kwargs = {
            "week_number": int(week_number),
            "week_hours": float(week_hours),
            "skills": skills,
            "subtopics": subtopics,
            "question_count": int(row.question_count),
        }
        try:
            regenerated = await generate_week_assessment_questions(**generation_kwargs)
        except TypeError as exc:
            if "week_hours" not in str(exc):
                raise
            generation_kwargs.pop("week_hours", None)
            regenerated = await generate_week_assessment_questions(**generation_kwargs)

        if len(regenerated) == int(row.question_count):
            row.questions_json = json.dumps(regenerated)
            row.status = "ready"
            row.updated_at = now
            db.add(row)
            # Clear cached generation for this week so next GET sees the regenerated set.
            _WEEK_GENERATION_CACHE.pop(_generation_lock_key(user_id=current_user.id, plan_id=plan_id, week_number=week_number), None)
            await db.flush()

    if passed:
        plan = await _get_user_plan(db=db, user_id=current_user.id, plan_id=plan_id)
        role = await db.scalar(select(Role).where(Role.id == plan.role_id))
        role_name = role.name if role else "Target Role"
        roadmap = await _load_roadmap_from_db(
            db=db,
            plan=plan,
            role_name=role_name,
            hours_per_week=int(WEEK_HOUR_CAP_DEFAULT),
            readiness_score=0.0,
        )
        if int(week_number) < int(len(roadmap.weeks)):
            next_week_number = int(week_number) + 1
            background_tasks.add_task(
                ensure_week_assessment_generated_background,
                current_user.id,
                plan_id,
                next_week_number,
            )

    await db.commit()

    response_payload = {
        "plan_id": plan_id,
        "week_number": int(week_number),
        "score": score,
        "passed": passed,
        "correct_count": correct_count,
        "total": total,
        "status": row.status,
    }
    # Results are stored in report_json; UI reads them from history/report page.

    return response_payload


@router.get("/{plan_id}/{week_number}/history")
async def get_week_assessment_history(
    plan_id: str,
    week_number: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    if week_number < 1:
        raise HTTPException(status_code=400, detail="week_number must be >= 1")

    await _get_user_plan(db=db, user_id=current_user.id, plan_id=plan_id)
    row = await db.scalar(
        select(WeekAssessment).where(
            WeekAssessment.user_id == current_user.id,
            WeekAssessment.plan_id == plan_id,
            WeekAssessment.week_number == week_number,
        )
    )
    if not row:
        return {
            "plan_id": plan_id,
            "week_number": int(week_number),
            "attempts": [],
        }

    attempts = (
        await db.execute(
            select(WeekAssessmentAttempt)
            .where(
                WeekAssessmentAttempt.week_assessment_id == row.id,
                WeekAssessmentAttempt.user_id == current_user.id,
            )
            .order_by(desc(WeekAssessmentAttempt.attempted_at))
        )
    ).scalars().all()

    result = []
    for attempt in attempts:
        try:
            selected_answers = json.loads(attempt.answers_json or "[]")
        except Exception:
            selected_answers = []
        result.append(
            {
                "attempt_id": attempt.id,
                "score": float(attempt.score),
                "passed": bool(attempt.passed),
                "selected_answers": selected_answers,
                "attempted_at": attempt.attempted_at,
                "report": json.loads(attempt.report_json) if attempt.report_json else None,
            }
        )

    return {
        "plan_id": plan_id,
        "week_number": int(week_number),
        "status": row.status,
        "question_count": int(row.question_count),
        "attempts": result,
    }
