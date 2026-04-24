import app.db.session as session_mod
import pytest
from sqlalchemy.exc import InterfaceError as SAInterfaceError


class InvalidCachedStatementError(Exception):
    pass


class WrapperWithOrig(Exception):
    def __init__(self, orig):
        super().__init__("wrapped")
        self.orig = orig


def test_detects_invalid_cached_statement_by_exception_name():
    err = InvalidCachedStatementError("cache invalidated")
    assert session_mod.is_invalid_cached_statement_error(err) is True


def test_detects_invalid_cached_statement_in_wrapped_exception_chain():
    err = WrapperWithOrig(InvalidCachedStatementError("cached statement plan is invalid"))
    assert session_mod.is_invalid_cached_statement_error(err) is True


def test_recovery_window_activation_and_expiry(monkeypatch):
    monkeypatch.setattr(session_mod, "monotonic", lambda: 100.0)
    session_mod.activate_cached_statement_recovery_window(seconds=120)
    assert session_mod.is_cached_statement_recovery_active() is True

    monkeypatch.setattr(session_mod, "monotonic", lambda: 500.0)
    assert session_mod.is_cached_statement_recovery_active() is False


def test_non_cached_statement_error_not_detected():
    err = RuntimeError("different database error")
    assert session_mod.is_invalid_cached_statement_error(err) is False


class _FakeResult:
    def __init__(self, value="ok"):
        self.value = value


class _PrimarySession:
    def __init__(self):
        self.calls = 0

    async def execute(self, statement):
        self.calls += 1
        if self.calls == 1:
            raise SAInterfaceError("SELECT 1", {}, Exception("connection is closed"))
        return _FakeResult(statement)


class _RetrySession:
    def __init__(self, should_fail=False):
        self.calls = 0
        self.should_fail = should_fail

    async def execute(self, statement):
        self.calls += 1
        if self.should_fail:
            raise SAInterfaceError("SELECT 1", {}, Exception("connection is closed"))
        return _FakeResult(statement)


class _SessionFactory:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        _ = (exc_type, exc, tb)
        return False


@pytest.mark.asyncio
async def test_execute_with_reconnect_retry_disposes_and_retries_once(monkeypatch):
    primary = _PrimarySession()
    retry = _RetrySession(should_fail=False)

    disposed = {"count": 0}

    async def _dispose():
        disposed["count"] += 1

    monkeypatch.setattr(session_mod, "AsyncSessionLocal", lambda: _SessionFactory(retry))
    monkeypatch.setattr(session_mod, "dispose_engine_for_connection_retry", _dispose)

    result = await session_mod.execute_with_reconnect_retry(primary, "SELECT 1")

    assert isinstance(result, _FakeResult)
    assert primary.calls == 1
    assert retry.calls == 1
    assert disposed["count"] == 1


@pytest.mark.asyncio
async def test_execute_with_reconnect_retry_does_not_loop_infinitely(monkeypatch):
    primary = _PrimarySession()
    retry = _RetrySession(should_fail=True)

    disposed = {"count": 0}

    async def _dispose():
        disposed["count"] += 1

    monkeypatch.setattr(session_mod, "AsyncSessionLocal", lambda: _SessionFactory(retry))
    monkeypatch.setattr(session_mod, "dispose_engine_for_connection_retry", _dispose)

    with pytest.raises(SAInterfaceError):
        await session_mod.execute_with_reconnect_retry(primary, "SELECT 1")

    assert primary.calls == 1
    assert retry.calls == 1
    assert disposed["count"] == 1