# Database Schema (SQLite dev / PostgreSQL-compatible)

Source of truth: `backend/app/models/models.py`.

This project uses **SQLAlchemy 2.0 async** models. In local dev the DB is typically **SQLite** at `backend/skilldb.sqlite3`.

## How the learning path is stored

The learning roadmap is persisted as:

- **`learning_plans`**: one row per user × role “plan” (active/in_progress/completed)
- **`learning_plan_items`**: ordered items inside a plan (one row per skill/module)

The 3-level hierarchy (skill → subtopics → sub-subtopics) and resource suggestions are stored in **`learning_plan_items.subtopics_json`** as JSON text.

### `learning_plan_items.subtopics_json` format

Backward-compatible loader supports two shapes:

1) **Legacy list**

```json
[
  {
    "title": "Subtopic A",
    "estimated_hours": 10.0,
    "sub_subtopics": [
      { "title": "Leaf 1", "estimated_hours": 5.0 },
      { "title": "Leaf 2", "estimated_hours": 5.0 }
    ]
  }
]
```

2) **Wrapper (current)**

```json
{
  "subtopics": [
    {
      "title": "Subtopic A",
      "estimated_hours": 10.0,
      "sub_subtopics": [
        { "title": "Leaf 1", "estimated_hours": 5.0 },
        { "title": "Leaf 2", "estimated_hours": 5.0 }
      ]
    }
  ],
  "resources": [
    {
      "title": "Example resource",
      "provider": "Official Docs",
      "url": "https://example.com",
      "resource_type": "docs",
      "estimated_hours": 2.0,
      "why": "Why this resource fits."
    }
  ]
}
```

Where:
- `subtopics[].sub_subtopics[]` are the **3rd level** leaves.
- `resources[]` are Gemini-suggested learning resources (Gap 1).

## Tables

Below is a concise inventory of all tables defined in `models.py`.

### `users`

**Purpose**: user accounts + org metadata + role targeting.

**Key columns**
- `id` (PK, UUID string)
- `email` (unique)
- `hashed_password`
- `full_name`
- `department`, `job_title`, `seniority_level`
- `manager_id` (FK → `users.id`)
- `target_role_id` (FK → `roles.id`)
- `is_active`, `is_manager`
- `created_at`, `updated_at`

### `resumes`

**Purpose**: uploaded resume files + processing state.

**Key columns**
- `id` (PK)
- `user_id` (FK → `users.id`)
- `file_name`, `file_type`, `file_hash`, `file_path`
- `job_id` (indexed)
- `status`, `error_message`
- `raw_text`
- `parsed_sections` (JSON string)
- `parse_confidence`, `layout_type`
- `created_at`, `processed_at`

### `skills`

**Purpose**: internal skill taxonomy.

**Key columns**
- `id` (PK)
- `name` (indexed)
- `description`
- `skill_type` (technical/soft/domain/tool/language)
- `category`
- `skill_band`
- `aliases` (JSON list as text)
- `prerequisites` (JSON list as text; names)
- `difficulty` (1..5)
- `time_to_learn_hours`
- `source_role`
- `embedding` (JSON float list as text)
- `created_at`

### `roles`

**Purpose**: job roles used for requirements and gap detection.

**Key columns**
- `id` (PK)
- `name` (indexed)
- `description`
- `department`, `seniority_level`
- `esco_occupation_id` (legacy field)
- `is_custom`

### `role_skill_requirements`

**Purpose**: role → required skills mapping.

**Constraints**
- Unique (`role_id`, `skill_id`)

**Key columns**
- `id` (PK)
- `role_id` (FK → `roles.id`)
- `skill_id` (FK → `skills.id`)
- `importance` (float)
- `is_mandatory` (bool)
- `min_proficiency` (string, default `intermediate`)

### `extracted_skills`

**Purpose**: skill mentions extracted from a resume.

**Constraints**
- Unique (`resume_id`, `skill_id`)

