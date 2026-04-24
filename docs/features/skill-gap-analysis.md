## Overview
Skill gap analysis compares a user’s demonstrated skill profile against target role requirements and computes readiness, prioritized gaps, and learning-hour estimates. It is the foundation for both roadmap generation and dashboard readiness metrics.

## Input
Inputs are:
- User target role (`users.target_role_id`)
- Role skill requirements (`role_skill_requirements`)
- User proficiency evidence (`user_skill_scores`)
- Skill metadata (`skills`)

API entry points:
- `POST /api/v1/users/me/target-role`
- `GET /api/v1/users/me/gaps`
- `GET /api/v1/users/me/gaps/summary`

## Output
`GapResult` with:
- `readiness_score`
- counts (`missing_skills`, `weak_skills`, `total_gaps`)
- `total_learning_hours`
- sorted list of gap items including proficiency mismatch, priority score, prerequisites, and estimated hours

Public API responses:
- `GET /users/me/gaps` returns gap items with `skill_id`, `skill_name`, `gap_type`, `priority_score`, `current_proficiency`, `required_proficiency`, `time_to_learn_hours`, `importance`, `is_mandatory`, `prerequisites`, and `prerequisite_coverage`.
- `GET /users/me/gaps/summary` returns aggregate counts/readiness plus `total_learning_hours`.

Note on `skill_band`:
- Internal gap objects include a `skill_band` attribute sourced from `skills.skill_band` (defaulting to `Technical Skills` when missing).
- Current public gap schemas do not expose `skill_band`; it is primarily consumed in roadmap generation logic.

## Core Algorithm / Logic
1. Target role resolution.
Role can be set by ID or exact name; compatibility fallback treats provided `role_id` as name when needed.

2. Skill requirement join.
Detector joins role requirements with skills and optional user skill scores.

3. Proficiency normalization.
Text proficiency levels map to numeric thresholds (`beginner=0.25`, `intermediate=0.5`, `advanced=0.75`) for comparison.

4. Gap typing.
Skills are classified as `missing` or `weak` based on current score versus required threshold.

5. Prerequisite coverage.
Prerequisite lists are parsed from JSON and evaluated against user’s known skills, yielding coverage ratio 0..1.

6. Priority scoring.
Priority combines requirement importance, estimated learnability (`1/time`), mandatory weighting, and prerequisite coverage using:
`priority_score = importance * (1 / time_to_learn_hours) * mandatory_weight * prereq_coverage`
where `mandatory_weight = 1.5` for mandatory skills and `1.0` otherwise, and `prereq_coverage` is clamped to `[0, 1]`.

7. Persistence.
Results are written back to `skill_gaps` for subsequent roadmap and content recommendation usage.

## Key Files
backend/app/services/gap/gap_detector.py: Scoring math, classification, persistence of computed gaps.
backend/app/api/v1/endpoints/gaps.py: User-facing API for target role + gap retrieval.
backend/app/schemas/gaps.py: Contract models used by API responses.
frontend/src/pages/SkillAnalysisPage.jsx: Frontend consumer of gap result payloads.

## Data Model
Reads:
- `users.target_role_id`
- `roles`, `role_skill_requirements`, `skills`
- `user_skill_scores`

Writes:
- `skill_gaps` rows per user/role snapshot.

## Edge Cases & Guards
If target role is missing, endpoints return 400 with explicit guidance. Nonexistent target role returns 404. Invalid prerequisite JSON is tolerated by safe parse helper and treated as empty prerequisites.

## Current Limitations
Readiness and priority are heuristic, not outcome-calibrated to historical learner performance. Compatibility fallback in target-role setter can mask client-side contract mistakes (name passed in role_id). SQLite write patterns can still create contention under heavy concurrent recomputation.

## Extension Points
Week 6: introduce deterministic caching windows for repeated gap reads. Add calibration datasets to tune priority coefficients. Add drift monitoring between gap predictions and actual assessment outcomes.