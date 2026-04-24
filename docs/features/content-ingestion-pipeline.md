## Overview
Content ingestion enables admins to upload learning materials, chunk them, and store indexable content for recommendations. A companion personalized endpoint ranks content by overlap with a user’s top skill gaps.

## Input
Admin ingestion accepts multipart upload fields:
- `file` (required, text-decoded)
- `title` (optional)
- `skill_tags` (optional comma list)
- `source_url` (optional)

Endpoints:
- `GET /api/v1/admin/content`
- `POST /api/v1/admin/content/upload`
- `DELETE /api/v1/admin/content/{title}`
- `GET /api/v1/content/personalized` (authenticated user)

## Output
Upload returns confirmation and chunk count. Admin list returns content metadata with aggregated chunk counts. Personalized endpoint returns up to 12 ranked items including `matched_skills` used for scoring transparency.

## Core Algorithm / Logic
1. Admin gate.
All management operations run through `require_admin`; only personalized read endpoint is non-admin.

2. Text extraction and validation.
Uploaded file bytes are decoded UTF-8 with ignore-errors; empty/undecodable content is rejected.

3. Chunking strategy.
`_chunk_text` normalizes non-empty lines and creates paragraph-aware chunks up to 1200 chars, splitting oversized paragraphs as needed.

4. Persistence.
One `ContentItem` row is created with metadata (`title`, `source_url`, `difficulty_level`, `skill_tags`) and N `ContentChunk` rows by index order.

5. Search/list.
Admin list supports case-insensitive title filtering and returns each content item with computed chunk count.

6. Personalized ranking.
User’s top gap skill names (up to 8) are matched against content title+tags text blob. Items are scored by number of skill matches and sorted descending.

## Key Files
backend/app/api/v1/endpoints/content.py: Upload/list/delete/personalized logic.
frontend/src/pages/ContentIngestionPage.jsx: Admin authoring UI and payload shaping.
frontend/src/pages/ContentManagementPage.jsx: Admin browsing and deletion UI.
frontend/src/services/api.js: Content API wrappers and form construction.

## Data Model
Writes:
- `content_items`
- `content_chunks`

Reads:
- `content_items`, `content_chunks`
- `skill_gaps` + `skills` for personalization matching

## Edge Cases & Guards
Empty file bytes, empty decoded text, and missing target records produce explicit 400/404 responses. Skill tags are parsed from either JSON object or string fallback to tolerate historical shapes.

## Current Limitations
Frontend now forwards metadata as JSON string in FormData (fixed Week 5). Backend content.py currently does not read or persist a metadata field, so metadata is silently dropped server-side and persistence remains unimplemented. Chunking is character-based, not embedding/token aware. Personalized ranking uses lexical containment only, with no semantic retrieval.

## Extension Points
Week 9-10: move from lexical recommendation to embedding-based retrieval with reranking. Add metadata persistence and filtering facets. Add duplicate-content detection using hash fingerprinting before chunk insertion.