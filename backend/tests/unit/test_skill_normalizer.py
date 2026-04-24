"""
tests/unit/test_skill_normalizer.py

Unit tests for Stage 3.3 — SkillNormalizer.
Uses a mock alias index so no DB is needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.normalization.skill_normalizer import SkillNormalizer, NormalizationResult


def make_normalizer(alias_index: dict) -> SkillNormalizer:
    """Create a normalizer with a pre-populated alias index (no DB needed)."""
    n = SkillNormalizer()
    n._alias_index = alias_index
    n._initialized = True
    return n


SAMPLE_INDEX = {
    "javascript":         ("uuid-js-001", "JavaScript"),
    "js":                 ("uuid-js-001", "JavaScript"),
    "ecmascript":         ("uuid-js-001", "JavaScript"),
    "python":             ("uuid-py-001", "Python"),
    "py":                 ("uuid-py-001", "Python"),
    "react":              ("uuid-react-001", "React"),
    "reactjs":            ("uuid-react-001", "React"),
    "react.js":           ("uuid-react-001", "React"),
    "postgresql":         ("uuid-pg-001", "PostgreSQL"),
    "postgres":           ("uuid-pg-001", "PostgreSQL"),
    "machine learning":   ("uuid-ml-001", "Machine Learning"),
}


class TestSkillNormalizerExactMatch:
    def setup_method(self):
        self.normalizer = make_normalizer(SAMPLE_INDEX)
        self.db = AsyncMock()

    @pytest.mark.asyncio
    async def test_exact_canonical_match(self):
        result = await self.normalizer.normalize("Python", self.db)
        assert result.canonical_name == "Python"
        assert result.match_type == "exact"
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_alias_match_js(self):
        result = await self.normalizer.normalize("JS", self.db)
        assert result.canonical_name == "JavaScript"
        assert result.match_type == "alias"
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_alias_match_reactjs(self):
        result = await self.normalizer.normalize("ReactJS", self.db)
        assert result.canonical_name == "React"
        assert result.match_type == "alias"

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        """Normalizer should be case-insensitive."""
        result = await self.normalizer.normalize("PYTHON", self.db)
        assert result.canonical_name == "Python"

    @pytest.mark.asyncio
    async def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be ignored."""
        result = await self.normalizer.normalize("  JavaScript  ", self.db)
        assert result.canonical_name == "JavaScript"

    @pytest.mark.asyncio
    async def test_multi_word_skill(self):
        result = await self.normalizer.normalize("Machine Learning", self.db)
        assert result.canonical_name == "Machine Learning"
        assert result.match_type == "exact"


class TestSkillNormalizerNoMatch:
    def setup_method(self):
        self.normalizer = make_normalizer(SAMPLE_INDEX)
        # Disable embedding fallback for unit tests
        self.normalizer._get_encoder = lambda: None
        self.db = AsyncMock()

    @pytest.mark.asyncio
    async def test_unknown_skill_returns_no_match(self):
        result = await self.normalizer.normalize("XYZ_UNKNOWN_SKILL_123", self.db)
        assert result.match_type == "no_match"
        assert result.canonical_skill_id is None
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_no_match_preserves_raw_text(self):
        result = await self.normalizer.normalize("SomeObscureTool", self.db)
        assert result.raw_text == "SomeObscureTool"


class TestSkillNormalizerBatch:
    def setup_method(self):
        self.normalizer = make_normalizer(SAMPLE_INDEX)
        self.normalizer._get_encoder = lambda: None
        self.db = AsyncMock()

    @pytest.mark.asyncio
    async def test_batch_normalize_all_known(self):
        skills = ["Python", "JS", "React", "PostgreSQL"]
        results = await self.normalizer.normalize_batch(skills, self.db)
        assert len(results) == 4
        names = [r.canonical_name for r in results]
        assert "Python" in names
        assert "JavaScript" in names
        assert "React" in names
        assert "PostgreSQL" in names

    @pytest.mark.asyncio
    async def test_batch_preserves_order(self):
        """Results must be in the same order as input."""
        skills = ["Python", "JS", "PostgreSQL"]
        results = await self.normalizer.normalize_batch(skills, self.db)
        assert results[0].canonical_name == "Python"
        assert results[1].canonical_name == "JavaScript"
        assert results[2].canonical_name == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_batch_mixed_known_unknown(self):
        skills = ["Python", "ObscureTool99", "React"]
        results = await self.normalizer.normalize_batch(skills, self.db)
        assert results[0].canonical_name == "Python"
        assert results[1].match_type == "no_match"
        assert results[2].canonical_name == "React"

    @pytest.mark.asyncio
    async def test_batch_empty_list(self):
        results = await self.normalizer.normalize_batch([], self.db)
        assert results == []
