from datetime import date
from decimal import Decimal

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


def test_home_payload_reuses_reservation_facts_for_breakdowns(
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

    loaded_fact_windows = []
    original_loader = analytics_service._load_reservation_facts

    def track_fact_load(session, hotel_id, loaded_from, loaded_to):
        loaded_fact_windows.append((hotel_id, loaded_from, loaded_to))
        return original_loader(session, hotel_id, loaded_from, loaded_to)

    with monkeypatch.context() as patch_context:
        patch_context.setattr(analytics_service, "_load_reservation_facts", track_fact_load)
        payload = build_home_payload(
            db,
            hotel_id=hotel_config.id,
            date_from=date_from,
            date_to=date_to,
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
        )

    assert loaded_fact_windows == [(hotel_config.id, date_from, date_to)]
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
