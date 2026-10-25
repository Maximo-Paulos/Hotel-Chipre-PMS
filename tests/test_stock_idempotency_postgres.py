"""PostgreSQL-backed contract checks for stock movement idempotency."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.hotel_config import HotelConfiguration
from app.models.stock import StockItem, StockMovement
from app.services.stock_service import (
    StockError,
    StockIdempotencyConflict,
    current_stock,
    register_movement,
)
from app.services.tenant_context import set_tenant_hotel_context


def test_stock_movement_idempotency_matches_payload_on_postgres(pg_engine):
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    hotel_id = 100_000_000 + uuid4().int % 100_000_000
    item_id = None
    session = session_factory()

    try:
        session.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic Stock Idempotency {hotel_id}"))
        session.flush()
        item = StockItem(hotel_id=hotel_id, name="Synthetic towels", unit="unit", active=True)
        session.add(item)
        session.flush()
        item_id = item.id

        payload = {
            "hotel_id": hotel_id,
            "item_id": item.id,
            "location_id": None,
            "movement_type": "in",
            "quantity": Decimal("10.00"),
            "reason": "synthetic inventory count",
            "reservation_id": None,
            "created_by_user_id": None,
            "idempotency_key": f"pg-stock-{uuid4().hex}",
        }
        original = register_movement(session, **payload)
        session.commit()

        replay = register_movement(session, **payload)
        assert replay.id == original.id

        conflicting_payload = {**payload, "reason": "different synthetic reason"}
        with pytest.raises(StockIdempotencyConflict):
            register_movement(session, **conflicting_payload)

        with pytest.raises(StockError, match="two decimal places"):
            register_movement(
                session,
                **{
                    **payload,
                    "idempotency_key": f"pg-stock-scale-{uuid4().hex}",
                    "quantity": Decimal("1.001"),
                },
            )

        assert current_stock(session, hotel_id=hotel_id, item_id=item.id) == Decimal("10.00")
        assert session.query(StockMovement).filter_by(hotel_id=hotel_id).count() == 1
    finally:
        session.rollback()
        session.query(StockMovement).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        if item_id is not None:
            session.query(StockItem).filter_by(hotel_id=hotel_id, id=item_id).delete(synchronize_session=False)
        session.query(HotelConfiguration).filter_by(id=hotel_id).delete(synchronize_session=False)
        session.commit()
        session.close()


def test_concurrent_stock_movement_key_reuse_with_different_payload_conflicts_on_postgres(pg_engine):
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    hotel_id = 200_000_000 + uuid4().int % 100_000_000
    suffix = uuid4().hex[:8]
    item_ids: list[int] = []
    seed = session_factory()

    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic Stock Race {suffix}"))
        seed.flush()
        items = [
            StockItem(hotel_id=hotel_id, name=f"Synthetic race item {suffix}-{index}", unit="unit", active=True)
            for index in range(2)
        ]
        seed.add_all(items)
        seed.commit()
        item_ids = [item.id for item in items]
    finally:
        seed.rollback()
        seed.close()

    initial_lookup_barrier = Barrier(2)
    idempotency_key = f"pg-stock-race-{uuid4().hex}"

    def submit_movement(item_id: int, reason: str) -> tuple[str, int | None]:
        session = session_factory()
        set_tenant_hotel_context(session, hotel_id)
        original_query = session.query
        first_movement_lookup = True

        class _SynchronizedLookup:
            def __init__(self, query):
                self.query = query

            def filter(self, *args, **kwargs):
                self.query = self.query.filter(*args, **kwargs)
                return self

            def one_or_none(self):
                result = self.query.one_or_none()
                initial_lookup_barrier.wait(timeout=10)
                return result

        def synchronized_query(model, *entities, **kwargs):
            nonlocal first_movement_lookup
            query = original_query(model, *entities, **kwargs)
            if model is StockMovement and first_movement_lookup:
                first_movement_lookup = False
                return _SynchronizedLookup(query)
            return query

        session.query = synchronized_query
        try:
            movement = register_movement(
                session,
                hotel_id=hotel_id,
                item_id=item_id,
                location_id=None,
                movement_type="in",
                quantity=Decimal("5.00"),
                reason=reason,
                reservation_id=None,
                created_by_user_id=None,
                idempotency_key=idempotency_key,
            )
            session.commit()
            return "created", movement.id
        except StockIdempotencyConflict:
            session.rollback()
            return "conflict", None
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="stock-idempotency-race") as executor:
            first = executor.submit(submit_movement, item_ids[0], "synthetic first payload")
            second = executor.submit(submit_movement, item_ids[1], "synthetic competing payload")
            outcomes = [first.result(timeout=20), second.result(timeout=20)]

        assert sorted(outcome for outcome, _ in outcomes) == ["conflict", "created"]

        check = session_factory()
        set_tenant_hotel_context(check, hotel_id)
        assert check.query(StockMovement).filter_by(hotel_id=hotel_id).count() == 1
        assert sum(current_stock(check, hotel_id=hotel_id, item_id=item_id) for item_id in item_ids) == Decimal("5.00")
        check.close()
    finally:
        cleanup = session_factory()
        set_tenant_hotel_context(cleanup, hotel_id)
        cleanup.query(StockMovement).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        cleanup.query(StockItem).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        cleanup.query(HotelConfiguration).filter_by(id=hotel_id).delete(synchronize_session=False)
        cleanup.commit()
        cleanup.close()
