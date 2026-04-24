# Skill Intelligence System — Project Context for Claude

## What This Project Is
An internal AI-powered skill intelligence platform for a company.
Employees upload resumes → system extracts skills → compares against
role requirements → generates personalized learning paths.

Built by: Rohit Ramana (ramanakolur@gmail.com)
Stack: Python 3.11, FastAPI, SQLite (local dev), SQLAlchemy async, Gemini AI + OpenAI (via LangChain)
Started: March 2026

**Repository layout:** Monorepo — `backend/` (FastAPI app, this `CLAUDE.md`, DB file when using SQLite defaults), `frontend/` (React + Vite), `docs/features/` (feature write-ups). Run the API from `backend/` so relative paths like `./skilldb.sqlite3` resolve correctly.

---

## Current Status
- Week 1 ✅ Complete
- Week 2 ✅ Complete
- Week 3 ✅ Complete — Role seeding + Gap detection
- Week 4 ✅ Implemented (working prototype) — Learning roadmap, persistence/regeneration, and progress tracking are in code; core path-generation logic is still under active review/finalization (ordering, week packing, resource stubs, regeneration rules)
- Week 5 ✅ Implemented (UI integration) — Frontend roadmap flow is wired to Week 4 APIs; product hardening and UX cleanup continue
- Week 6 🔲 Pending — Testing + Deploy
- Week 7–8 🔲 Pending — User corrections + Manager validation
- Week 9–10 🔲 Pending — Batch processing + HR admin
- Week 11–12 🔲 Pending — RAG + LangGraph + ML model

Focus note: this phase centers on resume -> skills -> gaps -> learning path. Content ingestion and automated assessment modules were imported from another project for scaffolding and are intentionally left as-is for now (not treated as first-class, reviewed product logic in this phase).

---

## Full 12-Week Detailed Plan

### Week 1 ✅ — Foundation & Data Pipeline
**Goal:** Working API with auth, DB, resume upload, parsing

**Completed:**
- FastAPI project structure
- SQLite DB + all ORM tables auto-created at startup (16 models: users, resumes, projects, skills, roles, role requirements, extracted skills, user scores, snapshots, gaps, learning plans/items, content, assessments, etc.)
- Auth system — JWT (python-jose) + bcrypt (passlib removed, Python 3.11 bug)
- Resume upload endpoint — file validation, MD5 dedup, job_id return
- UUID normalization fix for SQLite (dashes vs no dashes)
- Resume parser — PDF (pdfplumber) + DOCX (python-docx)
- Section detection — 80 aliases mapped to canonical sections
- Parse confidence scorer (0.0–1.0)
- Data quality router (Stage 2.8) — score >= 0.7 → Regex/NER, < 0.7 → LLM direct
- Skill normalizer skeleton — alias index + cosine similarity fallback
- Dropped ESCO entirely — using JD-driven taxonomy instead

**Files built:**
- app/core/config.py, security.py
- app/db/session.py
- app/models/models.py (all tables)
- app/schemas/auth.py, resume.py
- app/api/v1/endpoints/auth.py, resume.py
- app/services/parsing/resume_parser.py
- app/services/parsing/quality_router.py
- app/services/parsing/resume_processor.py
- app/services/normalization/skill_normalizer.py
- app/main.py

---

### Week 2 ✅ — Skill Extraction Engine
**Goal:** Resume in → structured skill profile out

