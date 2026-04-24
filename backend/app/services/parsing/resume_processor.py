"""
app/services/parsing/resume_processor.py

Orchestrates the full pipeline for a single resume:
  Stage 2   — Parse (text extraction + section detection)
  Stage 2.8 — Quality routing
  Stage 3   — Skill extraction (regex + LLM)
  Stage 3.3 — Skill normalization
  Stage 5   — Feature engineering
  DB        — Persist all results
"""
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ExtractedSkill as ExtractedSkillModel
from app.models.models import Resume, Skill, UserSkillScore
from app.services.extraction.extraction_pipeline import run as run_extraction
from app.services.normalization.skill_normalizer import skill_normalizer
from app.services.parsing.quality_router import QualityReport, route
from app.services.parsing.resume_parser import ParsedResume, resume_parser

log = logging.getLogger(__name__)


async def process_resume(
    resume_id: str,
    db: AsyncSession,
) -> dict:
    """
    Full pipeline for a single resume.
    Returns summary dict with extracted skills and stats.
    """
    # ── Fetch resume ──────────────────────────────────────────────────────────
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise ValueError(f"Resume {resume_id} not found")

    resume.status = "parsing"
    await db.flush()

    try:
        # ── Stage 2: Parse ────────────────────────────────────────────────────
        log.info(f"Parsing resume {resume_id}")
        parsed = resume_parser.parse(resume.file_path)

        # ── Stage 2.8: Quality routing ────────────────────────────────────────
        quality = route(parsed)

        # Persist parse results
        resume.raw_text        = parsed.raw_text
        resume.parsed_sections = json.dumps({
            **parsed.sections,
            **{f"misc_{k}": v for k, v in parsed.misc_sections.items()},
        })
        resume.parse_confidence = parsed.parse_confidence
        resume.layout_type      = parsed.layout_type
        await db.flush()

        # ── Stage 3: Skill extraction ─────────────────────────────────────────
        log.info(f"Extracting skills — path: {quality.extraction_path.value}")
        resume.status = "extracting"
        await db.flush()

        extracted = await run_extraction(parsed, quality)

        # ── Stage 3.3: Normalize + persist skills ─────────────────────────────
        saved_count = 0
        seen_skill_names: set[str] = set()  # prevent duplicate skill names
        for skill in extracted:
            # Normalize to your internal taxonomy
            norm = await skill_normalizer.normalize(skill.name, db)
            # Deduplicate by canonical name — skip if already saved this run
            display_name = (norm.canonical_name or skill.name).strip().lower()
            if display_name in seen_skill_names:
                continue
            seen_skill_names.add(display_name)

            skill_id = None
            if norm.canonical_skill_id:
                skill_id = norm.canonical_skill_id
            else:
                # New skill not in taxonomy yet — add it
                new_skill = Skill(
                    name       = norm.canonical_name or skill.name,
                    skill_type = skill.category,
                    category   = skill.category,
                    aliases    = json.dumps([skill.raw_text]),
                )
                db.add(new_skill)
                await db.flush()
                skill_id = new_skill.id

            # Save extracted skill record
            # Check if already exists (re-processing case)
            existing = await db.execute(
                select(ExtractedSkillModel).where(
                    ExtractedSkillModel.resume_id == resume.id,
                    ExtractedSkillModel.skill_id  == skill_id,
                )
            )
            if existing.scalar_one_or_none():
                continue

            db.add(ExtractedSkillModel(
                resume_id      = resume.id,
                skill_id       = skill_id,
                raw_text       = skill.raw_text,
                extractor      = skill.extractor,
                confidence     = skill.confidence,
                source_section = skill.source_section,
                source_text    = skill.context,
                frequency      = skill.frequency,
            ))

            # ── Stage 5: Upsert user skill score ──────────────────────────────
            existing_score = await db.execute(
                select(UserSkillScore).where(
                    UserSkillScore.user_id  == resume.user_id,
                    UserSkillScore.skill_id == skill_id,
                )
            )
            score_row = existing_score.scalar_one_or_none()

            # Simple proficiency rule (Stage 6 Phase 1)
            proficiency = _estimate_proficiency(
                years=skill.years_experience,
                frequency=skill.frequency,
                confidence=skill.confidence,
            )

            if score_row:
                # Update if new data is better
                if skill.confidence > score_row.proficiency_score:
                    score_row.years_of_experience   = skill.years_experience or score_row.years_of_experience
                    score_row.frequency             = max(skill.frequency, score_row.frequency)
                    score_row.proficiency           = proficiency
                    score_row.proficiency_score     = skill.confidence
                    score_row.context_strength      = skill.confidence
            else:
                db.add(UserSkillScore(
                    user_id             = resume.user_id,
                    skill_id            = skill_id,
                    proficiency         = proficiency,
                    proficiency_score   = skill.confidence,
                    years_of_experience = skill.years_experience,
                    frequency           = skill.frequency,
                    context_strength    = skill.confidence,
                ))

            saved_count += 1

        # ── Mark complete ─────────────────────────────────────────────────────
        resume.status       = "complete"
        resume.processed_at = datetime.now(timezone.utc)
        await db.flush()

        log.info(f"Resume {resume_id} complete — {saved_count} skills saved")

        return {
            "resume_id":        resume.id,
            "status":           "complete",
            "parse_confidence": parsed.parse_confidence,
            "extraction_path":  quality.extraction_path.value,
            "sections_found":   list(parsed.sections.keys()),
            "skills_extracted": saved_count,
            "warnings":         quality.warnings,
        }

    except Exception as e:
        log.error(f"Processing failed for resume {resume_id}: {e}")
        resume.status        = "failed"
        resume.error_message = str(e)
        await db.flush()
        raise


def _estimate_proficiency(
    years: float,
    frequency: int,
    confidence: float,
    ) -> str:
    """
    Stage 6 Phase 1 — rule-based proficiency estimation.
    
    Scoring:
    - frequency >= 3 mentions across resume = strong signal
    - years_experience > 0 = direct evidence
    - confidence from skills section = higher weight
    """
    score = 0.0

    # Years of experience (0–5 years maps to 0–0.5)
    score += min(years / 5.0, 1.0) * 0.5

    # Frequency — how many times skill appears across resume
    if frequency >= 5:
        score += 0.4
    elif frequency >= 3:
        score += 0.3
    elif frequency >= 2:
        score += 0.2
    else:
        score += 0.1

    # Confidence boost — skills section mention = more reliable
    if confidence >= 0.95:
        score += 0.15
    elif confidence >= 0.85:
        score += 0.10

    if score >= 0.60:
        return "advanced"
    elif score >= 0.30:
        return "intermediate"
    else:
        return "beginner"