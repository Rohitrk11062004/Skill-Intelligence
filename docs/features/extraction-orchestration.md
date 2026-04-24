## Overview
Extraction orchestration is Stage 3 of the pipeline. It chooses regex-first or LLM-first extraction based on parse quality, merges outputs, deduplicates aliases, and emits unified skill records for downstream persistence/scoring.

## Input
The orchestrator receives:
- `ParsedResume` from parsing (`raw_text`, section map)
- `QualityReport` from quality router (`HIGH_QUALITY` or `LOW_QUALITY` extraction path)

## Output
Returns a list of unified extracted skill objects with:
- normalized name key
- category
- confidence
- source section
- context
- frequency
- years of experience
- extractor origin (`regex`, `llm`, or merged `both`)

## Core Algorithm / Logic
1. Path selection from quality router.
If parse quality is high, run regex extraction first over structured sections.

2. Regex branch behavior.
Regex extractor scans against category-specific pattern inventories (languages, frontend, backend, databases, cloud, devops, ml_ai, tools, technical, soft_skills), applies section confidence weighting, and aggregates by normalized token.

3. LLM invocation policy.
For high-quality parses, regex runs first and LLM runs only when regex finds fewer than `REGEX_MINIMUM_THRESHOLD` skills. With the current value (`999`), this effectively means LLM runs after regex for high-quality parses. For low-quality parses, the orchestrator runs LLM directly (regex is skipped).

4. LLM extraction contract.
Gemini prompt enforces strict JSON schema with skill name/category/confidence/source/context/years fields, with additional anti-hallucination and dedup guidance.

5. Merge + dedup.
Outputs from regex and LLM are merged by normalized keys that strip punctuation/spacing and include alias collapsing (for example React variants). Frequency and extractor provenance are reconciled.

6. Final filtering.
LLM parser drops malformed items and confidence < 0.5. JSON parse errors or provider failures return empty LLM results gracefully.

## Key Files
backend/app/services/extraction/extraction_pipeline.py: Orchestration and merge rules.
backend/app/services/extraction/regex_extractor.py: Pattern-based extraction and section weighting.
backend/app/services/extraction/llm_extractor.py: Gemini prompt + JSON parsing + result sanitation.
backend/app/services/parsing/quality_router.py: High/low quality routing trigger.

## Data Model
The orchestrator itself is in-memory. Persistence happens in downstream processing stages that write extracted skills to DB tables linked to resume/job context.

## Edge Cases & Guards
Empty resume text exits early with no results. Regex compilation failures on malformed patterns are ignored per-pattern. LLM JSON blocks with markdown fences are stripped before parse. Any malformed skill entry is skipped without aborting full extraction.

## Current Limitations
`REGEX_MINIMUM_THRESHOLD=999` makes regex-only optimization effectively unreachable on the high-quality path and increases LLM cost/latency. Category labels in prompt and internal taxonomy are not fully harmonized (for example `languages` vs `language`). No confidence calibration step currently blends regex and LLM certainty scores statistically.

## Extension Points
Week 6: tune regex threshold and add empirical benchmark gates. Add cost guardrails (max LLM calls per resume, token budgeting). Add structured telemetry on regex-hit rate, LLM fallback rate, and post-merge precision estimates.