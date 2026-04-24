import asyncio
import uuid

from fastapi.testclient import TestClient

from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.models import Role, RoleSkillRequirement, Skill, UserSkillScore


def _create_test_user_and_token(client: TestClient, suffix: str) -> tuple[str, str]:
    email = f"gaps_{suffix}@example.com"
    password = "StrongPass123!"

    register_payload = {
        "email": email,
        "password": password,
        "full_name": f"Gap User {suffix}",
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
    token = login.json()["access_token"]
    return token, password


async def _seed_role_and_skills(suffix: str) -> tuple[str, str, str]:
    async with AsyncSessionLocal() as db:
        role = Role(
            name=f"Integration Role {suffix}",
            description="Role for integration testing",
            department=None,
            seniority_level="Mid-level",
            is_custom=True,
        )
        db.add(role)
        await db.flush()

        weak_skill = Skill(
            name=f"Weak Skill {suffix}",
            skill_type="technical",
            category="Technical Skills",
            prerequisites="[]",
            difficulty=3,
            time_to_learn_hours=80,
            source_role=role.name,
        )
        missing_skill = Skill(
            name=f"Missing Skill {suffix}",
            skill_type="technical",
            category="Technical Skills",
            prerequisites="[]",
            difficulty=4,
            time_to_learn_hours=120,
            source_role=role.name,
        )
        db.add_all([weak_skill, missing_skill])
        await db.flush()

        db.add_all(
            [
                RoleSkillRequirement(
                    role_id=role.id,
                    skill_id=weak_skill.id,
                    importance=1.0,
                    is_mandatory=True,
                    min_proficiency="advanced",
                ),
                RoleSkillRequirement(
                    role_id=role.id,
                    skill_id=missing_skill.id,
                    importance=0.9,
                    is_mandatory=True,
                    min_proficiency="intermediate",
                ),
            ]
        )

        await db.commit()
        return role.id, weak_skill.id, missing_skill.id


async def _seed_user_skill(user_id: str, skill_id: str) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            UserSkillScore(
                user_id=user_id,
                skill_id=skill_id,
                proficiency="beginner",
                proficiency_score=0.2,
                frequency=1,
                context_strength=0.5,
            )
        )
        await db.commit()


def test_gaps_flow_end_to_end():
    suffix = uuid.uuid4().hex[:8]

    with TestClient(app) as client:
        token, _ = _create_test_user_and_token(client, suffix)
        headers = {"Authorization": f"Bearer {token}"}

        me_resp = client.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200, me_resp.text
        user_id = me_resp.json()["id"]

        role_id, weak_skill_id, _ = asyncio.run(_seed_role_and_skills(suffix))
        asyncio.run(_seed_user_skill(user_id, weak_skill_id))

        set_target = client.post(
            "/api/v1/users/me/target-role",
            json={"role_id": role_id},
            headers=headers,
        )
        assert set_target.status_code == 200, set_target.text

        gaps_resp = client.get("/api/v1/users/me/gaps", headers=headers)
        assert gaps_resp.status_code == 200, gaps_resp.text
        gaps_data = gaps_resp.json()

        assert gaps_data["role_id"] == role_id
        assert gaps_data["total_gaps"] == 2
        assert gaps_data["missing_skills"] == 1
        assert gaps_data["weak_skills"] == 1
        assert len(gaps_data["gaps"]) == 2

        summary_resp = client.get("/api/v1/users/me/gaps/summary", headers=headers)
        assert summary_resp.status_code == 200, summary_resp.text
        summary = summary_resp.json()

        assert summary["role_id"] == role_id
        assert summary["total_gaps"] == 2
        assert summary["missing_skills"] == 1
        assert summary["weak_skills"] == 1
        assert 0.0 <= summary["readiness_score"] <= 1.0
        assert summary["total_learning_hours"] > 0


def test_set_target_role_by_name_compatibility():
    suffix = uuid.uuid4().hex[:8]

    with TestClient(app) as client:
        token, _ = _create_test_user_and_token(client, suffix)
        headers = {"Authorization": f"Bearer {token}"}

        role_id, _, _ = asyncio.run(_seed_role_and_skills(suffix))
        role_name = f"Integration Role {suffix}"

        resp = client.post(
            "/api/v1/users/me/target-role",
            json={"role_name": role_name},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["role_id"] == role_id
        assert payload["role_name"] == role_name
