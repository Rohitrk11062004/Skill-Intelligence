## Overview
Automated assessments provide lightweight skill checks with question generation, answer submission, scoring, and admin monitoring. They feed progression signals and assessment analytics used by both learner and admin UX.

## Input
Learner endpoints:
- `POST /api/v1/assessments/generate`
- `POST /api/v1/assessments/submit`
- `POST /api/v1/assessments/mastery/update`

Admin endpoints:
- `GET /api/v1/admin/assessments`
- `GET /api/v1/admin/assessments/summary`

Frontend orchestration is driven by topic assessment pages with local warning/anti-cheat handling.

## Output
Generation returns question records (ID, question_text, options, difficulty, skill_name). Submission returns percentage, total score, max score, and per-question correctness. Admin endpoints return attempt-level rows and aggregate accuracy metrics.

## Core Algorithm / Logic
1. Question generation.
Server uses template-based variants and persists each generated question row in `assessments` with skill, difficulty, and correct option.

2. Submission scoring.
Submitted answers are matched against stored assessment rows; each item is scored binary (1/0). Attempts persist to `assessment_attempts` with time spent metadata.

3. Aggregate result calculation.
Percentage is computed as `total_score / total_max_score * 100` and rounded to 2 decimals.

4. Admin visibility.
Admin list joins attempts, assessments, and users; supports optional skill filter. Summary computes total attempts, correct attempts, assessed-user count, and accuracy rate.

5. Frontend exam behavior.
Topic assessment UI tracks focus/visibility/fullscreen warnings. At 3 warnings, it auto-submits and writes local history events for results page rendering.

## Key Files
backend/app/api/v1/endpoints/assessments.py: Generation/submission/admin reporting.
frontend/src/pages/TopicAssessmentPage.jsx: Exam workflow, warning logic, submit pipeline.
frontend/src/pages/AssessmentResultsPage.jsx: Local history analytics presentation.
frontend/src/services/api.js: Assessment API client methods.

## Data Model
Writes:
- `assessments`
- `assessment_attempts`

Reads:
- `assessments` for answer validation
- admin joins with `users` for monitoring

## Edge Cases & Guards
Empty submission arrays return 400. Invalid assessment IDs are skipped per-row, and if all are invalid the API returns 400. Time taken is clamped non-negative. Admin routes are protected by `require_admin`.

## Current Limitations
`/assessments/mastery/update` currently returns a stub `{ok: true}` and does not persist mastery updates. Frontend call to learning progress uses an outdated payload shape in topic assessment flow, which can misalign completion updates unless compatibility handling exists server-side. Results history is localStorage-based and not server-authoritative.

## Extension Points
Persist mastery deltas into `user_skill_scores` for closed-loop adaptation. Move exam attempt history from local storage to backend user timeline APIs. Add question bank versioning and anti-replay controls for repeated attempts.