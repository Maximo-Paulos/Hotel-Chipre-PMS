"""PostgreSQL regression coverage for the stock movement audit projection."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.stock import StockItem, StockLocation, StockMovement
from app.models.user import User
from app.services import stock_service
from app.services.operational_audit_service import list_operational_audit
from app.services.tenant_context import set_tenant_hotel_context


def test_stock_movements_appear_once_in_inventory_audit_with_tenant_actor_and_filters(
    pg_session,
    monkeypatch,
):
    suffix = uuid4().hex[:10]
    hotel_id = 1_600_000_000 + uuid4().int % 100_000_000
    other_hotel_id = 1_700_000_000 + uuid4().int % 100_000_000
    occurred_at = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(
        stock_service,
        "hotel_business_now",
        lambda _db, _hotel_id: occurred_at,
    )

    set_tenant_hotel_context(pg_session, hotel_id)
    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Synthetic stock audit {suffix}",
        hotel_timezone="UTC",
    )
    actor = User(
        email=f"stock-audit-{suffix}@example.test",
        password_hash="synthetic-only",
        display_name="Operador sintético",
        is_active=True,
    )
    pg_session.add_all([hotel, actor])
    pg_session.flush()
    pg_session.add(
        HotelMembership(
            hotel_id=hotel_id,
            user_id=actor.id,
            role="manager",
            status="active",
            alias="Operador de inventario QA",
            alias_key="operador de inventario qa",
        )
    )
    item = StockItem(
        hotel_id=hotel_id,
        name=f"Toallas sintéticas {suffix}",
        unit="unidad",
        active=True,
    )
    source = StockLocation(hotel_id=hotel_id, name=f"Depósito QA {suffix}")
    destination = StockLocation(hotel_id=hotel_id, name=f"Lavandería QA {suffix}")
    pg_session.add_all([item, source, destination])
    pg_session.flush()

    purchase_movement = stock_service.register_movement(
        pg_session,
        hotel_id=hotel_id,
        item_id=item.id,
        location_id=source.id,
        movement_type="in",
        quantity=Decimal("25.00"),
        reason=f"Compra sintética contacto qa-{suffix}@example.test secret=synthetic-secret",
        created_by_user_id=actor.id,
    )
    _, outbound, inbound = stock_service.transfer_stock(
        pg_session,
        hotel_id=hotel_id,
        item_id=item.id,
        source_location_id=source.id,
        destination_location_id=destination.id,
        quantity=Decimal("3.50"),
        reason="Reposición de prueba",
        created_by_user_id=actor.id,
        idempotency_key=f"stock-audit-{suffix}",
    )
    stock_service.register_movement(
        pg_session,
        hotel_id=hotel_id,
        item_id=item.id,
        location_id=source.id,
        movement_type="adjustment",
        quantity=Decimal("1.00"),
        reason="Ajuste positivo sintético",
        created_by_user_id=actor.id,
    )
    stock_service.register_movement(
        pg_session,
        hotel_id=hotel_id,
        item_id=item.id,
        location_id=source.id,
        movement_type="adjustment_out",
        quantity=Decimal("0.25"),
        reason="Ajuste negativo sintético",
        created_by_user_id=actor.id,
    )
    old_movement = StockMovement(
        hotel_id=hotel_id,
        item_id=item.id,
        location_id=source.id,
        movement_type="adjustment",
        quantity=Decimal("1.00"),
        reason="Movimiento fuera del rango de fechas",
        created_by_user_id=actor.id,
        created_at=datetime(2026, 9, 3, 12),
    )
    pg_session.add(old_movement)
    pg_session.flush()

    # Older installations may contain a generic AuditLog marker for a stock
    # movement. The append-only StockMovement ledger is the authoritative
    # source for these records, so the UI must not show it twice.
    pg_session.add(
        AuditLog(
            hotel_id=hotel_id,
            table_name="stock_movements",
            record_id=outbound.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=actor.id,
            created_at=occurred_at.replace(tzinfo=None),
        )
    )

    set_tenant_hotel_context(pg_session, other_hotel_id)
    other_hotel = HotelConfiguration(
        id=other_hotel_id,
        hotel_name=f"Synthetic other hotel {suffix}",
        hotel_timezone="UTC",
    )
    other_actor = User(
        email=f"other-stock-audit-{suffix}@example.test",
        password_hash="synthetic-only",
        display_name="Otro operador sintético",
        is_active=True,
    )
    pg_session.add_all([other_hotel, other_actor])
    pg_session.flush()
    other_item = StockItem(
        hotel_id=other_hotel_id,
        name=f"Artículo de otro hotel {suffix}",
        unit="unidad",
        active=True,
    )
    pg_session.add(other_item)
    pg_session.flush()
    stock_service.register_movement(
        pg_session,
        hotel_id=other_hotel_id,
        item_id=other_item.id,
        location_id=None,
        movement_type="in",
        quantity=Decimal("999.00"),
        reason="Dato sintético de otro hotel",
        created_by_user_id=other_actor.id,
    )

    set_tenant_hotel_context(pg_session, hotel_id)
    inventory_items, inventory_total = list_operational_audit(
        pg_session,
        hotel_id=hotel_id,
        limit=20,
        offset=0,
        from_date=date(2026, 9, 4),
        to_date=date(2026, 9, 4),
        category="inventory",
    )
    actor_items, actor_total = list_operational_audit(
        pg_session,
        hotel_id=hotel_id,
        limit=20,
        offset=0,
        from_date=date(2026, 9, 4),
        to_date=date(2026, 9, 4),
        actor_user_id=actor.id,
    )
    transfer_action_items, transfer_action_total = list_operational_audit(
        pg_session,
        hotel_id=hotel_id,
        limit=20,
        offset=0,
        from_date=date(2026, 9, 4),
        to_date=date(2026, 9, 4),
        category="inventory",
        action="stock.transfer.out",
    )

    assert inventory_total == 5
    assert actor_total == 5
    assert transfer_action_total == 1
    assert transfer_action_items[0]["source_id"] == outbound.id
    inventory_source_ids = {item["source_id"] for item in inventory_items}
    assert len(inventory_source_ids) == 5
    assert purchase_movement.id in inventory_source_ids
    assert {outbound.id, inbound.id}.issubset(inventory_source_ids)
    assert {item["action"] for item in inventory_items} == {
        "stock.movement.in",
        "stock.movement.adjustment",
        "stock.movement.adjustment_out",
        "stock.transfer.in",
        "stock.transfer.out",
    }
    assert all(item["source"] == "stock_movement" for item in inventory_items)
    assert all(item["area"] == "inventory" for item in inventory_items)
    assert all(item["actor_user_id"] == actor.id for item in inventory_items)
    assert all(item["actor_name"] == "Operador de inventario QA" for item in inventory_items)
    assert {item["movement_type"] for item in inventory_items} == {
        "in",
        "out",
        "adjustment",
        "adjustment_out",
    }
    assert any("Toallas sintéticas" in item["summary"] for item in inventory_items)
    assert any(item["details"]["quantity"] == Decimal("3.50") for item in inventory_items)
    assert old_movement.id not in {item["source_id"] for item in inventory_items}
    assert all(item["actor_user_id"] == actor.id for item in actor_items)

    purchase = next(item for item in inventory_items if item["source_id"] == purchase_movement.id)
    assert purchase["reason_note"] is not None
    assert "qa-" + suffix + "@example.test" not in purchase["reason_note"]
    assert "synthetic-secret" not in purchase["reason_note"]
    assert "[REDACTED]" in purchase["reason_note"]
    assert f"Artículo de otro hotel {suffix}" not in str(inventory_items)
