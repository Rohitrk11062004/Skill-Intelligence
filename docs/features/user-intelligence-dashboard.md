## Overview
User intelligence dashboard aggregates readiness and progression signals into user/admin views. It combines skill extraction outcomes, gap analysis, `learning_plans` / `learning_plan_items` progress, and org-level operational metrics.

## Input
User-side sources:
- Latest completed resume skill extraction counts
- Gap summary from target role
- Learning plan/roadmap and progress status

Admin-side sources:
- User population/activity
- Skill, learning plan item, content chunk, and assessment volume
- Per-user skill/gap/path drilldown

## Output
User dashboard payload includes counts and quick insights (`detected_skills_count`, `skill_gaps_count`, `active_paths_count`, readiness-like mastery metric, recent skills, priority gaps).
Admin dashboard payload includes operational metrics and user management datasets.

## Core Algorithm / Logic
1. Latest resume scan.
User dashboard fetches most recent completed resume and counts extracted skill rows.

2. Recent skill labels.
Top-confidence extracted skills are deduped and truncated for quick UI badges.

3. Gap synthesis.
If target role exists, gap detector is invoked to compute readiness and priority gap list.

4. Frontend composition pattern.
DashboardPage does not call a dedicated dashboard endpoint. It calls three endpoints in sequence via Promise.allSettled: getGapSummary() first (writes gaps to DB), then getLearningPlan() and getProgressSummary() in parallel. This avoids concurrent gap writes that cause SQLite lock contention. All three failures must occur simultaneously before an error state is shown to the user.

5. Admin overview aggregation.
Admin overview computes global counts across users, skills, learning plans, content chunks, and assessment attempts.

6. Admin user drilldown.
Per-user progress endpoint joins skill scores, current gaps, and learning plans, then computes completion percentages.

## Key Files
backend/app/api/v1/endpoints/dashboard.py: Legacy/composite user dashboard endpoint.
backend/app/api/v1/endpoints/admin.py: Admin overview, user list, user progress APIs.
frontend/src/pages/DashboardPage.jsx: Current composed-API dashboard implementation.
frontend/src/pages/AdminDashboardPage.jsx: Admin metrics and management UI.

## Data Model
Reads:
- `resumes`, `extracted_skills`, `skills`
- `skill_gaps`
- `learning_plans`, `learning_plan_items`
- `users`, `user_skill_scores`
- `content_chunks`, `assessment_attempts`

Writes:
- No direct writes in dashboard endpoints except indirect writes when gap detector recomputes snapshots.

## Edge Cases & Guards
No completed resume yields zeroed skill counters without failure. Missing target role yields gap defaults in composite endpoint. Admin endpoints enforce manager-only access.

## Current Limitations
Frontend main dashboard currently avoids direct `/users/me/dashboard` usage and composes data from multiple endpoints to match newer contracts. This can create duplicate gap recomputation cost. Some metrics are lightweight proxies (for example path count estimation) rather than persisted analytics facts.

## Extension Points
Introduce a materialized analytics snapshot table to avoid repeated heavy recomputation on page load. Align all dashboard clients on one canonical contract (either composed or dedicated endpoint). Add time-series trend endpoints for readiness delta and completion velocity.