"""
tests/conftest.py
Shared pytest fixtures used across unit and integration tests.
"""
import os
import sys

import pytest
from unittest.mock import AsyncMock


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# Ensure tests run against SQLite by default (avoid accidentally hitting Neon/prod).
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_skilldb.sqlite3")


@pytest.fixture
def mock_db():
    """Async mock for SQLAlchemy AsyncSession."""
    return AsyncMock()
