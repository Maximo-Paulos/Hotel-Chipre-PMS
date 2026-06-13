from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest, GuestTag, GuestTagTypeEnum
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog


def _override_auth(hotel_id: int, role: str, user_id: int = 10):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=f"{role}@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    return client, db, engine


def _seed_blocked_reservation(db, hotel_id: int = 6201) -> Reservation:
    hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Hotel {hotel_id}", subscription_active=True)
    db.add(hotel)
    db.flush()
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Ana",
        last_name="Gomez",
        document_type="DNI",
        document_number="55111222",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Standard",
        code=f"STD{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        category_id=category.id,
        room_number="101",
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        check_in_date=date(2026, 2, 1),
        check_out_date=date(2026, 2, 2),
        num_adults=1,
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("100.00"),
        status=ReservationStatusEnum.FULLY_PAID,
        confirmation_code=f"OVR{hotel_id}",
    )
    db.add(reservation)
    db.flush()
    db.add(
        GuestTag(
            hotel_id=hotel_id,
            guest_id=guest.id,
            tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
            note="Prior incident",
        )
    )
    db.flush()
    return reservation


def test_unauthorized_role_cannot_override():
    client, db, engine = _client_with_db()
    reservation = _seed_blocked_reservation(db)
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(6201, "receptionist", user_id=123)
    try:
        response = client.post(f"/api/checkin/{reservation.id}", json={"override_prohibido": True})

        assert response.status_code == 403
        assert db.query(SecurityAuditLog).filter(SecurityAuditLog.action == "checkin.prohibido_override").count() == 0
        denied = db.query(SecurityAuditLog).filter(SecurityAuditLog.action == "permission.denied").one()
        assert "checkin:override_prohibido" in (denied.details or "")
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
