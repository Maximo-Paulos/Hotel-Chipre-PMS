from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.api import checkin as checkin_api
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.daily_rate import DailyRate
from app.models.laundry import LaundryBatch
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.stock import StockItem
from app.models.user import User
from app.services.permission_service import set_role_override, set_user_override


def _client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add(HotelConfiguration(id=1, hotel_name="RBAC routes", subscription_active=True))
    db.add_all(
        [
            User(id=10, email="owner-routes@example.test", password_hash="synthetic", is_verified=True),
            User(id=20, email="reception-routes@example.test", password_hash="synthetic", is_verified=True),
            User(id=30, email="manager-routes@example.test", password_hash="synthetic", is_verified=True),
        ]
    )
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=1, user_id=10, role="owner", status="active"),
            HotelMembership(hotel_id=1, user_id=20, role="receptionist", status="active"),
            HotelMembership(hotel_id=1, user_id=30, role="manager", status="active"),
        ]
    )
    category = RoomCategory(
        hotel_id=1, name="Standard", code="STD", base_price_per_night=Decimal("100.00"), max_occupancy=2
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=1, category_id=category.id, room_number="101", floor=1, status=RoomStatusEnum.AVAILABLE
    )
    guest = Guest(hotel_id=1, first_name="Ana", last_name="RBAC")
    db.add_all([room, guest])
    db.flush()
    reservation = Reservation(
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code="RBAC-ROUTE-1",
        check_in_date=date.today(),
        check_out_date=date.today() + timedelta(days=2),
        status=ReservationStatusEnum.PENDING,
        total_amount=Decimal("200.00"),
        num_adults=1,
    )
    stock_item = StockItem(hotel_id=1, name="Soap", unit="unit", active=True)
    db.add_all([reservation, stock_item])
    db.commit()

    auth = {"user_id": 20, "role": "receptionist"}

    def override_db():
        yield db

    def override_auth():
        return AuthContext(
            hotel_id=1,
            user_id=auth["user_id"],
            user_email="synthetic@example.test",
            user_role=auth["role"],
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    return TestClient(fastapi_app), db, engine, auth, reservation, stock_item


def _close(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_reservation_read_and_cancel_follow_individual_overrides_without_data_leak():
    client, db, engine, auth, reservation, _stock_item = _client()
    try:
        assert client.get("/api/reservations/").status_code == 200
        set_user_override(db, 1, 20, "receptionist", "reservation:read", False, actor_user_id=10)
        db.commit()

        denied_list = client.get("/api/reservations/")
        denied_detail = client.get(f"/api/reservations/{reservation.id}")
        assert denied_list.status_code == denied_detail.status_code == 403
        assert "RBAC-ROUTE-1" not in denied_list.text
        assert "RBAC-ROUTE-1" not in denied_detail.text

        set_user_override(db, 1, 20, "receptionist", "reservation:read", True, actor_user_id=10)
        set_user_override(db, 1, 20, "receptionist", "reservation:update", False, actor_user_id=10)
        db.commit()
        denied_update = client.patch(f"/api/reservations/{reservation.id}", json={"notes": "must not persist"})
        assert denied_update.status_code == 403
        db.refresh(reservation)
        assert reservation.notes is None

        set_user_override(db, 1, 20, "receptionist", "reservation:update", True, actor_user_id=10)
        db.commit()
        allowed_update = client.patch(f"/api/reservations/{reservation.id}", json={"notes": "allowed"})
        assert allowed_update.status_code == 200
        db.refresh(reservation)
        assert reservation.notes == "allowed"

        set_user_override(db, 1, 20, "receptionist", "reservation:cancel", False, actor_user_id=10)
        db.commit()
        denied_cancel = client.post(f"/api/reservations/{reservation.id}/cancel")
        assert denied_cancel.status_code == 403
        db.refresh(reservation)
        assert reservation.status == ReservationStatusEnum.PENDING

        set_user_override(db, 1, 20, "receptionist", "reservation:cancel", True, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/reservations/{reservation.id}/cancel").status_code == 200
    finally:
        _close(db, engine)


def test_stock_read_movement_and_admin_are_independently_enforced_without_mutation():
    client, db, engine, auth, _reservation, stock_item = _client()
    try:
        auth.update(user_id=30, role="manager")
        assert client.get("/api/stock/items").status_code == 200

        set_user_override(db, 1, 30, "manager", "stock:read", False, actor_user_id=10)
        db.commit()
        denied_read = client.get("/api/stock/items")
        assert denied_read.status_code == 403
        assert "Soap" not in denied_read.text

        set_user_override(db, 1, 30, "manager", "stock:read", True, actor_user_id=10)
        set_user_override(db, 1, 30, "manager", "stock:admin", False, actor_user_id=10)
        db.commit()
        assert client.get("/api/stock/items").status_code == 200
        denied_delete = client.delete(f"/api/stock/items/{stock_item.id}")
        assert denied_delete.status_code == 403
        assert db.get(StockItem, stock_item.id) is not None

        set_user_override(db, 1, 30, "manager", "stock:movement", False, actor_user_id=10)
        db.commit()
        denied_movement = client.post(
            "/api/stock/movements",
            json={"item_id": stock_item.id, "movement_type": "in", "quantity": "2.00"},
        )
        assert denied_movement.status_code == 403
        current = client.get(f"/api/stock/items/{stock_item.id}/current")
        assert current.status_code == 200
        assert Decimal(str(current.json()["quantity"])) == Decimal("0.00")

        auth.update(user_id=10, role="owner")
        set_role_override(db, 1, "owner", "stock:adjust", False, actor_user_id=10)
        db.commit()
        adjustment = {"item_id": stock_item.id, "movement_type": "adjustment", "quantity": "3.00"}
        assert client.post("/api/stock/movements", json=adjustment).status_code == 403
        set_role_override(db, 1, "owner", "stock:adjust", True, actor_user_id=10)
        db.commit()
        assert client.post("/api/stock/movements", json=adjustment).status_code == 201
    finally:
        _close(db, engine)


def test_checkin_checkout_and_force_checkout_use_distinct_action_permissions(monkeypatch):
    client, db, engine, auth, reservation, _stock_item = _client()
    calls: list[str] = []

    def fake_checkin(db, reservation_id, **_kwargs):
        calls.append("checkin")
        target = db.get(Reservation, reservation_id)
        target.status = ReservationStatusEnum.CHECKED_IN
        db.flush()
        return target

    def fake_checkout(db, reservation_id, *, force=False, **_kwargs):
        calls.append("force_checkout" if force else "checkout")
        target = db.get(Reservation, reservation_id)
        target.status = ReservationStatusEnum.CHECKED_OUT
        db.flush()
        return target

    monkeypatch.setattr(checkin_api, "perform_checkin", fake_checkin)
    monkeypatch.setattr(checkin_api, "perform_checkout", fake_checkout)
    try:
        set_user_override(db, 1, 20, "receptionist", "checkin:perform", False, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/checkin/{reservation.id}").status_code == 403
        assert calls == []

        set_user_override(db, 1, 20, "receptionist", "checkin:perform", True, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/checkin/{reservation.id}").status_code == 200
        assert calls == ["checkin"]

        set_user_override(db, 1, 20, "receptionist", "checkout:perform", False, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/checkin/checkout/{reservation.id}").status_code == 403
        assert calls == ["checkin"]

        set_user_override(db, 1, 20, "receptionist", "checkout:perform", True, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/checkin/checkout/{reservation.id}").status_code == 200
        assert calls[-1] == "checkout"

        assert client.post(f"/api/checkin/checkout/{reservation.id}?force=true").status_code == 403
        assert calls[-1] == "checkout"
        auth.update(user_id=10, role="owner")
        assert client.post(f"/api/checkin/checkout/{reservation.id}?force=true").status_code == 200
        assert calls[-1] == "force_checkout"
    finally:
        _close(db, engine)


def test_room_read_and_status_update_follow_revocation_and_grant_without_leak_or_mutation():
    client, db, engine, auth, _reservation, _stock_item = _client()
    room = db.query(Room).filter_by(hotel_id=1).one()
    try:
        auth.update(user_id=30, role="manager")
        set_user_override(db, 1, 30, "manager", "room:read", False, actor_user_id=10)
        db.commit()

        denied_read = client.get("/api/rooms/")
        assert denied_read.status_code == 403
        assert room.room_number not in denied_read.text

        set_user_override(db, 1, 30, "manager", "room:read", True, actor_user_id=10)
        set_user_override(db, 1, 30, "manager", "room:status_update", False, actor_user_id=10)
        db.commit()
        assert client.get("/api/rooms/").status_code == 200

        denied_status = client.patch(
            f"/api/rooms/{room.id}/status",
            json={"status": "maintenance"},
        )
        assert denied_status.status_code == 403
        db.refresh(room)
        assert room.status == RoomStatusEnum.AVAILABLE

        set_user_override(db, 1, 30, "manager", "room:status_update", True, actor_user_id=10)
        db.commit()
        allowed_status = client.patch(
            f"/api/rooms/{room.id}/status",
            json={"status": "maintenance"},
        )
        assert allowed_status.status_code == 200
        db.refresh(room)
        assert room.status == RoomStatusEnum.MAINTENANCE
    finally:
        _close(db, engine)


def test_laundry_read_and_movement_follow_revocation_and_grant_without_partial_mutation():
    client, db, engine, auth, _reservation, _stock_item = _client()
    try:
        auth.update(user_id=30, role="manager")
        seeded = client.post("/api/laundry/batches", json={"notes": "safe synthetic batch"})
        assert seeded.status_code == 201
        batch_code = seeded.json()["batch_code"]

        set_user_override(db, 1, 30, "manager", "laundry:read", False, actor_user_id=10)
        db.commit()
        denied_read = client.get("/api/laundry/batches")
        assert denied_read.status_code == 403
        assert batch_code not in denied_read.text

        set_user_override(db, 1, 30, "manager", "laundry:read", True, actor_user_id=10)
        set_user_override(db, 1, 30, "manager", "laundry:movement", False, actor_user_id=10)
        db.commit()
        allowed_read = client.get("/api/laundry/batches")
        assert allowed_read.status_code == 200
        before_count = db.query(LaundryBatch).filter_by(hotel_id=1).count()

        denied_movement = client.post("/api/laundry/batches", json={"notes": "must not persist"})
        assert denied_movement.status_code == 403
        assert db.query(LaundryBatch).filter_by(hotel_id=1).count() == before_count

        set_user_override(db, 1, 30, "manager", "laundry:movement", True, actor_user_id=10)
        db.commit()
        assert client.post("/api/laundry/batches", json={"notes": "allowed"}).status_code == 201
        assert db.query(LaundryBatch).filter_by(hotel_id=1).count() == before_count + 1
    finally:
        _close(db, engine)


def test_rate_read_and_update_follow_revocation_and_grant_without_partial_mutation():
    client, db, engine, auth, _reservation, _stock_item = _client()
    category = db.query(RoomCategory).filter_by(hotel_id=1).one()
    target_date = date.today() + timedelta(days=30)
    path = f"/api/rates/category/{category.id}"
    try:
        auth.update(user_id=30, role="manager")
        set_user_override(db, 1, 30, "manager", "rates:read", False, actor_user_id=10)
        db.commit()

        denied_read = client.get(
            path,
            params={"from_date": target_date.isoformat(), "to_date": target_date.isoformat()},
        )
        assert denied_read.status_code == 403
        assert "daily_rate" not in denied_read.text
        denied_calendar = client.get(
            "/api/rate-calendar/daily",
            params={
                "category_id": category.id,
                "date_from": target_date.isoformat(),
                "date_to": target_date.isoformat(),
            },
        )
        assert denied_calendar.status_code == 403

        set_user_override(db, 1, 30, "manager", "rates:read", True, actor_user_id=10)
        set_user_override(db, 1, 30, "manager", "rates:update", False, actor_user_id=10)
        db.commit()
        assert client.get(
            path,
            params={"from_date": target_date.isoformat(), "to_date": target_date.isoformat()},
        ).status_code == 200
        assert client.get(
            "/api/rate-calendar/daily",
            params={
                "category_id": category.id,
                "date_from": target_date.isoformat(),
                "date_to": target_date.isoformat(),
            },
        ).status_code == 200

        denied_update = client.post(
            f"{path}/daily",
            json={"date": target_date.isoformat(), "price": 123.45},
        )
        assert denied_update.status_code == 403
        assert db.query(DailyRate).filter_by(
            hotel_id=1,
            category_id=category.id,
            date=target_date,
        ).one_or_none() is None

        set_user_override(db, 1, 30, "manager", "rates:update", True, actor_user_id=10)
        db.commit()
        assert client.post(
            f"{path}/daily",
            json={"date": target_date.isoformat(), "price": 123.45},
        ).status_code == 200
        assert db.query(DailyRate).filter_by(
            hotel_id=1,
            category_id=category.id,
            date=target_date,
        ).one().price == 123.45
    finally:
        _close(db, engine)