**Completed:**
- Regex extractor (Layer 1) — SKILL_PATTERNS keyword matching across 10 categories
- Gemini LLM extractor (Layer 2) — context-aware extraction with structured JSON prompt; uses google-generativeai
- LangChain orchestration — unified interface for both Gemini (active) and OpenAI (available for fallback)
- Both always run (REGEX_MINIMUM_THRESHOLD = 999), results merged
- Deduplication in extraction_pipeline.py — handles React/ReactJS, OOP/OOPS, DSA/Algorithms, HITL
- Skill normalization — alias match → exact → cosine similarity
- Auto-add new skills to internal taxonomy when not found
- Proficiency estimation rule-based Phase 1
- process endpoint — triggers full pipeline
- results endpoint — returns full skill profile
- Tested on real resume (Rohit's resume) — 39 accurate skills
- Fixed: OOP appearing 3x — seen_skill_names guard in resume_processor.py
- Fixed: misc section noise — Percentage: 96%, Innovation. removed
- Fixed: extracurricular soft skills filtered (Ethical Behavior, Social Responsibility)
- Fixed: category inconsistency — forced LLM to use project taxonomy
- NLP infrastructure ready (spacy 3.7.0+ installed) — NER not yet active in pipeline, reserved for future enhancements

**Files built:**
- app/services/extraction/regex_extractor.py
- app/services/extraction/llm_extractor.py
- app/services/extraction/extraction_pipeline.py
- Updated: app/services/parsing/resume_processor.py
- Updated: app/api/v1/endpoints/resume.py (process + results endpoints)
- Updated: app/services/parsing/resume_parser.py (noise fixes)

**Extraction results on Rohit's resume:**
- 39 skills extracted cleanly
- Python: intermediate (frequency=3, years=0.5)
- FastAPI: intermediate (internship source)
- React, Flutter, Firebase, MongoDB, MERN: intermediate (project source)
- All OOP/DSA/HITL variants deduplicated

---

### Week 3 ✅ — Role Seeding + Skill Gap Detection
**Goal:** Roles seeded from Excel data → gap detection working end to end

**Status:** 100% Complete — All parts (A, B, C, D) finished and tested

**Context — Decisions Made:**
- No JDs received yet from team lead
- Employee Excel provided (188 employees, 6 columns)
- Excel columns: Employee Number, Display Name, Business Unit,
  Department, Sub Department, Job Title
- Decision: use Job Titles only for now to seed roles
- Decision: technical roles only — non-technical deferred to later
- Decision: use seniority levels (associate/mid/senior/lead/principal)
- Decision: ignore role suffixes (CDM, SAS, 3DS) for now
- Decision: skip Scrum Master, Project Manager, Implementation Consultant,
  Manager Professional Services for now
- Decision: Set role.department = NULL for all seeded roles (defer department assignment to later)
- Company tech context: R&D focused, evaluates and picks best stack per
  project — no single enforced stack — skill requirements domain-level
  not tool-specific
- When JDs arrive → run JD ingestion pipeline to override seeded requirements

**Final Role List — 22 roles seeded (actual roles extracted from employee data), ~513 requirements**

Actual roles extracted:
- Software Engineer (6 seniority levels)
- Technical Lead, Technical Architect
- AI/ML Engineer, Applied AI Researcher  
- Data Analyst, Data Engineer
- Quality Analyst, Test Automation Engineer
- System Administrator, Systems & Network Admin
- Product Designer, DevOps Engineer
- And more technical roles from employee job titles
- Total skills: 337 unique skills in internal taxonomy
- Total requirements: 513 role-skill associations

**Part A ✅ — Role Seeding (Completed)**

Files created:
- scripts/seed_roles.py
  → Extracted actual roles from employee Excel job titles
  → Gemini generates skill requirements per role+seniority combination
  → Gets domain-level skill requirements (not tool-specific)
  → Seeds roles table with 22 base roles (department = NULL)
  → Seeds skills table → builds internal taxonomy (337 skills)
  → Seeds role_skill_requirements table (513 records)
  → Idempotent script — maintains prerequisites, difficulty, time_to_learn_hours

Gemini prompt strategy for role seeding:
  Input: "{seniority} {role_name} at an R&D-focused tech company"
  Output: skills with importance + mandatory + min_proficiency + category
  Model: Gemini (google-generativeai via LangChain)
  Skill requirements: domain-level (e.g. "backend framework" not "FastAPI")
  Core skills: non-negotiable fundamentals
  Domain skills: category-level requirements
  Specific tools: examples only, not hard requirements

Model changes:
  Added to Skill table:
    - prerequisites: JSON list ["Python", "REST APIs"] (Week 3D)
    - difficulty: int (1-5) — used in priority scoring
    - time_to_learn_hours: int — used in priority and scheduling

Execution result:
  - Created 22 roles
  - Created 337 skills (internal taxonomy)
  - Created 513 role-skill requirements
  - Re-runs idempotent — updates existing roles to maintain NULL department

**Part B ✅ — Role Endpoints (Completed)**

Files created:
- app/api/v1/endpoints/roles.py (4 endpoints)
- app/schemas/roles.py (request/response types)

Endpoints implemented:
  GET  /api/v1/roles                  → list all roles with skill_count aggregate
  GET  /api/v1/roles/{id}/skills      → full skill requirements for role (join with RoleSkillRequirement)
  PUT  /api/v1/roles/{id}/skills      → HR override requirements (DELETE old + recreate new)
  DELETE /api/v1/roles/{id}           → remove role (soft delete possible, not implemented)

Testing:
  - Integration tests in test_roles_and_learning_flow.py
  - test_roles_endpoints_integration: PASSED

**Part C ✅ — Gap Detection Service (Completed)**

Files created:
- app/services/gap/gap_detector.py (gap detection logic)
- app/api/v1/endpoints/gaps.py (3 endpoints)
- app/schemas/gaps.py (request/response types)

Gap detection service features:
  - Compares user skill profile vs role requirements
  - Categorizes gaps: missing_skills, weak_skills, strong_skills
  - Calculates readiness_score: weighted % of role requirements met
  - Prioritizes gaps using formula:
    priority = importance × (1 / time_to_learn_hours) × mandatory_weight × prerequisite_coverage
  - Considers prerequisites: checks if user has prerequisite skills
  - Persists gaps to skill_gaps table with priority_score and gap_type

Endpoints implemented:
  POST /api/v1/users/me/target-role        → set user's target role
    - Accepts role_id OR role_name (backward-compatible name fallback)
    - Stores in user.target_role_id
    - Discovery: Name fallback needed for better Swagger UX
  GET  /api/v1/users/me/gaps               → detailed gap list vs role
    - Returns list of GapItemResponse with prerequisites and coverage info
    - Ordered by priority_score descending
  GET  /api/v1/users/me/gaps/summary       → readiness metrics
    - Returns readiness_score (0.0-1.0)
    - missing_count, weak_count, strong_count
    - total_hours_to_learn estimate

Bug fixes during implementation:
  - Fixed: AttributeError req.required_proficiency → changed to req.min_proficiency
  - Fixed: SetTargetRoleRequest needed name-as-id fallback for role lookup

Testing:
  - Integration tests in test_gaps_flow.py and test_roles_and_learning_flow.py
  - test_gaps_flow_end_to_end: PASSED
  - test_gaps_negative_paths: PASSED (401 auth, 400 missing target role)

**Part D ✅ — Prerequisites Handling (Completed)**

Implementation:
  - Added prerequisites field to Skill model (JSON array)
  - Gap detector checks prerequisite coverage per skill
  - Prerequisite_coverage metric included in gap priority calculation
  - Gaps with satisfied prerequisites get priority boost

Testing:
  - Coverage validated in integration tests
  - Prerequisites JSON field working as expected

---

### Week 4 ✅ — Learning Path Generation
**Goal:** Gap list → prioritized learning roadmap with resources

**Status:** Implemented as a working prototype: roadmap generation, persistence reuse/regeneration, item progress lifecycle, and progress summary are live. Core generation behavior is still under review and not finalized (ordering policy, week-packing heuristics, resource quality strategy, regeneration semantics).

**Files created:**
- app/services/learning/path_generator.py (path generation logic)
- app/api/v1/endpoints/learning.py (roadmap + progress endpoints)
- app/schemas/learning.py (request/response types)

**Endpoints implemented:**
  GET   /api/v1/users/me/learning-plan                    → full learning plan
  GET   /api/v1/users/me/learning-roadmap                 → hierarchical roadmap + plan_id/item_id
  PATCH /api/v1/users/me/learning-plan/{plan_id}/items/{item_id}/progress → status lifecycle + completed_at
  GET   /api/v1/users/me/learning-plan/progress           → aggregate progress summary

**Path generation logic (working prototype):**
- Calls gap detector to get gaps for user's target role
- Sorts gaps by prerequisites depth → priority_score → importance → mandatory flag
- Creates LearningPlanItem per gap: order, skill_id, gap_type, resources
- Calculates total_hours_estimate (sum of time_to_learn_hours)
- Resources stub: type (guide | practice), title, provider, url, estimated_hours
- Placeholder resources: "{skill} Guide" on Gemini + "{skill} Practice Problems" placeholder
- Returns structured LearningPlanResponse with readiness_score and ordered items

**Learning plan item format (implemented):**
  order, skill_name, gap_type (missing|weak), priority_score, proficiency_required,
  time_to_learn_hours, prerequisites, prerequisite_coverage, resources[]
  
  Each resource: type, title, provider, url, estimated_hours

**Resource fetching strategy (scaffolded for future):**
  1. Internal docs (RAG — Week 11–12, not yet implemented)
  2. Coursera API (Week 4 next, not yet implemented)
  3. YouTube Data API (Week 4 next, not yet implemented)
  4. Fallback: Gemini suggests top resources (currently using placeholder)

**Testing:**
  - `test_learning_plan_endpoint_integration` (in `test_roles_and_learning_flow.py`): PASSED — validates GET `/learning-plan` returns structured response with sorted items
  - Full roadmap + progress lifecycle: see `tests/integration/test_learning_roadmap_flow.py` (7 tests)

**Discoveries during Week 4 start:**
  - Learning plan generation works end-to-end with gap detector
  - Total hours estimate properly calculated
  - Prerequisites ordering validated
  - Placeholder resources acceptable for MVP
  
**Next steps for Week 4 (TODO):**
  1. Finalize core path-generation rules
    - Lock deterministic ordering policy across prerequisites/priority/importance
    - Tighten week-packing behavior and edge-case handling for oversized skills
    - Define stable regeneration rules (when to reuse vs regenerate persisted plans)

  2. Upgrade learning resources beyond placeholders
    - Replace current internal stub resources with provider-backed retrieval
    - Add provider abstraction + ranking strategy for returned resources

  3. Expand roadmap/progress test coverage
    - Add end-to-end coverage for force regeneration, persisted reuse, and progress state transitions
    - Validate roadmap/progress behavior through frontend roadmap flow assumptions

---

### Week 5 ✅ — Frontend UI (Integrated, Hardening Ongoing)
**Goal:** Working web interface for employees and managers

**Stack:** React (JSX) + Vite + Tailwind CSS

**Current implementation snapshot (verified in repo):**
- React app wiring complete with `BrowserRouter`, lazy-loaded pages, and protected routes
- Shared auth state implemented via `AuthProvider` + `useAuth`
- API client service layer implemented with JWT interceptor and role/gap/learning/admin/content/assessment calls
- Core navigation/layout shell implemented with responsive sidebar, topbar, and account controls
- Week 5 page scaffolds and integrations present (dashboard, skills, roadmap, assessment, content, admin)

**Pages / routes currently wired:**
  /login                       → Login page
  /auth/callback/{provider}    → OAuth callback
  /                            → Dashboard (protected)
  /dashboard                   → Redirect to `/`
  /skills                      → Skills page
  /skill-analysis              → Redirect to `/skills`
  /roadmap                     → Learning roadmap
  /assessment-results          → Assessment results
  /assessment-monitor          → Assessment monitor
  /topic-assessment            → Topic assessment
  /content                     → Content management
  /content-ingestion           → Content ingestion
  /admin                       → Admin dashboard
  /admin/users                 → User management

**Key components:**
  SkillRadarChart    → proficiency by category
  GapHeatmap         → missing vs weak vs strong
  LearningRoadmap    → visual timeline
  ProgressTracker    → % complete per skill
  TeamMatrix         → manager team view

---

### Week 6 🔲 — Testing + Accuracy Tuning + Deploy
**Goal:** Production-ready, observable, demo-ready

**Testing:**
  50 real resumes → measure extraction precision/recall (target >85%)
  Normalization accuracy target >90%
  Fix top 10 failure cases

**Observability:**
  LangSmith — trace all Gemini calls, cost + latency tracking
  Cloud Logging — structured logs
  Error alerting

**Performance:**
  Redis cache for skill normalizer index
  LLM response caching for identical text
  Target: < 5 seconds per resume

**Deployment:**
  Docker + Google Cloud Run
  Cloud SQL (managed PostgreSQL) replaces SQLite
  GCS bucket for resume storage

---

### Week 7–8 🔲 — User Corrections + Manager Validation
**Goal:** Human feedback loop to improve accuracy

**User correction:**
  User adjusts proficiency score → stored as user_override
  Corrections become training data for Week 11–12 ML model

**Manager validation:**
  Manager endorses or overrides scores → manager_override
  Manager override takes precedence over system estimate

**Skill snapshots:**
  Weekly cron → SkillSnapshot per user
  Powers skill growth chart

**Endpoints:**
  PATCH /api/v1/users/me/skills/{skill_id}
  PATCH /api/v1/manager/users/{user_id}/skills/{skill_id}
  GET   /api/v1/users/me/skill-history
  GET   /api/v1/manager/team
  GET   /api/v1/manager/team/gaps

---

### Week 9–10 🔲 — Enterprise Expansion + Batch Processing
**Goal:** Onboard all 188 employees, HR admin panel

**Batch processing:**
  Celery + Redis queue
  POST /api/v1/admin/batch-ingest — ZIP of resumes
  Background processing with progress tracking

**HR admin panel:**
  POST /api/v1/admin/roles
  PUT  /api/v1/admin/roles/{id}
  DELETE /api/v1/admin/roles/{id}
  POST /api/v1/admin/roles/{id}/skills
  GET  /api/v1/admin/team/coverage
  GET  /api/v1/admin/skills/taxonomy

**Employee import from Excel (188 employees):**
  When ready → scripts/seed_employees.py
  Reads Excel → creates user accounts
  Maps each employee to their role
  Temporary password generated (Welcome@EmpNumber)
  Force password change on first login

---

### Week 11–12 🔲 — Intelligence & Optimization
**Goal:** Self-improving system, smarter recommendations

**RAG:**
  Internal docs → pgvector → semantic search for learning recs
  POST /api/v1/admin/docs/upload

**LangGraph:**
  Replace linear pipeline with graph workflow
  Better error handling + retry logic
  Parallel execution where possible

**ML proficiency model v1:**
  Train on user_override + manager_override data
  scikit-learn RandomForest or XGBoost
  Replace rule-based _estimate_proficiency()
  Retrain monthly

**Skill trends:**
  Industry demand signals → gap priority weighting
  In-demand badge on high-demand skills

**PostgreSQL + pgvector:**
  Switch DATABASE_URL
  Enable pgvector for embedding similarity
  Replace Python cosine similarity

---

## Architecture — 11 Stages

| Stage | Name | Status |
|---|---|---|
| 1 | Data Ingestion | ✅ Done |
| 2 | Resume Parsing | ✅ Done |
| 2.5 | Auth & User System | ✅ Done |
| 2.8 | Data Quality Layer | ✅ Done |
| 3 | Skill Intelligence Core | ✅ Done |
| 4 | Project & Experience Analysis | 🔲 Partial |
| 5 | Feature Engineering | ✅ Done (rule-based) |
| 6 | Proficiency Estimation | ✅ Done (Phase 1) |
| 7 | Skill Gap Analysis | ✅ Week 3 |
| 8 | Learning Path Generation | ✅ Week 4 |
| 9 | Deployment & Infrastructure | 🔲 Week 6 |
| 10 | Enterprise Expansion | 🔲 Week 9–10 |
| 11 | Intelligence & Optimization | 🔲 Week 11–12 |

---

## Tech Stack

| Layer | Tech | Notes |
|---|---|---|
| API | FastAPI 0.111.0 | Python 3.11 |
| DB local | SQLite + aiosqlite | `skilldb.sqlite3` created under `backend/` cwd; `session.py` sets WAL + busy_timeout |
| DB production | PostgreSQL 16 + pgvector | Cloud SQL on GCP |
| ORM | SQLAlchemy 2.0 async | |
| Auth | python-jose + bcrypt 4.1.3 | passlib removed — Python 3.11 bug |
| PDF parsing | pdfplumber | |
| DOCX parsing | python-docx | |
| LLM — Gemini | google-generativeai | Primary extractor; gemini-2.5-flash-lite in config.py |
| LLM — OpenAI | langchain-openai + openai | Secondary provider; integrated via LangChain |
| LLM orchestration | LangChain 0.2.5 | Unified provider abstraction + traceable decorators |
| Observability | LangSmith 0.1.0+ | Tracing for LLM calls (cost + latency tracking) |
| NLP | spacy 3.7.0+ | Named entity recognition (infrastructure ready, not yet active in pipeline) |
| Embeddings | sentence-transformers MiniLM-L6-v2 | loaded at startup; not yet active in gap detection |
| Skill taxonomy | JD-driven + role seeding | NOT ESCO |
| Graph (future) | PostgreSQL skill_relationships + NetworkX | Week 6+ if needed |
| Infra future | Google Cloud Run | separate per service |
| Queue future | Celery + Redis | Week 9–10 |

---

## Key Design Decisions

### No ESCO
Switched from ESCO to JD-driven + role-seeded taxonomy.
Skills come from team lead JDs (when received) and role seeding (now).

### Knowledge Graph — Deferred
Discussed Neo4j vs NetworkX vs relational approach.
Decision: NOT building knowledge graph for POC.
Reason: not enough data yet, premature optimization.
Simple prerequisites JSON field on skills table instead.
Revisit after Week 6 when real JD data arrives and taxonomy stable.
If needed: PostgreSQL skill_relationships table + NetworkX cached at startup.
Neo4j only if skills exceed 2000 and query performance degrades.

### Gap Detection Approach
Weighted scoring formula — no graph needed for now.
Prerequisites JSON field handles learning order.
Priority formula: role_importance × (1/time_to_learn) × demand_weight
Readiness score: weighted % of role requirements met.

### Role Seeding Strategy
No JDs yet → LLM generates requirements per role+seniority.
Company is R&D focused → domain-level requirements, not tool-specific.
When JDs arrive → JD ingestion overwrites seeded requirements.
Current seed source in repository is data-driven (`Data/extracted_skills_results.json`) and currently yields 22 roles in this environment.

### SQLite → PostgreSQL migration
Only DATABASE_URL changes. Schema identical.

### Gemini model — one place only
app/core/config.py → gemini_model: str = "gemini-2.5-flash-lite"

### LLM Architecture
- **Skill extraction (Layer 2)**: Primary = Gemini (google-generativeai), Secondary = OpenAI (available via LangChain, not actively used)
- **Both always active**: regex (Layer 1) + LLM (Layer 2) always run; results merged in extraction_pipeline.py
- **LangChain integration**: Provides unified interface for provider switching; all LLM calls decorated with `@traceable` for LangSmith logging
- **Config flexibility**: Switch between Gemini and OpenAI by environment or programmatically; NO code changes required to extraction pipeline
- **LangSmith tracing**: Optional observability for cost/latency metrics on all LLM calls (when LANGCHAIN_API_KEY or LANGSMITH_API_KEY set)

### Admin Role — is_manager Flag
- User role types stored in User.is_manager boolean flag (True = admin/manager, False = employee)
- Admin endpoints check: `if not current_user.is_manager: raise HTTPException(403, "Admin access required")`
- No separate "admin" or "employee" table; role is a simple boolean property on user

### Both extractors always run
REGEX_MINIMUM_THRESHOLD = 999

### passlib removed
Using bcrypt directly. bcrypt.hashpw() and bcrypt.checkpw().

### Async pipeline deferred
Synchronous for POC. Celery + Redis queue in Week 9–10.

---

## Project Structure
```
skill-intelligence/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── auth.py
│   │   │   ├── resume.py
│   │   │   ├── roles.py                 # Week 3 ✅
│   │   │   ├── gaps.py                  # Week 3 ✅
│   │   │   ├── learning.py              # Week 4/5 ✅ + compatibility routes
│   │   │   ├── dashboard.py           # User dashboard summary
│   │   │   ├── admin.py               # Admin overview + user management
│   │   │   ├── content.py             # Admin content + public personalized feed
│   │   │   ├── assessments.py         # Assessment generation/submission/admin monitor
│   │   │   └── router.py
│   │   ├── core/
│   │   │   ├── config.py              # ALL settings — Gemini + OpenAI LLM config here (PostgreSQL URL available but commented)
│   │   │   └── security.py            # JWT + bcrypt direct
│   │   ├── db/
│   │   │   └── session.py             # SQLite: WAL + busy_timeout on connect
│   │   ├── models/
│   │   │   └── models.py              # all core DB tables (+ Week 3/4 learning fields)
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── resume.py
│   │   │   ├── roles.py               # Week 3 ✅
│   │   │   ├── gaps.py                # Week 3 ✅
│   │   │   └── learning.py            # Week 4 ✅ (generation rules still refined — see Week 4 status)
│   │   ├── services/
│   │   │   ├── extraction/
│   │   │   │   ├── regex_extractor.py
│   │   │   │   ├── llm_extractor.py
│   │   │   │   └── extraction_pipeline.py
│   │   │   ├── normalization/
│   │   │   │   └── skill_normalizer.py
│   │   │   ├── parsing/
│   │   │   │   ├── resume_parser.py
│   │   │   │   ├── quality_router.py
│   │   │   │   └── resume_processor.py
│   │   │   ├── gap/
│   │   │   │   └── gap_detector.py      # Week 3 ✅
│   │   │   └── learning/
│   │   │       └── path_generator.py    # Week 4 ✅ (roadmap/week packing — behavior still under review)
│   │   └── main.py
│   ├── scripts/
│   │   ├── seed_roles.py                # Week 3 ✅
│   │   ├── assign_skill_bands.py
│   │   └── add_skill_band_column.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── test_resume_parser.py
│   │   │   └── test_skill_normalizer.py
│   │   └── integration/
│   │       ├── test_gaps_flow.py
│   │       ├── test_roles_and_learning_flow.py
│   │       └── test_learning_roadmap_flow.py
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── docker-compose.yml
│   ├── .env.example
│   └── CLAUDE.md                        # This file
├── frontend/
│   └── src/                             # React (JSX) + Vite + Tailwind
└── docs/
    └── features/                        # See “Feature documentation” below
```

---

## Feature documentation

Longer feature notes (outside this file) live under `docs/features/`:

- `resume-parsing.md`
- `skill-normalization.md`
- `extraction-orchestration.md`
- `role-management-system.md`
- `skill-gap-analysis.md`
- `learning-path-generation.md`
- `user-intelligence-dashboard.md`
- `content-ingestion-pipeline.md`
- `automated-assessments.md`

---

## DB Tables

| Table | Purpose | Key Fields |
|---|---|---|
| users | Employee accounts | email, hashed_password, department, manager_id, target_role_id, is_manager |
| resumes | Upload records | user_id, job_id, status, parse_confidence, parsed_sections (JSON) |
| projects | Project rows linked to a resume | resume_id, name, description, tech_stack, complexity_score, team signals, dates |
| skills | Internal taxonomy | name, skill_type, category, aliases (JSON), embedding (JSON), prerequisites, difficulty, time_to_learn_hours |
| skill_prerequisites | Skill dependency graph | skill_id, prerequisite_skill_id |
| roles | Job roles | name, department, seniority_level, is_custom |
| role_skill_requirements | Role → skills mapping | role_id, skill_id, importance, is_mandatory, min_proficiency |
| extracted_skills | Skills from resume | resume_id, skill_id, extractor, confidence, source_section, frequency |
| user_skill_scores | Proficiency per user | user_id, skill_id, proficiency, proficiency_score, years_of_experience, frequency, user_override, manager_override |
| skill_snapshots | History | user_id, snapshot_data (JSON), created_at |
| skill_gaps | Gaps vs role | user_id, skill_id, role_id, gap_type, priority_score, time_to_learn_hours |
| learning_plans | User plan | user_id, role_id, status, total_hours_estimate |
| learning_plan_items | Plan items (skills) | plan_id, skill_id, order, resource_type, title, url, provider, status, skill_band, subtopics_json, completed_at |
| learning_plan_item_subtopics | Item subtopics (JSON) | item_id, subtopic_json |
| learning_plan_item_sub_subtopics | Leaf-level content | subtopic_id, sub_subtopic_json |
| learning_plan_item_resources | Learning resources | item_id, type, title, url, provider, estimated_hours |
| content_items | Curated learning content | title, source_url, difficulty_level, skill_tags |
| content_chunks | Searchable content chunks | content_item_id, chunk_text, chunk_index |
| assessments | Question bank | skill_name, difficulty, question_type, question_text, options, correct_option |
| assessment_attempts | User assessment submissions | user_id, assessment_id, answer, is_correct, score, max_score, time_taken_seconds |

---

## API Endpoints

### Core working endpoints (Weeks 1–4)
| Method | Endpoint | Description |
|---|---|---|
| POST | /api/v1/auth/register | Create user |
| POST | /api/v1/auth/login | Get JWT token |
| GET | /api/v1/auth/me | Current user |
| GET | /api/v1/auth/oauth/{provider}/url | OAuth authorization URL |
| POST | /api/v1/auth/oauth/{provider}/callback | OAuth callback exchange |
| POST | /api/v1/resumes/upload | Upload PDF/DOCX |
| GET | /api/v1/resumes/{job_id}/status | Processing status |
| POST | /api/v1/resumes/{job_id}/process | Run full pipeline |
| GET | /api/v1/resumes/{job_id}/results | Get skill profile |
| GET | /api/v1/roles/skills/search | Search skills for role editing |
| GET | /api/v1/roles | List all roles |
| GET | /api/v1/roles/{id}/skills | Role skill requirements |
| PUT | /api/v1/roles/{id}/skills | HR override |
| DELETE | /api/v1/roles/{id} | Remove role |
| POST | /api/v1/users/me/target-role | Set target role (name fallback added) |
| GET | /api/v1/users/me/gaps | Skill gaps vs role |
| GET | /api/v1/users/me/gaps/summary | Readiness score + counts |
| GET | /api/v1/users/me/dashboard | User dashboard data |

### Learning endpoints (implemented)
| Method | Endpoint | Status | Description |
|---|---|---|---|
| GET | /api/v1/users/me/learning-plan | ✅ Working | Get learning plan |
| GET | /api/v1/users/me/learning-roadmap | ✅ Working | Generate/reuse hierarchical roadmap |
| PATCH | /api/v1/users/me/learning-plan/{plan_id}/items/{item_id}/progress | ✅ Working | Mark item progress and update plan status |
| POST | /api/v1/users/me/learning-plan/{plan_id}/items/{item_id}/assessment-feedback | ✅ Working | Submit assessment feedback for item |
| GET | /api/v1/users/me/learning-plan/progress | ✅ Working | Overall progress summary |
| POST | /api/v1/users/me/manual-analysis | ✅ Working | Manual skill input analysis against target role |

### Admin + content + assessment endpoints (implemented)
| Method | Endpoint | Status | Description |
|---|---|---|---|
| GET | /api/v1/admin/overview | ✅ Working | Admin overview metrics |
| GET | /api/v1/admin/users | ✅ Working | Admin user list/filter |
| POST | /api/v1/admin/users/{user_id}/toggle-active | ✅ Working | Toggle user active state |
| POST | /api/v1/admin/users/{user_id}/role | ✅ Working | Update user role (admin/employee) |
| GET | /api/v1/admin/users/{user_id}/progress | ✅ Working | User progress detail for admin |
| GET | /api/v1/admin/content | ✅ Working | List uploaded content |
| POST | /api/v1/admin/content/upload | ✅ Working | Upload and chunk content |
| DELETE | /api/v1/admin/content/{title} | ✅ Working | Delete content by title |
| GET | /api/v1/content/personalized | ✅ Working | Personalized content feed |
| POST | /api/v1/assessments/generate | ✅ Working | Generate assessment questions |
| POST | /api/v1/assessments/submit | ✅ Working | Submit assessment answers |
| POST | /api/v1/assessments/mastery/update | ✅ Working | Mastery update placeholder endpoint |
| GET | /api/v1/admin/assessments | ✅ Working | Admin list of assessment attempts |
| GET | /api/v1/admin/assessments/summary | ✅ Working | Admin assessment summary |

### Week 7–8 — To Build
| Method | Endpoint | Description |
|---|---|---|
| PATCH | /api/v1/users/me/skills/{skill_id} | User correction |
| PATCH | /api/v1/manager/users/{user_id}/skills/{skill_id} | Manager validation |
| GET | /api/v1/users/me/skill-history | Skill evolution |
| GET | /api/v1/manager/team | Team overview |
| GET | /api/v1/manager/team/gaps | Team gap summary |

### Week 9–10 — To Build
| Method | Endpoint | Description |
|---|---|---|
| POST | /api/v1/admin/batch-ingest | Bulk resume upload |
| GET | /api/v1/admin/batch/{batch_id}/status | Batch progress |
| POST | /api/v1/admin/roles | Create role |
| PUT | /api/v1/admin/roles/{id} | Edit role |
| GET | /api/v1/admin/team/coverage | Team skill coverage |
| GET | /api/v1/admin/skills/taxonomy | Full skill list |
| POST | /api/v1/admin/skills | Add skill manually |

### Future — JD Ingestion (when data arrives)
| Method | Endpoint | Description |
|---|---|---|
| POST | /api/v1/roles/ingest-jd | Ingest JD → role requirements |

---

## Environment Variables (.env)

Place `.env` in **`backend/`** when running the FastAPI app from that directory.

```bash
APP_ENV=development
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./skilldb.sqlite3
SECRET_KEY=your-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# LLM — Gemini (primary) + OpenAI (secondary, available for fallback)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash-lite
OPENAI_API_KEY=sk-your-openai-key

# File uploads
MAX_UPLOAD_SIZE_MB=10
UPLOAD_DIR=/tmp/skill-intelligence/uploads

# Redis cache (optional until Week 9–10)
REDIS_URL=redis://localhost:6379/0

# LangSmith observability (optional, for LLM tracing)
# Accepts both LANGCHAIN_* and LANGSMITH_* env prefixes
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGSMITH_PROJECT=skill-intelligence
```

### LLM Setup Note
- **Active extractor**: Gemini (google-generativeai) — primary skill extraction engine
- **Available alternative**: OpenAI (via LangChain) — not currently used in core pipeline but integrated for future flexibility
- **Orchestration**: LangChain 0.2.5 provides unified provider interface + `@traceable` decorators for LangSmith logging
- **Observability**: LangSmith env settings (LANGCHAIN_API_KEY or LANGSMITH_API_KEY) enable optional cost/latency tracing for both Gemini and OpenAI calls

---

## Extraction Pipeline
```
Resume PDF/DOCX
      ↓
Stage 2 — pdfplumber / python-docx → raw_text + sections dict
      ↓
Stage 2.8 — quality_router.py
      score >= 0.7 → high quality
      score <  0.7 → low quality (LLM direct)
      ↓
Stage 3.1 — regex_extractor.py    (always runs)
           + llm_extractor.py     (always runs — THRESHOLD=999)
      ↓
extraction_pipeline.py — merge + deduplicate + canonical names
      ↓
Stage 3.3 — skill_normalizer.py — alias → exact → cosine similarity
      ↓
If new skill not in taxonomy → auto-add to skills table
      ↓
Stage 5 — feature engineering (years_exp, frequency, context_strength)
      ↓
Stage 6 — _estimate_proficiency() rule-based
      ↓
DB → extracted_skills + user_skill_scores
```

---

## Dedup Map (extraction_pipeline.py)
```
React / ReactJS / React.js                → React
Node.js / NodeJS                          → Node.js
OOP / OOPS / Object-Oriented Design       → Object-Oriented Programming
DSA / Algorithms / Data Structures        → Data Structures & Algorithms
HITL / Human-in-the-Loop                  → Human-in-the-Loop
VS Code / VSCode                          → VS Code
Core Java / Java                          → Java
HuggingFace / Hugging Face Transformers   → HuggingFace Transformers
Scikit-learn / sklearn                    → Scikit-learn
Vue.js / VueJS                            → Vue.js
Next.js / NextJS                          → Next.js
C++ (stored as cpp key)                   → C++
```

---

## Proficiency Rules
```
File: app/services/parsing/resume_processor.py → _estimate_proficiency()

years_experience:   min(years/5, 1.0) × 0.5
frequency >= 5:     +0.4
frequency >= 3:     +0.3
frequency >= 2:     +0.2
frequency  = 1:     +0.1
confidence >= 0.95: +0.15
confidence >= 0.85: +0.10

score >= 0.60 → advanced
score >= 0.30 → intermediate
else          → beginner
```

---

## Section Detection
```
File: app/services/parsing/resume_parser.py

Canonical sections:
  experience, skills, education, projects,
  certifications, summary, languages, extracurricular

Header filters:
  > 60 chars                              → not a header
  < 4 chars                               → not a header
  digit_ratio > 0.3                       → not a header
  ends with . or ,                        → not a header
  3+ title case words not in aliases      → person's name, skip
  IGNORE_LINES set                        → references, declaration, date, place

Extracurricular → recognised, excluded from skill extraction
Misc sections   → kept only if content > 100 chars
```

---

## Role Seeding Details (Week 3)
```
Script: scripts/seed_roles.py

Current repository seed source: Data/extracted_skills_results.json
Current observed count in this environment: 22 role entries (data-driven)
Note: Role counts are generated from input data and may change when source data changes.

LLM prompt approach:
  Input: "{seniority} {role} at R&D-focused tech company"
  Output: domain-level skills (not tool-specific)
  Core skills: non-negotiable fundamentals
  Domain skills: category-level (e.g. "backend framework" not "FastAPI")
  Specific tools: examples only, not hard requirements
  Also generates: prerequisites per skill, time_to_learn_hours, difficulty 1-5
```

---

## Week 3-4 Implementation: Discoveries & Learnings

### Key Discoveries Made During Implementation

**1. Role Name Fallback Essential for UX**
- Initial design had target-role endpoint accepting only role_id
- Users conceptually think about roles by name, not ID
- Solution: Added backward-compatible name-as-id fallback in SetTargetRoleRequest
- Allows Swagger users to send `{"role_name": "Senior Software Engineer"}` and it auto-resolves the ID
- Makes API more intuitive; users don't need to query roles first to get IDs

**2. ORM Field Naming Matters After Migration**
- Bug caught in gap detector: referenced `req.required_proficiency` (doesn't exist)
- Actual field is `req.min_proficiency` in RoleSkillRequirement model
- Lesson: When designing schema, field names should be consistent and unambiguous
- Test it early: integration tests caught this immediately (without tests, would fail in production)

**3. .env Syntax Errors Silent Until Runtime**
- python-dotenv produces warnings only at startup, not at parse
- Comment syntax must use `#`, not `;` — dotenv is strict about this
- Lesson: Validate .env on startup; can add env validation as part of app initialization

**4. Prerequisites JSON Working Better Than Alternatives**
- Simple prerequisites JSON list on Skill model is sufficient for MVP
- No need for knowledge graph; ordering by depth handles 95% of use cases
- Only 11-15 prerequisites per skill typically; can compute coverage in Python
- Revisit Neo4j/NetworkX only if prerequisites exceed 100+ per skill or queries slow

**5. Learning Plan Generation Works End-to-End**
- Gap detector → path generator → LearningPlanResponse completes full flow
- Sorting by (prerequisite_depth, priority_score, importance, mandatory) produces intuitive order
- Placeholder resources (guide + practice) acceptable for MVP; can swap for real APIs later
- Total hours estimation reliable; matches time_to_learn_hours from seed

**6. Role Department = NULL Decision Saves Time**
- User asked to defer department assignment; set role.department = NULL
- Allows seeding scripts to be idempotent (can re-run without overwriting department)
- When JDs/HR data arrives → single UPDATE can populate all departments at once
- Clean separation: role taxonomy separate from org structure

**7. Readiness Score Formula Validated**
- Formula: priority_score = importance × (1/time_to_learn_hours) × mandatory_weight × prereq_coverage
- Produces natural ordering: high-impact, quick skills first
- Proficiency scoring (missing=0, weak=0.3, strong=0.8) makes readiness_score intuitive (0.0-1.0)
- Integration tests confirm: typical user gets 0.4-0.6 readiness for mid-level roles

### Integration Test Coverage Achieved
- **test_roles_endpoints_integration**: GET /roles, GET /roles/{id}/skills, PUT /roles/{id}/skills ✅
- **test_gaps_flow_end_to_end**: Full flow register → upload → process → set role → gaps ✅
- **test_gaps_negative_paths**: 401 (no auth), 400 (no target role) ✅
- **test_set_target_role_by_name_compatibility**: Target role by name ✅
- **test_learning_plan_endpoint_integration**: GET /learning-plan with sorted items ✅
- **test_learning_roadmap_flow.py** (7 cases): roadmap auth/requirements, full flow, idempotency, progress lifecycle, progress summary, no-plan path ✅
- **Total: 12 integration test cases across 3 files** (runtime varies with I/O; roadmap tests are async)

### Code Quality Observations
- Async/await pattern stable; no race conditions found in testing
- SQLite performs well for role/skill/gap queries (< 100ms)
- Pydantic validation catches schema errors early
- Service layer separation (gap_detector, path_generator) makes testing easy

---

## Known Issues / Tech Debt

| Issue | Priority | Status | Week |
|---|---|---|---|
| prerequisites field in skills table | ✅ Done | Implemented Week 3 | 3 |
| Gap detection endpoint fixed | ✅ Done | req.min_proficiency corrected | 3 |
| Role name fallback added | ✅ Done | target-role accepts id OR name | 3 |
| .env dotenv parse warning | ✅ Done | Comment syntax fixed (`;` to `#`) | 4 |
| JD ingestion not built | High | Waiting for data | when data arrives |
| Learning path generation logic finalization | High | Prototype works; ordering/week-packing/regeneration rules still under review | 4-5 |
| Async pipeline not built | Medium | Sync processing fine for POC | 9–10 |
| sentence-transformers not active | Low | embeddings setup later | 11–12 |
| No ML proficiency model | Medium | Rule-based sufficient now | 11–12 |
| No batch processing | Medium | Celery + Redis | 9–10 |
| pgvector only for production | Low | PostgreSQL migration later | 6 |
| No LangSmith yet | Medium | Cost tracking | 6 |
| Resource fetching not built | Medium | Placeholder stubs working | 4 |
| google.generativeai deprecation warning | Low | Migrate to google-genai | 6 |
| Resource provider abstraction | Medium | Coursera/YouTube/Gemini | 6 |
| PostgreSQL migration for new columns | Low | skill_band, completed_at, subtopics_json | 6 |
| 5 resume parser unit test failures | Medium | Pre-existing expectation drift in test_resume_parser.py | 6 |
| subtopics_json migration needed for old plans | Low | Auto-invalidates on next load | 6 |
| AssessmentResultsPage localStorage-only | Medium | Backend-backed persistence | 6 |
| AssessmentMonitorPage error swallowing | Low | `.catch(() => {})` hides load failures — add error UI | 6 |
| getDashboard() unused in pages | Low | Exported in `api.js` but dashboard uses gap/plan/progress calls directly — remove or wire | 6 |
| DashboardPage double .map() on skills | Low | Minor cleanup | 6 |
| SQLite WAL + busy timeout | ✅ Done | `session.py` PRAGMA on SQLite connect | 6 |
| Employee import from Excel not built | Medium | scripts/seed_employees.py | 9–10 |

---

## Business Context

- Internal tool — not public product
- 188 employees across multiple departments
- Technical roles only in scope for now
- Non-technical roles (HR, Finance, Sales, Admin) deferred to later phase
- Team lead provides JDs — not yet received
- R&D company — evaluates and picks best stack per project
- No single enforced tech stack
- Manager validation important for accuracy
- HR admin panel needed for role management
- Voice agent mentioned as future separate deployment — not yet scoped
- Excel data available for employee import when ready (Week 9–10)

---

## Coding Guidelines for Claude

- Always give file name before code block
- Specify exactly where to paste:
  - "Replace entire file"
  - "Replace function X"
  - "Add after line Y"
  - "Find X, replace with Y"
- Do NOT create files in session — user pastes manually
- Give downloadable zip at end of each completed week
- Backend: Python + FastAPI unless frontend specified
- Frontend (Week 5): React (JSX) + Vite + Tailwind — source files are `.jsx`; `@types/react` is for editor/typing only
- Follow existing patterns exactly — no unnecessary refactoring
- SQLite now, all decisions must be PostgreSQL-compatible
- Gemini model: always use settings.gemini_model — never hardcode
- When fixing bugs: exact find + replace
- When adding features: full file or exact insertion point
- Keep responses focused — one file at a time unless closely related

---

## Append-Only Update Log

### 2026-04-09 — Full codebase reconciliation (CLAUDE.md)

- Corrected **monorepo layout**: documented `backend/`, `frontend/`, `docs/features/`; fixed tree so paths match the repo (this file is `backend/CLAUDE.md`).
- Aligned **frontend stack** everywhere: React **JSX** + Vite + Tailwind (not TypeScript); noted optional `@types/react`.
- Added **Feature documentation** section listing all `docs/features/*.md` topics.
- Expanded **scripts/** and **tests/** in the tree: `assign_skill_bands.py`, `add_skill_band_column.py`, `test_learning_roadmap_flow.py`, `conftest.py`.
- Updated **integration test inventory** to 12 cases across 3 files; refreshed Week 4 testing bullets.
- **Tech stack / DB**: SQLite file location relative to `backend/` cwd; documented WAL + `busy_timeout` in `session.py`.
- **Known issues**: marked SQLite WAL as done; clarified `getDashboard` as unused by pages; kept AssessmentMonitorPage silent-catch as open.
- **Routes**: documented `/dashboard` and `/skill-analysis` redirects in `App.jsx`.

### 2026-04-06 — Consistency + Focus Reconciliation

- Reconciled planning/status contradictions across Current Status, Week sections, architecture stages, and Known Issues.
- Week 4 is now documented as implemented but still under active review for core path-generation behavior (ordering, week packing, resource quality, regeneration rules).
- Week 5 frontend status is aligned with actual code integration (roadmap flow wired), while preserving that hardening remains.
- Corrected learning endpoint method wording to match implementation (`PATCH /learning-plan/{plan_id}/items/{item_id}/progress`).
- Role count references standardized to current repository data source behavior: seed data currently yields 22 roles in this environment.
- Scope alignment note added: content ingestion + automated assessment modules were imported as scaffolding from another project and are intentionally not treated as first-class reviewed logic in this phase.
- Narrative focus explicitly centered on resume -> skills -> gaps -> learning path.

### 2026-04-02 — Current Implementation Snapshot (Do Not Replace Original Plan)

This section is an addendum to preserve the original roadmap while tracking what is currently implemented in code.

#### Backend updates confirmed in code

- Learning endpoints now use roadmap-first canonical routes beyond the original Week 4 note:
  - `GET /api/v1/users/me/learning-plan` (dynamic generation from gaps)
  - `PATCH /api/v1/users/me/learning-plan/{plan_id}/items/{item_id}/progress` (module completion status update)
  - `GET /api/v1/users/me/learning-roadmap`
  - `GET /api/v1/users/me/learning-plan/progress`
  - `POST /api/v1/users/me/manual-analysis`

- Learning plan behavior (current state):
  - `learning-plan` response is generated at request time using gaps + path generator.
  - Resource suggestions are still placeholder stubs (guide + practice style entries).
  - Progress endpoint is implemented; it updates persisted `learning_plan_items` when present.

- Additional backend feature areas now present (beyond early Week 1–4 scope):
  - Dashboard endpoint module.
  - Content management/ingestion endpoint module.
  - Assessments endpoint module.
  - Admin management endpoint module.
  - OAuth helper/callback routes in auth endpoints.

#### Testing snapshot

- Integration tests currently present (12 cases, 3 modules):
  - `tests/integration/test_roles_and_learning_flow.py` — roles, gaps negatives, learning plan
  - `tests/integration/test_gaps_flow.py` — gaps E2E, target role by name
  - `tests/integration/test_learning_roadmap_flow.py` — roadmap + progress (7 tests)

#### Frontend snapshot

- Frontend implementation is now partially built (not fully pending):
  - Protected routing + auth context in place.
  - Pages wired for dashboard, skills, roadmap, assessments, content, and admin flows.
  - OAuth callback route included.

#### Notes to keep roadmap interpretation clear

- Keep the original 12-week plan above unchanged as baseline intent.
- Treat this addendum as the source of truth for "implemented in repository right now".
- Remaining Week 4 production-hardening work still applies (clean persistence model, richer progress semantics, external resource integrations, and additional E2E coverage).

### 2026-04-02 — Week 4 + Week 5 Completion Snapshot

Week 4 additions beyond original plan:
- Week-wise roadmap with 3-level topic hierarchy
  (skill → subtopics → sub-subtopics)
- Dependency-aware week packing using Kahn's topological sort
- skill_band field on Skill model + assign_skill_bands.py script
- Subtopics persisted as JSON on LearningPlanItem.subtopics_json
- Auto-invalidation: plans without subtopics regenerate once on next load
- item_id exposed on WeekSkillNode for progress tracking
- item_status seeded from DB on roadmap load
- force_regenerate parameter for on-demand plan refresh
- 7 integration tests for full roadmap flow (0 failures)

Week 5 additions:
- api.js updated with getLearningRoadmap, updateItemProgress,
  getProgressSummary; PATCH method fix on progress update
- DashboardPage rewired from /dashboard (nonexistent) to real
  endpoint composition via Promise.allSettled
- RoadmapPage rewritten to week-wise hierarchy with subtopic
  expand/collapse, skill_band badges, inline progress update
- AdminDashboardPage error state added (was silently swallowing)
- ContentIngestionPage metadata now forwarded to API
- Backend: SQLite WAL mode + busy timeout enabled in `app/db/session.py` (Week 6 infra note largely satisfied for local SQLite)

Assessment → roadmap update path (planned for future weeks):
- Assessment completion triggers force_regenerate=True
- Gemini reruns with updated gap_type (weak vs missing) per skill
- Subtopics regenerated focusing on failed areas
- Persisted immediately, loaded from DB on next visit