"""Regression guard for a real bug: `dee1bd0660f6_ota_allocation_foundation`
created the native `ota_reservation_lifecycle_enum` type using the Python
enum members' uppercase *names* ('NEW', 'MANUAL_RESOLUTION_REQUIRED', ...),
but `OTAReservationLink.provider_state` is declared with
`values_callable=lambda enum_cls: [e.value for e in enum_cls]`, so every read
and write actually sends/expects lowercase values ("new",
"manual_resolution_required", ...). On production Postgres this broke any
query that filters on `provider_state` by Python enum value with
`psycopg2.errors.InvalidTextRepresentation` -- the root cause of the
persistent 500 on GET /api/reservations/actions/pending.

`Base.metadata.create_all` (what the rest of the pytest suite uses) always
reflects the *current* model and so never reproduces this: it renders the
CHECK constraint straight from `values_callable`. Only a database built via
`alembic upgrade head` carries the actual, frozen-at-migration-time labels --
same pattern as tests/test_reservation_status_enum_migration.py.
"""
import os
import subprocess
import sys
import tempfile
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_migrated_db_accepts_lowercase_provider_state():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/mig.db"
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=cwd
        )
        assert result.returncode == 0, f"upgrade head failed:\n{result.stderr}"

        from app.models.hotel_config import HotelConfiguration
        from app.models.ota_core import OTAProvider, OTAReservationLifecycleEnum, OTAReservationLink

        engine = create_engine(f"sqlite:///{db_path}")
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            db.add(HotelConfiguration(id=1, subscription_active=True))
            provider = OTAProvider(name="Test Provider", code="test_provider")
            db.add(provider)
            db.flush()

            link = OTAReservationLink(
                hotel_id=1,
                provider_id=provider.id,
                external_reservation_id="EXT-1",
                provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
                sync_status="manual_resolution_required",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(link)
            db.commit()

            db.refresh(link)
            assert link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED

            # This is the exact shape of the query that 500'd in production:
            # a WHERE-clause comparison against the Python enum's .value.
            found = (
                db.query(OTAReservationLink)
                .filter(OTAReservationLink.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED)
                .all()
            )
            assert len(found) == 1
        finally:
            db.close()
            engine.dispose()
