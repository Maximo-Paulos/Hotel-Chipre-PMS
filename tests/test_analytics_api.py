from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.analytics import (
    AnalyticsAIUsageMonthly,
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
from app.services.analytics_facts import refresh_fact_reservation_daily, refresh_fact_room_occupancy_daily
from app.services.security import create_access_token, hash_password


def assert_freshness_metadata(payload: dict) -> None:
    assert payload["data_source"] in {"postgresql", "clickhouse"}
    assert payload["source_lag_seconds"] >= 0
    assert payload["data_as_of"]


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

    anomalies_resp = client.post(
        "/api/analytics/insights/anomalies",
        json={"date_from": "2026-04-01", "date_to": "2026-04-05"},
        headers=headers,
    )
    assert anomalies_resp.status_code == 200, anomalies_resp.text
    assert anomalies_resp.json()["insight_code"] == "anomalies"

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

    with SessionLocal() as db:
        job = db.query(AnalyticsExportJob).filter(AnalyticsExportJob.id == job_id).first()
        assert job is not None
        job.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
        object_key = job.file_path
    assert object_key
    # Sanity check: the export bytes actually exist in object storage before cleanup runs.
    get_object_storage().get_bytes(object_key)

    result = analytics_tasks_module.cleanup_expired_exports.run(database_url="sqlite:///:memory:")
    assert result["expired"] >= 1

    with SessionLocal() as db:
        job = db.query(AnalyticsExportJob).filter(AnalyticsExportJob.id == job_id).first()
        assert job is not None
        assert job.status == AnalyticsExportStatusEnum.EXPIRED

    # cleanup_expired_exports must also delete the object-storage file, not just
    # flip the job status.
    with pytest.raises(ObjectStorageError):
        get_object_storage().get_bytes(object_key)


def test_analytics_freshness_reflects_stale_derived_facts(api_client):
    # Fase 8: the analytics home/rooms/etc payloads are built entirely from
    # FactReservationDaily/FactRoomOccupancyDaily, which are only refreshed by
    # the Celery beat job (every 5 minutes in prod; never in this test
    # environment unless a test calls refresh_fact_* directly, same as
    # _seed_analytics_data does above). If those derived rows go stale
    # (worker lagging, or -- in this local/E2E environment -- no worker at
    # all), the UI must say so via source_lag_seconds/data_as_of instead of
    # silently claiming "al dia" for data that predates a real operation.
    client, SessionLocal, headers, plan_state = api_client
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
    assert_freshness_metadata(payload)
    # The derived facts backing this payload were computed 2 hours ago: the
    # reported lag must reflect that, not the instant the request ran.
    assert payload["source_lag_seconds"] >= 7000, payload


def test_analytics_home_self_heals_when_derived_facts_were_never_materialized(api_client):
    # Reproduces the real production bug (2026-07-26, hotel_id=4): nothing in
    # this codebase ever schedules/triggers analytics.refresh_fact_* (no
    # Celery beat entry, no signal on reservation/payment writes, no manual
    # call outside tests) -- so on a deployment without that piece wired up,
    # FactReservationDaily/FactRoomOccupancyDaily stay empty forever and
    # /api/analytics/home silently reports $0 revenue/occupancy despite real
    # paid reservations. Unlike _seed_analytics_data, this test deliberately
    # never calls refresh_fact_* -- exactly the "no worker ever ran" state.
    # The inline fallback is intentionally bounded, so the requested window
    # stays within its 31-day limit while still containing the reservation.
    client, SessionLocal, headers, plan_state = api_client
    plan_state["plan"] = "pro"

    with SessionLocal() as db:
        from app.models.guest import Guest

        category = RoomCategory(
            hotel_id=1,
            name="Standard",
            code="STD-SH",
            description="Standard room",
            base_price_per_night=100.0,
            variable_cost_per_night=12.50,
            max_occupancy=2,
        )
        db.add(category)
        db.flush()
        room = Room(hotel_id=1, room_number="201", floor=2, category_id=category.id, status=RoomStatusEnum.AVAILABLE, is_active=True)
        db.add(room)
        db.flush()
        guest = Guest(hotel_id=1, first_name="Rita", last_name="Gomez", email="rita@test.com", terms_accepted=True)
        db.add(guest)
        db.flush()
        db.add(
            Reservation(
                confirmation_code="RES-SELFHEAL",
                hotel_id=1,
                guest_id=guest.id,
                room_id=room.id,
                category_id=category.id,
                check_in_date=date(2026, 5, 1),
                check_out_date=date(2026, 5, 3),
                total_amount=198000.0,
                subtotal_amount=180000.0,
                tax_amount=18000.0,
                fee_amount=0.0,
                commission_amount=0.0,
                net_amount=180000.0,
                amount_paid=198000.0,
                deposit_amount=0.0,
                currency_code="ARS",
                status=ReservationStatusEnum.FULLY_PAID,
                outcome=ReservationOutcomeEnum.PENDING,
                source=ReservationSourceEnum.DIRECT,
                channel_code=ReservationChannelCodeEnum.OTHER_DIRECT,
                guest_segment=ReservationGuestSegmentEnum.LEISURE,
                guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
                no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.NONE,
                num_adults=2,
                num_children=0,
            )
        )
        db.commit()
        assert db.query(FactReservationDaily).filter(FactReservationDaily.hotel_id == 1).count() == 0

    resp = client.get(
        "/api/analytics/home",
        params={"date_from": "2026-04-20", "date_to": "2026-05-20"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    cards = {card["card_code"]: card for card in payload["data"]["cards"]}
    assert Decimal(cards["home_revenue_gross"]["value_ars"]) > 0, payload
    assert Decimal(cards["home_revenue_net"]["value_ars"]) > 0, payload
    assert cards["home_occupancy"]["value_pct"] > 0, payload

    with SessionLocal() as db:
        # Self-heal must have materialized the facts, not just computed them
        # ad hoc -- future reads (and the freshness annotation) stay correct.
        assert db.query(FactReservationDaily).filter(FactReservationDaily.hotel_id == 1).count() > 0
        assert db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == 1).count() > 0
