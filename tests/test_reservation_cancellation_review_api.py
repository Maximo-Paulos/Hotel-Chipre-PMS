"""Coverage for the manual cancellation review workflow and its access boundary."""

import importlib.util
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.cancellation_review import ReservationCancellationReview
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.transaction import Transaction
from app.models.user import User
from app.services import reservation_cancellation_service
from app.services.reservation_service import find_available_rooms

_POLICY = {
    "schema_version": 1,
    "source": "rate_plan",
    "rate_plan_name": "Flexible QA",
    "cancellation_model": "flexible",
    "is_refundable": True,
    "free_cancellation_hours": 48,
    "penalty_type": "percentage",
    "penalty_value": "50",
    "currency": "ARS",
}


def _auth(ctx):
    return AuthContext(
        hotel_id=ctx["hotel_id"],
        user_id=ctx["user_id"],
        user_email=f"{ctx['role']}@cancellation.test",
        user_role=ctx["role"],
        is_verified=True,
        permissions=set(),
    )


@pytest.fixture
def cancellation_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()
    db.add_all(
        [
            HotelConfiguration(
                id=1,
                subscription_active=True,
                check_in_time="15:00",
                hotel_timezone="America/Argentina/Buenos_Aires",
            ),
            HotelConfiguration(
                id=2,
                subscription_active=True,
                check_in_time="15:00",
                hotel_timezone="America/Argentina/Buenos_Aires",
            ),
            User(id=10, email="requester@cancellation.test", password_hash="test", is_active=True),
            User(id=11, email="manager@cancellation.test", password_hash="test", is_active=True),
        ]
    )
    db.flush()
    ctx = {"hotel_id": 1, "role": "receptionist", "user_id": 10}

    def override_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_auth_context] = lambda: _auth(ctx)
    client = TestClient(fastapi_app)
    monkeypatch.setattr(
        "app.api.reservations.process_payment_link_revocations_after_commit",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.api.bookings.process_payment_link_revocations_after_commit",
        lambda *_args, **_kwargs: None,
    )
    try:
        yield client, db, ctx
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed_reservation(db, *, hotel_id=1, snapshot=_POLICY, check_in_time="15:00"):
    config = db.get(HotelConfiguration, hotel_id)
    config.check_in_time = check_in_time
    guest = Guest(
        hotel_id=hotel_id,
        first_name="QA",
        last_name="Guest",
        email=f"cancel-{hotel_id}-{db.query(Reservation).count()}@example.test",
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Cancellation {hotel_id}",
        code=f"CANCEL-{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"CANCEL-{hotel_id}-{guest.id}",
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        check_in_date=date(2026, 12, 2),
        check_out_date=date(2026, 12, 4),
        reserved_nights=2,
        total_amount=Decimal("1000.00"),
        amount_paid=Decimal("0.00"),
        deposit_amount=Decimal("0.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        cancellation_policy_snapshot=snapshot,
        allocation_status="assigned",
        num_adults=1,
        num_children=0,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation, category, room


def _set_now(monkeypatch, value: datetime) -> None:
    monkeypatch.setattr(reservation_cancellation_service, "utc_now", lambda: value)


def test_penalty_request_is_pending_idempotent_and_keeps_room_inventory(cancellation_client, monkeypatch):
    client, db, _ctx = cancellation_client
    request_time = datetime(2026, 11, 30, 20, tzinfo=timezone.utc)
    _set_now(monkeypatch, request_time)
    reservation, category, room = _seed_reservation(db)

    first = client.post(f"/api/reservations/{reservation.id}/cancel")
    second = client.post(f"/api/reservations/{reservation.id}/cancel")

    assert first.status_code == second.status_code == 200
    assert first.json()["cancellation_outcome"] == "approval_required"
    assert first.json()["status"] == "pending"
    assert first.json()["cancellation_review"]["penalty_amount"] == "500.00"
    assert second.json()["cancellation_review"]["id"] == first.json()["cancellation_review"]["id"]
    assert db.query(ReservationCancellationReview).filter_by(reservation_id=reservation.id).count() == 1
    assert db.query(Transaction).count() == 0
    assert db.get(Reservation, reservation.id).room_id == room.id
    assert find_available_rooms(
        db, category.id, reservation.check_in_date, reservation.check_out_date, hotel_id=1
    ) == []


def test_legacy_bookings_cancel_route_uses_the_same_penalty_review_flow(
    cancellation_client,
    monkeypatch,
):
    client, db, _ctx = cancellation_client
    _set_now(monkeypatch, datetime(2026, 11, 30, 20, tzinfo=timezone.utc))
    reservation, _category, room = _seed_reservation(db)

    response = client.post(f"/api/bookings/{reservation.id}/cancel")

    assert response.status_code == 200, response.text
    assert response.json()["cancellation_outcome"] == "approval_required"
    assert response.json()["status"] == "pending"
    assert response.json()["cancellation_review"]["penalty_amount"] == "500.00"
    assert db.get(Reservation, reservation.id).room_id == room.id
    assert db.query(Transaction).filter_by(hotel_id=1, reservation_id=reservation.id).count() == 0
    assert db.query(ReservationCancellationReview).filter_by(
        hotel_id=1,
        reservation_id=reservation.id,
    ).count() == 1


def test_manager_approval_cancels_but_does_not_create_a_charge(cancellation_client, monkeypatch):
    client, db, ctx = cancellation_client
    _set_now(monkeypatch, datetime(2026, 11, 30, 20, tzinfo=timezone.utc))
    reservation, _category, _room = _seed_reservation(db)
    requested = client.post(f"/api/reservations/{reservation.id}/cancel")
    review_id = requested.json()["cancellation_review"]["id"]
    ctx.update(role="manager", user_id=11)

    response = client.post(
        f"/api/reservations/cancellation-reviews/{review_id}/decision",
        json={"decision": "approve", "reason": "Se confirma la penalidad del plan"},
    )

    assert response.status_code == 200
    assert response.json()["cancellation_review"]["status"] == "approved"
    assert response.json()["reservation"]["status"] == "cancelled"
    assert db.query(Transaction).count() == 0
    assert db.get(Reservation, reservation.id).total_amount == Decimal("1000.00")

    retry = client.post(
        f"/api/reservations/cancellation-reviews/{review_id}/decision",
        json={"decision": "approve", "reason": "Se confirma la penalidad del plan"},
    )
    assert retry.status_code == 200
    assert retry.json()["cancellation_review"]["id"] == review_id
    assert db.query(Transaction).count() == 0


def test_manager_rejection_leaves_reservation_active(cancellation_client, monkeypatch):
    client, db, ctx = cancellation_client
    _set_now(monkeypatch, datetime(2026, 11, 30, 20, tzinfo=timezone.utc))
    reservation, _category, _room = _seed_reservation(db)
    requested = client.post(f"/api/reservations/{reservation.id}/cancel")
    review_id = requested.json()["cancellation_review"]["id"]
    ctx.update(role="manager", user_id=11)

    response = client.post(
        f"/api/reservations/cancellation-reviews/{review_id}/decision",
        json={"decision": "reject", "reason": "No corresponde aplicar el cargo"},
    )

    assert response.status_code == 200
    assert response.json()["cancellation_review"]["status"] == "rejected"
    assert response.json()["reservation"]["status"] == "pending"
    assert db.query(Transaction).count() == 0


def test_receptionist_cannot_read_or_resolve_review_and_other_tenant_cannot_resolve(cancellation_client, monkeypatch):
    client, db, ctx = cancellation_client
    _set_now(monkeypatch, datetime(2026, 11, 30, 20, tzinfo=timezone.utc))
    reservation, _category, _room = _seed_reservation(db)
    requested = client.post(f"/api/reservations/{reservation.id}/cancel")
    review_id = requested.json()["cancellation_review"]["id"]

    assert client.get("/api/reservations/cancellation-reviews/pending").status_code == 403
    ctx.update(role="manager", user_id=11, hotel_id=2)
    assert client.get("/api/reservations/cancellation-reviews/pending").json() == []
    foreign_resolution = client.post(
        f"/api/reservations/cancellation-reviews/{review_id}/decision",
        json={"decision": "approve", "reason": "No debe cruzar hoteles"},
    )
    assert foreign_resolution.status_code == 404
    assert db.get(Reservation, reservation.id).status == ReservationStatusEnum.PENDING


def test_historical_reservation_requires_review_and_approval_does_not_apply_current_policy(cancellation_client, monkeypatch):
    client, db, ctx = cancellation_client
    _set_now(monkeypatch, datetime(2026, 11, 30, 20, tzinfo=timezone.utc))
    reservation, _category, _room = _seed_reservation(db, snapshot=None)

    request = client.post(f"/api/reservations/{reservation.id}/cancel")
    assert request.status_code == 200
    review = request.json()["cancellation_review"]
    assert request.json()["cancellation_outcome"] == "manager_review_required"
    assert review["review_type"] == "historical_policy_missing"
    assert review["penalty_amount"] is None
    assert db.get(Reservation, reservation.id).status == ReservationStatusEnum.PENDING

    ctx.update(role="manager", user_id=11)
    approved = client.post(
        f"/api/reservations/cancellation-reviews/{review['id']}/decision",
        json={"decision": "approve", "reason": "Se autoriza cancelar sin cargo"},
    )
    assert approved.status_code == 200
    assert approved.json()["reservation"]["status"] == "cancelled"
    assert approved.json()["cancellation_review"]["penalty_amount"] is None
    assert db.query(Transaction).count() == 0


def test_free_window_cancels_without_review(cancellation_client, monkeypatch):
    client, db, _ctx = cancellation_client
    _set_now(monkeypatch, datetime(2026, 11, 30, 17, tzinfo=timezone.utc))
    reservation, _category, _room = _seed_reservation(db)

    response = client.post(f"/api/reservations/{reservation.id}/cancel")

    assert response.status_code == 200
    assert response.json()["cancellation_outcome"] == "cancelled"
    assert response.json()["cancellation_review"] is None
    assert db.get(Reservation, reservation.id).status == ReservationStatusEnum.CANCELLED
    assert db.query(ReservationCancellationReview).count() == 0
    assert db.query(Transaction).count() == 0


def test_missing_hotel_checkin_time_blocks_cancellation(cancellation_client, monkeypatch):
    client, db, _ctx = cancellation_client
    _set_now(monkeypatch, datetime(2026, 11, 30, 20, tzinfo=timezone.utc))
    reservation, _category, _room = _seed_reservation(db, check_in_time=None)

    response = client.post(f"/api/reservations/{reservation.id}/cancel")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "check_in_schedule_not_configured"
    assert db.get(Reservation, reservation.id).status == ReservationStatusEnum.PENDING
    assert db.query(ReservationCancellationReview).count() == 0


def test_cancellation_review_migration_creates_tenant_table_and_seeds_roles_without_overwriting_overrides():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20261025_reservation_cancellation_review.py"
    )
    spec = importlib.util.spec_from_file_location("reservation_cancellation_review_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE hotel_configuration (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            connection.execute(
                text(
                    "CREATE TABLE reservations (id INTEGER PRIMARY KEY, hotel_id INTEGER NOT NULL, "
                    "UNIQUE(hotel_id, id))"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE permissions (code TEXT PRIMARY KEY, description TEXT NOT NULL, "
                    "critical BOOLEAN NOT NULL, step_up_required BOOLEAN NOT NULL, delegable BOOLEAN NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE role_permission_defaults (role TEXT NOT NULL, permission_code TEXT NOT NULL, "
                    "allowed BOOLEAN NOT NULL, UNIQUE(role, permission_code))"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE hotel_permission_overrides (hotel_id INTEGER NOT NULL, role TEXT NOT NULL, "
                    "permission_code TEXT NOT NULL, allowed BOOLEAN NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO permissions (code, description, critical, step_up_required, delegable) "
                    "VALUES ('reservation:cancel_penalty_approve', 'custom description', 0, 0, 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO role_permission_defaults (role, permission_code, allowed) "
                    "VALUES ('receptionist', 'reservation:cancel_penalty_approve', 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO hotel_permission_overrides (hotel_id, role, permission_code, allowed) "
                    "VALUES (1, 'receptionist', 'reservation:cancel_penalty_approve', 0)"
                )
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()

            assert "reservation_cancellation_reviews" in inspect(connection).get_table_names()
            assert connection.execute(
                text("SELECT description FROM permissions WHERE code='reservation:cancel_penalty_approve'")
            ).scalar_one() == "custom description"
            defaults = dict(
                connection.execute(
                    text(
                        "SELECT role, allowed FROM role_permission_defaults "
                        "WHERE permission_code='reservation:cancel_penalty_approve'"
                    )
                ).all()
            )
            assert defaults == {
                "owner": 1,
                "co_owner": 1,
                "manager": 1,
                "receptionist": 1,
                "housekeeping": 0,
            }
            dirty_defaults = dict(
                connection.execute(
                    text(
                        "SELECT role, allowed FROM role_permission_defaults "
                        "WHERE permission_code='reservation:room_dirty_override'"
                    )
                ).all()
            )
            assert dirty_defaults == {
                "owner": 1,
                "co_owner": 1,
                "manager": 1,
                "receptionist": 0,
                "housekeeping": 0,
            }
            assert connection.execute(
                text(
                    "SELECT critical = 0 AND step_up_required = 0 AND delegable = 1 "
                    "FROM permissions WHERE code='reservation:room_dirty_override'"
                )
            ).scalar_one() == 1
            assert connection.execute(
                text(
                    "SELECT allowed FROM hotel_permission_overrides "
                    "WHERE hotel_id=1 AND role='receptionist' AND permission_code='reservation:cancel_penalty_approve'"
                )
            ).scalar_one() == 0

        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            assert "reservation_cancellation_reviews" not in inspect(connection).get_table_names()
            assert connection.execute(
                text("SELECT count(*) FROM permissions WHERE code='reservation:cancel_penalty_approve'")
            ).scalar_one() == 1
    finally:
        engine.dispose()
