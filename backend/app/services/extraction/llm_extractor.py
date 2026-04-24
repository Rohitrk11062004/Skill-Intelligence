"""
app/services/extraction/llm_extractor.py

Stage 3.1 — Layer 2 (LLM fallback) of the extraction chain.
Uses Gemini to extract skills from resume text.
Called when:
  - Parse quality score < 0.7 (low quality parse)
  - Regex extraction returns < 5 skills (insufficient coverage)
"""
import json
import logging
from dataclasses import dataclass

from langsmith import traceable

from app.services.llm.llm_client import gemini_generate

log = logging.getLogger(__name__)


@dataclass
class LLMExtractedSkill:
    name: str
    category: str           # technical | soft | tool | language | domain
    confidence: float       # 0.0 – 1.0
    source_section: str     # which part of resume
    context: str            # surrounding sentence for evidence
    years_experience: float = 0.0


# ── Extraction prompt ─────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """
You are an expert HR analyst extracting skills from a resume.

Extract ALL skills mentioned in the resume text below.
For each skill include:
- name: exact skill name (normalize variations — "JS" → "JavaScript", "ReactJS" → "React")
- category: pick the MOST SPECIFIC category from this list:
  * languages    → programming languages (Python, Java, SQL, C++)
  * frontend     → UI frameworks and web tech (React, HTML, CSS, Flutter)
  * backend      → server frameworks and APIs (FastAPI, Node.js, REST, GraphQL)
  * databases    → databases and storage (PostgreSQL, MongoDB, Firebase)
  * cloud        → cloud platforms (AWS, GCP, Azure)
  * devops       → infrastructure and CI/CD (Docker, Kubernetes, Git)
  * ml_ai        → ML, AI, data science, NLP (TensorFlow, LangChain, NLP, HITL)
  * tools        → development tools and IDEs (VS Code, JIRA, Postman)
  * soft_skills  → interpersonal and professional skills (Communication, Leadership)
  * technical    → CS fundamentals (DSA, OOP, DBMS, SDLC, Algorithms)
- confidence: 0.0–1.0 (how confident you are this is a real skill)
- source_section: where in resume (experience, skills, projects, education, summary)
- context: the sentence or phrase where this skill appears
- years_experience: estimate years of experience from context clues:
  * If actively used in a current internship/job = 0.5
  * If used across multiple projects = 0.5
  * If explicitly mentioned "X years" = use that number
  * If only listed in skills section with no usage context = 0
  * Maximum value = 10

Rules:
- Include technical skills, tools, frameworks, languages, soft skills
- Normalize aliases: "JS" → "JavaScript", "Postgres" → "PostgreSQL", "ML" → "Machine Learning"
- Do NOT include generic words like "computer", "internet", "email"
- Do NOT hallucinate skills not present in the text
- Do NOT extract vague soft skills from extracurricular sections (e.g. "ethical behavior", "social responsibility", "logistics management")
- Deduplicate: "Object-Oriented Programming" and "Object-Oriented Design" are the same → use "Object-Oriented Programming" only
- Deduplicate: "Team Coordination" and "Team Collaboration" and "Teamwork" → use "Teamwork" only
- Return ONLY valid JSON, no explanation, no markdown

Resume text:
{resume_text}

Return JSON in exactly this format:
{{
  "skills": [
    {{
      "name": "Python",
      "category": "language",
      "confidence": 0.95,
      "source_section": "experience",
      "context": "Built REST APIs using Python and FastAPI",
      "years_experience": 3.0
    }}
  ]
}}
"""


@traceable(name="gemini_resume_skill_extraction", run_type="llm")
async def extract(
    resume_text: str,
    sections: dict[str, str] | None = None,
) -> list[LLMExtractedSkill]:
    """
    Extract skills from resume text using Gemini.

    Args:
        resume_text: Full resume text or section content
        sections: Optional dict of sections for better context

    Returns:
        List of LLMExtractedSkill objects
    """
    if not resume_text.strip():
        return []

    # Use sections if available for better extraction
    text_to_use = resume_text
    if sections:
        # Combine sections with labels for better context
        labeled = []
        for section, content in sections.items():
            if content.strip():
                labeled.append(f"[{section.upper()}]\n{content}")
        if labeled:
            text_to_use = "\n\n".join(labeled)

    # Trim to avoid token limits
    text_to_use = text_to_use[:8000]

    try:
        prompt = EXTRACTION_PROMPT.format(resume_text=text_to_use)

        log.info("Calling Gemini for skill extraction...")
        raw = (await gemini_generate(
            purpose="resume_skill_extraction",
            prompt=prompt,
        )).strip()

        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        skills_data = data.get("skills", [])

        results = []
        for s in skills_data:
            try:
                results.append(LLMExtractedSkill(
                    name=s.get("name", "").strip(),
                    category=s.get("category", "technical"),
                    confidence=float(s.get("confidence", 0.8)),
                    source_section=s.get("source_section", ""),
                    context=s.get("context", ""),
                    years_experience=float(s.get("years_experience", 0.0)),
                ))
            except Exception as e:
                log.warning(f"Skipping malformed skill entry: {e}")
                continue

        # Filter out low confidence and empty names
        results = [r for r in results if r.name and r.confidence >= 0.5]
        log.info(f"Gemini extracted {len(results)} skills")
        return results

    except json.JSONDecodeError as e:
        log.error(f"Gemini returned invalid JSON: {e}")
        return []
    except Exception as e:
        log.error(f"Gemini extraction failed: {e}")
        return []