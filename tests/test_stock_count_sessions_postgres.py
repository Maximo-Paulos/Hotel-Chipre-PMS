"""PostgreSQL locking regression for stock-count confirmation."""

from __future__ import annotations

from decimal import Decimal
from queue import Queue
from threading import Event, Thread
from time import monotonic, sleep
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.models.audit_log import AuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.stock import (
    StockCountLine,
    StockCountSession,
    StockItem,
    StockMovement,
)
from app.models.user import User
from app.services.stock_service import (
    StockCountRecountRequired,
    confirm_stock_count_session,
    create_stock_count_session,
    record_stock_count,
    register_movement,
)
from app.services.tenant_context import set_tenant_hotel_context


def test_confirmation_waits_for_inflight_movement_then_requires_recount(pg_engine):
    """An in-flight movement cannot slip between stale-check and adjustment."""
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10]
    hotel_id = 1_100_000_000 + uuid4().int % 100_000_000
    counter_id = 1_200_000_000 + uuid4().int % 100_000_000
    confirmer_id = 1_300_000_000 + uuid4().int % 100_000_000
    session_id = item_id = None
    mover = session_factory()
    confirm_started = Event()
    confirm_pid: Queue[int] = Queue()
    confirm_result: Queue[object] = Queue()

    try:
        with session_factory.begin() as seed:
            set_tenant_hotel_context(seed, hotel_id)
            seed.add(
                HotelConfiguration(
                    id=hotel_id,
                    hotel_name=f"Synthetic stock count {suffix}",
                    subscription_active=True,
                )
            )
            seed.add_all(
                [
                    User(
                        id=counter_id,
                        email=f"stock-counter-{suffix}@example.test",
                        password_hash="synthetic",
                    ),
                    User(
                        id=confirmer_id,
                        email=f"stock-confirmer-{suffix}@example.test",
                        password_hash="synthetic",
                    ),
                ]
            )
            seed.flush()
            item = StockItem(
                hotel_id=hotel_id,
                name=f"Synthetic soap {suffix}",
                unit="unit",
                active=True,
            )
            seed.add(item)
            seed.flush()
            item_id = item.id
            register_movement(
                seed,
                hotel_id=hotel_id,
                item_id=item_id,
                location_id=None,
                movement_type="in",
                quantity=Decimal("10.00"),
                reason="synthetic opening quantity",
                created_by_user_id=counter_id,
            )
            count_session = create_stock_count_session(
                seed,
                hotel_id=hotel_id,
                created_by_user_id=counter_id,
                reason="synthetic count",
            )
            session_id = count_session.id
            record_stock_count(
                seed,
                hotel_id=hotel_id,
                session_id=session_id,
                item_id=item_id,
                location_id=None,
                counted_quantity=Decimal("10.00"),
                counted_by_user_id=counter_id,
            )

        # Keep the movement's item-row lock while the confirmer reaches the
        # same lock. After commit, the confirmer must observe the new movement
        # version and refuse the stale count.
        set_tenant_hotel_context(mover, hotel_id)
        register_movement(
            mover,
            hotel_id=hotel_id,
            item_id=item_id,
            location_id=None,
            movement_type="in",
            quantity=Decimal("1.00"),
            reason="synthetic movement concurrent with confirmation",
            created_by_user_id=counter_id,
        )
        mover.flush()

        def confirm() -> None:
            db = session_factory()
            try:
                set_tenant_hotel_context(db, hotel_id)
                db.execute(
                    text("SET application_name = 'stock_count_confirm_lock_test'")
                )
                confirm_pid.put(
                    db.execute(text("SELECT pg_backend_pid()")).scalar_one()
                )
                confirm_started.set()
                try:
                    confirm_stock_count_session(
                        db,
                        hotel_id=hotel_id,
                        session_id=session_id,
                        confirmed_by_user_id=confirmer_id,
                        reason="synthetic concurrency check",
                    )
                except StockCountRecountRequired as error:
                    confirm_result.put(error)
                else:
                    confirm_result.put(None)
            except BaseException as error:  # propagate thread failures to pytest
                confirm_result.put(error)
            finally:
                db.rollback()
                db.close()

        thread = Thread(target=confirm, daemon=True)
        thread.start()
        assert confirm_started.wait(timeout=5)
        pid = confirm_pid.get(timeout=5)

        deadline = monotonic() + 5
        observed_lock_wait = False
        while monotonic() < deadline:
            with pg_engine.connect() as monitor:
                wait_event = monitor.execute(
                    text(
                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"
                    ),
                    {"pid": pid},
                ).scalar_one_or_none()
            if wait_event == "Lock":
                observed_lock_wait = True
                break
            sleep(0.05)

        assert observed_lock_wait, (
            "confirmation did not block on the in-flight item lock"
        )
        mover.commit()
        thread.join(timeout=5)
        assert not thread.is_alive(), (
            "confirmation did not finish after movement commit"
        )
        result = confirm_result.get(timeout=1)
        assert isinstance(result, StockCountRecountRequired)
        assert result.items == [{"item_id": item_id, "location_id": None}]

    finally:
        mover.rollback()
        mover.close()
        cleanup = session_factory()
        try:
            set_tenant_hotel_context(cleanup, hotel_id)
            cleanup.query(AuditLog).filter(AuditLog.hotel_id == hotel_id).delete(
                synchronize_session=False
            )
            cleanup.query(StockMovement).filter(
                StockMovement.hotel_id == hotel_id
            ).delete(synchronize_session=False)
            cleanup.query(StockCountLine).filter(
                StockCountLine.hotel_id == hotel_id
            ).delete(synchronize_session=False)
            cleanup.query(StockCountSession).filter(
                StockCountSession.hotel_id == hotel_id
            ).delete(synchronize_session=False)
            cleanup.query(StockItem).filter(StockItem.hotel_id == hotel_id).delete(
                synchronize_session=False
            )
            cleanup.query(User).filter(User.id.in_([counter_id, confirmer_id])).delete(
                synchronize_session=False
            )
            cleanup.query(HotelConfiguration).filter(
                HotelConfiguration.id == hotel_id
            ).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.rollback()
            cleanup.close()
