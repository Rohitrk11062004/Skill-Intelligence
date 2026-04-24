import json
import os
import time
import uuid


def _require_requests():
    try:
        import requests  # type: ignore
    except Exception as e:
        raise SystemExit(f"requests not available in venv: {e}")
    return requests


def main() -> int:
    requests = _require_requests()

    base = os.environ.get("SKILLLENS_BASE_URL", "http://localhost:8000").rstrip("/")
    api = base + "/api/v1"

    s = requests.Session()

    def post_json(path: str, payload: dict, token: str | None = None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return s.post(api + path, headers=headers, data=json.dumps(payload), timeout=60)

    def post_form(path: str, payload: dict, token: str | None = None):
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return s.post(api + path, headers=headers, data=payload, timeout=60)

    def get(path: str, token: str | None = None, params: dict | None = None, timeout: int = 60):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return s.get(api + path, headers=headers, params=params, timeout=timeout)

    print("### Backend health")
    r = requests.get(base + "/openapi.json", timeout=20)
    print("openapi", r.status_code)
    r.raise_for_status()

    rand = uuid.uuid4().hex[:8]
    employee = {
        "username": f"user_{rand}",
        "email": f"user_{rand}@example.com",
        "password": "Password123",
        "full_name": f"User {rand}",
        "account_role": "employee",
    }
    hr = {
        "username": f"hr_{rand}",
        "email": f"hr_{rand}@example.com",
        "password": "Password123",
        "full_name": f"HR {rand}",
        "account_role": "hr",
    }

    print("\n### Register + login employee")
    r = post_json("/auth/register", employee)
    print("register", r.status_code)
    if r.status_code not in (200, 201):
        raise SystemExit(r.text)

    r = post_form("/auth/login", {"username": employee["username"], "password": employee["password"]})
    print("login", r.status_code)
    r.raise_for_status()
    user_token = r.json()["access_token"]

    r = get("/auth/me", user_token)
    print("me", r.status_code, r.json().get("username"))
    r.raise_for_status()

    print("\n### Upload resume + process")
    resume_path = os.path.join(os.path.dirname(__file__), "..", "resume_cf5f1119.docx")
    resume_path = os.path.abspath(resume_path)
    if not os.path.exists(resume_path):
        raise SystemExit(f"Missing resume file: {resume_path}")

    with open(resume_path, "rb") as f:
        files = {
            "file": (
                os.path.basename(resume_path),
                f,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        r = s.post(api + "/resumes/upload", headers={"Authorization": f"Bearer {user_token}"}, files=files, timeout=120)
    print("upload", r.status_code)
    if r.status_code not in (200, 202):
        raise SystemExit(r.text)
    job_id = r.json().get("job_id")
    print("job_id", job_id)

    r = s.post(api + f"/resumes/{job_id}/process", headers={"Authorization": f"Bearer {user_token}"}, timeout=300)
    print("process", r.status_code)
    r.raise_for_status()

    status = None
    for i in range(20):
        r = s.get(api + f"/resumes/{job_id}/status", headers={"Authorization": f"Bearer {user_token}"}, timeout=30)
        r.raise_for_status()
        status = r.json().get("status")
        print("status", i, status)
        if status == "complete":
            break
        time.sleep(1)

    r = s.get(api + f"/resumes/{job_id}/results", headers={"Authorization": f"Bearer {user_token}"}, timeout=60)
    print("results", r.status_code)
    r.raise_for_status()
    skills = r.json().get("skills") or []
    print("skills_count", len(skills))

    print("\n### Set target role + generate roadmap")
    r = get("/roles", user_token)
    print("roles", r.status_code)
    r.raise_for_status()
    roles = r.json()
    if not roles:
        raise SystemExit("No roles in DB")
    role_id = roles[0]["id"]

    r = post_json("/users/me/target-role", {"role_id": role_id}, user_token)
    print("set_target_role", r.status_code)
    r.raise_for_status()

    print("requesting roadmap (can take a bit)...")
    r = get("/users/me/learning-roadmap", user_token, params={"hours_per_week": 10}, timeout=300)
    print("roadmap", r.status_code)
    r.raise_for_status()
    roadmap = r.json()
    plan_id = roadmap.get("plan_id")
    print("plan_id", plan_id, "weeks", len(roadmap.get("weeks") or []))
    if not plan_id:
        raise SystemExit("Roadmap missing plan_id")

    print("\n### Week assessment load + submit")
    week = 1
    print("requesting week assessment (can take a bit)...")
    r = s.get(api + f"/assessments/weeks/{plan_id}/{week}", headers={"Authorization": f"Bearer {user_token}"}, timeout=300)
    print("week_get", r.status_code)
    r.raise_for_status()
    data = r.json()
    qcount = int(data.get("question_count") or 0)
    print("question_count", qcount)
    answers = [0] * qcount

    r = s.post(
        api + f"/assessments/weeks/{plan_id}/{week}/submit",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"answers": answers},
        timeout=120,
    )
    print("week_submit", r.status_code)
    r.raise_for_status()

    r = get("/assessments/summary", user_token)
    print("assessments_summary", r.status_code)
    r.raise_for_status()
    print("summary", r.json())

    print("\n### Register + login HR (manager) + ingest JD")
    r = post_json("/auth/register", hr)
    print("register_hr", r.status_code)
    if r.status_code not in (200, 201):
        raise SystemExit(r.text)

    r = post_form("/auth/login", {"username": hr["username"], "password": hr["password"]})
    print("login_hr", r.status_code)
    r.raise_for_status()
    admin_token = r.json()["access_token"]

    with open(resume_path, "rb") as f:
        files = {
            "file": (
                "jd.docx",
                f,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        data = {"role_name": f"Role From JD {rand}", "department": "Engineering", "seniority_level": "Senior"}
        r = s.post(api + "/roles/ingest-jd", headers={"Authorization": f"Bearer {admin_token}"}, files=files, data=data, timeout=300)
    print("ingest_jd", r.status_code)
    r.raise_for_status()
    ingest = r.json()
    print("ingest_res", ingest)

    r = s.get(api + f"/roles/{ingest['role_id']}/skills", headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
    print("role_skills", r.status_code)
    r.raise_for_status()
    print("role_skill_count", len(r.json().get("skills") or []))

    print("\nOK: E2E smoke completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

