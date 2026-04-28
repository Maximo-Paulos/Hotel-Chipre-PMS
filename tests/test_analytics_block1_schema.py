from sqlalchemy import Numeric, UniqueConstraint

from app.models.analytics import (
    FactReservationDaily,
    FactRoomOccupancyDaily,
    AnalyticsAlertSnooze,
    RoomStateEvent,
)
from app.models.hotel_config import HotelConfiguration
from app.models.company import Company
from app.models.room import RoomCategory


def test_room_state_events_schema():
    table = RoomStateEvent.__table__
    assert list(table.columns.keys()) == [
        "id",
        "hotel_id",
        "room_id",
        "event_type",
        "reason_code",
        "reason_note",
        "started_at",
        "ended_at",
        "created_by_user_id",
        "closed_by_user_id",
        "created_at",
        "updated_at",
    ]
    assert table.c.event_type.type.enums == [
        "out_of_service",
        "maintenance",
        "housekeeping_block",
        "renovation",
    ]
    assert table.c.reason_code.type.enums == [
        "plumbing",
        "electrical",
        "furniture",
        "deep_clean",
        "inspection",
        "other",
    ]
    assert {idx.name for idx in table.indexes} == set()
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    } == set()


def test_fact_reservation_daily_schema():
    table = FactReservationDaily.__table__
    assert list(table.columns.keys()) == [
        "id",
        "hotel_id",
        "reservation_id",
        "stay_date",
        "room_id",
        "category_id",
        "company_id",
        "channel_code",
        "guest_segment",
        "status",
        "outcome",
        "row_kind",
        "occupied_night",
        "chargeable_night",
        "revenue_gross_ars",
        "revenue_gross_usd",
        "revenue_net_ars",
        "revenue_net_usd",
        "tax_ars",
        "tax_usd",
        "fee_ars",
        "fee_usd",
        "commission_ars",
        "commission_usd",
        "variable_cost_ars",
        "variable_cost_usd",
        "margin_operating_ars",
        "margin_operating_usd",
        "source_currency",
        "fx_rate_snapshot",
        "created_at",
        "updated_at",
    ]
    assert isinstance(table.c.revenue_gross_ars.type, Numeric)
    assert table.c.revenue_gross_ars.type.precision == 12
    assert table.c.revenue_gross_ars.type.scale == 2
    assert table.c.channel_code.type.enums == [
        "website_direct",
        "whatsapp",
        "phone",
        "walk_in",
        "booking",
        "expedia",
        "despegar",
        "other_ota",
        "other_direct",
    ]
    assert table.c.row_kind.type.enums == [
        "occupied",
        "no_show_chargeable",
        "no_show_waived",
    ]
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_fact_reservation_daily_hotel_reservation_date"}
    assert {idx.name for idx in table.indexes} == {
        "ix_fact_reservation_daily_hotel_date",
        "ix_fact_reservation_daily_hotel_reservation",
        "ix_fact_reservation_daily_hotel_category_date",
        "ix_fact_reservation_daily_hotel_room_date",
        "ix_fact_reservation_daily_hotel_company_date",
        "ix_fact_reservation_daily_hotel_channel_date",
        "ix_fact_reservation_daily_hotel_segment_date",
        "ix_fact_reservation_daily_hotel_outcome_date",
    }


def test_fact_room_occupancy_daily_schema():
    table = FactRoomOccupancyDaily.__table__
    assert list(table.columns.keys()) == [
        "id",
        "hotel_id",
        "room_id",
        "stay_date",
        "category_id",
        "status_at_night",
        "is_sellable_night",
        "is_occupied",
        "reservation_id",
        "revenue_net_ars",
        "revenue_net_usd",
        "margin_operating_ars",
        "margin_operating_usd",
        "created_at",
        "updated_at",
    ]
    assert table.c.status_at_night.type.enums == [
        "available",
        "occupied",
        "out_of_service",
        "maintenance",
        "housekeeping_block",
        "renovation",
    ]
    assert isinstance(table.c.revenue_net_ars.type, Numeric)
    assert table.c.revenue_net_ars.type.precision == 12
    assert table.c.revenue_net_ars.type.scale == 2
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_fact_room_occupancy_daily_hotel_room_date"}
    assert {idx.name for idx in table.indexes} == {
        "ix_fact_room_occupancy_daily_hotel_date",
        "ix_fact_room_occupancy_daily_hotel_room_date",
        "ix_fact_room_occupancy_daily_hotel_category_date",
        "ix_fact_room_occupancy_daily_hotel_status_date",
    }
    assert HotelConfiguration.__table__.c.analytics_ai_enabled.nullable is False
    assert isinstance(RoomCategory.__table__.c.variable_cost_per_night.type, Numeric)
    assert RoomCategory.__table__.c.variable_cost_per_night.type.precision == 12
    assert RoomCategory.__table__.c.variable_cost_per_night.type.scale == 2


def test_companies_schema():
    table = Company.__table__
    assert list(table.columns.keys()) == [
        "id",
        "hotel_id",
        "legal_name",
        "display_name",
        "tax_id",
        "country_code",
        "notes",
        "is_active",
        "created_at",
        "updated_at",
        "deactivated_at",
        "deactivated_by_user_id",
    ]
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_companies_hotel_display_name"}
    assert {idx.name for idx in table.indexes} == {
        "ix_companies_hotel_id",
        "ix_companies_hotel_active",
        "uq_companies_hotel_tax_id_not_null",
    }


def test_alert_snooze_schema():
    table = AnalyticsAlertSnooze.__table__
    assert {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_analytics_alert_snoozes_hotel_alert_scope"}
    assert {idx.name for idx in table.indexes} == {
        "ix_analytics_alert_snoozes_hotel_until",
        "ix_analytics_alert_snoozes_hotel_alert_scope",
    }
