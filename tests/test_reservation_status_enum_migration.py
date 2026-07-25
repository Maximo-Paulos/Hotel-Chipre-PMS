"""Regression guard for a real bug B3.1 uncovered: on a SQLite database built
from `alembic upgrade head` (not `Base.metadata.create_all`, which the rest of
the pytest suite uses and which always reflects the *current* model), the
`reservations.status` CHECK constraint was frozen at baseline-migration time
and never got 'pre_check_in' added -- so writing that status, dead code until
B3.1, raised `sqlite3.IntegrityError: CHECK constraint failed`. Exercise the
CHECK constraint itself against a migrated (not model-created) database,
using the ORM models so every other NOT NULL column gets its normal default.
"""
import os
import subprocess
import sys
import tempfile
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_migrated_sqlite_reservation_status_accepts_pre_check_in():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/mig.db"
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=cwd
        )
        assert result.returncode == 0, f"upgrade head failed:\n{result.stderr}"

        # Import app models only now (matching DATABASE_URL doesn't matter for
        # imports) and bind a fresh engine to the *migrated* file -- this must
        # NOT call Base.metadata.create_all, which would regenerate the CHECK
        # constraint from the current model and hide the exact bug this guards.
        from app.models.guest import Guest
        from app.models.hotel_config import HotelConfiguration
        from app.models.reservation import Reservation, ReservationStatusEnum
        from app.models.room import RoomCategory

        engine = create_engine(f"sqlite:///{db_path}")
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            db.add(HotelConfiguration(id=1, subscription_active=True))
            guest = Guest(hotel_id=1, first_name="Test", last_name="Guest")
            category = RoomCategory(
                hotel_id=1, name="Standard", code="STD",
                base_price_per_night=Decimal("100.00"), max_occupancy=2,
            )
            db.add_all([guest, category])
            db.flush()

            reservation = Reservation(
                hotel_id=1, guest_id=guest.id, category_id=category.id,
                confirmation_code="MIGTEST",
                check_in_date=date(2026, 1, 1), check_out_date=date(2026, 1, 2),
                status=ReservationStatusEnum.PRE_CHECK_IN,
                total_amount=Decimal("100.00"), amount_paid=Decimal("100.00"),
                deposit_amount=Decimal("0"), num_adults=1,
            )
            db.add(reservation)
            db.commit()

            db.refresh(reservation)
            assert reservation.status == ReservationStatusEnum.PRE_CHECK_IN
        finally:
            db.close()
            engine.dispose()
