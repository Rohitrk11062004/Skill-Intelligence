"""
app/services/extraction/extraction_pipeline.py

Orchestrates the full Stage 3 extraction flow:
  1. Check quality score from Stage 2.8
  2. High quality  → Regex first, LLM only if regex finds < 5 skills
  3. Low quality   → LLM directly
  4. Merge results, deduplicate
  5. Normalize skill names
  6. Return unified skill list
"""
import logging
from dataclasses import dataclass

from app.services.extraction import regex_extractor, llm_extractor
from app.services.parsing.quality_router import ExtractionPath, QualityReport
from app.services.parsing.resume_parser import ParsedResume

log = logging.getLogger(__name__)

# If regex finds fewer than this, also run LLM
REGEX_MINIMUM_THRESHOLD = 999


@dataclass
class ExtractedSkill:
    name: str                  # normalized name
    raw_text: str              # as seen in resume
    category: str
    confidence: float
    source_section: str
    context: str = ""
    frequency: int = 1
    years_experience: float = 0.0
    extractor: str = "regex"   # regex | llm | both


async def run(
    parsed: ParsedResume,
    quality: QualityReport,
) -> list[ExtractedSkill]:
    """
    Run the full extraction pipeline for a parsed resume.

    Args:
        parsed: Output from ResumeParser
        quality: Output from quality_router

    Returns:
        Deduplicated list of ExtractedSkill objects
    """
    regex_results = []
    llm_results = []

    # ── Decide extraction path ────────────────────────────────────────────────
    if quality.extraction_path == ExtractionPath.HIGH_QUALITY:
        log.info("Running regex extraction (high quality parse)")
        regex_results = regex_extractor.extract_from_sections(parsed.sections)

        if len(regex_results) < REGEX_MINIMUM_THRESHOLD:
            log.info(
                f"Regex found only {len(regex_results)} skills "
                f"(threshold={REGEX_MINIMUM_THRESHOLD}) — also running LLM"
            )
            llm_results = await llm_extractor.extract(
                parsed.raw_text, parsed.sections
            )
        else:
            log.info(f"Regex found {len(regex_results)} skills — skipping LLM")

    else:
        log.info("Low quality parse — running LLM extraction directly")
        llm_results = await llm_extractor.extract(
            parsed.raw_text, parsed.sections
        )

    # ── Merge and deduplicate ─────────────────────────────────────────────────
    merged = _merge(regex_results, llm_results)
    log.info(f"Final skill count after merge: {len(merged)}")
    return merged


def _merge(
    regex_results: list,
    llm_results: list,
) -> list[ExtractedSkill]:
    """
    Merge regex and LLM results.
    Normalizes skill names to catch duplicates like React/ReactJS/React.js
    """
    skills: dict[str, ExtractedSkill] = {}

    def normalize_key(name: str) -> str:
        """Normalize skill name for deduplication."""
        key = name.lower().strip()
        # Remove all punctuation and spaces for clean comparison
        key = key.replace(".", "").replace("-", "").replace(" ", "").replace("_", "").replace("/", "")
        # Known aliases → canonical key
        alias_map = {
            # React variants
            "reactjs": "react",
            "react.js": "react",
            # Node variants
            "nodejs": "nodejs",
            "node.js": "nodejs",
            # Vue variants
            "vuejs": "vue",
            "vue.js": "vue",
            # Next variants
            "nextjs": "nextjs",
            "next.js": "nextjs",
            # Sklearn variants
            "scikit-learn": "scikitlearn",
            "sklearn": "scikitlearn",
            # Language variants
            "c++": "cpp",
            "c#": "csharp",
            # HuggingFace variants
            "huggingface": "huggingface",
            "hugging face": "huggingface",
            "huggingfacetransformers": "huggingface",
            # OOP variants — all map to same key
            "oops": "oop",
            "oop": "oop",
            "object-orientedprogramming": "oop",
            "object-orienteddesign": "oop",
            "objectoriented": "oop",
            # DSA variants
            "dsa": "dsa",
            "datastructures&algorithms": "dsa",
            "datastructuresandalgorithms": "dsa",
            "datastructures": "dsa",
            "algorithms": "dsa",
            # HITL variants
            "hitl": "hitl",
            "human-in-the-loop": "hitl",
            "humanintheloop": "hitl",
            # VSCode variants
            "vscode": "vscode",
            "vs code": "vscode",
            # Java variants
            "core java": "java",
            "java": "java",
        }
        return alias_map.get(key, key)

    def canonical_name(name: str) -> str:
        """Return the clean canonical display name."""
        canonical_map = {
            # React
            "reactjs": "React",
            "react.js": "React",
            "react": "React",
            # Node
            "nodejs": "Node.js",
            "node.js": "Node.js",
            # Vue / Next
            "vuejs": "Vue.js",
            "next.js": "Next.js",
            # Sklearn
            "scikit-learn": "Scikit-learn",
            "sklearn": "Scikit-learn",
            # HuggingFace
            "hugging face transformers": "HuggingFace Transformers",
            "huggingface transformers": "HuggingFace Transformers",
            "huggingface": "HuggingFace",
            # Languages
            "c++": "C++",
            "core java": "Java",
            # OOP — all variants → one canonical
            "oops": "Object-Oriented Programming",
            "oop": "Object-Oriented Programming",
            "object-oriented design": "Object-Oriented Programming",
            "object-oriented programming": "Object-Oriented Programming",
            # DSA — all variants → one canonical
            "dsa": "Data Structures & Algorithms",
            "algorithms": "Data Structures & Algorithms",
            "data structures": "Data Structures & Algorithms",
            "data structures & algorithms": "Data Structures & Algorithms",
            # HITL
            "hitl": "Human-in-the-Loop",
            "human-in-the-loop": "Human-in-the-Loop",
            # VSCode
            "vscode": "VS Code",
            "vs code": "VS Code",
        }
        return canonical_map.get(name.lower().strip(), name)
        return canonical_map.get(name.lower().strip(), name)

    # Add regex results
    for r in regex_results:
        key = normalize_key(r.raw_text)
        skills[key] = ExtractedSkill(
            name=canonical_name(r.raw_text),
            raw_text=r.raw_text,
            category=r.category,
            confidence=r.confidence,
            source_section=r.source_section,
            frequency=r.frequency,
            extractor="regex",
        )

    # Merge LLM results
    for r in llm_results:
        # Filter out overly generic or irrelevant skills
        if r.name.lower() in {
            "programming", "code optimization", "adaptability",
            "computer", "internet", "email", "microsoft office",
            "communication skills", "teamwork skills",
            "ethical behavior", "social responsibility",
            "logistics management", "logistics", "operations management",
            "team coordination", "team collaboration",
            "community service", "event management", "event planning",
        }:
            continue

        # Skip low-value skills from extracurricular section
        if r.source_section == "extracurricular" and r.category == "soft_skills":
            continue

        key = normalize_key(r.name)
        if key in skills:
            existing = skills[key]
            existing.confidence = max(existing.confidence, r.confidence)
            existing.extractor = "both"
            if r.context and not existing.context:
                existing.context = r.context
            if r.years_experience > existing.years_experience:
                existing.years_experience = r.years_experience
        else:
            skills[key] = ExtractedSkill(
                name=canonical_name(r.name),
                raw_text=r.name,
                category=r.category,
                confidence=r.confidence,
                source_section=r.source_section,
                context=r.context,
                years_experience=r.years_experience,
                extractor="llm",
            )

    return sorted(
        skills.values(),
        key=lambda x: (x.confidence, x.frequency),
        reverse=True,
    )