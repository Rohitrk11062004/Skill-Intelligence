## Overview
Skill normalization converts noisy extracted skill text into canonical skills stored in the internal taxonomy (`skills` table). This sits after extraction and before durable scoring/gap analysis so aliases like "JS", "ReactJS", or partial variants can map to one canonical skill identity.

## Input
Primary input is a raw skill string (or list of strings) from extraction stages. The normalizer also depends on taxonomy rows loaded from the database (`Skill.id`, `Skill.name`, `Skill.aliases`, and optional embedding vectors).

## Output
The service returns `NormalizationResult` objects containing:
- `raw_text`
- `canonical_skill_id`
- `canonical_name`
- `match_type` (`exact`, `alias`, `embedding`, `no_match`)
- `confidence`

## Core Algorithm / Logic
1. One-time index initialization.
On first call, `SkillNormalizer.initialize` builds an in-memory lowercase alias index from all `skills` rows. The instance is singleton-scoped and reused.

2. Exact and alias lookup.
`normalize` first does O(1) lookup in alias index; exact canonical-name match returns `match_type=exact`, alias hit returns `alias`, both with confidence 1.0.

3. Partial alias fallback.
If direct lookup misses, a substring containment pass is applied (`cleaned in alias` or `alias in cleaned`) with minimum length guards (>2 chars) and confidence 0.85.

4. Embedding similarity fallback.
If needed and sentence-transformers is available, it loads `all-MiniLM-L6-v2`, encodes the input, pulls all persisted skill embeddings, and computes cosine similarity via dot product on normalized vectors.

5. Threshold decision.
Embedding result is accepted only when score >= 0.72 (`SIMILARITY_THRESHOLD`). Below threshold, output is `no_match`.

6. Batch mode.
`normalize_batch` fast-paths exact/alias rows first, then embedding fallback only for unresolved items, and finally restores original input order.

## Key Files
backend/app/services/normalization/skill_normalizer.py: Core singleton implementation, alias/embedding matching.
backend/app/models/models.py: Skill schema source (`name`, `aliases`, `embedding`).
backend/app/services/extraction/extraction_pipeline.py: Upstream producer of raw skills that are candidates for normalization.

## Data Model
Reads:
- `skills.id`
- `skills.name`
- `skills.aliases`
- `skills.embedding` (JSON-serialized vector for embedding fallback)

Writes:
- No direct writes in normalizer itself; it is read-only matching logic.

## Edge Cases & Guards
If sentence-transformers is not installed, embedding fallback is disabled and unresolved values return `no_match`. If embeddings are absent in DB, similarity stage exits safely. Invalid embedding rows are skipped row-by-row without failing the full request. Empty/whitespace input is normalized through stripping before matching.

## Current Limitations
Embedding fallback is SQLite-friendly but not scalable because it scans all skill vectors in Python. Alias matching is case-insensitive but heuristic substring matching may overmatch short ambiguous fragments. No language-aware normalization exists for multilingual skill names.

## Extension Points
Week 6+: replace full-table embedding scan with vector index strategy for production DB. Add curated alias governance tooling for taxonomy admins. Add per-category thresholds (for example, stricter threshold for soft skills than technical frameworks).