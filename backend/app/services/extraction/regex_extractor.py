"""
app/services/extraction/regex_extractor.py

Stage 3.1 — Layer 1 of the extraction fallback chain.
Fast keyword-based skill extraction using regex.
No ML, no API calls — runs in milliseconds.
Covers ~60% of skills in a well-structured resume.
"""
import re
import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ── Master skill keyword list ─────────────────────────────────────────────────

SKILL_PATTERNS: dict[str, list[str]] = {
    "languages": [
        "Python", "Java", "JavaScript", "TypeScript", "C\\+\\+", "C#",
        "Go", "Golang", "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala",
        "R", "MATLAB", "Perl", "Shell", "Bash", "PowerShell",
        "SQL", "Core Java",
    ],
    "frontend": [
        "React", "ReactJS", "React\\.js", "Angular", "AngularJS", "Vue",
        "Vue\\.js", "Next\\.js", "Nuxt\\.js", "HTML", "CSS", "SASS", "SCSS",
        "Tailwind", "Bootstrap", "jQuery", "Redux", "GraphQL", "REST",
        "HTML5", "CSS3", "Flutter", "Streamlit",
    ],
    "backend": [
        "FastAPI", "Django", "Flask", "Spring", "Spring Boot", "Express",
        "Node\\.js", "NodeJS", "Laravel", "Rails", "ASP\\.NET", "Gin",
        "FastHTTP", "Fiber", "LiveKit",
    ],
    "databases": [
        "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Cassandra",
        "DynamoDB", "Elasticsearch", "Oracle", "SQL Server", "MariaDB",
        "Firebase", "Supabase", "Neo4j",
    ],
    "cloud": [
        "AWS", "GCP", "Azure", "Google Cloud", "Heroku", "Vercel",
        "Netlify", "DigitalOcean", "Cloudflare",
    ],
    "devops": [
        "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins",
        "GitHub Actions", "GitLab CI", "CircleCI", "ArgoCD", "Helm",
        "Prometheus", "Grafana", "Nginx", "Apache",
    ],
    "ml_ai": [
        "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
        "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "scikit-learn",
        "Pandas", "NumPy", "Matplotlib", "Seaborn", "Hugging Face",
        "HuggingFace", "HuggingFace Transformers", "LangChain", "LangGraph",
        "OpenAI", "Gemini", "LLM", "Speech-to-Text", "Text-to-Speech",
        "Natural Language Processing", "Transformer",
    ],
    "technical": [
        "Data Structures", "Algorithms", "DSA",
        "Object-Oriented Programming", "OOP", "OOPS",
        "DBMS", "Database Management",
        "SDLC", "Software Engineering",
        "Operating Systems", "Computer Networks",
        "System Design", "Design Patterns",
        "Human-in-the-Loop", "HITL",
    ],
    "tools": [
        "Git", "GitHub", "GitLab", "Bitbucket", "JIRA", "Confluence",
        "Postman", "Swagger", "VS Code", "IntelliJ", "Linux", "Unix",
        "Kafka", "RabbitMQ", "Celery", "Airflow",
        "Unreal Engine", "MS Excel", "Sarvam",
    ],
    "soft_skills": [
        "Communication", "Leadership", "Teamwork", "Problem Solving",
        "Critical Thinking", "Agile", "Scrum", "Kanban",
    ],
}

# Flatten into a single compiled pattern
ALL_SKILLS: list[str] = []
for skills in SKILL_PATTERNS.values():
    ALL_SKILLS.extend(skills)


@dataclass
class RegexMatch:
    raw_text: str
    normalized: str       # lowercased canonical form
    category: str
    confidence: float = 0.9
    source_section: str = ""
    frequency: int = 1


def _find_category(skill_name: str) -> str:
    for category, skills in SKILL_PATTERNS.items():
        for s in skills:
            if re.sub(r"\\", "", s).lower() == skill_name.lower():
                return category
    return "general"


def extract(text: str, source_section: str = "") -> list[RegexMatch]:
    """
    Extract skills from text using regex pattern matching.

    Args:
        text: Raw text to search (section content or full resume)
        source_section: Which resume section this text came from

    Returns:
        List of RegexMatch objects, deduplicated, sorted by frequency
    """
    if not text:
        return []

    found: dict[str, RegexMatch] = {}  # normalized → RegexMatch

    for skill_pattern in ALL_SKILLS:
        # Word boundary match, case insensitive
        pattern = r"(?<![a-zA-Z0-9])" + skill_pattern + r"(?![a-zA-Z0-9])"
        try:
            matches = re.findall(pattern, text, re.IGNORECASE)
        except re.error:
            continue

        if matches:
            raw = matches[0]
            normalized = re.sub(r"\\", "", skill_pattern).lower()
            canonical = re.sub(r"\\", "", skill_pattern)

            if normalized in found:
                found[normalized].frequency += len(matches)
            else:
                found[normalized] = RegexMatch(
                    raw_text=raw,
                    normalized=normalized,
                    category=_find_category(canonical),
                    confidence=0.9,
                    source_section=source_section,
                    frequency=len(matches),
                )

    # Sort by frequency descending
    return sorted(found.values(), key=lambda x: x.frequency, reverse=True)


def extract_from_sections(sections: dict[str, str]) -> list[RegexMatch]:
    """
    Run regex extraction across all resume sections.
    Tracks which section each skill came from.
    Higher confidence for skills found in dedicated skills section.
    """
    all_matches: dict[str, RegexMatch] = {}

    section_confidence = {
        "skills": 1.0,
        "experience": 0.85,
        "projects": 0.85,
        "summary": 0.75,
        "education": 0.70,
    }

    for section_name, content in sections.items():
        confidence_boost = section_confidence.get(section_name, 0.75)
        matches = extract(content, source_section=section_name)

        for match in matches:
            if match.normalized in all_matches:
                # Already found — increase frequency, update source if higher confidence
                existing = all_matches[match.normalized]
                existing.frequency += match.frequency
                if confidence_boost > existing.confidence:
                    existing.confidence = confidence_boost
                    existing.source_section = section_name
            else:
                match.confidence = confidence_boost
                all_matches[match.normalized] = match

    return sorted(all_matches.values(), key=lambda x: x.frequency, reverse=True)