"""
tests/unit/test_resume_parser.py

Unit tests for Stage 2 — ResumeParser and quality routing.
No DB or file I/O required — tests use synthetic text input directly.
"""
import pytest
from app.services.parsing.resume_parser import ResumeParser, SECTION_ALIASES
from app.services.parsing.quality_router import ExtractionPath, route
from app.services.parsing.resume_parser import ParsedResume


# ── Fixtures ───────────────────────────────────────────────────────────────────

GOOD_RESUME_TEXT = """
John Doe
john@example.com | +91 9876543210 | Hyderabad

PROFESSIONAL SUMMARY
Software engineer with 4 years of experience in backend systems.

WORK EXPERIENCE
Software Engineer — Acme Corp (2021–2024)
- Built REST APIs using FastAPI and Python
- Managed PostgreSQL databases, wrote complex SQL queries
- Deployed services on AWS EC2 and Docker

TECHNICAL SKILLS
Python, FastAPI, PostgreSQL, Docker, AWS, Redis, Git, Linux

EDUCATION
B.Tech Computer Science — JNTU Hyderabad (2017–2021)

PROJECTS
Inventory Management System
- Built with Django, PostgreSQL, deployed on Heroku
- Served 500+ daily active users
"""

GARBLED_RESUME_TEXT = """
\x00\x01\x02\xffJohn\x00\x01 Doe\x02\xff
\x00\x01skills\x02\xff Python\x00\x01 Java
\x00\x01\x02\xffExperience\x00\x01 \x02\xff at company
"""

MINIMAL_RESUME_TEXT = """
John Doe
Python Developer
Email: john@test.com
"""

NO_SECTIONS_TEXT = """
Experienced software engineer with skills in Python, FastAPI, PostgreSQL.
Worked at Acme Corp for 3 years building backend APIs.
Graduated from JNTU in 2020 with B.Tech CS.
"""


# ── Parser tests ───────────────────────────────────────────────────────────────

class TestResumeParser:
    def setup_method(self):
        self.parser = ResumeParser()

    def test_section_detection_good_resume(self):
        """Should correctly identify all major sections."""
        parsed = self._parse_text(GOOD_RESUME_TEXT)
        assert "experience" in parsed.sections
        assert "skills" in parsed.sections
        assert "education" in parsed.sections
        assert "projects" in parsed.sections
        assert "summary" in parsed.sections

    def test_section_content_not_empty(self):
        """Each detected section should have meaningful content."""
        parsed = self._parse_text(GOOD_RESUME_TEXT)
        for section, content in parsed.sections.items():
            assert len(content.strip()) > 10, f"Section '{section}' is too short"

    def test_skills_section_contains_skills(self):
        """Skills section should contain the actual skill list."""
        parsed = self._parse_text(GOOD_RESUME_TEXT)
        assert "skills" in parsed.sections
        skills_text = parsed.sections["skills"].lower()
        assert "python" in skills_text
        assert "postgresql" in skills_text

    def test_no_sections_falls_back_to_misc(self):
        """Resume with no headers → full text in misc_sections."""
        parsed = self._parse_text(NO_SECTIONS_TEXT)
        assert len(parsed.sections) == 0
        assert len(parsed.misc_sections) > 0

    def test_parse_confidence_good_resume(self):
        """Well-structured resume should get high confidence."""
        parsed = self._parse_text(GOOD_RESUME_TEXT)
        assert parsed.parse_confidence >= 0.7, (
            f"Expected confidence >= 0.7, got {parsed.parse_confidence}"
        )

    def test_parse_confidence_minimal_resume(self):
        """Very minimal text should get low confidence."""
        parsed = self._parse_text(MINIMAL_RESUME_TEXT)
        assert parsed.parse_confidence < 0.7

    def test_garble_detection(self):
        """Garbled text should produce a warning and low confidence."""
        parsed = self._parse_text(GARBLED_RESUME_TEXT)
        assert parsed.parse_confidence < 0.5
        assert any("symbol" in w.lower() or "encoding" in w.lower()
                   for w in parsed.warnings), \
            f"Expected garble warning, got: {parsed.warnings}"

    def test_section_alias_uppercase(self):
        """ALL CAPS section headers should be detected."""
        text = "WORK EXPERIENCE\nSoftware Engineer at Acme\n\nSKILLS\nPython, Java"
        parsed = self._parse_text(text)
        assert "experience" in parsed.sections
        assert "skills" in parsed.sections

    def test_section_alias_with_colon(self):
        """Headers ending with colon should be detected."""
        text = "Technical Skills:\nPython, FastAPI, Docker\n\nEducation:\nB.Tech CS"
        parsed = self._parse_text(text)
        assert "skills" in parsed.sections
        assert "education" in parsed.sections

    def test_misc_sections_preserved(self):
        """Unrecognised section headers should be kept in misc, not discarded."""
        text = "INTERESTS\nPlaying chess and reading\n\nHOBBIES\nCoding side projects"
        parsed = self._parse_text(text)
        # Should be in misc, not dropped
        assert len(parsed.misc_sections) > 0

    def _parse_text(self, text: str) -> "ParsedResume":
        """Helper to run section detection + confidence scoring on raw text."""
        from app.services.parsing.resume_parser import ParsedResume
        result = ParsedResume(raw_text=text)
        result.sections, result.misc_sections = self.parser._detect_sections(text)
        result.parse_confidence = self.parser._score_confidence(result)
        return result


