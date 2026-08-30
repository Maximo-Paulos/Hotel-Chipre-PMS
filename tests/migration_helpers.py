"""Helpers for seeding schemas before a migration under test."""

from datetime import datetime, timezone

from sqlalchemy import MetaData, Table


def insert_historical_hotel_config(engine, *hotel_ids: int) -> None:
    """Insert the hotel-config shape that existed before the 2026-08 changes.

    Migration tests intentionally open a database at an older revision. The
    current ORM includes newer authority columns, so using ``add`` there
    would ask SQLite to insert columns that do not exist yet.
    """
    values = {
        "deposit_percentage": 30.0,
        "enable_full_payment": True,
        "enable_deposit_payment": True,
        "enable_cash": True,
        "enable_mercado_pago": True,
        "enable_paypal": True,
        "enable_credit_card": True,
        "enable_debit_card": True,
        "enable_bank_transfer": False,
        "free_cancellation_hours": 48,
        "cancellation_penalty_percentage": 0.0,
        "allow_cancellation_after_checkin": False,
        "enable_booking_sync": True,
        "enable_expedia_sync": True,
        "enable_despegar_sync": True,
        "require_document_for_checkin": True,
        "require_terms_acceptance": True,
        "hotel_name": "Mi Hotel",
        "hotel_timezone": "America/Argentina/Buenos_Aires",
        "default_currency": "ARS",
        "languages": ["es"],
        "jurisdiction_code": "AR",
        "owner_email": None,
        "subscription_active": True,
        "receptionist_view_past_days": 0,
        "receptionist_view_future_days": 7,
        "allow_revenue_manager": True,
        "allow_revenue_receptionist": False,
        "sync_interval_minutes": 5,
        "safety_buffer_rooms": 0,
        "allow_overbooking": False,
        "max_overallocation_pct": 0.0,
        "no_show_cutoff_hours": 24,
        "ota_autopush_enabled": False,
        "card_validation_enabled": False,
        "payment_retry_attempts": 2,
        "auth_amount_pct": 0.0,
        "stop_sell_channels": None,
        "event_notifications": None,
        "extra_policies": None,
        "updated_at": datetime.now(timezone.utc),
    }
    with engine.begin() as connection:
        table = Table("hotel_configuration", MetaData(), autoload_with=connection)
        available = set(table.c.keys())
        for hotel_id in hotel_ids:
            payload = {"id": hotel_id, **{key: value for key, value in values.items() if key in available}}
            connection.execute(table.insert().values(payload))
