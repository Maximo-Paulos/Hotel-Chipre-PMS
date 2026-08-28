from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.config import get_settings as real_get_settings
from app.main import app as fastapi_app


@pytest.fixture
def inquiry_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def override_get_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(fastapi_app), db, monkeypatch
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _payload(**overrides):
    payload = {
        "name": "Ana Pérez",
        "email": "ana@example.com",
        "company_name": "Hotel Ejemplo",
        "phone": "+54 11 5555-1234",
        "message": "Quiero conocer el sistema para mi hotel.",
        "source_path": "/contacto",
        "privacy_consent": True,
        "website": "",
    }
    payload.update(overrides)
    return payload


def _configured_settings():
    settings = real_get_settings().model_dump()
    settings["PUBLIC_INQUIRY_RECIPIENT_EMAIL"] = "ventas@example.com"
    return SimpleNamespace(**settings)


def _inquiry_rows(db):
    table = Base.metadata.tables["public_inquiries"]
    return db.execute(select(table)).mappings().all()


def test_public_inquiry_persists_and_notifies_after_acceptance(inquiry_client):
    client, db, monkeypatch = inquiry_client
    sent = []
    monkeypatch.setattr(
        "app.config.get_settings",
        _configured_settings,
    )
    monkeypatch.setattr(
        "app.services.email_service.send_platform_email",
        lambda to, subject, body: sent.append((to, subject, body)) or True,
    )

    response = client.post("/api/public/inquiries", json=_payload())

    assert response.status_code == 201, response.text
    assert response.json() == {"status": "accepted"}
    inquiry = _inquiry_rows(db)[0]
    assert inquiry["email"] == "ana@example.com"
    assert inquiry["privacy_consent_at"] is not None
    assert inquiry["notification_status"] == "sent"
    assert sent and sent[0][0] == "ventas@example.com"


def test_public_inquiry_keeps_record_when_notification_fails(inquiry_client):
    client, db, monkeypatch = inquiry_client
    monkeypatch.setattr("app.config.get_settings", _configured_settings)

    def fail_to_send(*args, **kwargs):
        raise RuntimeError("transport unavailable")

    monkeypatch.setattr("app.services.email_service.send_platform_email", fail_to_send)

    response = client.post("/api/public/inquiries", json=_payload())

    assert response.status_code == 201, response.text
    inquiry = _inquiry_rows(db)[0]
    assert inquiry["notification_status"] == "failed"
    assert inquiry["notification_error_type"] == "RuntimeError"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "not-an-email"),
        ("message", ""),
        ("privacy_consent", False),
    ],
)
def test_public_inquiry_rejects_invalid_required_fields(inquiry_client, field, value):
    client, db, _monkeypatch = inquiry_client

    response = client.post("/api/public/inquiries", json=_payload(**{field: value}))

    assert response.status_code == 422, response.text
    assert _inquiry_rows(db) == []


def test_public_inquiry_rejects_honeypot_submission(inquiry_client):
    client, db, _monkeypatch = inquiry_client

    response = client.post("/api/public/inquiries", json=_payload(website="https://spam.example"))

    assert response.status_code == 400, response.text
    assert _inquiry_rows(db) == []


def test_public_inquiry_is_rate_limited_by_source_and_email(inquiry_client):
    client, db, monkeypatch = inquiry_client
    monkeypatch.setattr("app.config.get_settings", _configured_settings)
    monkeypatch.setattr("app.services.email_service.send_platform_email", lambda *args, **kwargs: True)

    responses = [
        client.post("/api/public/inquiries", json=_payload(message=f"Mensaje {index}"))
        for index in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [201] * 5
    assert responses[5].status_code == 429, responses[5].text
    assert len(_inquiry_rows(db)) == 5


def test_public_inquiry_limits_repeated_email_even_when_other_fields_change(inquiry_client):
    client, db, monkeypatch = inquiry_client
    monkeypatch.setattr("app.config.get_settings", _configured_settings)
    monkeypatch.setattr("app.services.email_service.send_platform_email", lambda *args, **kwargs: True)

    for index in range(5):
        response = client.post(
            "/api/public/inquiries",
            json=_payload(name=f"Ana {index}", company_name=f"Hotel {index}"),
        )
        assert response.status_code == 201, response.text

    blocked = client.post(
        "/api/public/inquiries",
        json=_payload(name="Otra persona", company_name="Otro hotel"),
    )

    assert blocked.status_code == 429, blocked.text
    assert len(_inquiry_rows(db)) == 5
