"""
app/services/parsing/quality_router.py

Stage 2.8 — Data Quality Layer

Scores a parsed resume and decides which extraction path to use:
  - score >= 0.7  →  HIGH quality  →  Regex → NER → LLM fallback chain
  - score <  0.7  →  LOW quality   →  Skip to LLM directly

This prevents regex/NER from producing garbage on garbled or
poorly-parsed input (e.g. image-based PDFs, corrupted encoding).
"""
import logging
from dataclasses import dataclass
from enum import Enum

from app.services.parsing.resume_parser import ParsedResume

log = logging.getLogger(__name__)

HIGH_QUALITY_THRESHOLD = 0.70


class ExtractionPath(str, Enum):
    HIGH_QUALITY = "high_quality"   # Regex → NER → LLM fallback
    LOW_QUALITY  = "low_quality"    # LLM direct


@dataclass
class QualityReport:
    parse_confidence: float
    extraction_path: ExtractionPath
    section_coverage: dict[str, bool]   # which key sections were found
    warnings: list[str]
    recommendation: str


def route(parsed: ParsedResume) -> QualityReport:
    """
    Evaluate parse quality and decide the extraction path.

    Args:
        parsed: Output from ResumeParser.parse()

    Returns:
        QualityReport with routing decision and diagnostic info
    """
    score = parsed.parse_confidence
    found_sections = set(parsed.sections.keys())

    section_coverage = {
        "skills":          "skills"     in found_sections,
        "experience":      "experience" in found_sections,
        "education":       "education"  in found_sections,
        "projects":        "projects"   in found_sections,
    }

    warnings = list(parsed.warnings)

    # Extra warnings based on coverage
    if not section_coverage["skills"] and not section_coverage["experience"]:
        warnings.append("Neither skills nor experience section found — text may be image-based")

    if not parsed.raw_text.strip():
        warnings.append("Empty text — PDF may be scanned image, OCR needed")

    # Routing decision
    if score >= HIGH_QUALITY_THRESHOLD:
        path = ExtractionPath.HIGH_QUALITY
        recommendation = (
            f"Score {score:.2f} ≥ {HIGH_QUALITY_THRESHOLD} → "
            "Use Regex → NER → LLM fallback chain"
        )
    else:
        path = ExtractionPath.LOW_QUALITY
        recommendation = (
            f"Score {score:.2f} < {HIGH_QUALITY_THRESHOLD} → "
            "Skip to LLM directly for best extraction quality"
        )

    log.info(
        "quality_routing",
        extra={
            "score": score,
            "path": path.value,
            "sections_found": list(found_sections),
            "warnings": warnings,
        }
    )

    return QualityReport(
        parse_confidence=score,
        extraction_path=path,
        section_coverage=section_coverage,
        warnings=warnings,
        recommendation=recommendation,
    )