**Key columns**
- `id` (PK)
- `resume_id` (FK → `resumes.id`)
- `skill_id` (FK → `skills.id`, nullable while normalizing)
- `raw_text`
- `extractor` (regex/llm)
- `confidence`
- `source_section`, `source_text`
- `frequency`

### `projects`

**Purpose**: project rows extracted/associated with a resume.

**Key columns**
- `id` (PK)
- `resume_id` (FK → `resumes.id`)
- `name`, `description`
- `tech_stack` (JSON string)
- `complexity_score`
- `is_team_project`, `team_size_signal`
- `start_date`, `end_date`

### `user_skill_scores`

**Purpose**: per-user proficiency per skill.

**Constraints**
- Unique (`user_id`, `skill_id`)

**Key columns**
- `id` (PK)
- `user_id` (FK → `users.id`)
- `skill_id` (FK → `skills.id`)
- `proficiency` (beginner/intermediate/advanced)
- `proficiency_score` (float)
- `years_of_experience`, `frequency`, `recency_months`
- `project_complexity_max`, `context_strength`
- `user_override`, `manager_validated`, `manager_override`
- `updated_at`

### `skill_snapshots`

**Purpose**: historical snapshots of a user’s skill profile.

**Key columns**
- `id` (PK)
- `user_id` (FK → `users.id`)
- `snapshot_data` (JSON string)
- `created_at`

### `skill_gaps`

**Purpose**: persisted gap results for a user vs a role.

**Constraints**
- Unique (`user_id`, `skill_id`, `role_id`)

**Key columns**
- `id` (PK)
- `user_id` (FK → `users.id`)
- `skill_id` (FK → `skills.id`)
- `role_id` (FK → `roles.id`)
- `gap_type` (`missing` or `weak`)
- `priority_score` (float)
- `time_to_learn_hours`
- `current_proficiency`, `required_proficiency`
- `created_at`, `resolved_at`

### `learning_plans`

**Purpose**: a persisted plan instance per user/role.

**Key columns**
- `id` (PK)
- `user_id` (FK → `users.id`)
- `role_id` (FK → `roles.id`)
- `total_hours_estimate`
- `status` (`active`/`in_progress`/`completed`)
- `created_at`, `updated_at`, `completed_at`

### `learning_plan_items`

**Purpose**: the ordered modules of a plan (one module per skill).

**Key columns**
- `id` (PK)
- `plan_id` (FK → `learning_plans.id`)
- `skill_id` (FK → `skills.id`)
- `order` (int; lower = earlier)
- `priority_score` (float; used for rerank logic)
- `resource_type` (currently used as `gap_type`: `missing`/`weak`)
- `title` (skill name)
- `url`, `provider` (legacy fields; resources now live in `subtopics_json` wrapper)
- `skill_band`
- `subtopics_json` (JSON text; subtopics + resources)
- `estimated_hours`
- `status` (`not_started`/`in_progress`/`completed`/`needs_review`)
- `completed_at`

### `content_items`

**Purpose**: admin-curated learning content.

**Key columns**
- `id` (PK)
- `title` (indexed)
- `source_url`
- `difficulty_level`
- `skill_tags` (JSON)
- `created_at`

### `content_chunks`

**Purpose**: chunked text for search/retrieval over content.

**Key columns**
- `id` (PK)
- `content_item_id` (FK → `content_items.id`, indexed)
- `chunk_text`
- `chunk_index`

### `assessments`

**Purpose**: generated questions (simple question bank).

**Key columns**
- `id` (PK)
- `skill_name` (indexed)
- `difficulty`
- `question_type`
- `question_text`
- `options` (JSON)
- `correct_option`
- `created_at`

### `assessment_attempts`

**Purpose**: user submissions against assessments.

**Key columns**
- `id` (PK)
- `user_id` (FK → `users.id`, indexed)
- `assessment_id` (FK → `assessments.id`, indexed)
- `answer`
- `is_correct`
- `score`, `max_score`
- `time_taken_seconds`
- `submitted_at` (indexed)

