# Skill Intelligence System

AI-powered skill extraction, gap detection, and personalized learning path generation for internal company use.

---

## Tech Stack

| Layer | Tech |
|---|---|
| API | FastAPI + Python 3.11 |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Embeddings | sentence-transformers (MiniLM-L6-v2) |
| LLM | OpenAI / Gemini via LangChain |
| Infra | Docker + Google Cloud Run |

---

## Prerequisites

Install these before starting:

- **Python 3.11+** → https://python.org
- **Docker Desktop** → https://docker.com/products/docker-desktop
- **Git** → https://git-scm.com

---

## Step 1 — Clone / Unzip
```bash
unzip skill-intelligence.zip
cd skill-intelligence
```

---

## Step 2 — Python Virtual Environment
```bash
# Create venv
python -m venv venv

# Activate — Mac/Linux
source venv/bin/activate

# Activate — Windows (PowerShell)
.\venv\Scripts\Activate.ps1
& c:\Users\Rohit.r\Desktop\skill-intelligence\venv\Scripts\Activate.ps1

# Activate — Windows (CMD)
venv\Scripts\activate.bat

# Confirm correct Python
python --version   # should say 3.11+
```

---

## Step 3 — Install Dependencies
```bash
pip install -r requirements.txt
```

This installs FastAPI, SQLAlchemy, pdfplumber, sentence-transformers, and all other deps.
First run takes 2–3 minutes (sentence-transformers is large).

---

## Step 4 — Environment Variables
```bash
cp .env.example .env
```

Open `.env` and set:
```
SECRET_KEY=any-random-string-at-least-32-characters-long
# Leave OPENAI_API_KEY blank for now — not needed until Week 3
```

### LangSmith (optional — LLM tracing)

Resume skill extraction is traced with LangSmith when enabled. Add to `.env`:

```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=skill-intelligence
```

Legacy names `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, and `LANGCHAIN_PROJECT` are also accepted. On startup the app syncs these into the environment so the LangSmith client picks them up.

---

## Step 5 — Database Setup

### Option A (recommended) — Neon Postgres

1. Create a Neon project + database and copy the **Direct** connection string.
2. Set this in `backend/.env`:

```
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>/<db>?sslmode=require
```

3. Run migrations:

```bash
alembic upgrade head
```

4. Seed baseline roles/skills (fresh DB):

```bash
python scripts/seed_roles.py
```

### Option B — SQLite (local-only dev)

No setup needed. SQLite is built into Python.

The database file `skilldb.sqlite3` will be created automatically in the `backend/` directory when you first run the API.

Just make sure your `.env` has:

```
DATABASE_URL=sqlite+aiosqlite:///./skilldb.sqlite3
```

## Step 6 — Run the API
```bash
uvicorn app.main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     database_ready
INFO:     skill_normalizer_ready
```

---

## Step 7 — Verify it works

Open in browser:
```
http://localhost:8000/docs
```

Swagger quick login credential (local dev):
```
username: admin
password: admin123
```

This login path auto-creates a local admin user (`admin@local.dev`) on first use.

Try in order:
1. `POST /api/v1/auth/register` — create a user
2. `POST /api/v1/auth/login` — get a JWT token
3. `GET /api/v1/auth/me` — verify token works
4. `POST /api/v1/resumes/upload` — upload a PDF resume

---
## Step 8 — Ingest JDs to build your skill taxonomy

Once the API is running, for each JD your team lead provides:
```bash
POST /api/v1/roles/ingest-jd
{
  "role_name": "Backend Engineer",
  "jd_text": "paste the full JD here..."
}
```
This automatically:
- Creates the role in the DB
- Extracts required skills using LLM
- Builds your internal skill taxonomy
- Stores role → skill requirements for gap detection

No CSV downloads, no external datasets needed.
Your taxonomy grows as you add more JDs.
```

---

## Running Tests
```bash
pytest tests/unit/ -v
```

---

## Common Issues

**`connection refused` on DB**
```bash
# Mac — check postgres is running
brew services list | grep postgresql

# Start it if stopped
brew services start postgresql@16

# Ubuntu
sudo systemctl status postgresql
sudo systemctl start postgresql

# Windows — open Services app, find PostgreSQL, click Start
```

**`role "postgres" does not exist` on Mac**
```bash
# Mac Homebrew creates a role matching your system username, not "postgres"
# Either create the postgres role:
createuser -s postgres

# Or use your system username in .env:
DATABASE_URL=postgresql+asyncpg://YOUR_MAC_USERNAME:@localhost:5432/skilldb
```

**`extension "vector" does not exist`**
```bash
# pgvector not installed or not enabled — run inside psql:
psql -U postgres -d skilldb
CREATE EXTENSION vector;
\q
```

**`ModuleNotFoundError: No module named 'app'`**
```bash
# Always run from the project root folder
cd skill-intelligence
uvicorn app.main:app --reload
```

**Port 8000 already in use**
```bash
uvicorn app.main:app --reload --port 8001
```