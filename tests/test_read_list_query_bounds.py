from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import event
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.analytics import (
    AnalyticsCurrencyDisplayEnum,
    AnalyticsExportFormatEnum,
    AnalyticsExportJob,
    AnalyticsExportStatusEnum,
)
from app.models.hotel_config import HotelConfiguration
from app.models.payment_link_test import PaymentLinkTest
from app.models.user import User
from app.schemas.payment_link_test import PaymentLinkTestRead
from app.services.analytics_exports import list_export_jobs
from app.services.payment_link_test_service import list_payment_link_tests


@pytest.fixture
def payment_link_tests_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def override_get_db():
        yield db

    def override_auth():
        return AuthContext(
            hotel_id=8301,
            user_id=8301,
            user_email="read-list-owner@example.test",
            user_role="owner",
            is_verified=True,
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    try:
        yield TestClient(fastapi_app), db, engine
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_payment_link_test_history_is_tenant_scoped_bounded_and_projection_only(db):
    db.add_all(
        [
            HotelConfiguration(id=8101, hotel_name="Read List Hotel A"),
            HotelConfiguration(id=8102, hotel_name="Read List Hotel B"),
        ]
    )
    db.flush()
    base_time = datetime(2026, 10, 1, tzinfo=timezone.utc)
    hotel_a = [
        PaymentLinkTest(
            hotel_id=8101,
            recipient_email=f"guest-{index}@example.test",
            amount=100 + index,
            description=f"Test payment {index}",
            external_reference=f"read-list-a-{index}",
            payment_link=f"https://payments.example.test/{index}",
            gateway_response={"unused_provider_payload": "x" * 20_000},
            created_at=base_time + timedelta(minutes=index),
        )
        for index in range(3)
    ]
    foreign = PaymentLinkTest(
        hotel_id=8102,
        recipient_email="foreign@example.test",
        amount=999,
        description="Foreign hotel payment",
        external_reference="read-list-b-1",
        created_at=base_time + timedelta(days=1),
    )
    db.add_all([*hotel_a, foreign])
    db.flush()
    first_page_expected = [hotel_a[2].id, hotel_a[1].id]
    second_page_expected = [hotel_a[0].id]
    db.expunge_all()

    selects: list[str] = []

    def capture_select(_connection, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("select") and " from payment_link_tests " in normalized:
            selects.append(normalized)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_select)
    try:
        first_page = list_payment_link_tests(db, 8101, limit=2, offset=0)
        first_page_ids = [item.id for item in first_page]
        [PaymentLinkTestRead.model_validate(item) for item in first_page]
        second_page = list_payment_link_tests(db, 8101, limit=2, offset=2)
        second_page_ids = [item.id for item in second_page]
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert first_page_ids == first_page_expected
    assert second_page_ids == second_page_expected
    assert len(selects) == 2, selects
    assert all("payment_link_tests.gateway_response" not in statement for statement in selects)
    assert all("limit" in statement and "offset" in statement for statement in selects)


def test_payment_link_test_api_serializes_one_bounded_select_without_committing(payment_link_tests_client):
    client, db, engine = payment_link_tests_client
    db.add(HotelConfiguration(id=8301, hotel_name="Payment Test API Hotel"))
    db.flush()
    db.add_all(
        [
            PaymentLinkTest(
                hotel_id=8301,
                recipient_email=f"api-guest-{index}@example.test",
                amount=100 + index,
                description=f"API payment test {index}",
                external_reference=f"api-read-list-{index}",
                gateway_response={"large_unreturned_provider_data": "x" * 20_000},
            )
            for index in range(3)
        ]
    )
    db.flush()
    db.expunge_all()

    selects: list[str] = []

    def capture_select(_connection, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("select") and " from payment_link_tests " in normalized:
            selects.append(normalized)

    event.listen(engine, "before_cursor_execute", capture_select)
    try:
        response = client.get("/api/payment-link-tests?limit=2")
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    assert "gateway_response" not in response.text
    assert len(selects) == 1, selects
    assert "payment_link_tests.gateway_response" not in selects[0]


def test_analytics_export_history_is_tenant_scoped_and_bounded(db):
    db.add_all(
        [
            HotelConfiguration(id=8201, hotel_name="Export List Hotel A"),
            HotelConfiguration(id=8202, hotel_name="Export List Hotel B"),
            User(id=8201, email="export-list@example.test", password_hash="test-hash"),
        ]
    )
    db.flush()
    expires_at = datetime(2026, 11, 1, tzinfo=timezone.utc)
    hotel_a = [
        AnalyticsExportJob(
            hotel_id=8201,
            user_id=8201,
            entity_code="home",
            format=AnalyticsExportFormatEnum.XLSX,
            currency_display=AnalyticsCurrencyDisplayEnum.ARS,
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 31),
            filters_json="{}",
            status=AnalyticsExportStatusEnum.COMPLETED,
            expires_at=expires_at,
            created_at=expires_at - timedelta(days=index + 1),
        )
        for index in range(3)
    ]
    foreign = AnalyticsExportJob(
        hotel_id=8202,
        user_id=8201,
        entity_code="home",
        format=AnalyticsExportFormatEnum.XLSX,
        currency_display=AnalyticsCurrencyDisplayEnum.ARS,
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 31),
        filters_json="{}",
        status=AnalyticsExportStatusEnum.COMPLETED,
        expires_at=expires_at,
        created_at=expires_at,
    )
    db.add_all([*hotel_a, foreign])
    db.flush()

    page = list_export_jobs(db, hotel_id=8201, limit=2, offset=1)

    assert [job.id for job in page] == [hotel_a[1].id, hotel_a[2].id]
    assert all(job.hotel_id == 8201 for job in page)
