from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from time import time_ns

from sqlalchemy.orm import sessionmaker

from app.models.cash_register import (
    CashCloseReport,
    CashCustodyHandoff,
    CashMovement,
    CashMovementTypeEnum,
    CashSession,
)
from app.models.hotel_config import HotelConfiguration
from app.services import cash_register_service
from app.services.cash_register_service import CashRegisterError, add_movement, close_session, open_session


def test_close_serializes_with_cash_movement_and_rejects_late_write(pg_engine, monkeypatch):
    """A movement cannot land after close has calculated and committed the arqueo."""
    hotel_id = 10_000_000 + time_ns() % 80_000_000
    Session = sessionmaker(bind=pg_engine, expire_on_commit=False)
    setup = Session()
    try:
        setup.add(HotelConfiguration(id=hotel_id, hotel_name="Synthetic Cash Lock Test"))
        setup.flush()
        session = open_session(
            setup,
            hotel_id=hotel_id,
            opened_by_user_id=None,
            opening_balance=Decimal("0.00"),
        )
        setup.commit()
        session_id = session.id
    finally:
        setup.close()

    close_has_lock = Event()
    allow_close_to_finish = Event()
    writer_reached_open_session_check = Event()
    writer_finished = Event()
    original_total = cash_register_service._confirmed_cash_movements_total
    original_require_open = cash_register_service._require_open_session

    def pause_close_after_lock(db, cash_session, closed_at):
        close_has_lock.set()
        if not allow_close_to_finish.wait(timeout=10):
            raise TimeoutError("cash-close concurrency test timed out waiting to release the close")
        return original_total(db, cash_session, closed_at)

    monkeypatch.setattr(cash_register_service, "_confirmed_cash_movements_total", pause_close_after_lock)

    def signal_writer_lock_attempt(db, target_hotel_id, target_session_id):
        writer_reached_open_session_check.set()
        return original_require_open(db, target_hotel_id, target_session_id)

    monkeypatch.setattr(cash_register_service, "_require_open_session", signal_writer_lock_attempt)

    def close_cash():
        db = Session()
        try:
            report = close_session(
                db,
                hotel_id=hotel_id,
                session_id=session_id,
                closed_by_user_id=None,
                counted_balance=Decimal("0.00"),
            )
            db.commit()
            return ("closed", report.expected_balance)
        except Exception as exc:  # returned to the test thread for a useful assertion
            db.rollback()
            return ("error", exc)
        finally:
            db.close()

    def write_cash():
        db = Session()
        try:
            add_movement(
                db,
                hotel_id=hotel_id,
                session_id=session_id,
                recorded_by_user_id=None,
                movement_type=CashMovementTypeEnum.INCOME,
                amount=Decimal("10.00"),
            )
            db.commit()
            return ("written", None)
        except CashRegisterError as exc:
            db.rollback()
            return ("rejected", str(exc))
        except Exception as exc:  # returned to the test thread for a useful assertion
            db.rollback()
            return ("error", exc)
        finally:
            writer_finished.set()
            db.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            close_future = executor.submit(close_cash)
            assert close_has_lock.wait(timeout=10), "close did not reach its locked balance calculation"
            writer_future = executor.submit(write_cash)
            assert writer_reached_open_session_check.wait(timeout=10), "writer did not reach the open-session lock"

            # The writer has an independent connection and may run immediately.
            # While close owns the CashSession row lock it must wait there.
            writer_blocked = not writer_finished.wait(timeout=0.25)
            allow_close_to_finish.set()
            close_result = close_future.result(timeout=10)
            writer_result = writer_future.result(timeout=10)

        assert writer_blocked, "cash movement bypassed the close row lock"
        assert close_result == ("closed", Decimal("0.00"))
        assert writer_result[0] == "rejected", writer_result

        check = Session()
        try:
            assert check.query(CashMovement).filter_by(hotel_id=hotel_id, session_id=session_id).count() == 0
            report = check.query(CashCloseReport).filter_by(hotel_id=hotel_id, session_id=session_id).one()
            assert report.expected_balance == Decimal("0.00")
        finally:
            check.close()
    finally:
        allow_close_to_finish.set()
        cleanup = Session()
        try:
            cleanup.query(CashCustodyHandoff).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(CashCloseReport).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(CashMovement).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(CashSession).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
            cleanup.query(HotelConfiguration).filter_by(id=hotel_id).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.close()
