from datetime import date
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from app.models.commercial import TaxPolicy
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.ota.contracts import NormalizedOTAReservation
from app.services.ota_service import OTAIntegrationService
import app.services.ota_service as ota_service_module


def test_ota_room_selection_rechecks_stale_candidate_after_postgres_lock(pg_engine, monkeypatch):
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:8].upper()
    hotel_id = int(uuid4().hex[:7], 16) + 100_000_000
    category_code = f"RACE_{suffix}"
    room_ids: list[int] = []
    session_a = session_factory()

    try:
        hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic OTA Race {suffix}")
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic Race Category {suffix}",
            code=category_code,
            base_price_per_night=100,
            max_occupancy=2,
        )
        session_a.add(hotel)
        session_a.flush()
        session_a.add(category)
        session_a.flush()
        rooms = [
            Room(
                hotel_id=hotel_id,
                room_number=f"R{suffix[:6]}{label}",
                floor=1,
                category_id=category.id,
                status=RoomStatusEnum.AVAILABLE,
                is_active=True,
            )
            for label in ("A", "B")
        ]
        session_a.add_all(rooms)
        session_a.commit()
        room_ids = [room.id for room in rooms]
        category = session_a.query(RoomCategory).filter_by(hotel_id=hotel_id, code=category_code).one()

        normalized = NormalizedOTAReservation(
            provider_code="booking",
            external_reservation_id=f"PG-OTA-RACE-{suffix}",
            external_confirmation_code=None,
            guest_full_name="Synthetic OTA Guest",
            guest_email=None,
            check_in_date=date(2027, 1, 10),
            check_out_date=date(2027, 1, 12),
            sellable_product_code=None,
            rate_plan_code=None,
            num_adults=1,
            num_children=0,
            currency_code="ARS",
            gross_total=200.0,
            tax_total=0.0,
            fee_total=0.0,
            commission_total=0.0,
        )

        original_find_available_rooms = ota_service_module.find_available_rooms
        raced_room_ids: list[int] = []

        def scan_then_commit_competing_booking(*args, **kwargs):
            candidates = original_find_available_rooms(*args, **kwargs)
            if candidates and not raced_room_ids:
                raced_room = candidates[0]
                with session_factory() as session_b:
                    competing_guest = Guest(
                        hotel_id=hotel_id,
                        first_name="Synthetic",
                        last_name="Competitor",
                    )
                    session_b.add(competing_guest)
                    session_b.flush()
                    session_b.add(
                        Reservation(
                            hotel_id=hotel_id,
                            confirmation_code=f"PG-OTA-RACE-{suffix}-COMP",
                            guest_id=competing_guest.id,
                            room_id=raced_room.id,
                            category_id=category.id,
                            check_in_date=normalized.check_in_date,
                            check_out_date=normalized.check_out_date,
                            total_amount=200,
                            subtotal_amount=200,
                            net_amount=200,
                            amount_paid=0,
                            deposit_amount=0,
                            currency_code="ARS",
                            status=ReservationStatusEnum.PENDING,
                            source=ReservationSourceEnum.BOOKING,
                            num_adults=1,
                            num_children=0,
                        )
                    )
                    session_b.commit()
                raced_room_ids.append(raced_room.id)
            return candidates

        monkeypatch.setattr(
            ota_service_module,
            "find_available_rooms",
            scan_then_commit_competing_booking,
        )

        selected_category, selected_room = OTAIntegrationService._select_room_for_normalized_reservation(
            session_a,
            hotel_id=hotel_id,
            reservation_id=None,
            normalized=normalized,
            candidate_categories=[category],
        )

        assert len(room_ids) == 2
        assert raced_room_ids
        assert selected_category is not None
        assert selected_category.id == category.id
        assert selected_room is not None
        assert selected_room.id != raced_room_ids[0]
        assert selected_room.id in room_ids
    finally:
        session_a.rollback()
        session_a.close()
        with session_factory.begin() as cleanup:
            cleanup.query(Reservation).filter(Reservation.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(TaxPolicy).filter(TaxPolicy.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(Room).filter(Room.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(Guest).filter(Guest.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).delete(
                synchronize_session=False
            )
