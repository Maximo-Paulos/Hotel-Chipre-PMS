from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql

from app.models.domain_event_outbox import DomainEventOutbox


PRE_REVISION = "20260830_fix_receptionist_move_default"
REVISION = "20260901_domain_event_outbox"


def _alembic(cwd: str, db_path: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=cwd,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"


def test_domain_event_outbox_migration_round_trips_on_fresh_sqlite(tmp_path):
    cwd = os.path.dirname(os.path.dirname(__file__))
    db_path = str(tmp_path / "domain-event-outbox.db")

    _alembic(cwd, db_path, "upgrade", REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        assert "domain_event_outbox" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("domain_event_outbox")}
        assert columns >= {
            "id",
            "hotel_id",
            "domain",
            "event_type",
            "payload",
            "revision",
            "occurred_at",
            "published_at",
            "attempts",
            "last_error",
        }
        assert {index["name"] for index in inspector.get_indexes("domain_event_outbox")} >= {
            "ix_domain_event_outbox_pending"
        }
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "downgrade", PRE_REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        assert "domain_event_outbox" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    _alembic(cwd, db_path, "upgrade", REVISION)
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        assert "domain_event_outbox" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_domain_event_outbox_uses_jsonb_on_postgresql():
    payload_type = DomainEventOutbox.__table__.c.payload.type.dialect_impl(postgresql.dialect())
    assert isinstance(payload_type, postgresql.JSONB)
