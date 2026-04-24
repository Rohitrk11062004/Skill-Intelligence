## Overview
The resume parsing feature is the Stage 2 entry point of the backend pipeline: it converts uploaded PDF or DOCX resumes into structured sections and a quality score that controls downstream extraction behavior. Its purpose is to normalize noisy real-world resume formats into deterministic fields (`raw_text`, `sections`, `layout_type`, `parse_confidence`) so extraction can avoid garbage-in failure modes, especially for scanned PDFs, malformed encodings, and non-standard headers.

## Input
Input enters from `POST /api/v1/resumes/upload` followed by `POST /api/v1/resumes/{job_id}/process`. The parser receives a persisted resume file path from the `resumes` table and infers parser strategy from extension (`.pdf`, `.docx`, `.doc`). For parsing quality decisions, it uses the extracted text and detected sections, then passes a `ParsedResume` object to the quality router, which adds extraction-path routing context (`high_quality` vs `low_quality`).

## Output
The parser emits a `ParsedResume` dataclass with `raw_text`, `layout_type`, `sections`, `misc_sections`, `parse_confidence`, and `warnings`. The processor persists these into `resumes.raw_text`, `resumes.parsed_sections` (JSON string), `resumes.parse_confidence`, and `resumes.layout_type`. The quality router emits `QualityReport` containing threshold decision, section coverage flags, warnings, and recommendation text that is consumed by the extraction pipeline.

## Core Algorithm / Logic
The implementation executes a deterministic multi-step pipeline.

1. File-type dispatch and extraction.
The parser dispatches on extension. For PDF, it uses `pdfplumber` page-by-page extraction and computes a column vote from word bounding boxes (`x0` split around page midpoint). If more than 40% of pages appear two-column, `layout_type` becomes `multi_column`; otherwise `single`. For DOCX, it uses paragraph text via `python-docx`, and marks `multi_column` when document tables have at least two columns.

2. Header detection and section slicing.
The raw text is split into lines. Each non-empty line is classified by `_classify_header`. Header classification rejects lines that are too short/long, sentence-like endings, digit-heavy content, ignored boilerplate (`references`, `declaration`, etc.), weak alphabetic ratio, or non-heading style. Valid aliases are mapped through a large vocabulary (about 80 aliases) into canonical sections (`experience`, `skills`, `education`, `projects`, `certifications`, `summary`, `languages`, `extracurricular`). Unknown but header-like lines can be retained as misc headers.

3. Noise filtering and misc handling.
For each detected header, content is sliced until the next header. Sections shorter than `MIN_SECTION_LENGTH` are dropped. Recognized sections are merged when repeated. Unrecognized sections are stored only if content is substantial (`>100` chars), preventing short noise fragments from polluting results.

4. Confidence scoring.
`_score_confidence` computes a bounded score in `[0.0, 1.0]` using explicit features: key-section presence (`skills`, `experience`, `education`), text length thresholds (`>500`, `>2000`), symbol ratio (non-ASCII ratio), and layout preference (`single` gets a small boost). High symbol ratios add warnings for likely encoding corruption.

5. Quality routing (Stage 2.8).
`quality_router.route` applies threshold `0.70` and marks `HIGH_QUALITY` vs `LOW_QUALITY` extraction paths. In current extraction orchestration, both regex and LLM execute in practice because `REGEX_MINIMUM_THRESHOLD` is set to 999, so quality routing affects ordering semantics more than LLM inclusion.

6. Pipeline persistence.
`resume_processor.process_resume` writes parse and routing artifacts before extraction, updates resume status transitions (`parsing`, `extracting`, `complete` or `failed`), and propagates warnings through processing summary.

7. Extracurricular exclusion behavior.
`extracurricular` and `languages` are recognized intentionally but listed in `SKIP_FOR_SKILLS` so downstream skill extraction can ignore them as low-signal domains for technical capability scoring.

## Key Files
`backend/app/services/parsing/resume_parser.py`: Core parsing engine, section alias map, header classification, confidence scoring.
`backend/app/services/parsing/quality_router.py`: Threshold-based routing logic (`0.70`) and quality report generation.
`backend/app/services/parsing/resume_processor.py`: Orchestrates parse -> route -> extraction and persists parse outputs.
`backend/app/api/v1/endpoints/resume.py`: Upload/process/results/status APIs that drive parser execution lifecycle.

## Data Model
Primary writes occur on `resumes`:
- `status` (`uploaded` -> `parsing` -> `extracting` -> `complete`/`failed`)
- `raw_text`
- `parsed_sections` (JSON string)
- `parse_confidence`
- `layout_type`
- `error_message` on failures
- `processed_at` when complete

Reads include `resumes` row lookup by `job_id` and `user_id` ownership checks before processing/status/results access.

## Edge Cases & Guards
Empty extracted text is explicitly handled: the parser returns zero confidence with warning instead of hard failure, which prevents silent corruption. Unsupported MIME types are blocked at upload (`415`), oversize files are rejected (`413`), and duplicate uploads are deduplicated by file hash per user. Header detection has multiple guards to prevent names, dates, percentages, and sentence fragments from being misclassified as section headers. Low-confidence parses still propagate through quality routing, but current extraction behavior runs both regex and LLM due to threshold configuration. Process endpoint is idempotent for already-complete resumes, returning existing results rather than re-running.

## Current Limitations
The parser does not perform OCR, so image-only or heavily scanned PDFs still produce low-confidence outputs. Confidence scoring is heuristic and can mis-rank uncommon resume templates. Section alias coverage is broad but static, so novel header phrasing may fall into misc. Layout inference for PDFs uses simple geometric heuristics, not full document structure reconstruction. `parsed_sections` is stored as JSON text instead of normalized relational structures, which limits indexed querying. Some parser unit tests currently show expectation drift and need cleanup during Week 6 quality pass.

## Extension Points
Week 6: accuracy tuning pass should recalibrate confidence scoring weights and parser edge heuristics against a larger resume corpus. Week 6: parser test stabilization should align expected section behavior and garble warnings with current implementation. Week 9-10: batch ingest will stress parser concurrency and should add parse metrics instrumentation. Week 11-12: RAG and ML enhancements can consume richer parse metadata if section confidence is persisted per section rather than only global confidence. OCR integration can be inserted at extraction stage before `_detect_sections` when low-text PDFs are detected.