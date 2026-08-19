"""Regression guard: verify the notification backend migration against a
REAL `alembic upgrade head` SQLite file (not Base.metadata.create_all, which
always reflects the *current* model and would hide a migration bug -- same
convention as tests/test_reservation_status_enum_migration.py)."""
import os
import subprocess
import sys
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


def test_migrated_sqlite_enforces_notification_outbox_dedupe_and_isolation():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/mig.db"
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=cwd,
        )
        assert result.returncode == 0, f"upgrade head failed:\n{result.stderr}"

        downgraded = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "20260818_stock_movement_idem"],
            capture_output=True, text=True, env=env, cwd=cwd,
        )
        assert downgraded.returncode == 0, f"downgrade failed:\n{downgraded.stderr}"

        reupgraded = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=cwd,
        )
        assert reupgraded.returncode == 0, f"re-upgrade failed:\n{reupgraded.stderr}"

        from app.models.hotel_config import HotelConfiguration
        from app.models.notification import NotificationChannelEnum, NotificationOutbox
        from app.models.user import User

        engine = create_engine(f"sqlite:///{db_path}")
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            db.add(HotelConfiguration(id=1, subscription_active=True))
            db.add(HotelConfiguration(id=2, subscription_active=True))
            user = User(email="mig-test@example.test", password_hash="x")
            db.add(user)
            db.flush()

            row = NotificationOutbox(
                hotel_id=1, event_type="reservation.created", dedupe_key="reservation:1:created",
                channel=NotificationChannelEnum.IN_APP, recipient_user_id=user.id, title="t",
            )
            db.add(row)
            db.flush()

            duplicate = NotificationOutbox(
                hotel_id=1, event_type="reservation.created", dedupe_key="reservation:1:created",
                channel=NotificationChannelEnum.IN_APP, recipient_user_id=user.id, title="t",
            )
            db.add(duplicate)
            try:
                db.flush()
                raise AssertionError("duplicate (hotel, dedupe_key, channel, recipient) must be rejected")
            except IntegrityError:
                db.rollback()

            # A migrated DB must still allow the same dedupe_key across a
            # different hotel -- the unique index is tenant-scoped, not global.
            cross_hotel = NotificationOutbox(
                hotel_id=2, event_type="reservation.created", dedupe_key="reservation:1:created",
                channel=NotificationChannelEnum.IN_APP, recipient_user_id=user.id, title="t",
            )
            db.add(cross_hotel)
            db.flush()
        finally:
            db.rollback()
            db.close()
