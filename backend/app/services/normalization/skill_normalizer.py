"""
app/services/normalization/skill_normalizer.py

Maps raw extracted skill text → canonical skill in YOUR internal taxonomy.
Taxonomy is built from JDs ingested via POST /api/v1/roles/ingest-jd.

Two-stage approach:
  1. Exact / alias lookup  (fast, zero cost)
  2. Embedding cosine similarity  (fallback for unknowns)

The normalizer is a singleton — load once at startup, reuse across requests.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Skill

log = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.72


@dataclass
class NormalizationResult:
    raw_text: str
    canonical_skill_id: Optional[str]
    canonical_name: Optional[str]
    match_type: str        # "exact" | "alias" | "embedding" | "no_match"
    confidence: float      # 0.0 – 1.0


class SkillNormalizer:
    """
    Normalizes raw skill strings to canonical ESCO skills.

    Usage:
        normalizer = SkillNormalizer()
        await normalizer.initialize(db)        # once at startup
        result = await normalizer.normalize("JS", db)
    """

    def __init__(self):
        self._encoder = None
        self._alias_index: dict[str, tuple[str, str]] = {}
        self._initialized = False
        self._embedding_disabled = False

    # ── Initialization ────────────────────────────────────────────────────────

    async def initialize(self, db: AsyncSession) -> None:
        if self._initialized:
            return
        log.info("Initializing skill normalizer...")
        await self._build_alias_index(db)
        self._initialized = True
        log.info(f"Alias index loaded: {len(self._alias_index):,} entries")

    async def _build_alias_index(self, db: AsyncSession) -> None:
        import json
        result = await db.execute(select(Skill.id, Skill.name, Skill.aliases))
        rows = result.fetchall()
        for skill_id, name, aliases in rows:
            sid = str(skill_id)
            self._alias_index[name.lower()] = (sid, name)
            if aliases:
                parsed_aliases: list[str] = []
                if isinstance(aliases, str):
                    try:
                        payload = json.loads(aliases)
                        if isinstance(payload, list):
                            parsed_aliases = [str(x) for x in payload]
                    except Exception:
                        parsed_aliases = []
                elif isinstance(aliases, list):
                    parsed_aliases = [str(x) for x in aliases]

                for alias in parsed_aliases:
                    alias = str(alias or "").strip()
                    if alias:
                        self._alias_index[alias.lower()] = (sid, name)

    def _get_encoder(self):
        if self._embedding_disabled:
            return None
        if self._encoder is None:
            try:
                from sentence_transformers import SentenceTransformer
                log.info("Loading sentence-transformers model (MiniLM)...")
                self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
                log.info("Model loaded")
            except ImportError as e:
                log.warning(f"sentence-transformers not installed — embedding fallback disabled ({e})")
                self._embedding_disabled = True
            except OSError as e:
                # Common on Windows when torch native deps are missing (e.g. fbgemm.dll).
                log.warning(f"Embedding encoder unavailable — embedding fallback disabled ({e})")
                self._embedding_disabled = True
            except Exception as e:
                log.warning(f"Embedding encoder init failed — embedding fallback disabled ({e})")
                self._embedding_disabled = True
        return self._encoder

    # ── Public API ────────────────────────────────────────────────────────────

    async def normalize(self, raw_text: str, db: AsyncSession) -> NormalizationResult:
        if not self._initialized:
            await self.initialize(db)

        cleaned = raw_text.strip().lower()

        # Stage 1: exact or alias match
        if cleaned in self._alias_index:
            skill_id, canonical = self._alias_index[cleaned]
            match_type = "exact" if cleaned == canonical.lower() else "alias"
            return NormalizationResult(
                raw_text=raw_text,
                canonical_skill_id=skill_id,
                canonical_name=canonical,
                match_type=match_type,
                confidence=1.0,
            )

        # Stage 2: partial string match
        for alias, (skill_id, canonical) in self._alias_index.items():
            if cleaned in alias or alias in cleaned:
                if len(cleaned) > 2 and len(alias) > 2:
                    return NormalizationResult(
                        raw_text=raw_text,
                        canonical_skill_id=skill_id,
                        canonical_name=canonical,
                        match_type="alias",
                        confidence=0.85,
                    )

        # Stage 3: embedding similarity fallback
        return await self._embedding_match(raw_text, db)

    async def normalize_batch(
        self, raw_skills: list[str], db: AsyncSession
    ) -> list[NormalizationResult]:
        if not self._initialized:
            await self.initialize(db)

        results = []
        needs_embedding = []

        for raw in raw_skills:
            cleaned = raw.strip().lower()
            if cleaned in self._alias_index:
                skill_id, canonical = self._alias_index[cleaned]
                match_type = "exact" if cleaned == canonical.lower() else "alias"
                results.append((raw, NormalizationResult(
                    raw_text=raw,
                    canonical_skill_id=skill_id,
                    canonical_name=canonical,
                    match_type=match_type,
                    confidence=1.0,
                )))
            else:
                needs_embedding.append(raw)

        for raw in needs_embedding:
            result = await self._embedding_match(raw, db)
            results.append((raw, result))

        order = {r: i for i, r in enumerate(raw_skills)}
        results.sort(key=lambda x: order.get(x[0], 0))
        return [r for _, r in results]

    async def _embedding_match(self, raw_text: str, db: AsyncSession) -> NormalizationResult:
        """
        Use cosine similarity in Python to find the closest ESCO skill.
        SQLite-compatible — no pgvector needed.
        """
        encoder = self._get_encoder()
        if encoder is None:
            return NormalizationResult(
                raw_text=raw_text,
                canonical_skill_id=None,
                canonical_name=None,
                match_type="no_match",
                confidence=0.0,
            )

        try:
            import numpy as np
            from sqlalchemy import select, text

            # Encode the query
            query_vec = encoder.encode(raw_text, normalize_embeddings=True)

            # Fetch all skills with embeddings from DB
            # Note: for large DBs this would be slow — use pgvector in production
            result = await db.execute(
                text("SELECT id, name, embedding FROM skills WHERE embedding IS NOT NULL")
            )
            rows = result.fetchall()

            if not rows:
                return NormalizationResult(
                    raw_text=raw_text,
                    canonical_skill_id=None,
                    canonical_name=None,
                    match_type="no_match",
                    confidence=0.0,
                )

            # Compute cosine similarity for all skills
            best_id, best_name, best_score = None, None, -1.0
            for row in rows:
                try:
                    import json
                    skill_vec = np.array(json.loads(row.embedding), dtype=np.float32)
                    # Both vectors are already normalized — dot product = cosine similarity
                    score = float(np.dot(query_vec, skill_vec))
                    if score > best_score:
                        best_score = score
                        best_id = str(row.id)
                        best_name = row.name
                except Exception:
                    continue

            if best_score >= SIMILARITY_THRESHOLD:
                return NormalizationResult(
                    raw_text=raw_text,
                    canonical_skill_id=best_id,
                    canonical_name=best_name,
                    match_type="embedding",
                    confidence=round(best_score, 4),
                )

        except Exception as e:
            log.warning(f"Embedding match failed for '{raw_text}': {e}")

        return NormalizationResult(
            raw_text=raw_text,
            canonical_skill_id=None,
            canonical_name=None,
            match_type="no_match",
            confidence=0.0,
        )


# ── Singleton instance ────────────────────────────────────────────────────────
skill_normalizer = SkillNormalizer()