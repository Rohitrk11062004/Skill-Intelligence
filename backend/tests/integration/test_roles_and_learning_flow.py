import asyncio
import uuid

from fastapi.testclient import TestClient

from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.models import Role, RoleSkillRequirement, Skill


def _create_test_user_and_token(client: TestClient, suffix: str) -> str:
    email = f"roles_{suffix}@example.com"
    password = "StrongPass123!"

    register_payload = {
        "email": email,
        "password": password,
        "full_name": f"Roles User {suffix}",
        "department": "Engineering",
        "job_title": "Software Engineer",
    }
    reg = client.post("/api/v1/auth/register", json=register_payload)
    assert reg.status_code == 201, reg.text

    login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


async def _seed_role_with_skills(suffix: str) -> tuple[str, str, str]:
    async with AsyncSessionLocal() as db:
        role = Role(
            name=f"Roles Integration {suffix}",
            description="Role for roles endpoint integration tests",
            department=None,
            seniority_level="Mid-level",
            is_custom=True,
        )
        db.add(role)
        await db.flush()

        skill_a = Skill(
            name=f"Roles Skill A {suffix}",
            skill_type="technical",
            category="Technical Skills",
            prerequisites="[]",
            difficulty=3,
            time_to_learn_hours=80,
            source_role=role.name,
        )
        skill_b = Skill(
            name=f"Roles Skill B {suffix}",
            skill_type="technical",
            category="Technical Skills",
            prerequisites="[]",
            difficulty=2,
            time_to_learn_hours=40,
            source_role=role.name,
        )
        db.add_all([skill_a, skill_b])
        await db.flush()

        db.add_all(
            [
                RoleSkillRequirement(
                    role_id=role.id,
                    skill_id=skill_a.id,
                    importance=0.9,
                    is_mandatory=True,
                    min_proficiency="intermediate",
                ),
                RoleSkillRequirement(
                    role_id=role.id,
                    skill_id=skill_b.id,
                    importance=0.6,
                    is_mandatory=False,
                    min_proficiency="beginner",
                ),
            ]
        )

        await db.commit()
        return role.id, skill_a.id, skill_b.id


def test_roles_endpoints_integration():
    suffix = uuid.uuid4().hex[:8]

    with TestClient(app) as client:
        token = _create_test_user_and_token(client, suffix)
        headers = {"Authorization": f"Bearer {token}"}

        role_id, _, _ = asyncio.run(_seed_role_with_skills(suffix))

        roles_resp = client.get("/api/v1/roles", headers=headers)
        assert roles_resp.status_code == 200, roles_resp.text
        roles = roles_resp.json()
        assert any(r["id"] == role_id for r in roles)

        detail_resp = client.get(f"/api/v1/roles/{role_id}/skills", headers=headers)
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()
        assert detail["role_id"] == role_id
        assert len(detail["skills"]) >= 2

        update_resp = client.put(
            f"/api/v1/roles/{role_id}/skills",
            headers=headers,
            json={
                "skills": [
                    {
                        "skill_name": f"Updated Skill {suffix}",
                        "category": "Technical Skills",
                        "importance": 0.8,
                        "is_mandatory": True,
                        "min_proficiency": "intermediate",
                    }
                ]
            },
        )
        assert update_resp.status_code == 200, update_resp.text
        updated = update_resp.json()
        assert len(updated["skills"]) == 1
        assert updated["skills"][0]["skill_name"] == f"Updated Skill {suffix}"


def test_gaps_negative_paths():
    suffix = uuid.uuid4().hex[:8]

    with TestClient(app) as client:
        token = _create_test_user_and_token(client, suffix)
        headers = {"Authorization": f"Bearer {token}"}

        unauth_resp = client.get("/api/v1/users/me/gaps")
        assert unauth_resp.status_code == 401

        no_target_resp = client.get("/api/v1/users/me/gaps", headers=headers)
        assert no_target_resp.status_code == 400


def test_learning_plan_endpoint_integration():
    suffix = uuid.uuid4().hex[:8]

    with TestClient(app) as client:
        token = _create_test_user_and_token(client, suffix)
        headers = {"Authorization": f"Bearer {token}"}

        role_id, _, _ = asyncio.run(_seed_role_with_skills(suffix))

        set_target = client.post(
            "/api/v1/users/me/target-role",
            headers=headers,
            json={"role_id": role_id},
        )
        assert set_target.status_code == 200, set_target.text

        plan_resp = client.get("/api/v1/users/me/learning-plan", headers=headers)
        assert plan_resp.status_code == 200, plan_resp.text
        plan = plan_resp.json()

        assert plan["role_id"] == role_id
        assert plan["item_count"] >= 1
        assert plan["total_hours_estimate"] > 0
        assert len(plan["items"]) == plan["item_count"]
