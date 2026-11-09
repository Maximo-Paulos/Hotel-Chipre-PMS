"""PostgreSQL regression for saving a guest profile with the first arrival."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import (
    Room,
    RoomCategory,
    RoomHousekeepingStatusEnum,
    RoomStatusEnum,
)
from app.models.user import User
from app.services import checkin_service
from app.services.tenant_context import set_tenant_context


def test_guest_profile_save_and_first_arrival_are_atomic_and_tenant_scoped(pg_engine, monkeypatch):
    """The primary guest's synthetic profile is saved with the recorded arrival."""
    suffix = uuid4().hex[:10].upper()
    hotel_id = 210_000_000 + uuid4().int % 20_000_000
    foreign_hotel_id = hotel_id + 1
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    active_role = ["owner"]
    guest_id: int | None = None
    reservation_id: int | None = None

    seed = session_factory()
    try:
        seed.add_all(
            [
                HotelConfiguration(
                    id=hotel_id,
                    hotel_name=f"Synthetic check-in profile {suffix}",
                    subscription_active=True,
                    require_document_for_checkin=True,
                    require_terms_acceptance=True,
                ),
                HotelConfiguration(
                    id=foreign_hotel_id,
                    hotel_name=f"Synthetic foreign profile {suffix}",
                    subscription_active=True,
                ),
            ]
        )
        seed.flush()
        user = User(
            email=f"checkin-profile-{suffix.lower()}@example.test",
            password_hash="test-only",
            role="owner",
            is_verified=True,
        )
        seed.add(user)
        seed.flush()

        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic profile category {suffix}",
            code=f"CP{suffix}",
            base_price_per_night=Decimal("1000.00"),
            max_occupancy=1,
        )
        foreign_category = RoomCategory(
            hotel_id=foreign_hotel_id,
            name=f"Synthetic foreign category {suffix}",
            code=f"FP{suffix}",
            base_price_per_night=Decimal("1000.00"),
            max_occupancy=1,
        )
        primary_guest = Guest(
            hotel_id=hotel_id,
            first_name="QA",
            last_name=f"Profile {suffix}",
        )
        foreign_guest = Guest(
            hotel_id=foreign_hotel_id,
            first_name="Foreign",
            last_name=f"Profile {suffix}",
        )
        seed.add_all([category, foreign_category, primary_guest, foreign_guest])
        seed.flush()

        room = Room(
            hotel_id=hotel_id,
            category_id=category.id,
            room_number=f"P{suffix[:7]}",
            status=RoomStatusEnum.AVAILABLE,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
        )
        foreign_room = Room(
            hotel_id=foreign_hotel_id,
            category_id=foreign_category.id,
            room_number=f"F{suffix[:7]}",
            status=RoomStatusEnum.AVAILABLE,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
        )
        seed.add_all([room, foreign_room])
        seed.flush()

        check_in = date.today()
        check_out = check_in + timedelta(days=1)
        reservation = Reservation(
            hotel_id=hotel_id,
            guest_id=primary_guest.id,
            category_id=category.id,
            room_id=room.id,
            check_in_date=check_in,
            check_out_date=check_out,
            num_adults=1,
            total_amount=Decimal("1000.00"),
            amount_paid=Decimal("1000.00"),
            status=ReservationStatusEnum.FULLY_PAID,
            confirmation_code=f"CP-{suffix}",
        )
        seed.add(reservation)
        seed.commit()
        guest_id = primary_guest.id
        reservation_id = reservation.id
        actor_user_id = user.id
        foreign_guest_id = foreign_guest.id
    finally:
        seed.close()

    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date.today())

    def override_auth():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=actor_user_id,
            user_email=f"checkin-profile-{suffix.lower()}@example.test",
            user_role=active_role[0],
            is_verified=True,
            permissions=set(),
        )

    def override_db():
        db = session_factory()
        set_tenant_context(db, user_id=actor_user_id, hotel_id=hotel_id)
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    guest_patch = {
        "document_type": "DNI",
        "document_number": f"QA-{suffix}",
        "nationality": "Argentina",
        "country": "Argentina",
        "birth_place": "Buenos Aires",
        "birth_country": "Argentina",
        "marital_status": "Soltero/a",
        "occupation": "QA Tester",
        "terms_accepted": True,
    }

    try:
        assert guest_id is not None and reservation_id is not None

        # The request cannot write a guest from another hotel into this stay.
        foreign_attempt = client.post(
            f"/api/checkin/{reservation_id}/guests/{foreign_guest_id}",
            json={"guest": guest_patch},
        )
        assert foreign_attempt.status_code == 400

        # A role without check-in permission cannot save the same profile.
        active_role[0] = "housekeeping"
        denied_attempt = client.post(
            f"/api/checkin/{reservation_id}/guests/{guest_id}",
            json={"guest": guest_patch},
        )
        assert denied_attempt.status_code == 403

        # The owner path applies every form field and records arrival atomically.
        active_role[0] = "owner"
        response = client.post(
            f"/api/checkin/{reservation_id}/guests/{guest_id}",
            json={"guest": guest_patch},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["arrived_guest_count"] == 1
        assert payload["already_recorded"] is False
        assert payload["arrival"]["guest_id"] == guest_id
        assert payload["reservation_status"] == "checked_in"

        with session_factory() as verify:
            saved_guest = verify.query(Guest).filter_by(id=guest_id, hotel_id=hotel_id).one()
            saved_reservation = verify.query(Reservation).filter_by(
                id=reservation_id,
                hotel_id=hotel_id,
            ).one()
            assert saved_guest.document_type.value == "DNI"
            assert saved_guest.document_number == guest_patch["document_number"]
            assert saved_guest.nationality == "Argentina"
            assert saved_guest.country == "Argentina"
            assert saved_guest.birth_place == "Buenos Aires"
            assert saved_guest.birth_country == "Argentina"
            assert saved_guest.marital_status == "Soltero/a"
            assert saved_guest.occupation == "QA Tester"
            assert saved_guest.terms_accepted is True
            assert saved_reservation.status == ReservationStatusEnum.CHECKED_IN
            foreign_profile = verify.query(Guest).filter_by(id=foreign_guest_id, hotel_id=foreign_hotel_id).one()
            assert foreign_profile.document_number is None
            assert foreign_profile.terms_accepted is False
    finally:
        fastapi_app.dependency_overrides.clear()

        # The test database itself is disposable. Keep rows isolated under its
        # synthetic hotel IDs and let the session-scoped PG fixture drop schema.
