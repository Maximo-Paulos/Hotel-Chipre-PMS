from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.hotel_membership import HotelMembership
from app.models.operations import BillingAdjustment
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.operational_task import (
    OperationalTaskPriorityEnum,
    OperationalTaskStatusEnum,
    OperationalTaskTypeEnum,
)
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.models.user import User
from app.api import reservations as reservation_api
from app.services import payment_link_service
from app.services.collaboration import editable_resource_values, resource_revision
from app.services.operational_task_service import create_task
from app.services.permission_service import seed_default_permissions
from app.services.row_locks import lock_query
from app.services import company_night_charge_service


def test_lock_query_targets_reservations_in_postgresql_sql():
    engine = create_engine("sqlite://")
    try:
        with Session(engine) as session:
            query = lock_query(session.query(Reservation).filter(Reservation.id == 1), Reservation)
            sql = str(query.statement.compile(dialect=postgresql.dialect()))

        assert "LEFT OUTER JOIN" in sql
        assert "FOR UPDATE OF reservations" in sql
    finally:
        engine.dispose()


def test_company_night_charge_reservation_lock_targets_only_reservation():
    """Reservation has nullable joined relations, so payment locks must name the row."""
    engine = create_engine("sqlite://")
    try:
        with Session(engine) as session:
            query = lock_query(
                session.query(Reservation).filter(
                    Reservation.id == 1,
                    Reservation.hotel_id == 1,
                    Reservation.deleted_at.is_(None),
                ),
                Reservation,
            )
            sql = str(query.statement.compile(dialect=postgresql.dialect()))

        assert "LEFT OUTER JOIN" in sql
        assert "FOR UPDATE OF reservations" in sql
    finally:
        engine.dispose()


def test_company_night_charge_billing_adjustment_lock_targets_only_adjustment():
    """BillingAdjustment also eager-loads optional relations used by night-charge corrections."""
    engine = create_engine("sqlite://")
    try:
        with Session(engine) as session:
            query = lock_query(
                session.query(BillingAdjustment).filter(
                    BillingAdjustment.id == 1,
                    BillingAdjustment.hotel_id == 1,
                ),
                BillingAdjustment,
            )
            sql = str(query.statement.compile(dialect=postgresql.dialect()))

        assert "LEFT OUTER JOIN" in sql
        assert "FOR UPDATE OF billing_adjustments" in sql
    finally:
        engine.dispose()


def test_company_night_charge_payment_path_uses_reservation_lock_target(monkeypatch):
    """The payment helper must lock the reservation despite joined optional relations."""
    engine = create_engine("sqlite://")
    captured: dict[str, str] = {}
    original_lock_query = company_night_charge_service.lock_query

    def capture_lock_target(query, model):
        locked_query = original_lock_query(query, model)
        captured[model.__tablename__] = str(
            locked_query.statement.compile(dialect=postgresql.dialect())
        )
        return locked_query

    monkeypatch.setattr(company_night_charge_service, "lock_query", capture_lock_target)

    try:
        with Session(engine) as session:
            class StopBeforeDatabaseExecution(Exception):
                pass

            def capture_orm_statement(state):
                captured["executed"] = str(state.statement.compile(dialect=postgresql.dialect()))
                raise StopBeforeDatabaseExecution

            event.listen(session, "do_orm_execute", capture_orm_statement)
            with pytest.raises(StopBeforeDatabaseExecution):
                company_night_charge_service.prepare_company_night_charge_payment(
                    session,
                    hotel_id=1,
                    reservation_id=1,
                    amount=Decimal("1.00"),
                    charge_ids=[],
                    idempotency_key=None,
                )

        sql = captured["reservations"]
        assert "LEFT OUTER JOIN" in sql
        assert "FOR UPDATE OF reservations" in sql
        assert "LEFT OUTER JOIN" in captured["executed"]
        assert "FOR UPDATE OF reservations" in captured["executed"]
    finally:
        engine.dispose()


def test_lock_query_executes_on_postgres_with_joined_eager_loads(pg_session):
    reservations = lock_query(pg_session.query(Reservation), Reservation).limit(1).all()

    assert reservations == []


