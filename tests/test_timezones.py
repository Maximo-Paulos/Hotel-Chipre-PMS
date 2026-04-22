import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main_module
from app.schemas.hotel_config import HotelConfigUpdate
from app.schemas.onboarding import HotelIdentityPayload
from app.services import timezones as timezones_service


def test_timezone_catalog_is_cached(monkeypatch):
    calls = {"count": 0}

    def fake_available_timezones():
        calls["count"] += 1
        return {"Europe/Madrid", "America/Argentina/Buenos_Aires"}

    monkeypatch.setattr(timezones_service, "available_timezones", fake_available_timezones)
    timezones_service.get_timezone_catalog.cache_clear()

    first = timezones_service.get_timezone_catalog()
    second = timezones_service.get_timezone_catalog()

    assert first == ("America/Argentina/Buenos_Aires", "Europe/Madrid")
    assert second == first
    assert calls["count"] == 1


def test_timezone_catalog_endpoint_returns_list(monkeypatch):
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr("app.api.reference.get_timezone_catalog", lambda: ("UTC", "Europe/Madrid"))

    with TestClient(main_module.app) as client:
        response = client.get("/api/reference/timezones")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, list)
    assert payload == ["UTC", "Europe/Madrid"]


def test_hotel_identity_rejects_invalid_timezone(monkeypatch):
    monkeypatch.setattr(timezones_service, "get_timezone_catalog", lambda: ("UTC",))

    with pytest.raises(ValidationError):
        HotelIdentityPayload(
            name="Hotel Chipre",
            timezone="Not/A_Real_Zone",
            currency="ARS",
            languages=["es"],
            jurisdiction_code="AR",
        )


def test_hotel_config_rejects_invalid_timezone(monkeypatch):
    monkeypatch.setattr(timezones_service, "get_timezone_catalog", lambda: ("UTC",))

    with pytest.raises(ValidationError):
        HotelConfigUpdate(hotel_timezone="Not/A_Real_Zone")
