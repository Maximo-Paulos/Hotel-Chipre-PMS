"""PostgreSQL regression coverage for guest full-name searches."""

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.services.guest_service import search_guests


def test_search_guests_matches_full_name_phrase_without_cross_hotel_results(pg_session):
    hotel_a = HotelConfiguration(
        id=941001,
        hotel_name="Synthetic Guest Search A",
        subscription_active=True,
    )
    hotel_b = HotelConfiguration(
        id=941002,
        hotel_name="Synthetic Guest Search B",
        subscription_active=True,
    )
    guest_a = Guest(
        hotel_id=hotel_a.id,
        first_name="QA",
        last_name="Auditor",
        document_type="DNI",
        document_number="QA-20260428",
    )
    guest_b = Guest(
        hotel_id=hotel_b.id,
        first_name="QA",
        last_name="Auditor",
        document_type="DNI",
        document_number="QA-OTHER-HOTEL",
    )
    pg_session.add_all([hotel_a, hotel_b])
    pg_session.flush()
    pg_session.add_all([guest_a, guest_b])
    pg_session.flush()

    assert search_guests(pg_session, hotel_a.id, "QA Auditor") == [guest_a]
    assert search_guests(pg_session, hotel_a.id, "qa auditor") == [guest_a]
