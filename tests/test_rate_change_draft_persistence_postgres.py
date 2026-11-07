"""PostgreSQL regression coverage for persisted daily rate drafts."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.daily_rate import DailyRate
from app.models.hotel_config import HotelConfiguration
from app.models.rate_change_draft import RateChangeDraft
from app.models.room import RoomCategory
from app.services.rate_change_draft_service import create_rate_change_draft, serialize_draft
from app.services.tenant_context import set_tenant_hotel_context


def test_postgres_creates_two_date_daily_rate_draft_without_changing_rates(pg_session):
    suffix = uuid4().hex[:10]
    hotel_id = 1_300_000_000 + uuid4().int % 10_000_000
    dates = [date(2026, 12, 30), date(2026, 12, 31)]
    set_tenant_hotel_context(pg_session, hotel_id)

    pg_session.add(
        HotelConfiguration(
            id=hotel_id,
            hotel_name=f"Synthetic rate draft hotel {suffix}",
            subscription_active=True,
            default_currency="ARS",
        )
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic DBC category {suffix}",
        code=f"D{suffix[:2]}",
        base_price_per_night=Decimal("60000.00"),
        max_occupancy=2,
    )
    pg_session.add(category)
    pg_session.flush()

    pg_session.add_all(
        [
            DailyRate(
                hotel_id=hotel_id,
                category_id=category.id,
                date=target_date,
                price=Decimal("60000.00"),
                price_cash=Decimal("50000.00"),
                price_transfer=Decimal("55000.00"),
                price_mercadopago=Decimal("55000.00"),
            )
            for target_date in dates
        ]
    )
    pg_session.flush()

    draft = create_rate_change_draft(
        pg_session,
        hotel_id=hotel_id,
        user_id=None,
        category_id=category.id,
        changes=[
            {"date": target_date.isoformat(), "values": {"price": 60001}}
            for target_date in dates
        ],
    )
    pg_session.commit()
    pg_session.refresh(draft)

    assert draft.changes[0]["raw_before"] == {"price": 60000.0}
    assert draft.changes[1]["raw_before"] == {"price": 60000.0}
    serialized = serialize_draft(pg_session, draft)
    assert serialized["status"] == "draft"
    assert [change["date"] for change in serialized["changes"]] == [
        "2026-12-30",
        "2026-12-31",
    ]
    assert [change["after"]["price"] for change in serialized["changes"]] == [
        60001.0,
        60001.0,
    ]
    assert pg_session.query(RateChangeDraft).filter_by(
        hotel_id=hotel_id, category_id=category.id, status="draft"
    ).count() == 1
    persisted_rates = (
        pg_session.query(DailyRate)
        .filter_by(hotel_id=hotel_id, category_id=category.id)
        .order_by(DailyRate.date)
        .all()
    )
    assert [rate.price for rate in persisted_rates] == [Decimal("60000.00")] * 2
    assert [rate.price_cash for rate in persisted_rates] == [Decimal("50000.00")] * 2
    assert [rate.price_transfer for rate in persisted_rates] == [Decimal("55000.00")] * 2
    assert [rate.price_mercadopago for rate in persisted_rates] == [Decimal("55000.00")] * 2
