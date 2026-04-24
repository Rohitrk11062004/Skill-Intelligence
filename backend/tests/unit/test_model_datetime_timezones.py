from datetime import timezone

from sqlalchemy import DateTime

from app.db.session import Base
import app.models.models  # noqa: F401 - populate metadata


def test_persisted_datetime_columns_are_timezone_aware():
    datetime_columns = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, DateTime):
                datetime_columns.append((table.name, column.name, column.type.timezone))

    assert datetime_columns, "expected at least one mapped datetime column"
    assert all(timezone_enabled is True for _, _, timezone_enabled in datetime_columns)


def test_now_utc_returns_timezone_aware_datetime():
    from app.models.models import now_utc

    timestamp = now_utc()
    assert timestamp.tzinfo is not None
    assert timestamp.tzinfo.utcoffset(timestamp) == timezone.utc.utcoffset(timestamp)