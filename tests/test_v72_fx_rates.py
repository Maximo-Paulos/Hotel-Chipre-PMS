from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.fx_rates as fx_rates_module
import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.hotel_config import HotelConfiguration
from app.models.fx_rate_snapshot import FxRateSnapshot
from app.models.user import User


@pytest.fixture
def fx_client(monkeypatch: pytest.MonkeyPatch):
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

    async def fake_snapshot():
        return {
            "oficial": {"moneda": "USD", "compra": 900.0, "venta": 920.0},
            "blue": {"moneda": "USD", "compra": 1000.0, "venta": 1020.0},
            "eur": {"moneda": "EUR", "casa": "oficial", "compra": 1000.0, "venta": 1010.0},
            "eur_blue": {"moneda": "EUR", "casa": "blue_derivado", "compra": 1100.0, "venta": 1120.0},
            "brl": {"moneda": "BRL", "casa": "oficial", "compra": 200.0, "venta": 210.0},
            "clp": {"moneda": "CLP", "casa": "oficial", "compra": 1.0, "venta": 1.1},
            "uyu": {"moneda": "UYU", "casa": "oficial", "compra": 25.0, "venta": 26.0},
        }

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    monkeypatch.setattr(fx_rates_module, "get_all_rates_snapshot", fake_snapshot)
    db_module.init_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # FX snapshots are financial config -- manager's default matrix does not
    # grant reports:financial:view, so the fixture uses owner here.
    auth_state = {"hotel_id": 1, "user_id": 21, "role": "owner"}

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=auth_state["hotel_id"],
            user_id=auth_state["user_id"],
            user_email="manager-fx@example.com",
            user_role=auth_state["role"],
            is_verified=True,
            permissions=set(),
        )

    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_auth_context

    with SessionLocal() as db:
        db.add_all(
            [
                HotelConfiguration(id=1, owner_email="owner1@example.com", subscription_active=True),
                HotelConfiguration(id=2, owner_email="owner2@example.com", subscription_active=True),
                User(id=21, email="manager-fx@example.com", password_hash="test", is_active=True, is_verified=True),
            ]
        )
        db.commit()

    with TestClient(main_module.app) as client:
        yield client, SessionLocal, auth_state

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_create_fx_snapshot(fx_client):
    client, SessionLocal, _ = fx_client

    response = client.post("/api/fx/snapshot")

    assert response.status_code == 201, response.text
    assert response.json()["stored"] == 7
    with SessionLocal() as db:
        rows = db.query(FxRateSnapshot).filter(FxRateSnapshot.hotel_id == 1).all()
        assert {row.rate_type for row in rows} == {
            "oficial", "blue", "eur_oficial", "eur_blue", "brl_oficial", "clp_oficial", "uyu_oficial"
        }


