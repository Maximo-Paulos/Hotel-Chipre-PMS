from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum


def register_owner(client: TestClient, email: str) -> tuple[dict[str, str], int]:
    with patch("app.api.auth._generate_code", return_value="123456"):
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": "Demo123!", "role": "owner"},
        )
    assert response.status_code == 201, response.text

    verify = client.post("/api/auth/verify-email", json={"email": email, "code": "123456"})
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    hotel_id = payload["hotel_id"]
    headers = {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Hotel-Id": str(hotel_id),
        "X-User-Id": str(payload["user"]["id"]),
    }
    return headers, hotel_id


def seed_operational_reservation(
    engine,
    hotel_id: int,
    *,
    reservation_status: ReservationStatusEnum = ReservationStatusEnum.PENDING,
    total_amount: float = 100.0,
    amount_paid: float = 0.0,
    deposit_amount: float = 30.0,
    requires_manual_review: bool = False,
    allocation_status: str = "assigned",
    with_valid_guest: bool = True,
) -> dict[str, int]:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    suffix = uuid4().hex[:6].upper()

    with SessionLocal() as db:
        config = db.get(HotelConfiguration, hotel_id)
        if not config:
            config = HotelConfiguration(id=hotel_id, owner_email=f"owner-{hotel_id}@example.com")
            db.add(config)
            db.flush()
        config.subscription_active = True
        config.require_document_for_checkin = True
        config.require_terms_acceptance = True
        config.hotel_name = f"Smoke Hotel {hotel_id}"
        config.set_extra_policies({"jurisdiction_code": "AR"})

        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Smoke Standard {suffix}",
            code=f"SMK{suffix[:3]}",
            description="Smoke category",
            base_price_per_night=total_amount,
            max_occupancy=2,
        )
        db.add(category)
        db.flush()

        room = Room(
            hotel_id=hotel_id,
            room_number=f"{suffix[:3]}",
            floor=1,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
        )
        db.add(room)
        db.flush()

        guest = Guest(
            hotel_id=hotel_id,
            first_name="Ada",
            last_name="Lovelace",
            document_type="DNI" if with_valid_guest else None,
            document_number=f"{hotel_id}{suffix}" if with_valid_guest else None,
            nationality="AR",
            country="AR",
            email=f"guest-{suffix.lower()}@example.com",
            terms_accepted=with_valid_guest,
        )
        db.add(guest)
        db.flush()

        reservation = Reservation(
            confirmation_code=f"SMOKE-{suffix}",
            hotel_id=hotel_id,
            guest_id=guest.id,
            room_id=room.id,
            category_id=category.id,
            check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=3),
            total_amount=total_amount,
            amount_paid=amount_paid,
            deposit_amount=deposit_amount,
            subtotal_amount=total_amount,
            tax_amount=0.0,
            fee_amount=0.0,
            commission_amount=0.0,
            net_amount=total_amount,
            currency_code="ARS",
            status=reservation_status,
            source=ReservationSourceEnum.DIRECT,
            num_adults=1,
            num_children=0,
            allocation_status=allocation_status,
            requires_manual_review=requires_manual_review,
            payment_collection_model="hotel_collect",
            settlement_status="not_applicable",
        )
        db.add(reservation)
        db.commit()
        db.refresh(reservation)

        return {
            "reservation_id": reservation.id,
            "guest_id": guest.id,
            "room_id": room.id,
            "category_id": category.id,
        }
