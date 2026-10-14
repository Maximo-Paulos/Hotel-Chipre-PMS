"""Comprueba tres hallazgos de la lectura completa contra la app real (PostgreSQL migrada).

    DATABASE_URL=postgresql+psycopg2://USER:PASS@127.0.0.1:5440/hotel_measure \
    APP_ENV=development python docs/audits/perf-2026-10-13/scripts/verify_misc_findings.py
"""
import os

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import app.database as appdb
from app.database import get_engine
from app.main import app
from app.schemas.onboarding import PaymentMethodsPayload, ProviderSetupPayload
from app.services import onboarding_service

engine = get_engine(os.environ["DATABASE_URL"])
appdb._engine = engine
appdb._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
client = TestClient(app)

# 1) /health/datastores es público
r = client.get("/health/datastores")
print("GET /health/datastores sin autenticación ->", r.status_code, sorted(r.json().keys()))

# 2) api/connections.py no está montado: el catch-all de main.py responde 410
r = client.post("/api/connections/mercadopago/connect", json={"credentials": {"k": "v"}})
print("POST /api/connections/mercadopago/connect ->", r.status_code)

# 3) el asistente de onboarding guarda credenciales de proveedores en texto plano
# El modelo de suscripciones existe en el ORM pero no tiene migración Alembic (deriva conocida):
# se crean esas cuatro tablas solo en esta base descartable para poder ejecutar el flujo.
from app.database import Base

drift = ["hotel_entitlement_overrides", "hotel_subscriptions", "subscription_entitlements", "subscription_plans"]
Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables[t] for t in drift], checkfirst=True)
db = appdb._SessionLocal()
payload = PaymentMethodsPayload(
    enable_cash=True,
    mercado_pago=ProviderSetupPayload(enabled=True, credentials={"access_token": "APP_USR-SECRETO-DE-PRUEBA"}),
)
onboarding_service.upsert_payment_methods(db, payload, hotel_id=1)
db.commit()
stored = db.execute(text("select payment_methods_json from onboarding_state where hotel_id = 1")).scalar()
print("onboarding_state.payment_methods_json contiene el secreto en claro:", "APP_USR-SECRETO-DE-PRUEBA" in (stored or ""))
db.close()