def test_room_move_handler_executes_on_postgres_with_joined_reservation_relations(pg_session, monkeypatch):
    hotel = HotelConfiguration(id=901, hotel_name="Synthetic PostgreSQL Room Move")
    category = RoomCategory(
        hotel_id=901,
        name="PG Standard",
        code="PG_STD",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(hotel_id=901, first_name="Synthetic", last_name="Guest")
    user = User(
        email="pg-room-move@example.test",
        password_hash="test-only-hash",
        is_active=True,
        is_verified=True,
    )
    pg_session.add(hotel)
    pg_session.flush()
    pg_session.add(category)
    pg_session.add(user)
    pg_session.flush()
    pg_session.add(guest)
    pg_session.flush()
    seed_default_permissions(pg_session)

    origin = Room(hotel_id=901, room_number="PG101", floor=1, category_id=category.id)
    destination = Room(hotel_id=901, room_number="PG102", floor=1, category_id=category.id)
    pg_session.add_all([origin, destination])
    pg_session.flush()
    reservation = Reservation(
        hotel_id=901,
        confirmation_code="PG16-ROOM-MOVE-001",
        guest_id=guest.id,
        room_id=origin.id,
        category_id=category.id,
        check_in_date=date(2026, 10, 1),
        check_out_date=date(2026, 10, 3),
        total_amount=200,
        subtotal_amount=200,
        net_amount=200,
        amount_paid=0,
        deposit_amount=0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
    )
    pg_session.add(reservation)
    pg_session.flush()

    monkeypatch.setattr(reservation_api, "_project_reservation_graph", lambda *_args: None)
    monkeypatch.setattr(reservation_api, "project_room_movement", lambda *_args: None)
    monkeypatch.setattr(reservation_api, "_trigger_reoptimization_bg", lambda *_args, **_kwargs: None)

    def override_get_db():
        yield pg_session

    def override_auth_context():
        return AuthContext(
            hotel_id=901,
            user_id=user.id,
            user_email=user.email,
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    monkeypatch.setitem(fastapi_app.dependency_overrides, get_db, override_get_db)
    monkeypatch.setitem(fastapi_app.dependency_overrides, get_auth_context, override_auth_context)
    response = TestClient(fastapi_app).post(
        f"/api/reservations/{reservation.id}/room-move",
        json={
            "client_version": reservation.version,
            "to_room_id": destination.id,
            "reason_code": "operational",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["reservation"]["room_id"] == destination.id
    assert response.json()["price_action"] == "keep"
    pg_session.refresh(reservation)
    assert reservation.room_id == destination.id


def test_reservation_and_task_mutation_routes_execute_on_postgres_with_joined_relations(pg_session, monkeypatch):
    hotel_id = 902
    hotel = HotelConfiguration(id=hotel_id, hotel_name="Synthetic PostgreSQL Row Lock Flows")
    category = RoomCategory(
        hotel_id=hotel_id,
        name="PG Operations",
        code="PG_OPS",
        base_price_per_night=100,
        max_occupancy=2,
    )
    owner = User(
        email="pg-row-lock-owner@example.test",
        password_hash="test-only-hash",
        is_active=True,
        is_verified=True,
    )
    housekeeper = User(
        email="pg-row-lock-housekeeper@example.test",
        password_hash="test-only-hash",
        is_active=True,
        is_verified=True,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Operations")
    pg_session.add(hotel)
    pg_session.flush()
    pg_session.add_all([category, owner, housekeeper, guest])
    pg_session.flush()
    pg_session.add_all([
        HotelMembership(hotel_id=hotel_id, user_id=owner.id, role="owner", status="active"),
        HotelMembership(hotel_id=hotel_id, user_id=housekeeper.id, role="housekeeping", status="active"),
    ])
    seed_default_permissions(pg_session)
    pg_session.flush()

    room = Room(hotel_id=hotel_id, room_number="PG201", floor=2, category_id=category.id)
    pg_session.add(room)
    pg_session.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code="PG16-ROW-LOCK-FLOWS-001",
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date(2026, 10, 1),
        check_out_date=date(2026, 10, 3),
        total_amount=200,
        subtotal_amount=200,
        net_amount=200,
        amount_paid=0,
        deposit_amount=0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
    )
    pg_session.add(reservation)
    pg_session.flush()
    extension_reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code="PG16-ROW-LOCK-FLOWS-002",
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date(2026, 10, 5),
        check_out_date=date(2026, 10, 7),
        total_amount=200,
        subtotal_amount=200,
        net_amount=200,
        amount_paid=200,
        deposit_amount=0,
        currency_code="ARS",
        status=ReservationStatusEnum.FULLY_PAID,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
    )
    no_show_reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code="PG16-ROW-LOCK-FLOWS-003",
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date(2026, 10, 8),
        check_out_date=date(2026, 10, 10),
        total_amount=200,
        subtotal_amount=200,
        net_amount=200,
        amount_paid=0,
        deposit_amount=0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
    )
    pg_session.add_all([extension_reservation, no_show_reservation])
    pg_session.flush()
    task = create_task(
        pg_session,
        hotel_id=hotel_id,
        task_type=OperationalTaskTypeEnum.HOUSEKEEPING,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Preparar habitación PG201",
        room_id=room.id,
        assigned_to_user_id=housekeeper.id,
        created_by_user_id=owner.id,
    )

    actor = {
        "context": AuthContext(
            hotel_id=hotel_id,
            user_id=owner.id,
            user_email=owner.email,
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )
    }

    def override_get_db():
        yield pg_session

    def override_auth_context():
        return actor["context"]

    monkeypatch.setitem(fastapi_app.dependency_overrides, get_db, override_get_db)
    monkeypatch.setitem(fastapi_app.dependency_overrides, get_auth_context, override_auth_context)
    monkeypatch.setattr(reservation_api, "_trigger_reoptimization_bg", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(payment_link_service, "external_connections_enabled", lambda: False)
    client = TestClient(fastapi_app)

    base_values = editable_resource_values("reservation", reservation)
    edit = client.patch(
        f"/api/collaboration/resources/reservation/{reservation.id}",
        json={
            "base_revision": resource_revision(base_values),
            "base_values": base_values,
            "changes": {"reservation_comment": "Actualizada con PostgreSQL"},
        },
    )
    assert edit.status_code == 200, edit.text
    pg_session.refresh(reservation)
    assert reservation.reservation_comment == "Actualizada con PostgreSQL"

    cancel = client.post(f"/api/reservations/{reservation.id}/cancel")
    assert cancel.status_code == 200, cancel.text
    pg_session.refresh(reservation)
    assert reservation.status == ReservationStatusEnum.CANCELLED

    extension = client.post(
        f"/api/reservations/{extension_reservation.id}/extend",
        json={
            "new_checkout_date": "2026-10-08",
            "client_version": 0,
            "pricing_mode": "original_average",
            "payment_action": "payment_link",
            "payment_link": {
                "reservation_id": extension_reservation.id,
                "requested_amount": "100.00",
                "recipient_email": "synthetic-guest@example.com",
                "currency": "ARS",
            },
        },
    )
    assert extension.status_code == 200, extension.text
    assert extension.json()["reservation"]["check_out_date"] == "2026-10-08"
    assert extension.json()["payment_link"]["execution_mode"] == "local_only"

    no_show = client.post(
        f"/api/reservations/{no_show_reservation.id}/noshow",
        json={"client_version": 0, "notes": "No llegó"},
    )
    assert no_show.status_code == 200, no_show.text
    assert no_show.json()["status"] == ReservationStatusEnum.NO_SHOW.value

    actor["context"] = AuthContext(
        hotel_id=hotel_id,
        user_id=housekeeper.id,
        user_email=housekeeper.email,
        user_role="housekeeping",
        base_role="housekeeping",
        is_verified=True,
        permissions=set(),
    )
    take = client.patch(
        f"/api/operational-tasks/{task.id}",
        json={
            "client_version": 0,
            "status": OperationalTaskStatusEnum.IN_PROGRESS.value,
            "comment": "Tomada por limpieza",
        },
    )
    assert take.status_code == 200, take.text
    assert take.json()["status"] == OperationalTaskStatusEnum.IN_PROGRESS.value

    history = client.get(f"/api/operational-tasks/{task.id}/history")
    assert history.status_code == 200, history.text
    assert history.json()[-1]["to_status"] == OperationalTaskStatusEnum.IN_PROGRESS.value

    comment = client.patch(
        f"/api/operational-tasks/{task.id}",
        json={
            "client_version": take.json()["version"],
            "comment": "Reposición completada; revisar disponibilidad.",
        },
    )
    assert comment.status_code == 200, comment.text
    assert comment.json()["status"] == OperationalTaskStatusEnum.IN_PROGRESS.value

    review = client.patch(
        f"/api/operational-tasks/{task.id}",
        json={
            "client_version": comment.json()["version"],
            "status": OperationalTaskStatusEnum.PENDING_REVIEW.value,
        },
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == OperationalTaskStatusEnum.PENDING_REVIEW.value

    actor["context"] = AuthContext(
        hotel_id=hotel_id,
        user_id=owner.id,
        user_email=owner.email,
        user_role="owner",
        base_role="owner",
        is_verified=True,
        permissions=set(),
    )
    resolved = client.post(
        f"/api/operational-tasks/{task.id}/resolve",
        json={"client_version": review.json()["version"]},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == OperationalTaskStatusEnum.RESOLVED.value

    final_history = client.get(f"/api/operational-tasks/{task.id}/history")
    assert final_history.status_code == 200, final_history.text
    assert any(
        event["comment"] == "Reposición completada; revisar disponibilidad."
        for event in final_history.json()
    )
    assert final_history.json()[-1]["to_status"] == OperationalTaskStatusEnum.RESOLVED.value
