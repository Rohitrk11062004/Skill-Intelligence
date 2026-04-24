from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql, sqlite

from app.api.v1.endpoints import auth


class _FakeResult:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class _FakeDB:
    def __init__(self, dialect_name: str, user):
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))
        self._user = user
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _FakeResult(self._user)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dialect_name", "dialect", "expected_local_part_function"),
    [
        ("postgresql", postgresql.dialect(), "split_part"),
        ("sqlite", sqlite.dialect(), "instr"),
    ],
)
async def test_login_uses_dialect_specific_local_part_expression(monkeypatch, dialect_name, dialect, expected_local_part_function):
    user = SimpleNamespace(
        id="user-1",
        email="Jane.Doe@example.com",
        hashed_password="hashed-password",
        is_active=True,
    )
    db = _FakeDB(dialect_name, user)
    form = SimpleNamespace(username="Jane.Doe", password="secret")

    monkeypatch.setattr(auth, "verify_password", lambda password, hashed: True)
    monkeypatch.setattr(auth, "create_access_token", lambda subject: "token")

    token_response = await auth.login(form=form, db=db)

    assert token_response.access_token == "token"
    assert token_response.token_type == "bearer"

    compiled_sql = str(db.statements[0].compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
    assert expected_local_part_function in compiled_sql
    assert "lower(users.email)" in compiled_sql
    assert "example.com" not in compiled_sql