def test_get_rate_snapshot_by_date(fx_client):
    client, _, _ = fx_client
    create = client.post("/api/fx/snapshot")
    assert create.status_code == 201, create.text

    all_snapshots = client.get("/api/fx/snapshots", params={"rate_type": "oficial"})
    assert all_snapshots.status_code == 200, all_snapshots.text
    fetched_date = datetime.fromisoformat(all_snapshots.json()[0]["fetched_at"]).date().isoformat()

    response = client.get(
        "/api/fx/snapshots",
        params={"from": fetched_date, "to": fetched_date, "rate_type": "oficial"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["rate_type"] == "oficial"
    assert payload[0]["venta"] == 920.0

    direct_currency = client.get("/api/fx/snapshots", params={"rate_type": "eur_oficial"})
    assert direct_currency.status_code == 200, direct_currency.text
    assert len(direct_currency.json()) == 1
    assert direct_currency.json()[0]["rate_type"] == "eur_oficial"
    assert direct_currency.json()[0]["provider_market"] == "oficial"

    derived_currency = client.get("/api/fx/snapshots", params={"rate_type": "eur_blue"})
    assert derived_currency.status_code == 200, derived_currency.text
    assert len(derived_currency.json()) == 1
    assert derived_currency.json()[0]["rate_type"] == "eur_blue"
    assert derived_currency.json()[0]["provider_market"] == "blue_derivado"

    disallowed_usd_market = client.get("/api/fx/snapshots", params={"rate_type": "tarjeta"})
    assert disallowed_usd_market.status_code == 422


def test_fx_snapshots_are_hotel_scoped(fx_client):
    client, SessionLocal, auth_state = fx_client
    create = client.post("/api/fx/snapshot")
    assert create.status_code == 201, create.text

    auth_state["hotel_id"] = 2
    response = client.get("/api/fx/snapshots")

    assert response.status_code == 200, response.text
    assert response.json() == []

    with SessionLocal() as db:
        db.add(
            FxRateSnapshot(
                hotel_id=None,
                rate_type="oficial",
                moneda="USD",
                compra=910.0,
                venta=930.0,
                source="dolarapi.com",
            )
        )
        db.commit()

    platform_response = client.get("/api/fx/snapshots", params={"rate_type": "oficial"})
    assert platform_response.status_code == 200, platform_response.text
    assert [row["hotel_id"] for row in platform_response.json()] == [None]


@pytest.mark.parametrize("path", ["/api/fx/rates", "/fx/rates"])
def test_generic_fx_list_exposes_only_supported_conversion_quotes(fx_client, monkeypatch, path):
    client, _, _ = fx_client
    async def fake_rates():
        return {
            "oficial": {"moneda": "USD", "compra": 1000, "venta": 1010},
            "blue": {"moneda": "USD", "compra": 1100, "venta": 1110},
            "eur": {"moneda": "EUR", "compra": 1200, "venta": 1210},
            "brl": {"moneda": "BRL", "compra": 200, "venta": 210},
            "clp": {"moneda": "CLP", "compra": 1, "venta": 1.1},
            "uyu": {"moneda": "UYU", "compra": 25, "venta": 26},
            "eur_blue": {"moneda": "EUR", "casa": "blue_derivado", "compra": 2200, "venta": 2210},
            "brl_blue": {"moneda": "BRL", "casa": "blue_derivado", "compra": 400, "venta": 410},
            "clp_blue": {"moneda": "CLP", "casa": "blue_derivado", "compra": 2, "venta": 2.1},
            "uyu_blue": {"moneda": "UYU", "casa": "blue_derivado", "compra": 50, "venta": 51},
            "tarjeta": {"moneda": "USD", "compra": 1400, "venta": 1500},
            "bolsa": {"moneda": "USD", "compra": 1300, "venta": 1310},
            "contadoconliqui": {"moneda": "USD", "compra": 1300, "venta": 1310},
            "cripto": {"moneda": "USD", "compra": 1500, "venta": 1600},
            "mayorista": {"moneda": "USD", "compra": 900, "venta": 910},
        }

    monkeypatch.setattr(fx_rates_module, "fetch_all_rates", fake_rates)
    response = client.get(path)

    assert response.status_code == 200, response.text
    assert {item["type"] for item in response.json()} == {
        "oficial", "blue", "eur", "brl", "clp", "uyu",
        "eur_blue", "brl_blue", "clp_blue", "uyu_blue",
    }


def test_single_fx_quote_endpoint_rejects_other_usd_markets(fx_client):
    client, _, _ = fx_client

    response = client.get("/api/fx/rates/tarjeta")

    assert response.status_code == 422


def test_single_fx_quote_endpoint_exposes_derived_blue_currency(fx_client, monkeypatch):
    client, _, _ = fx_client

    async def fake_quote(rate_type):
        assert rate_type == "eur_blue"
        return {
            "type": "eur_blue",
            "moneda": "EUR",
            "casa": "blue_derivado",
            "compra": 1100,
            "venta": 1120,
        }

    monkeypatch.setattr(fx_rates_module, "fetch_rate", fake_quote)
    response = client.get("/api/fx/rates/eur_blue")

    assert response.status_code == 200, response.text
    assert response.json()["type"] == "eur_blue"
    assert response.json()["casa"] == "blue_derivado"


def test_current_conversion_quote_returns_configured_cross_currency_rate_without_writing_snapshot(
    fx_client, monkeypatch
):
    client, SessionLocal, _ = fx_client
    with SessionLocal() as db:
        config = db.get(HotelConfiguration, 1)
        config.fx_conversion_rate_type = "blue"
        db.commit()

    def quote(db, *, hotel_id, amount, from_currency, to_currency, fx_policy_id, provider_code, persist_snapshots):
        assert hotel_id == 1
        assert amount == 1.0
        assert from_currency == "EUR"
        assert to_currency == "UYU"
        assert fx_policy_id is None
        assert provider_code is None
        assert persist_snapshots is False
        return 1.25, 1.25, {
            "provider": "dolarapi.com",
            "configured_usd_market": "blue",
            "path": "via_ars",
            "source_quote": {"currency": "EUR", "is_derived_blue": True},
            "target_quote": {"currency": "UYU", "is_derived_blue": True},
        }

    monkeypatch.setattr(fx_rates_module, "_convert_amount", quote)
    response = client.post(
        "/api/fx/conversion-quote",
        json={"from_currency": "EUR", "to_currency": "UYU"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["rate"] == 1.25
    assert payload["provider"] == "dolarapi.com"
    assert payload["configured_market"] == "blue"
    assert payload["quote_details"]["source_quote"]["is_derived_blue"] is True
    with SessionLocal() as db:
        assert db.query(FxRateSnapshot).filter(FxRateSnapshot.hotel_id == 1).count() == 0
