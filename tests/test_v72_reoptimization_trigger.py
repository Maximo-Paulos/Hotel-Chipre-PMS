"""
V72 §5.2 — Reoptimización continua del motor de asignación.

After each new reservation, the allocation engine must run in background
to reoptimize room assignments for all future reservations.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import create_reservation


DEFAULT_HOTEL_ID = 1


class TestReoptimizationTrigger:
    """§5.2 — Motor reoptimizes after every new reservation."""

    def test_trigger_reoptimization_bg_is_importable(self):
        """_trigger_reoptimization_bg is a callable in app.api.reservations."""
        from app.api.reservations import _trigger_reoptimization_bg
        assert callable(_trigger_reoptimization_bg)

    def test_trigger_reoptimization_bg_ignores_engine_errors(self):
        """
        §5.2 — Reoptimization failures must NEVER break the booking flow.
        If the allocation engine crashes, must be swallowed silently.
        """
        from app.api.reservations import _trigger_reoptimization_bg

        # Patch the source module since get_session_factory is a local import inside the fn
        with patch("app.database.get_session_factory", side_effect=RuntimeError("DB error")):
            try:
                _trigger_reoptimization_bg(hotel_id=DEFAULT_HOTEL_ID)
            except Exception:
                pytest.fail("_trigger_reoptimization_bg must swallow all exceptions")

    def test_create_reservation_service_stays_synchronous(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """
        §5.2 — The service layer create_reservation has no reoptimization side effect.
        The trigger lives only in the API layer (BackgroundTasks), keeping service pure.
        """
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 10, 1),
            check_out_date=date(2026, 10, 3),
        )
        reservation = create_reservation(db, data, hotel_id=DEFAULT_HOTEL_ID)
        db.flush()

        assert reservation.id is not None
        assert reservation.status == ReservationStatusEnum.PENDING


class TestReoptimizationIntegration:
    """§5.2 — Integration: after new booking, allocation engine receives correct args."""

    def test_reoptimization_calls_run_persisted_with_new_reservation_trigger(self):
        """
        When _trigger_reoptimization_bg runs, it must call run_persisted_allocation
        with trigger_type='new_reservation'.
        """
        from app.api.reservations import _trigger_reoptimization_bg

        captured = {}

        fake_db = MagicMock()
        fake_session_factory = MagicMock(return_value=fake_db)

        def fake_run(db, *, hotel_id, trigger_type, **kwargs):
            captured["hotel_id"] = hotel_id
            captured["trigger_type"] = trigger_type
            return MagicMock()  # fake result, shape doesn't matter

        with patch("app.database.get_session_factory", return_value=fake_session_factory), \
             patch("app.services.allocation_runtime_service.run_persisted_allocation", side_effect=fake_run):
            _trigger_reoptimization_bg(hotel_id=DEFAULT_HOTEL_ID)

        assert captured.get("hotel_id") == DEFAULT_HOTEL_ID
        assert captured.get("trigger_type") == "new_reservation", (
            "§5.2 trigger must use trigger_type='new_reservation'"
        )

    def test_reoptimization_commits_and_closes_session(self):
        """The background task must commit and close its own DB session."""
        from app.api.reservations import _trigger_reoptimization_bg

        fake_db = MagicMock()
        fake_session_factory = MagicMock(return_value=fake_db)

        with patch("app.database.get_session_factory", return_value=fake_session_factory), \
             patch("app.services.allocation_runtime_service.run_persisted_allocation",
                   return_value=MagicMock()):
            _trigger_reoptimization_bg(hotel_id=DEFAULT_HOTEL_ID)

        fake_db.commit.assert_called_once()
        fake_db.close.assert_called_once()

    def test_reoptimization_rolls_back_on_engine_failure(self):
        """
        If run_persisted_allocation raises, rollback must be called (not commit).
        """
        from app.api.reservations import _trigger_reoptimization_bg

        fake_db = MagicMock()
        fake_session_factory = MagicMock(return_value=fake_db)

        with patch("app.database.get_session_factory", return_value=fake_session_factory), \
             patch("app.services.allocation_runtime_service.run_persisted_allocation",
                   side_effect=RuntimeError("engine failed")):
            _trigger_reoptimization_bg(hotel_id=99)

        fake_db.rollback.assert_called_once()
        fake_db.commit.assert_not_called()
        fake_db.close.assert_called_once()
