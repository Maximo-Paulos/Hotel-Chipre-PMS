from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.config import get_settings as real_get_settings
from app.models.rate_limit_event import RateLimitEvent
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
        ("privacy_consent", "yes"),
        ("name", "Ana\u0000 Pérez"),
        ("message", "Consulta\u0000 inválida"),
    ],
)
def test_public_inquiry_rejects_invalid_required_fields(inquiry_client, field, value):
    client, db, _monkeypatch = inquiry_client

    response = client.post("/api/public/inquiries", json=_payload(**{field: value}))

    assert response.status_code == 422, response.text
    assert _inquiry_rows(db) == []


def test_public_inquiry_honeypot_is_silently_accepted_without_storage(inquiry_client):
    client, db, monkeypatch = inquiry_client
    monkeypatch.setattr("app.config.get_settings", _configured_settings)
    sent = []
    monkeypatch.setattr(
        "app.services.email_service.send_platform_email",
        lambda *args, **kwargs: sent.append(args),
    )

    response = client.post("/api/public/inquiries", json=_payload(website="https://spam.example"))

    assert response.status_code == 201, response.text
    assert response.json() == {"status": "accepted"}
    assert _inquiry_rows(db) == []
    assert sent == []


def test_public_inquiry_is_rate_limited_by_source_and_email(inquiry_client):
    client, db, monkeypatch = inquiry_client
    monkeypatch.setattr("app.config.get_settings", _configured_settings)
    monkeypatch.setattr("app.services.email_service.send_platform_email", lambda *args, **kwargs: True)

    responses = [
        client.post(
            "/api/public/inquiries",
            json=_payload(email=f"ana{index}@example.com", message=f"Mensaje {index}"),
            headers={"CF-Connecting-IP": "203.0.113.7"},
        )
        for index in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [201] * 5
    assert responses[5].status_code == 429, responses[5].text
    assert len(_inquiry_rows(db)) == 5


def test_public_inquiry_does_not_trust_spoofable_forwarded_for(inquiry_client):
    client, db, monkeypatch = inquiry_client
    monkeypatch.setattr("app.config.get_settings", _configured_settings)
    monkeypatch.setattr("app.services.email_service.send_platform_email", lambda *args, **kwargs: True)

    responses = [
        client.post(
            "/api/public/inquiries",
            json=_payload(email=f"person{index}@example.com"),
            headers={"X-Forwarded-For": "203.0.113.7"},
        )
        for index in range(6)
    ]

    assert [response.status_code for response in responses] == [201] * 6
    assert len(_inquiry_rows(db)) == 6


def test_public_inquiry_rate_limit_keys_are_keyed_and_not_raw(inquiry_client):
    client, db, monkeypatch = inquiry_client
    monkeypatch.setattr("app.config.get_settings", _configured_settings)
    monkeypatch.setattr("app.services.email_service.send_platform_email", lambda *args, **kwargs: True)

    response = client.post(
        "/api/public/inquiries",
        json=_payload(),
        headers={"CF-Connecting-IP": "203.0.113.7"},
    )

    assert response.status_code == 201, response.text
    events = db.query(RateLimitEvent).all()
    assert len(events) == 3
    assert all("203.0.113.7" not in event.subject_key for event in events)
    assert all("ana@example.com" not in event.subject_key for event in events)
    assert all(event.created_at.tzinfo is None for event in events)


def test_public_inquiry_has_global_limit_when_trusted_edge_ip_is_missing(inquiry_client):
    _client, db, monkeypatch = inquiry_client
    settings = _configured_settings()
    settings.PUBLIC_INQUIRY_GLOBAL_RATE_LIMIT = 2
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.email_service.send_platform_email", lambda *args, **kwargs: True)
    # Simulate a private reverse-proxy peer without the trusted edge header.
    proxy_client = TestClient(fastapi_app, client=("10.0.0.5", 8000))

    responses = [
        proxy_client.post(
            "/api/public/inquiries",
            json=_payload(email=f"person{index}@example.com"),
            headers={"X-Forwarded-For": f"203.0.113.{index + 1}"},
        )
        for index in range(3)
    ]

    assert [response.status_code for response in responses] == [201, 201, 429]
    events = db.query(RateLimitEvent).all()
    assert sum(event.scope == "public_inquiry_global" for event in events) == 3
    assert not any(event.scope == "public_inquiry_source" for event in events)
    assert all("203.0.113." not in event.subject_key for event in events)
    assert len(_inquiry_rows(db)) == 2


def test_rejected_source_or_email_does_not_consume_the_shared_global_budget(inquiry_client):
    client, db, monkeypatch = inquiry_client
    settings = _configured_settings()
    settings.PUBLIC_INQUIRY_RATE_LIMIT = 1
    settings.PUBLIC_INQUIRY_GLOBAL_RATE_LIMIT = 2
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.email_service.send_platform_email", lambda *args, **kwargs: True)

    first = client.post(
        "/api/public/inquiries",
        json=_payload(),
        headers={"CF-Connecting-IP": "203.0.113.7"},
    )
    source_limited = client.post(
        "/api/public/inquiries",
        json=_payload(email="other@example.com"),
        headers={"CF-Connecting-IP": "203.0.113.7"},
    )
    second_source = client.post(
        "/api/public/inquiries",
        json=_payload(email="third@example.com"),
        headers={"CF-Connecting-IP": "203.0.113.8"},
    )

    assert [first.status_code, source_limited.status_code, second_source.status_code] == [201, 429, 201]
    global_events = db.query(RateLimitEvent).filter_by(scope="public_inquiry_global").count()
    assert global_events == 2


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


def test_rejected_email_does_not_consume_the_shared_global_budget(inquiry_client):
    client, db, monkeypatch = inquiry_client
    settings = _configured_settings()
    settings.PUBLIC_INQUIRY_RATE_LIMIT = 5
    settings.PUBLIC_INQUIRY_GLOBAL_RATE_LIMIT = 6
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.email_service.send_platform_email", lambda *args, **kwargs: True)

    accepted_same_email = [
        client.post(
            "/api/public/inquiries",
            json=_payload(),
            headers={"CF-Connecting-IP": f"198.51.100.{index}"},
        )
        for index in range(1, 6)
    ]
    email_limited = client.post(
        "/api/public/inquiries",
        json=_payload(name="Different name"),
        headers={"CF-Connecting-IP": "198.51.100.6"},
    )
    second = client.post(
        "/api/public/inquiries",
        json=_payload(email="other@example.com"),
        headers={"CF-Connecting-IP": "198.51.100.7"},
    )
    global_limited = client.post(
        "/api/public/inquiries",
        json=_payload(email="third@example.com"),
        headers={"CF-Connecting-IP": "198.51.100.8"},
    )

    assert [response.status_code for response in accepted_same_email] == [201] * 5
    assert [email_limited.status_code, second.status_code, global_limited.status_code] == [429, 201, 429]
    global_events = db.query(RateLimitEvent).filter_by(scope="public_inquiry_global").count()
    assert global_events == 7
    assert len(_inquiry_rows(db)) == 6


def test_public_inquiry_collapses_newlines_in_single_line_email_fields(inquiry_client):
    client, _db, monkeypatch = inquiry_client
    sent = []
    monkeypatch.setattr("app.config.get_settings", _configured_settings)
    monkeypatch.setattr(
        "app.services.email_service.send_platform_email",
        lambda to, subject, body: sent.append(body) or True,
    )

    response = client.post(
        "/api/public/inquiries",
        json=_payload(name="Ana\nEmail: forged@example.com", company_name="Hotel\r\nUrgente", phone="11\n0000"),
    )

    assert response.status_code == 201, response.text
    assert "Nombre: Ana Email: forged@example.com\n" in sent[0]
    assert "Empresa: Hotel Urgente\n" in sent[0]
    assert "Teléfono: 11 0000\n" in sent[0]
    assert "\nEmail: forged@example.com\n" not in sent[0]


def test_public_inquiry_does_not_attempt_email_without_recipient(inquiry_client):
    client, db, monkeypatch = inquiry_client
    settings = _configured_settings()
    settings.PUBLIC_INQUIRY_RECIPIENT_EMAIL = ""
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.email_service.send_platform_email",
        lambda *args, **kwargs: pytest.fail("email must not be sent without a configured recipient"),
    )

    response = client.post("/api/public/inquiries", json=_payload())

    assert response.status_code == 201, response.text
    assert _inquiry_rows(db)[0]["notification_status"] == "not_configured"
