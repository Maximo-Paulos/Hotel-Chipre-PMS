from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.models.reservation import (
    Reservation,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationNoShowPolicyAppliedEnum,
    ReservationOutcomeEnum,
    ReservationSourceEnum,
    ReservationStatusEnum,
    ReservationChannelCodeEnum,
)
from app.services import analytics_service
from app.services.analytics_facts import refresh_fact_reservation_daily, refresh_fact_room_occupancy_daily
from app.services.analytics_service import build_home_payload


def test_home_payload_aggregates_without_hydrating_reservation_facts(
    db, hotel_config, sample_guest, sample_categories, sample_rooms, monkeypatch
):
    date_from = date(2026, 5, 1)
    date_to = date(2026, 5, 1)
    reservation = Reservation(
        confirmation_code="FACT-HOME-REUSE-001",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date_from,
        check_out_date=date(2026, 5, 2),
        total_amount=Decimal("100.00"),
        subtotal_amount=Decimal("90.00"),
        net_amount=Decimal("90.00"),
        amount_paid=Decimal("100.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.FULLY_PAID,
        outcome=ReservationOutcomeEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        channel_code=ReservationChannelCodeEnum.OTHER_DIRECT,
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
        no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.NONE,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()
    refresh_fact_reservation_daily(db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to)
    refresh_fact_room_occupancy_daily(db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to)

    original_loader = analytics_service._load_reservation_facts
    fact_queries = []

    def capture_fact_query(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "from fact_reservation_daily" in statement.lower():
            fact_queries.append(statement.lower())

    with monkeypatch.context() as patch_context:
        patch_context.setattr(
            analytics_service,
            "_load_reservation_facts",
            lambda *_args, **_kwargs: pytest.fail("home analytics must aggregate reservation facts in SQL"),
        )
        event.listen(db.get_bind(), "before_cursor_execute", capture_fact_query)
        try:
            payload = build_home_payload(
                db,
                hotel_id=hotel_config.id,
                date_from=date_from,
                date_to=date_to,
                compare_previous=False,
                compare_yoy=False,
                currency_display="ARS",
            )
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", capture_fact_query)

    assert len(fact_queries) == 3
    assert any("sum(" in query for query in fact_queries)
    assert sum("group by" in query for query in fact_queries) == 2
    assert all("select fact_reservation_daily.id, fact_reservation_daily.hotel_id" not in query for query in fact_queries)
    facts = original_loader(db, hotel_config.id, date_from, date_to)

    assert payload["data"]["top_channels"] == analytics_service.build_channels_breakdown(
        db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to, facts=facts
    )
    assert payload["data"]["top_channels"] == analytics_service.build_channels_breakdown(
        db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to
    )
    assert payload["data"]["segments"] == analytics_service.build_segments_breakdown(
        db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to, facts=facts
    )
    assert payload["data"]["segments"] == analytics_service.build_segments_breakdown(
        db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to
    )