# ── Section alias vocabulary tests ────────────────────────────────────────────

class TestSectionAliases:
    def test_all_aliases_map_to_valid_canonical(self):
        """Every alias must map to a known canonical section name."""
        from app.services.parsing.resume_parser import CANONICAL_SECTIONS
        for alias, canonical in SECTION_ALIASES.items():
            assert canonical in CANONICAL_SECTIONS, \
                f"Alias '{alias}' maps to unknown canonical '{canonical}'"

    def test_key_aliases_present(self):
        """Spot-check that critical aliases exist."""
        assert SECTION_ALIASES.get("work experience") == "experience"
        assert SECTION_ALIASES.get("technical skills") == "skills"
        assert SECTION_ALIASES.get("academic background") == "education"
        assert SECTION_ALIASES.get("personal projects") == "projects"
        assert SECTION_ALIASES.get("professional summary") == "summary"


# ── Quality router tests ───────────────────────────────────────────────────────

class TestQualityRouter:
    def _make_parsed(self, sections: dict, raw_text: str = "x" * 2500,
                     confidence: float = 0.0, warnings=None) -> ParsedResume:
        p = ParsedResume(
            raw_text=raw_text,
            sections=sections,
            parse_confidence=confidence,
            warnings=warnings or [],
        )
        return p

    def test_high_quality_routes_to_regex_ner(self):
        """Score >= 0.7 should route to high quality (Regex/NER) path."""
        parsed = self._make_parsed(
            sections={"skills": "Python", "experience": "3 years", "education": "B.Tech"},
            confidence=0.80,
        )
        report = route(parsed)
        assert report.extraction_path == ExtractionPath.HIGH_QUALITY

    def test_low_quality_routes_to_llm_direct(self):
        """Score < 0.7 should route directly to LLM."""
        parsed = self._make_parsed(
            sections={},
            raw_text="x" * 100,
            confidence=0.40,
        )
        report = route(parsed)
        assert report.extraction_path == ExtractionPath.LOW_QUALITY

    def test_threshold_boundary_high(self):
        """Exactly 0.70 should be HIGH quality."""
        parsed = self._make_parsed(sections={"skills": "Python"}, confidence=0.70)
        report = route(parsed)
        assert report.extraction_path == ExtractionPath.HIGH_QUALITY

    def test_threshold_boundary_low(self):
        """0.69 should be LOW quality."""
        parsed = self._make_parsed(sections={}, confidence=0.69)
        report = route(parsed)
        assert report.extraction_path == ExtractionPath.LOW_QUALITY

    def test_warning_added_for_no_key_sections(self):
        """Missing both skills and experience should generate a warning."""
        parsed = self._make_parsed(sections={"education": "B.Tech"}, confidence=0.30)
        report = route(parsed)
        assert len(report.warnings) > 0

    def test_section_coverage_reported(self):
        """Section coverage should reflect what was actually found."""
        parsed = self._make_parsed(
            sections={"skills": "Python", "projects": "My app"},
            confidence=0.50,
        )
        report = route(parsed)
        assert report.section_coverage["skills"] is True
        assert report.section_coverage["projects"] is True
        assert report.section_coverage["experience"] is False
        assert report.section_coverage["education"] is False
