## Overview
Role management defines target job roles and their required skills, which directly drive gap detection and roadmap generation. It is the source-of-truth contract between taxonomy and user progression features.

## Input
Role APIs support:
- role list retrieval
- skill search against taxonomy
- role skill retrieval
- full skill requirement replacement
- role deletion

Endpoints:
- `GET /api/v1/roles`
- `GET /api/v1/roles/skills/search`
- `GET /api/v1/roles/{role_id}/skills`
- `PUT /api/v1/roles/{role_id}/skills`
- `DELETE /api/v1/roles/{role_id}`

## Output
Returns normalized role summaries and role-skill requirement payloads containing importance, mandatory flag, and minimum proficiency for each skill requirement.

## Core Algorithm / Logic
1. Role listing.
Role list aggregates requirement counts via outer join and group-by for quick catalog display.

2. Skill search.
Case-insensitive contains filter over `skills.name`, limited to 100 rows.

3. Requirement fetch.
Role-skill endpoint joins `role_skill_requirements` with `skills`, sorted by mandatory first, then importance, then name.

4. Replace semantics.
`PUT /roles/{id}/skills` is destructive-replace: existing requirement rows are deleted first, then rebuilt from payload.

5. Skill upsert behavior.
If payload provides `skill_name` and no existing taxonomy match, new `Skill` row is auto-created with default category and source role.

6. Role deletion.
Delete endpoint removes requirements before deleting role.

## Key Files
backend/app/api/v1/endpoints/roles.py: Full role CRUD-style requirement management.
backend/app/schemas/roles.py: Role list and role skill response contracts.
backend/scripts/seed_roles.py: Seed path for initial role + requirement corpus.
backend/app/services/gap/gap_detector.py: Downstream consumer of role requirements.

## Data Model
Reads/Writes:
- `roles`
- `role_skill_requirements`
- `skills` (including creation in replace flow when missing)

## Edge Cases & Guards
Nonexistent role IDs return 404 across fetch/update/delete. Invalid requirement entries without resolvable skill produce 422. Search endpoint tolerates empty query and returns alphabetical sample set.

## Current Limitations
Role-modifying endpoints currently require authentication but not explicit admin authorization in `roles.py`, which may be too permissive for production governance. Replace endpoint is all-or-nothing and can lose previous state without revision history.

## Extension Points
Add admin-only authorization guard for mutating role endpoints. Introduce patch-based requirement updates with optimistic locking/versioning. Add audit trails for role requirement changes to support compliance and rollback.