"""
Tests for OTA Integration — Race condition handling and webhook processing.
"""
import pytest
from datetime import date
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.ota import OTAReservationMapping, OTASyncStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.services.ota_service import OTAIntegrationService, OTAError
from app.services.reservation_service import create_reservation, ReservationError
from app.schemas.reservation import ReservationCreate


class TestBookingWebhook:
    def test_process_booking_reservation(self, db, sample_rooms, sample_categories, hotel_config):
        payload = {
            "reservation_id": "BK-123456",
            "guest_name": "John Smith",
            "guest_email": "john@email.com",
            "checkin": "2026-04-01",
            "checkout": "2026-04-05",
            "room_type": "STD_DBL",
            "num_adults": 2,
            "num_children": 0,
            "total_price": 500.00,
            "currency": "ARS",
        }
        mapping = OTAIntegrationService.process_booking_webhook(db, payload)
        db.flush()

        assert mapping.sync_status == OTASyncStatusEnum.SYNCED
        assert mapping.reservation_id is not None
        assert mapping.ota_name == "booking"
        assert mapping.ota_reservation_id == "BK-123456"

        res = db.query(Reservation).filter(Reservation.id == mapping.reservation_id).first()
        assert res is not None
        assert res.status == ReservationStatusEnum.FULLY_PAID
        assert res.total_amount == 500.0
        assert res.source.value == "booking"

    def test_duplicate_booking_ignored(self, db, sample_rooms, sample_categories, hotel_config):
        payload = {
            "reservation_id": "BK-DUP-001",
            "guest_name": "Duplicate Guest",
            "checkin": "2026-05-01",
            "checkout": "2026-05-03",
            "room_type": "STD_DBL",
            "num_adults": 1,
            "total_price": 200.0,
        }
        m1 = OTAIntegrationService.process_booking_webhook(db, payload)
        db.flush()
        m2 = OTAIntegrationService.process_booking_webhook(db, payload)
        assert m1.id == m2.id  # Same mapping returned


class TestExpediaWebhook:
    def test_process_expedia_reservation(self, db, sample_rooms, sample_categories, hotel_config):
        payload = {
            "booking_id": "EXP-987654",
            "guest": {"first_name": "Jane", "last_name": "Doe", "email": "jane@email.com"},
            "stay": {"checkin": "2026-04-10", "checkout": "2026-04-13"},
            "room_type_id": "SUP_DBL",
            "occupancy": {"adults": 2, "children": 1},
            "pricing": {"total": 450.00, "currency": "ARS"},
        }
        mapping = OTAIntegrationService.process_expedia_webhook(db, payload)
        db.flush()

        assert mapping.sync_status == OTASyncStatusEnum.SYNCED
        assert mapping.ota_name == "expedia"
        res = db.query(Reservation).filter(Reservation.id == mapping.reservation_id).first()
        assert res is not None
        assert res.total_amount == 450.0
        assert res.source.value == "expedia"


class TestOTARaceCondition:
    """
    Critical test: Simulates simultaneous booking from OTA and direct.
    Verifies that the system handles the race condition correctly.
    """
    def test_last_room_race_condition(self, db, sample_categories, hotel_config):
        """
        Scenario: Only 1 room of category SUITE_P (room 406, 407, 408).
        Book 2 of them directly, leaving 1 available.
        Then simultaneously: a web booking and a Booking.com reservation
        compete for the last room.
        
        Expected: One succeeds, the other fails with overbooking error.
        """
        cat_suite = sample_categories[2]

        # Create only 1 suite room to force contention
        single_room = Room(
            room_number="SUITE-RACE",
            floor=4,
            category_id=cat_suite.id,
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
        )
        db.add(single_room)
        db.flush()

        # Create a guest for the direct booking
        guest = Guest(first_name="Direct", last_name="Booker", email="direct@test.com")
        db.add(guest)
        db.flush()

        # Direct booking takes the last room
        direct_data = ReservationCreate(
            guest_id=guest.id,
            category_id=cat_suite.id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),
        )
        direct_res = create_reservation(db, direct_data)
        db.flush()
        assert direct_res.room_id == single_room.id

        # Now Booking.com tries to book the same dates/category
        booking_payload = {
            "reservation_id": "BK-RACE-001",
            "guest_name": "OTA Racer",
            "checkin": "2026-04-01",
            "checkout": "2026-04-05",
            "room_type": "SUITE_P",
            "num_adults": 2,
            "total_price": 1000.0,
        }

        with pytest.raises(OTAError, match="OVERBOOKING"):
            OTAIntegrationService.process_booking_webhook(db, booking_payload)

        # Verify the mapping was created with CONFLICT status
        mapping = db.query(OTAReservationMapping).filter(
            OTAReservationMapping.ota_reservation_id == "BK-RACE-001"
        ).first()
        assert mapping is not None
        assert mapping.sync_status == OTASyncStatusEnum.CONFLICT

    def test_non_overlapping_ota_succeeds(self, db, sample_categories, hotel_config):
        """Non-overlapping OTA booking should succeed even with 1 room."""
        cat_suite = sample_categories[2]
        room = Room(room_number="SUITE-OK", floor=4, category_id=cat_suite.id, status=RoomStatusEnum.AVAILABLE)
        db.add(room)
        db.flush()

        guest = Guest(first_name="First", last_name="Guest")
        db.add(guest)
        db.flush()

        # Book Apr 1-5
        d1 = ReservationCreate(
            guest_id=guest.id, category_id=cat_suite.id,
            check_in_date=date(2026,4,1), check_out_date=date(2026,4,5),
        )
        create_reservation(db, d1)
        db.flush()

        # OTA books Apr 5-8 (no overlap — checkout day = checkin day)
        payload = {
            "reservation_id": "BK-NOOVERLAP",
            "guest_name": "Second Guest",
            "checkin": "2026-04-05",
            "checkout": "2026-04-08",
            "room_type": "SUITE_P",
            "num_adults": 1,
            "total_price": 750.0,
        }
        mapping = OTAIntegrationService.process_booking_webhook(db, payload)
        db.flush()
        assert mapping.sync_status == OTASyncStatusEnum.SYNCED


class TestAvailabilityUpdate:
    def test_build_availability(self, db, sample_rooms, sample_categories, sample_guest, hotel_config):
        cat_std = sample_categories[0]
        d = ReservationCreate(
            guest_id=sample_guest.id, category_id=cat_std.id,
            check_in_date=date(2026,4,1), check_out_date=date(2026,4,3),
        )
        create_reservation(db, d)
        db.flush()

        avail = OTAIntegrationService.build_availability_update(
            db, cat_std.id, date(2026,4,1), date(2026,4,4)
        )
        assert len(avail) == 3
        assert avail[0]["available"] == 19  # 20 std rooms - 1 booked
        assert avail[2]["available"] == 20  # Apr 3: no booking
