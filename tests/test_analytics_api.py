from __future__ import annotations

import asyncio
import csv
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
import json
import xml.etree.ElementTree as ET
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.config import Settings
from app.models.analytics import (
    AnalyticsAIUsageMonthly,
    AnalyticsCurrencyDisplayEnum,
    AnalyticsExportFormatEnum,
    AnalyticsExportJob,
    AnalyticsExportStatusEnum,
    FactReservationDaily,
    FactRoomOccupancyDaily,
    HotelAuditEvent,
    RoomStateEvent,
    RoomStateEventReasonCodeEnum,
    RoomStateEventTypeEnum,
)
from app.models.company import Company
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.permission import Permission, UserPermissionOverride
from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationNoShowPolicyAppliedEnum,
    ReservationOutcomeEnum,
    ReservationStatusEnum,
    ReservationSourceEnum,
)
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.schemas.analytics import AnalyticsComparisonStateRead, AnalyticsComparisonWindowRead
from app.schemas.analytics_api import AnalyticsExportRequest
from app.services.analytics_facts import refresh_fact_reservation_daily, refresh_fact_room_occupancy_daily
from app.services.analytics_exports import (
    _build_xlsx_bytes,
    _build_xlsx_spool,
    _flatten_payload_rows,
    _png_export_content,
    _sheet_xml_from_table,
    create_xlsx_export_job,
    generate_xlsx_export_job,
    iter_export_file_chunks,
    prepare_xlsx_export_jobs_for_recovery,
)
from app.services.object_storage import LocalObjectStorage
from app.services.security import create_access_token, hash_password
from app.services.permission_service import PERMISSION_COMPANY_VIEW
from app.services.analytics_service import _analytics_window


def assert_freshness_metadata(payload: dict) -> None:
    assert payload["data_source"] in {"postgresql", "clickhouse"}
    if payload["data_as_of"] is None:
        assert payload["source_lag_seconds"] is None
    else:
        assert payload["source_lag_seconds"] >= 0


def _wait_for_xlsx_completion(client, job_id: int, headers: dict, *, timeout_seconds: float = 5.0) -> dict:
    # The fixture uses an in-memory SQLite StaticPool, which shares one DB
    # connection across threads. Wait for its background worker before issuing
    # another request so the test does not race two sessions on that connection.
    queue = getattr(client.app.state, "analytics_export_queue", None)
    loop = getattr(client.app.state, "analytics_export_loop", None)
    if queue is not None and loop is not None and not loop.is_closed():
        asyncio.run_coroutine_threadsafe(queue.join(), loop).result(timeout=timeout_seconds)
    response = client.get(f"/api/analytics/exports/{job_id}", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "completed", (
        f"XLSX job {job_id} ended as {result['status']}: "
        f"{result.get('error_code')} {result.get('error_message')}"
    )
    return result


def test_xlsx_worker_serializes_exports(monkeypatch):
    import threading
    import time

    import app.services.analytics_exports as exports_module

    active_jobs = 0
    max_active_jobs = 0
    completed_jobs: list[tuple[int, int]] = []
    state_lock = threading.Lock()

    def record_export(job_id: int, hotel_id: int) -> None:
        nonlocal active_jobs, max_active_jobs
        with state_lock:
            active_jobs += 1
            max_active_jobs = max(max_active_jobs, active_jobs)
        time.sleep(0.02)
        with state_lock:
            completed_jobs.append((job_id, hotel_id))
            active_jobs -= 1

    monkeypatch.setattr(exports_module, "generate_xlsx_export_job", record_export)

    async def consume_three_jobs():
        queue: asyncio.Queue[tuple[int, int] | None] = asyncio.Queue()
        for job in ((1, 8), (2, 8), (3, 9)):
            queue.put_nowait(job)
        queue.put_nowait(None)
        await main_module._consume_xlsx_export_queue(queue)
        assert queue.empty()

    asyncio.run(consume_three_jobs())

    assert completed_jobs == [(1, 8), (2, 8), (3, 9)]
    assert max_active_jobs == 1


def test_analytics_export_window_does_not_truncate_historical_dates():
    request = AnalyticsExportRequest(
        date_from=date(1900, 1, 1),
        date_to=date(2100, 12, 31),
        compare_previous=False,
        compare_yoy=False,
    )

    window = _analytics_window(
        None,
        1,
        date_from=request.date_from,
        date_to=request.date_to,
        compare_previous=request.compare_previous,
        compare_yoy=request.compare_yoy,
    )

    assert window.date_from == date(1900, 1, 1)
    assert window.date_to == date(2100, 12, 31)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    plan_state = {"plan": "starter"}

    import app.services.analytics_service as analytics_service_module

    monkeypatch.setattr(
        analytics_service_module,
        "get_subscription_snapshot",
        lambda db, hotel_id: {"plan": plan_state["plan"], "status": "active", "can_write": True, "enforcement_enabled": True},
    )

    with SessionLocal() as db:
        if not db.get(HotelConfiguration, 1):
            db.add(
                HotelConfiguration(
                    id=1,
                    owner_email="owner@test.com",
                    hotel_name="Hotel Analytics",
                    hotel_timezone="America/Argentina/Buenos_Aires",
                    subscription_active=True,
                )
            )
            db.flush()
        user = db.query(User).filter(User.email == "owner@test.com").first()
        if not user:
            user = User(
                email="owner@test.com",
                password_hash=hash_password("Secret123!"),
                role="owner",
                is_verified=True,
                is_active=True,
            )
            db.add(user)
            db.flush()
        if not db.query(HotelMembership).filter(HotelMembership.hotel_id == 1, HotelMembership.user_id == user.id).first():
            db.add(HotelMembership(hotel_id=1, user_id=user.id, role="owner", status="active"))
            db.flush()
        token = create_access_token(
            subject=user.id,
            extra={
                "email": user.email,
                "role": "owner",
                "verified": True,
                "hotel_id": 1,
                "hotel_ids": [1],
            },
        )
        headers = {"Authorization": f"Bearer {token}", "X-Hotel-Id": "1"}
        db.commit()

    with TestClient(main_module.app) as client:
        yield client, SessionLocal, headers, plan_state

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_analytics_data(SessionLocal):
    with SessionLocal() as db:
        hotel = db.get(HotelConfiguration, 1)
        if not hotel:
            raise RuntimeError("hotel missing")
        category = db.query(RoomCategory).filter(RoomCategory.hotel_id == 1, RoomCategory.code == "STD").first()
        if not category:
            category = RoomCategory(
                hotel_id=1,
                name="Standard",
                code="STD",
                description="Standard room",
                base_price_per_night=100.0,
                variable_cost_per_night=12.50,
                max_occupancy=2,
            )
            db.add(category)
            db.flush()
        room = db.query(Room).filter(Room.hotel_id == 1, Room.room_number == "101").first()
        if not room:
            room = Room(
                hotel_id=1,
                room_number="101",
                floor=1,
                category_id=category.id,
                status=RoomStatusEnum.AVAILABLE,
                is_active=True,
            )
            db.add(room)
            db.flush()
        company = db.query(Company).filter(Company.hotel_id == 1, Company.display_name == "Acme").first()
        if not company:
            company = Company(
                hotel_id=1,
                legal_name="Acme SRL",
                display_name="Acme",
                tax_id="30-12345678-9",
                country_code="AR",
            )
            db.add(company)
            db.flush()
        guest = db.query(User).filter(User.email == "guest-seed@test.com").first()
        if not guest:
            pass
        from app.models.guest import Guest

        guest_obj = db.query(Guest).filter(Guest.hotel_id == 1, Guest.email == "guest@acme.test").first()
        if not guest_obj:
            guest_obj = Guest(
                hotel_id=1,
                first_name="Ana",
                last_name="Paz",
                email="guest@acme.test",
                terms_accepted=True,
            )
            db.add(guest_obj)
            db.flush()

        reservation = db.query(Reservation).filter(Reservation.hotel_id == 1, Reservation.confirmation_code == "RES-001").first()
        if not reservation:
            reservation = Reservation(
                confirmation_code="RES-001",
                hotel_id=1,
                guest_id=guest_obj.id,
                room_id=room.id,
                category_id=category.id,
                company_id=company.id,
                check_in_date=date(2026, 4, 1),
                check_out_date=date(2026, 4, 3),
                total_amount=200.0,
                subtotal_amount=180.0,
                tax_amount=20.0,
                fee_amount=5.0,
                commission_amount=10.0,
                net_amount=165.0,
                amount_paid=200.0,
                deposit_amount=60.0,
                currency_code="ARS",
                status=ReservationStatusEnum.FULLY_PAID,
                outcome=ReservationOutcomeEnum.PENDING,
                source=ReservationSourceEnum.BOOKING,
                source_provider_code="booking",
                channel_code=ReservationChannelCodeEnum.BOOKING,
                guest_segment=ReservationGuestSegmentEnum.LEISURE,
                guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
                no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.NONE,
                num_adults=2,
                num_children=0,
            )
            db.add(reservation)
            db.flush()

        no_show = db.query(Reservation).filter(Reservation.hotel_id == 1, Reservation.confirmation_code == "RES-NS").first()
        if not no_show:
            no_show = Reservation(
                confirmation_code="RES-NS",
                hotel_id=1,
                guest_id=guest_obj.id,
                room_id=room.id,
                category_id=category.id,
                company_id=company.id,
                check_in_date=date(2026, 4, 4),
                check_out_date=date(2026, 4, 5),
                total_amount=120.0,
                subtotal_amount=110.0,
                tax_amount=10.0,
                fee_amount=3.0,
                commission_amount=6.0,
                net_amount=101.0,
                amount_paid=0.0,
                deposit_amount=0.0,
                currency_code="ARS",
                status=ReservationStatusEnum.NO_SHOW,
                outcome=ReservationOutcomeEnum.NO_SHOW,
                source=ReservationSourceEnum.DIRECT,
                channel_code=ReservationChannelCodeEnum.OTHER_DIRECT,
                guest_segment=ReservationGuestSegmentEnum.LEISURE,
                guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
                no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.FULL_CHARGE,
                num_adults=2,
                num_children=0,
            )
            db.add(no_show)
            db.flush()

        event = db.query(RoomStateEvent).filter(RoomStateEvent.hotel_id == 1, RoomStateEvent.room_id == room.id).first()
        if not event:
            db.add(
                RoomStateEvent(
                    hotel_id=1,
                    room_id=room.id,
                    event_type=RoomStateEventTypeEnum.MAINTENANCE,
                    reason_code=RoomStateEventReasonCodeEnum.INSPECTION,
                    reason_note="Inspection programada",
                    started_at=datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc),
                    ended_at=datetime(2026, 4, 3, 0, 0, tzinfo=timezone.utc),
                    created_by_user_id=1,
                )
            )

        refresh_fact_reservation_daily(db, hotel_id=1, date_from=date(2026, 4, 1), date_to=date(2026, 4, 5))
        refresh_fact_room_occupancy_daily(db, hotel_id=1, date_from=date(2026, 4, 1), date_to=date(2026, 4, 5))
        db.commit()


def test_starter_summary_and_plan_gate(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)

    starter = client.get("/api/analytics/starter-summary", params={"date_from": "2026-04-01", "date_to": "2026-04-05"}, headers=headers)
    assert starter.status_code == 200, starter.text
    starter_payload = starter.json()
    assert starter_payload["hotel_id"] == 1
    assert len(starter_payload["data"]["cards"]) == 3
    assert_freshness_metadata(starter_payload)

    channels = client.get(
        "/api/analytics/channels",
        params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert channels.status_code == 200, channels.text
    assert "channels" in channels.json()["data"]
    assert_freshness_metadata(channels.json())

    segments = client.get(
        "/api/analytics/segments",
        params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert segments.status_code == 200, segments.text
    assert "segments" in segments.json()["data"]
    assert_freshness_metadata(segments.json())

    blocked = client.get("/api/analytics/home", params={"date_from": "2026-04-01", "date_to": "2026-04-05"}, headers=headers)
    assert blocked.status_code == 402, blocked.text

    plan_state["plan"] = "pro"

    home = client.get("/api/analytics/home", params={"date_from": "2026-04-01", "date_to": "2026-04-05"}, headers=headers)
    assert home.status_code == 200, home.text
    payload = home.json()
    assert payload["comparison"]["previous"]["requested"] is True
    assert "cards" in payload["data"]
    assert len(payload["data"]["cards"]) >= 4
    assert_freshness_metadata(payload)


def test_company_crud_and_analytics_detail(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)

    plan_state["plan"] = "pro"

    create = client.post(
        "/api/companies",
        json={
            "legal_name": "Globex SRL",
            "display_name": "Globex",
            "tax_id": "30-99999999-9",
            "country_code": "ar",
            "notes": "Corporate account",
        },
        headers=headers,
    )
    assert create.status_code == 201, create.text
    company_id = create.json()["id"]

    fetched = client.get(f"/api/companies/{company_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["display_name"] == "Globex"

    patched = client.patch(f"/api/companies/{company_id}", json={"display_name": "Globex Travel"}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Globex Travel"

    analytic_detail = client.get(
        f"/api/analytics/companies/{company_id}",
        params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert analytic_detail.status_code == 200, analytic_detail.text
    detail_payload = analytic_detail.json()
    assert detail_payload["data"]["company"]["display_name"] == "Globex Travel"
    assert detail_payload["data"]["cards"][0]["card_code"] == "company_nights"
    assert_freshness_metadata(detail_payload)

    deactivated = client.post(f"/api/companies/{company_id}/deactivate", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    reactivated = client.post(f"/api/companies/{company_id}/reactivate", headers=headers)
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True

    with SessionLocal() as db:
        action_codes = [row.action_code for row in db.query(HotelAuditEvent).filter(HotelAuditEvent.hotel_id == 1).order_by(HotelAuditEvent.id.asc())]
    assert "analytics.company.created" in action_codes
    assert "analytics.company.updated" in action_codes
    assert "analytics.company.deactivated" in action_codes
    assert "analytics.company.reactivated" in action_codes


def test_company_detail_and_exports_only_include_reservations_overlapping_the_selected_window(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    plan_state["plan"] = "pro"

    date_from = date(2026, 4, 10)
    date_to = date(2026, 4, 12)
    expected_codes = {"RANGE-START", "RANGE-IN", "RANGE-END"}
    excluded_codes = {"RANGE-BEFORE", "RANGE-CHECKOUT", "RANGE-AFTER"}

    with SessionLocal() as db:
        company = db.query(Company).filter_by(hotel_id=1, display_name="Acme").one()
        template = db.query(Reservation).filter_by(hotel_id=1, confirmation_code="RES-001").one()
        cases = [
            ("RANGE-BEFORE", date(2026, 4, 7), date(2026, 4, 9)),
            ("RANGE-CHECKOUT", date(2026, 4, 8), date_from),
            ("RANGE-START", date(2026, 4, 9), date(2026, 4, 11)),
            ("RANGE-IN", date_from, date(2026, 4, 11)),
            ("RANGE-END", date_to, date(2026, 4, 14)),
            ("RANGE-AFTER", date(2026, 4, 13), date(2026, 4, 15)),
        ]
        for code, check_in, check_out in cases:
            db.add(
                Reservation(
                    confirmation_code=code,
                    hotel_id=1,
                    guest_id=template.guest_id,
                    room_id=None,
                    category_id=template.category_id,
                    company_id=company.id,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    total_amount=0,
                    amount_paid=0,
                    currency_code="ARS",
                    status=ReservationStatusEnum.PENDING,
                    outcome=ReservationOutcomeEnum.PENDING,
                )
            )
        company_id = company.id
        db.commit()

    detail = client.get(
        f"/api/analytics/companies/{company_id}",
        params={"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    detail_codes = {row["confirmation_code"] for row in detail.json()["data"]["reservations"]}
    assert expected_codes <= detail_codes
    assert not (excluded_codes & detail_codes)

    export = client.post(
        "/api/analytics/exports/csv",
        json={
            "entity_code": "company",
            "company_id": company_id,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "compare_previous": False,
            "compare_yoy": False,
        },
        headers=headers,
    )
    assert export.status_code == 200, export.text
    rows = csv.reader(export.text.splitlines())
    export_codes = {
        row[2]
        for row in rows
        if len(row) == 3 and row[0].startswith("reservations[") and row[1] == "confirmation_code"
    }
    assert expected_codes <= export_codes
    assert not (excluded_codes & export_codes)


def test_streamed_detail_exports_match_materialized_payloads(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)

    from app.services.analytics_exports import _build_payload_for_request, _iter_export_payload_rows
    from app.services.analytics_exports import build_export_payload

    with SessionLocal() as db:
        room_id = db.query(Room.id).filter_by(hotel_id=1, room_number="101").scalar()
        category_id = db.query(RoomCategory.id).filter_by(hotel_id=1, code="STD").scalar()
        company_id = db.query(Company.id).filter_by(hotel_id=1, display_name="Acme").scalar()

        requests = [
            AnalyticsExportRequest(
                entity_code="room", room_id=room_id,
                date_from=date(2026, 4, 1), date_to=date(2026, 4, 5),
                compare_previous=False, compare_yoy=False,
            ),
            AnalyticsExportRequest(
                entity_code="category", category_id=category_id,
                date_from=date(2026, 4, 1), date_to=date(2026, 4, 5),
                compare_previous=False, compare_yoy=False,
            ),
            AnalyticsExportRequest(
                entity_code="company", company_id=company_id,
                date_from=date(2026, 4, 1), date_to=date(2026, 4, 5),
                compare_previous=False, compare_yoy=False,
            ),
            AnalyticsExportRequest(
                entity_code="operations",
                date_from=date(2026, 4, 1), date_to=date(2026, 4, 5),
                compare_previous=False, compare_yoy=False,
            ),
        ]

        for request in requests:
            expected = build_export_payload(db, hotel_id=1, request=request)
            streamed = _build_payload_for_request(db, hotel_id=1, request=request, stream_details=True)
            expected["generated_at"] = streamed["generated_at"]
            assert list(_iter_export_payload_rows(streamed)) == list(_iter_export_payload_rows(expected))

            detail_sections = [
                value for key, value in streamed["data"].items()
                if key != "cards" and isinstance(value, Iterable)
            ]
            assert detail_sections
            assert all(not isinstance(section, list) for section in detail_sections)


def test_room_state_events_and_variable_cost_audit(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)

    plan_state["plan"] = "pro"
    with SessionLocal() as db:
        category = db.query(RoomCategory).filter(RoomCategory.hotel_id == 1, RoomCategory.code == "STD").first()
        room = db.query(Room).filter(Room.hotel_id == 1, Room.room_number == "101").first()
        category_id = category.id
        room_id = room.id

    event_create = client.post(
        "/api/room-state-events",
        json={
            "room_id": room_id,
            "event_type": "maintenance",
            "reason_code": "inspection",
            "reason_note": "Revisión programada",
            "started_at": "2026-04-04T10:00:00Z",
        },
        headers=headers,
    )
    assert event_create.status_code == 201, event_create.text
    event_id = event_create.json()["id"]

    close = client.post(f"/api/room-state-events/{event_id}/close", headers=headers)
    assert close.status_code == 200
    assert close.json()["ended_at"] is not None

    update_category = client.patch(
        f"/api/rooms/categories/{category_id}",
        json={"variable_cost_per_night": 18.75},
        headers=headers,
    )
    assert update_category.status_code == 200, update_category.text
    assert update_category.json()["variable_cost_per_night"] == 18.75

    room_detail = client.get(
        f"/api/analytics/rooms/{room_id}",
        params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert room_detail.status_code == 200, room_detail.text
    room_payload = room_detail.json()
    assert room_payload["data"]["room"]["room_number"] == "101"
    assert len(room_payload["data"]["events"]) >= 2
    assert_freshness_metadata(room_payload)

    with SessionLocal() as db:
        action_codes = [row.action_code for row in db.query(HotelAuditEvent).filter(HotelAuditEvent.hotel_id == 1).order_by(HotelAuditEvent.id.asc())]
    assert "analytics.room_state_event.created" in action_codes
    assert "analytics.room_state_event.closed" in action_codes
    assert "analytics.variable_cost.updated" in action_codes


def test_alert_settings_ai_config_and_breakdowns(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)

    plan_state["plan"] = "ultra"

    settings_resp = client.get("/api/analytics/alert-settings", headers=headers)
    assert settings_resp.status_code == 200, settings_resp.text
    settings_payload = settings_resp.json()
    assert settings_payload["cancellation_rate_threshold_pct"] == 15.0

    patch_resp = client.patch(
        "/api/analytics/alert-settings",
        json={"cancellation_rate_threshold_pct": 22.5},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["cancellation_rate_threshold_pct"] == 22.5

    snooze_resp = client.post(
        "/api/analytics/alerts/cancellation_rate/snooze",
        json={"scope_key": "global", "duration_code": "24h"},
        headers=headers,
    )
    assert snooze_resp.status_code == 200, snooze_resp.text
    snooze_id = snooze_resp.json()["id"]

    delete_resp = client.delete("/api/analytics/alerts/cancellation_rate/snooze", params={"scope_key": "global"}, headers=headers)
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json()["deleted"] is True

    ai_resp = client.get("/api/analytics/ai-config", headers=headers)
    assert ai_resp.status_code == 200, ai_resp.text
    ai_payload = ai_resp.json()
    assert ai_payload["hotel_id"] == 1
    assert "quota_monthly" in ai_payload

    ai_patch = client.patch("/api/analytics/ai-config", json={"analytics_ai_enabled": True}, headers=headers)
    assert ai_patch.status_code == 200, ai_patch.text
    assert ai_patch.json()["analytics_ai_enabled"] is True

    segments = client.get("/api/analytics/segments", params={"date_from": "2026-04-01", "date_to": "2026-04-05"}, headers=headers)
    assert segments.status_code == 200
    assert "segments" in segments.json()["data"]
    assert_freshness_metadata(segments.json())

    channels = client.get("/api/analytics/channels", params={"date_from": "2026-04-01", "date_to": "2026-04-05"}, headers=headers)
    assert channels.status_code == 200
    assert "channels" in channels.json()["data"]
    assert_freshness_metadata(channels.json())

    operations = client.get("/api/analytics/operations", params={"date_from": "2026-04-01", "date_to": "2026-04-05"}, headers=headers)
    assert operations.status_code == 200
    assert "room_events" in operations.json()["data"]
    assert_freshness_metadata(operations.json())

    with SessionLocal() as db:
        action_codes = [row.action_code for row in db.query(HotelAuditEvent).filter(HotelAuditEvent.hotel_id == 1).order_by(HotelAuditEvent.id.asc())]
    assert "analytics.alert_settings.updated" in action_codes
    assert "analytics.alert.snoozed" in action_codes
    assert "analytics.alert.unsnoozed" in action_codes
    assert "analytics.ai.settings.updated" in action_codes


def test_analytics_exports_png_csv_xlsx(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)

    plan_state["plan"] = "pro"
    png_resp = client.post(
        "/api/analytics/exports/png",
        json={"entity_code": "home", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert png_resp.status_code == 200, png_resp.text
    assert png_resp.headers["content-type"].startswith("image/png")
    assert png_resp.content[:8] == b"\x89PNG\r\n\x1a\n"

    csv_resp = client.post(
        "/api/analytics/exports/csv",
        json={"entity_code": "home", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert csv_resp.status_code == 200, csv_resp.text
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "section,key,value" in csv_resp.text

    with SessionLocal() as db:
        job_count_before = db.query(AnalyticsExportJob).filter(AnalyticsExportJob.hotel_id == 1).count()

    plan_state["plan"] = "ultra"

    xlsx_resp = client.post(
        "/api/analytics/exports/xlsx",
        json={"entity_code": "home", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert xlsx_resp.status_code == 201, xlsx_resp.text
    job_payload = xlsx_resp.json()
    job_id = job_payload["id"]

    completed_payload = _wait_for_xlsx_completion(client, job_id, headers)
    assert completed_payload["status"] == "completed"
    job_detail = client.get(f"/api/analytics/exports/{job_id}", headers=headers)
    assert job_detail.status_code == 200, job_detail.text
    assert job_detail.json()["entity_code"] == "home"

    download_resp = client.get(f"/api/analytics/exports/{job_id}/download", headers=headers)
    assert download_resp.status_code == 200, download_resp.text
    assert download_resp.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert download_resp.content[:2] == b"PK"
    # Downloaded bytes came back through object storage (app/services/object_storage.py),
    # not a filesystem path -- read them straight off the response instead of the disk.
    with zipfile.ZipFile(io.BytesIO(download_resp.content), "r") as archive:
        assert "xl/workbook.xml" in archive.namelist()
        assert "xl/worksheets/sheet1.xml" in archive.namelist()

    with SessionLocal() as db:
        job_count_after = db.query(AnalyticsExportJob).filter(AnalyticsExportJob.hotel_id == 1).count()
    assert job_count_after >= job_count_before


def test_analytics_breakdowns_reuse_facts_and_room_detail_filters_by_room(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    plan_state["plan"] = "pro"
    with SessionLocal() as db:
        room_id = db.query(Room.id).filter(Room.hotel_id == 1, Room.room_number == "101").scalar()
    engine = SessionLocal.kw["bind"]
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "from fact_reservation_daily" in statement.lower():
            statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        channels = client.get(
            "/api/analytics/channels",
            params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
            headers=headers,
        )
        assert channels.status_code == 200, channels.text
        assert len(statements) == 1
        assert "group by" in statements[0] and "count(distinct" in statements[0]
        statements.clear()

        segments = client.get(
            "/api/analytics/segments",
            params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
            headers=headers,
        )
        assert segments.status_code == 200, segments.text
        assert len(statements) == 1
        assert "group by" in statements[0] and "count(distinct" in statements[0]
        statements.clear()

        overview = client.get(
            "/api/analytics/rooms",
            params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
            headers=headers,
        )
        assert overview.status_code == 200, overview.text
        assert len(statements) == 1
        assert "fact_reservation_daily.room_id =" not in statements[0]
        statements.clear()

        detail = client.get(
            f"/api/analytics/rooms/{room_id}",
            params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
            headers=headers,
        )
        assert detail.status_code == 200, detail.text
        reservation_fact_queries = [
            statement for statement in statements if "from fact_reservation_daily" in statement
        ]
        assert len(reservation_fact_queries) == 1
        assert "fact_reservation_daily.room_id =" in reservation_fact_queries[0]
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_grouped_channel_and_segment_sql_matches_fact_row_aggregation(api_client):
    from app.services.analytics_service import (
        _facts_data_as_of,
        _load_reservation_facts,
        build_channels_breakdown,
        build_channels_payload,
        build_segments_breakdown,
        build_segments_payload,
    )

    _, SessionLocal, _, _ = api_client
    _seed_analytics_data(SessionLocal)
    with SessionLocal() as db:
        facts = _load_reservation_facts(db, 1, date(2026, 4, 1), date(2026, 4, 5))
        expected_segments = build_segments_breakdown(
            db,
            hotel_id=1,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
            facts=facts,
        )
        expected_channels = build_channels_breakdown(
            db,
            hotel_id=1,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
            facts=facts,
        )
        expected_data_as_of = _facts_data_as_of(facts)
        segments = build_segments_payload(
            db,
            hotel_id=1,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
        )
        channels = build_channels_payload(
            db,
            hotel_id=1,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
        )

    assert segments["data"]["segments"] == expected_segments
    assert channels["data"]["channels"] == expected_channels
    assert segments["data_as_of"] == expected_data_as_of
    assert channels["data_as_of"] == expected_data_as_of


def test_grouped_channel_and_segment_sql_preserves_currency_availability_rules(api_client):
    from app.services.analytics_service import (
        _load_reservation_facts,
        build_channels_breakdown,
        build_segments_breakdown,
    )

    _, SessionLocal, _, _ = api_client
    _seed_analytics_data(SessionLocal)
    with SessionLocal() as db:
        facts = (
            db.query(FactReservationDaily)
            .filter(FactReservationDaily.hotel_id == 1)
            .order_by(FactReservationDaily.stay_date.asc(), FactReservationDaily.id.asc())
            .all()
        )
        assert len(facts) >= 3

        # Missing FX makes the opposite currency unavailable only when source
        # currency values exist; an unsupported source makes both unavailable.
        facts[0].channel_code = ReservationChannelCodeEnum.BOOKING
        facts[0].guest_segment = ReservationGuestSegmentEnum.LEISURE
        facts[0].source_currency = "USD"
        facts[0].fx_rate_snapshot = None
        facts[0].revenue_gross_ars = 0
        facts[0].revenue_net_ars = 0
        facts[0].revenue_gross_usd = 100
        facts[0].revenue_net_usd = 90

        facts[1].channel_code = ReservationChannelCodeEnum.WEBSITE_DIRECT
        facts[1].guest_segment = ReservationGuestSegmentEnum.BUSINESS
        facts[1].source_currency = "ARS"
        facts[1].fx_rate_snapshot = None
        facts[1].revenue_gross_ars = 100
        facts[1].revenue_net_ars = 90
        facts[1].revenue_gross_usd = 0
        facts[1].revenue_net_usd = 0

        facts[2].channel_code = ReservationChannelCodeEnum.OTHER_DIRECT
        facts[2].guest_segment = ReservationGuestSegmentEnum.LEISURE
        facts[2].source_currency = "XYZ"
        facts[2].fx_rate_snapshot = None
        db.commit()

        loaded_facts = _load_reservation_facts(db, 1, date(2026, 4, 1), date(2026, 4, 5))
        expected_segments = build_segments_breakdown(
            db,
            hotel_id=1,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
            facts=loaded_facts,
        )
        expected_channels = build_channels_breakdown(
            db,
            hotel_id=1,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
            facts=loaded_facts,
        )
        actual_segments = build_segments_breakdown(
            db,
            hotel_id=1,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
        )
        actual_channels = build_channels_breakdown(
            db,
            hotel_id=1,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
        )

    assert actual_segments == expected_segments
    assert actual_channels == expected_channels
    assert {row["channel_code"]: row["unavailable_currencies"] for row in actual_channels} == {
        "booking": ["ARS"],
        "other_direct": ["ARS", "USD"],
        "website_direct": ["USD"],
    }


def test_home_sql_aggregates_match_row_based_dashboard_with_currency_edge_cases(api_client):
    from app.services.analytics_service import _load_reservation_facts, _load_room_facts, build_home_payload

    _, SessionLocal, _, _ = api_client
    _seed_analytics_data(SessionLocal)
    with SessionLocal() as db:
        facts = (
            db.query(FactReservationDaily)
            .filter(FactReservationDaily.hotel_id == 1)
            .order_by(FactReservationDaily.stay_date.asc(), FactReservationDaily.id.asc())
            .all()
        )
        assert len(facts) >= 3
        facts[0].source_currency = "USD"
        facts[0].fx_rate_snapshot = None
        facts[0].revenue_gross_ars = 0
        facts[0].revenue_net_ars = 0
        facts[0].revenue_gross_usd = 100
        facts[0].revenue_net_usd = 90
        facts[1].source_currency = "ARS"
        facts[1].fx_rate_snapshot = None
        facts[1].revenue_gross_ars = 100
        facts[1].revenue_net_ars = 90
        facts[1].revenue_gross_usd = 0
        facts[1].revenue_net_usd = 0
        facts[2].source_currency = "XYZ"
        facts[2].fx_rate_snapshot = None
        db.commit()

        date_from, date_to = date(2026, 4, 1), date(2026, 4, 5)
        row_facts = _load_reservation_facts(db, 1, date_from, date_to)
        room_facts = _load_room_facts(db, 1, date_from, date_to)
        expected = build_home_payload(
            db,
            hotel_id=1,
            date_from=date_from,
            date_to=date_to,
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
            reservation_facts=row_facts,
            room_facts=room_facts,
        )
        actual = build_home_payload(
            db,
            hotel_id=1,
            date_from=date_from,
            date_to=date_to,
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
        )

    assert actual["data"] == expected["data"]
    assert actual["data_as_of"] == expected["data_as_of"]


def test_rooms_overview_sql_aggregates_match_daily_fact_rows(api_client):
    from app.services.analytics_service import (
        _facts_data_as_of,
        _load_reservation_facts,
        _load_room_facts,
        _room_lookup_map,
        _category_lookup_map,
        _unavailable_currency_metadata,
        _sum_money,
        build_rooms_overview_payload,
    )

    _, SessionLocal, _, _ = api_client
    _seed_analytics_data(SessionLocal)
    with SessionLocal() as db:
        date_from, date_to = date(2026, 4, 1), date(2026, 4, 5)
        room_facts = _load_room_facts(db, 1, date_from, date_to)
        reservation_facts = _load_reservation_facts(db, 1, date_from, date_to)
        rooms = _room_lookup_map(db, 1)
        categories = _category_lookup_map(db, 1)
        occupancy_by_room: dict[int, list] = {}
        currency_by_room: dict[int, list] = {}
        for row in room_facts:
            occupancy_by_room.setdefault(row.room_id, []).append(row)
        for row in reservation_facts:
            currency_by_room.setdefault(row.room_id, []).append(row)
        expected_rooms = []
        for room in rooms.values():
            facts = occupancy_by_room.get(room.id, [])
            category = categories.get(room.category_id)
            expected_rooms.append(
                {
                    "room_id": room.id,
                    "room_number": room.room_number,
                    "floor": room.floor,
                    "category_id": room.category_id,
                    "category_name": category.name if category else None,
                    "is_active": room.is_active,
                    "status": room.status.value if hasattr(room.status, "value") else str(room.status),
                    "occupied_nights": len([fact for fact in facts if fact.is_occupied]),
                    "revenue_net_ars": f"{_sum_money(facts, 'revenue_net_ars'):.2f}",
                    "revenue_net_usd": f"{_sum_money(facts, 'revenue_net_usd'):.2f}",
                    "margin_operating_ars": f"{_sum_money(facts, 'margin_operating_ars'):.2f}",
                    "margin_operating_usd": f"{_sum_money(facts, 'margin_operating_usd'):.2f}",
                    **_unavailable_currency_metadata(currency_by_room.get(room.id, [])),
                }
            )
        expected_rooms.sort(key=lambda item: item["room_number"] or "")
        expected_data_as_of = _facts_data_as_of(room_facts, reservation_facts)
        actual = build_rooms_overview_payload(
            db,
            hotel_id=1,
            date_from=date_from,
            date_to=date_to,
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
        )

    assert actual["data"]["rooms"] == expected_rooms
    assert actual["data_as_of"] == expected_data_as_of


def test_export_comparison_models_and_xml_control_characters_are_serialized_safely():
    comparison = AnalyticsComparisonStateRead(
        previous=AnalyticsComparisonWindowRead(
            requested=True,
            available=True,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
        ),
        yoy=AnalyticsComparisonWindowRead(
            requested=False,
            available=False,
        ),
    )
    rows = _flatten_payload_rows({"comparison": comparison, "data": {"cards": []}})
    assert ["comparison.previous", "available", "true"] in rows
    assert ["comparison.previous", "date_from", "2026-03-01"] in rows

    xml_text = _sheet_xml_from_table([["valid\u0001text", "tab\tok"]])
    parsed = ET.fromstring(xml_text)
    assert "validtext" in "".join(parsed.itertext())
    assert "tab\tok" in "".join(parsed.itertext())


def test_xlsx_writer_accepts_one_pass_row_iterators():
    row_count = 2_000
    workbook_bytes = _build_xlsx_bytes(
        [("Facts", ([str(index), f"value-{index}"] for index in range(row_count)))]
    )

    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as archive:
        worksheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    sheet_data = worksheet.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData")
    assert sheet_data is not None
    assert len(sheet_data) == row_count


def test_xlsx_writer_splits_unlimited_rows_across_excel_sheet_boundaries():
    source_rows = [["id", "value"]] + [[str(index), f"value-{index}"] for index in range(8)]
    workbook_bytes = _build_xlsx_bytes(
        [("Facts", iter(source_rows))],
        max_rows_per_sheet=3,
    )

    with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as archive:
        worksheet_names = sorted(
            name for name in archive.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        assert len(worksheet_names) == 4
        data_values = []
        for worksheet_name in worksheet_names:
            worksheet = ET.fromstring(archive.read(worksheet_name))
            sheet_data = worksheet.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData")
            assert sheet_data is not None
            assert len(sheet_data) <= 3
            data_values.extend(
                "".join(cell.itertext())
                for row in list(sheet_data)[1:]
                for cell in [list(row)[0]]
            )

    assert data_values == [str(index) for index in range(8)]


def test_xlsx_spool_rolls_large_workbooks_to_disk_without_losing_zip_structure(monkeypatch):
    import app.services.analytics_exports as exports_module

    monkeypatch.setattr(exports_module, "XLSX_EXPORT_SPOOL_MEMORY_BYTES", 128)
    output = _build_xlsx_spool(
        [("Facts", ([str(index), "x" * 128] for index in range(2_000)))]
    )
    try:
        assert getattr(output, "_rolled", False)
        workbook_bytes = output.read()
        assert zipfile.is_zipfile(io.BytesIO(workbook_bytes))
        with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as archive:
            assert "xl/worksheets/sheet1.xml" in archive.namelist()
    finally:
        output.close()


def test_long_png_export_is_spooled_as_pages_without_dropping_rows(monkeypatch):
    import app.services.analytics_exports as exports_module

    monkeypatch.setattr(exports_module, "PNG_EXPORT_PAGE_ROWS", 3)
    monkeypatch.setattr(
        exports_module,
        "_png_from_rows",
        lambda rows, title: "\n".join(f"{row[1]}={row[2]}" for row in rows[1:]).encode(),
    )
    source_rows = [["section", "key", "value"]] + [
        ["facts", str(index), f"value-{index}"] for index in range(8)
    ]

    archive_file = _png_export_content(iter(source_rows), title="Analytics export")
    assert not isinstance(archive_file, bytes)
    archive_bytes = b"".join(iter_export_file_chunks(archive_file, chunk_size=17))
    assert archive_file.closed

    with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
        pages = sorted(archive.namelist())
        assert len(pages) == 3
        rendered_values = [
            line
            for page_name in pages
            for line in archive.read(page_name).decode().splitlines()
        ]

    assert rendered_values == [f"{index}=value-{index}" for index in range(8)]


def test_xlsx_export_persists_resolved_hotel_window(api_client):
    _, SessionLocal, _, _ = api_client
    _seed_analytics_data(SessionLocal)
    with SessionLocal() as db:
        user_id = db.query(User.id).filter(User.email == "owner@test.com").scalar()
        job = create_xlsx_export_job(
            db,
            hotel_id=1,
            user_id=user_id,
            request=AnalyticsExportRequest(entity_code="home"),
        )
        persisted_request = json.loads(job.filters_json)
        assert job.date_from == date.fromisoformat(persisted_request["date_from"])
        assert job.date_to == date.fromisoformat(persisted_request["date_to"])
        assert job.date_to >= job.date_from


def test_startup_recovery_requeues_only_unexpired_xlsx_jobs_by_hotel(api_client, monkeypatch):
    _, SessionLocal, _, _ = api_client
    from app.services import analytics_exports as exports_module

    contexts: list[int | None] = []
    original_set_tenant = exports_module.set_tenant_hotel_context

    def record_context(db, hotel_id):
        contexts.append(hotel_id)
        original_set_tenant(db, hotel_id)

    monkeypatch.setattr(exports_module, "set_tenant_hotel_context", record_context)
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        second_hotel = HotelConfiguration(id=2, hotel_name="Hotel Recovery 2")
        db.add(second_hotel)
        db.flush()
        user_id = db.query(User.id).filter(User.email == "owner@test.com").scalar()

        def add_job(*, hotel_id, status, expires_at):
            job = AnalyticsExportJob(
                hotel_id=hotel_id,
                user_id=user_id,
                entity_code="home",
                format=AnalyticsExportFormatEnum.XLSX,
                currency_display=AnalyticsCurrencyDisplayEnum.ARS,
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 5),
                compare_previous=False,
                compare_yoy=False,
                filters_json='{"entity_code":"home","date_from":"2026-04-01","date_to":"2026-04-05"}',
                status=status,
                started_at=now if status == AnalyticsExportStatusEnum.RUNNING else None,
                completed_at=now if status == AnalyticsExportStatusEnum.COMPLETED else None,
                expires_at=expires_at,
            )
            db.add(job)
            db.flush()
            return job

        interrupted = add_job(
            hotel_id=1,
            status=AnalyticsExportStatusEnum.RUNNING,
            expires_at=now + timedelta(hours=1),
        )
        pending = add_job(
            hotel_id=2,
            status=AnalyticsExportStatusEnum.PENDING,
            expires_at=now + timedelta(hours=1),
        )
        expired = add_job(
            hotel_id=1,
            status=AnalyticsExportStatusEnum.RUNNING,
            expires_at=now - timedelta(seconds=1),
        )
        completed = add_job(
            hotel_id=2,
            status=AnalyticsExportStatusEnum.COMPLETED,
            expires_at=now + timedelta(hours=1),
        )
        interrupted_id, pending_id = interrupted.id, pending.id
        expired_id, completed_id = expired.id, completed.id
        db.commit()

        recovered = prepare_xlsx_export_jobs_for_recovery(db)

        assert recovered == [(interrupted_id, 1), (pending_id, 2)]
        assert contexts == [None, 1, 2]
        assert db.get(AnalyticsExportJob, interrupted_id).status == AnalyticsExportStatusEnum.PENDING
        assert db.get(AnalyticsExportJob, interrupted_id).started_at is None
        assert db.get(AnalyticsExportJob, expired_id).status == AnalyticsExportStatusEnum.RUNNING
        assert db.get(AnalyticsExportJob, completed_id).status == AnalyticsExportStatusEnum.COMPLETED


def test_restart_recovers_xlsx_to_local_storage_and_downloads_it(api_client, tmp_path, monkeypatch):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    plan_state["plan"] = "ultra"

    with SessionLocal() as db:
        user_id = db.query(User.id).filter(User.email == "owner@test.com").scalar()
        job = create_xlsx_export_job(
            db,
            hotel_id=1,
            user_id=user_id,
            request=AnalyticsExportRequest(
                entity_code="home",
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 5),
            ),
        )
        job.status = AnalyticsExportStatusEnum.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job_id = job.id
        db.commit()

    import app.services.analytics_exports as exports_module
    import app.services.stored_object_service as stored_object_module

    local_storage = LocalObjectStorage(tmp_path / "object-storage")
    monkeypatch.setattr(exports_module, "get_object_storage", lambda: local_storage)
    monkeypatch.setattr(stored_object_module, "get_object_storage", lambda: local_storage)
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr(main_module, "_seed_permission_matrix_once", lambda: None)
    monkeypatch.setattr(main_module, "validate_runtime_security", lambda: None)
    startup_app = FastAPI(lifespan=main_module.lifespan)

    async def restart_once():
        async with main_module.lifespan(startup_app):
            pass

    asyncio.run(restart_once())

    with SessionLocal() as db:
        recovered = db.get(AnalyticsExportJob, job_id)
        assert recovered.status == AnalyticsExportStatusEnum.COMPLETED
        assert recovered.file_path
        assert recovered.file_size_bytes > 0

    download = client.get(f"/api/analytics/exports/{job_id}/download", headers=headers)
    assert download.status_code == 200, download.text
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert archive.testzip() is None
        assert "[Content_Types].xml" in archive.namelist()


def test_long_png_export_uses_streamed_zip_response(api_client, monkeypatch):
    from tempfile import SpooledTemporaryFile

    import app.api.analytics as analytics_api

    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    plan_state["plan"] = "pro"
    archive = SpooledTemporaryFile(max_size=8 * 1024, mode="w+b")
    archive.write(b"local-paged-png-archive")
    archive.seek(0)
    monkeypatch.setattr(analytics_api, "render_export_png", lambda *_args, **_kwargs: archive)

    response = client.post(
        "/api/analytics/exports/png",
        json={"entity_code": "home", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    assert response.headers["content-disposition"].endswith(".zip\"")
    assert response.content == b"local-paged-png-archive"
    assert archive.closed


def test_xlsx_completed_job_is_idempotent_and_foreign_hotel_retry_is_noop(api_client, monkeypatch):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    plan_state["plan"] = "ultra"
    response = client.post(
        "/api/analytics/exports/xlsx",
        json={"entity_code": "home", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    completed_id = response.json()["id"]
    _wait_for_xlsx_completion(client, completed_id, headers)

    with SessionLocal() as db:
        user_id = db.query(User.id).filter(User.email == "owner@test.com").scalar()
        pending = AnalyticsExportJob(
            hotel_id=1,
            user_id=user_id,
            entity_code="home",
            format=AnalyticsExportFormatEnum.XLSX,
            currency_display=AnalyticsCurrencyDisplayEnum.ARS,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
            compare_previous=False,
            compare_yoy=False,
            filters_json='{"entity_code":"home","date_from":"2026-04-01","date_to":"2026-04-05"}',
            status=AnalyticsExportStatusEnum.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(pending)
        db.flush()
        pending_id = pending.id
        db.commit()

    import app.services.analytics_exports as exports_module

    monkeypatch.setattr(exports_module, "get_session_factory", lambda: SessionLocal)
    monkeypatch.setattr(
        exports_module,
        "render_export_xlsx_file",
        lambda *_args, **_kwargs: pytest.fail("a completed export must not be rendered again"),
    )
    generate_xlsx_export_job(completed_id, hotel_id=1)
    generate_xlsx_export_job(pending_id, hotel_id=999)

    with SessionLocal() as db:
        assert db.get(AnalyticsExportJob, completed_id).status == AnalyticsExportStatusEnum.COMPLETED
        assert db.get(AnalyticsExportJob, pending_id).status == AnalyticsExportStatusEnum.PENDING


def test_company_exports_require_sensitive_company_view_permission(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    with SessionLocal() as db:
        company = db.query(Company).filter_by(hotel_id=1, display_name="Acme").one()
        owner = db.query(User).filter_by(email="owner@test.com").one()
        permission = db.query(Permission).filter_by(code=PERMISSION_COMPANY_VIEW).one_or_none()
        if permission is None:
            db.add(Permission(code=PERMISSION_COMPANY_VIEW, description="view company profile"))
            db.flush()
        db.add(
            UserPermissionOverride(
                hotel_id=1,
                user_id=owner.id,
                permission_code=PERMISSION_COMPANY_VIEW,
                allowed=False,
                updated_by_user_id=owner.id,
            )
        )
        company_id = company.id
        db.commit()

    plan_state["plan"] = "ultra"
    company_request = {"entity_code": "company", "company_id": company_id}
    png = client.post("/api/analytics/exports/png", json=company_request, headers=headers)
    csv = client.post("/api/analytics/exports/csv", json=company_request, headers=headers)
    xlsx = client.post("/api/analytics/exports/xlsx", json=company_request, headers=headers)
    assert png.status_code == 403, png.text
    assert csv.status_code == 403, csv.text
    assert xlsx.status_code == 403, xlsx.text
    detail = client.get(f"/api/analytics/companies/{company_id}", headers=headers)
    assert detail.status_code == 403, detail.text

    home = client.post(
        "/api/analytics/exports/png",
        json={"entity_code": "home"},
        headers=headers,
    )
    assert home.status_code == 200, home.text
    with SessionLocal() as db:
        assert db.query(AnalyticsExportJob).filter_by(hotel_id=1).count() == 0


def test_company_exports_remain_available_with_company_and_advanced_analytics_access(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    with SessionLocal() as db:
        company_id = db.query(Company).filter_by(hotel_id=1, display_name="Acme").one().id

    plan_state["plan"] = "pro"
    company_request = {"entity_code": "company", "company_id": company_id}
    assert client.post("/api/analytics/exports/png", json=company_request, headers=headers).status_code == 200
    assert client.post("/api/analytics/exports/csv", json=company_request, headers=headers).status_code == 200

    plan_state["plan"] = "ultra"
    xlsx = client.post("/api/analytics/exports/xlsx", json=company_request, headers=headers)
    assert xlsx.status_code == 201, xlsx.text
    job_id = xlsx.json()["id"]

    with SessionLocal() as db:
        owner = db.query(User).filter_by(email="owner@test.com").one()
        db.add(
            UserPermissionOverride(
                hotel_id=1,
                user_id=owner.id,
                permission_code=PERMISSION_COMPANY_VIEW,
                allowed=False,
                updated_by_user_id=owner.id,
            )
        )
        db.commit()

    assert client.get(f"/api/analytics/exports/{job_id}", headers=headers).status_code == 403
    assert client.get(f"/api/analytics/exports/{job_id}/download", headers=headers).status_code == 403
    listed = client.get("/api/analytics/exports", headers=headers)
    assert listed.status_code == 200, listed.text
    assert all(item["entity_code"] != "company" for item in listed.json())


def test_analytics_insights_status_and_payloads(api_client, monkeypatch: pytest.MonkeyPatch):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)

    plan_state["plan"] = "ultra"

    import app.services.analytics_service as analytics_service_module
    import app.services.analytics_insights as analytics_insights_module
    from app.services.analytics_ai_providers import AnalyticsAIProviderStatus, AnalyticsAIResult

    class _Provider:
        def status(self):
            return AnalyticsAIProviderStatus(
                provider="gemma",
                configured=True,
                runtime_healthy=True,
                effective_model="gemma-test",
                runtime_status="ready",
            )

        def generate_insight(self, request):
            assert request.hotel_id == 1
            assert request.insight_code in {"home", "anomalies", "pricing"}
            return AnalyticsAIResult(
                summary="Analisis IA generado",
                warnings=["Revisar pickups"],
                recommendations=["Ajustar tarifa base"],
                data={"signals": ["ocupacion_baja"]},
                raw_response={"summary": "Analisis IA generado"},
            )

        def generate_chat_answer(self, request, *, message):
            assert request.hotel_id == 1
            assert request.insight_code == "chat"
            assert "hotel" in message.lower()
            return AnalyticsAIResult(
                summary="Analisis IA generado",
                warnings=["Revisar pickups"],
                recommendations=["Ajustar tarifa base"],
                data={"signals": ["ocupacion_baja"]},
                raw_response={"answer": "Analisis IA generado"},
            )

    monkeypatch.setattr(analytics_service_module, "get_analytics_ai_provider", lambda: _Provider())
    monkeypatch.setattr(analytics_insights_module, "get_analytics_ai_provider", lambda: _Provider())

    ai_enable = client.patch("/api/analytics/ai-config", json={"analytics_ai_enabled": True}, headers=headers)
    assert ai_enable.status_code == 200, ai_enable.text
    assert ai_enable.json()["analytics_ai_enabled"] is True

    status_resp = client.get("/api/analytics/insights/status", headers=headers)
    assert status_resp.status_code == 200, status_resp.text
    status_payload = status_resp.json()
    assert status_payload["runtime_healthy"] is True
    assert status_payload["provider"] == "gemma"

    home_resp = client.post(
        "/api/analytics/insights/home",
        json={"date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert home_resp.status_code == 200, home_resp.text
    home_payload = home_resp.json()
    assert home_payload["summary"] == "Analisis IA generado"
    assert home_payload["warnings"] == ["Revisar pickups"]
    assert home_payload["recommendations"] == ["Ajustar tarifa base"]
    assert home_payload["data"]["model_output"]["summary"] == "Analisis IA generado"

    free_prompt_resp = client.post(
        "/api/analytics/insights/home",
        json={"date_from": "2026-04-01", "date_to": "2026-04-05", "prompt": "escribi una novela"},
        headers=headers,
    )
    assert free_prompt_resp.status_code == 422

    engine = SessionLocal.kw["bind"]
    anomaly_fact_queries: list[str] = []

    def capture_anomaly_facts(_connection, _cursor, statement, _parameters, _context, _executemany):
        lowered = statement.lower()
        if "from fact_reservation_daily" in lowered or "from fact_room_occupancy_daily" in lowered:
            anomaly_fact_queries.append(lowered)

    event.listen(engine, "before_cursor_execute", capture_anomaly_facts)
    try:
        anomalies_resp = client.post(
            "/api/analytics/insights/anomalies",
            json={"date_from": "2026-04-01", "date_to": "2026-04-05"},
            headers=headers,
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_anomaly_facts)
    assert anomalies_resp.status_code == 200, anomalies_resp.text
    assert anomalies_resp.json()["insight_code"] == "anomalies"
    assert sum("from fact_reservation_daily" in query for query in anomaly_fact_queries) == 1
    assert sum("from fact_room_occupancy_daily" in query for query in anomaly_fact_queries) == 1
    anomaly_context = anomalies_resp.json()["data"]["context"]
    assert "top_channels" not in anomaly_context["home"]
    assert "segments" not in anomaly_context["home"]

    pricing_resp = client.post(
        "/api/analytics/insights/pricing",
        json={"date_from": "2026-04-01", "date_to": "2026-04-05", "category_id": 1},
        headers=headers,
    )
    assert pricing_resp.status_code == 200, pricing_resp.text
    assert pricing_resp.json()["insight_code"] == "pricing"

    chat_resp = client.post(
        "/api/analytics/ai-chat",
        json={"message": "Resumime el estado del hotel este mes", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert chat_resp.status_code == 200, chat_resp.text
    assert chat_resp.json()["hotel_id"] == 1
    assert chat_resp.json()["answer"] == "Analisis IA generado"

    blocked_chat = client.post(
        "/api/analytics/ai-chat",
        json={"message": "Escribi una novela de ciencia ficcion", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert blocked_chat.status_code == 400
    assert "dominio hotelero" in blocked_chat.json()["detail"]

    with SessionLocal() as db:
        usage_row = db.query(AnalyticsAIUsageMonthly).filter(AnalyticsAIUsageMonthly.hotel_id == 1).first()
    assert usage_row is not None
    assert usage_row.calls_used >= 4


def test_analytics_ai_quota_is_read_only_and_enforced_before_provider_calls(api_client, monkeypatch: pytest.MonkeyPatch):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    plan_state["plan"] = "ultra"

    from types import SimpleNamespace

    import app.services.analytics_service as analytics_service_module
    import app.services.analytics_insights as analytics_insights_module
    from app.services.analytics_ai_providers import AnalyticsAIProviderStatus, AnalyticsAIResult

    class _Provider:
        calls = 0

        def status(self):
            return AnalyticsAIProviderStatus(
                provider="local-test",
                configured=True,
                runtime_healthy=True,
                effective_model="local-test-model",
                runtime_status="ready",
            )

        def generate_insight(self, request):
            self.calls += 1
            return AnalyticsAIResult(summary="Respuesta local", raw_response={"summary": "Respuesta local"})

        def generate_chat_answer(self, request, *, message):
            raise AssertionError("el test sólo invoca insights")

    provider = _Provider()
    monkeypatch.setattr(analytics_service_module, "get_analytics_ai_provider", lambda: provider)
    monkeypatch.setattr(analytics_insights_module, "get_analytics_ai_provider", lambda: provider)
    monkeypatch.setattr(
        analytics_service_module,
        "build_analytics_ai_config",
        lambda settings: SimpleNamespace(quota_monthly=1, model="local-test-model"),
    )

    config_read = client.get("/api/analytics/ai-config", headers=headers)
    assert config_read.status_code == 200, config_read.text
    with SessionLocal() as db:
        assert db.query(AnalyticsAIUsageMonthly).filter(AnalyticsAIUsageMonthly.hotel_id == 1).count() == 0

    enabled = client.patch(
        "/api/analytics/ai-config",
        json={"analytics_ai_enabled": True},
        headers=headers,
    )
    assert enabled.status_code == 200, enabled.text

    request_body = {"date_from": "2026-04-01", "date_to": "2026-04-05"}
    first = client.post("/api/analytics/insights/home", json=request_body, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["quota_used"] == 1
    assert first.json()["quota_remaining"] == 0

    over_limit = client.post("/api/analytics/insights/home", json=request_body, headers=headers)
    assert over_limit.status_code == 429, over_limit.text
    assert provider.calls == 1
    with SessionLocal() as db:
        usage_rows = db.query(AnalyticsAIUsageMonthly).filter(AnalyticsAIUsageMonthly.hotel_id == 1).all()
    assert len(usage_rows) == 1
    assert usage_rows[0].calls_used == 1


def test_analytics_dashboard_and_ai_chat_without_provider(api_client):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    plan_state["plan"] = "ultra"

    home_resp = client.get(
        "/api/analytics/home",
        params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert home_resp.status_code == 200, home_resp.text
    assert "cards" in home_resp.json()["data"]

    chat_resp = client.post(
        "/api/analytics/ai-chat",
        json={"message": "Resumime el estado del hotel este mes", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert chat_resp.status_code == 503
    assert chat_resp.json()["detail"] == "La IA todavía no está conectada. Configurá el proveedor de IA para usar el asistente."


def test_cleanup_expired_exports_task(api_client, monkeypatch: pytest.MonkeyPatch):
    client, SessionLocal, headers, plan_state = api_client
    _seed_analytics_data(SessionLocal)
    plan_state["plan"] = "ultra"

    import app.services.analytics_service as analytics_service_module
    import app.services.analytics_insights as analytics_insights_module
    import app.tasks.analytics_tasks as analytics_tasks_module
    from app.services.analytics_ai_providers import AnalyticsAIProviderStatus, AnalyticsAIResult
    from app.services.object_storage import ObjectStorageError, get_object_storage

    monkeypatch.setattr(analytics_tasks_module, "get_engine", lambda url: SessionLocal.kw["bind"])
    class _Provider:
        def status(self):
            return AnalyticsAIProviderStatus(
                provider="gemma",
                configured=True,
                runtime_healthy=True,
                effective_model="gemma-test",
                runtime_status="ready",
            )

        def generate_insight(self, request):
            return AnalyticsAIResult(summary="ok", raw_response={"summary": "ok"})

    monkeypatch.setattr(analytics_service_module, "get_analytics_ai_provider", lambda: _Provider())
    monkeypatch.setattr(analytics_insights_module, "get_analytics_ai_provider", lambda: _Provider())

    client.patch("/api/analytics/ai-config", json={"analytics_ai_enabled": True}, headers=headers)
    xlsx_resp = client.post(
        "/api/analytics/exports/xlsx",
        json={"entity_code": "home", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert xlsx_resp.status_code == 201, xlsx_resp.text
    job_id = xlsx_resp.json()["id"]

    active_xlsx_resp = client.post(
        "/api/analytics/exports/xlsx",
        json={"entity_code": "home", "date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert active_xlsx_resp.status_code == 201, active_xlsx_resp.text
    active_job_id = active_xlsx_resp.json()["id"]
    _wait_for_xlsx_completion(client, job_id, headers)
    _wait_for_xlsx_completion(client, active_job_id, headers)

    with SessionLocal() as db:
        job = db.query(AnalyticsExportJob).filter(AnalyticsExportJob.id == job_id).first()
        assert job is not None
        job.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
        object_key = job.file_path
        active_job = db.query(AnalyticsExportJob).filter(AnalyticsExportJob.id == active_job_id).first()
        assert active_job is not None
        active_object_key = active_job.file_path
    assert object_key
    assert active_object_key
    expired_download = client.get(f"/api/analytics/exports/{job_id}/download", headers=headers)
    assert expired_download.status_code == 410
    with SessionLocal() as db:
        assert db.get(AnalyticsExportJob, job_id).status == AnalyticsExportStatusEnum.EXPIRED
    # Sanity check: the export bytes actually exist in object storage before cleanup runs.
    get_object_storage().get_bytes(object_key)

    from sqlalchemy import event

    cleanup_sql: list[str] = []
    engine = SessionLocal.kw["bind"]

    def capture_cleanup_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "analytics_export_jobs" in statement.lower():
            cleanup_sql.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture_cleanup_sql)
    try:
        result = analytics_tasks_module.cleanup_expired_exports.run(database_url="sqlite:///:memory:")
    finally:
        event.remove(engine, "before_cursor_execute", capture_cleanup_sql)
    assert result["deleted_objects"] >= 1
    assert any("expires_at" in statement and "file_path is not null" in statement for statement in cleanup_sql)

    with SessionLocal() as db:
        job = db.query(AnalyticsExportJob).filter(AnalyticsExportJob.id == job_id).first()
        assert job is not None
        assert job.status == AnalyticsExportStatusEnum.EXPIRED
        assert job.file_path is None
        active_job = db.get(AnalyticsExportJob, active_job_id)
        assert active_job is not None
        assert active_job.status == AnalyticsExportStatusEnum.COMPLETED
        assert active_job.file_path == active_object_key

    # cleanup_expired_exports must also delete the object-storage file, not just
    # flip the job status.
    with pytest.raises(ObjectStorageError):
        get_object_storage().get_bytes(object_key)
    get_object_storage().get_bytes(active_object_key)


def test_analytics_read_preserves_stale_metadata_without_rebuilding_complete_facts(api_client):
    # Fact timestamps are materialization metadata, not a source-write
    # watermark. A complete window is not rescanned just because it is old;
    # the caller receives honest freshness metadata instead.
    client, SessionLocal, headers, plan_state = api_client
    import app.services.analytics_service as analytics_service_module

    _seed_analytics_data(SessionLocal)
    plan_state["plan"] = "pro"

    stale_since = datetime.now(timezone.utc) - timedelta(hours=2)
    with SessionLocal() as db:
        db.query(FactReservationDaily).filter(FactReservationDaily.hotel_id == 1).update({"updated_at": stale_since})
        db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == 1).update({"updated_at": stale_since})
        db.commit()

    resp = client.get(
        "/api/analytics/home",
        params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert Decimal(payload["source_lag_seconds"]) >= Decimal("7000")

    with SessionLocal() as db:
        timestamps = [
            analytics_service_module._ensure_utc(row.updated_at)
            for row in db.query(FactReservationDaily.updated_at)
            .filter(FactReservationDaily.hotel_id == 1)
            .all()
        ]
    assert timestamps
    assert min(timestamps) == stale_since


def test_analytics_home_does_not_rebuild_missing_facts_on_read(api_client, monkeypatch):
    # Even a legacy opt-in environment value cannot turn an Analytics GET into
    # a historical repair. Supported reservation writes maintain facts in
    # their own transaction; out-of-band gaps stay explicitly unverified until
    # the reviewed maintenance command is run.
    client, SessionLocal, headers, plan_state = api_client
    plan_state["plan"] = "pro"
    import app.services.analytics_service as analytics_service_module

    monkeypatch.setenv("SYNC_FACT_REFRESH_ENABLED", "true")
    monkeypatch.setattr(
        analytics_service_module,
        "get_settings",
        lambda: Settings(
            _env_file=None,
            SYNC_FACT_REFRESH_ENABLED=True,
            SYNC_FACT_REFRESH_MAX_DAYS=31,
        ),
    )
    _seed_analytics_data(SessionLocal)
    with SessionLocal() as db:
        db.query(FactReservationDaily).filter(FactReservationDaily.hotel_id == 1).delete()
        db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == 1).delete()
        db.commit()

    resp = client.get(
        "/api/analytics/home",
        params={"date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["data_as_of"] is None
    assert payload["source_lag_seconds"] is None

    with SessionLocal() as db:
        assert db.query(FactReservationDaily).filter(FactReservationDaily.hotel_id == 1).count() == 0
        assert db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == 1).count() == 0
