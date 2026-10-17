"""Verifica si una clave de API pública `web_engine` puede leer el documento de un huésped
ajeno creando una reserva con `guest_id` elegido por el cliente.

    DATABASE_URL=postgresql+psycopg2://USER:PASS@127.0.0.1:5440/hotel_measure \
    APP_ENV=development python docs/audits/perf-2026-10-13/scripts/verify_public_booking_pii.py
"""
import os
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import app.database as appdb
from app.database import get_engine
from app.main import app
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_api_key import APIKeyPurposeEnum
from app.models.room import Room, RoomCategory
from app.services.hotel_api_key_service import issue_key

engine = get_engine(os.environ["DATABASE_URL"])
appdb._engine = engine
appdb._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = appdb._SessionLocal()

from app.models.hotel_config import HotelConfiguration
cfg = db.get(HotelConfiguration, 1)
cfg.deposit_policy_configured = True
from app.models.commercial import TaxPolicy
db.add(TaxPolicy(hotel_id=1, code="IVA", name="IVA", taxes_included=True, apply_vat_by_default=True, vat_rate=21, is_active=True))
category = RoomCategory(hotel_id=1, name="Doble", code="DBL", base_price_per_night=100, max_occupancy=2)
db.add(category)
db.flush()
db.add(Room(hotel_id=1, room_number="101", floor=1, category_id=category.id, status="available", is_active=True))
victim = Guest(hotel_id=1, first_name="Ana", last_name="Pérez", document_type=DocumentTypeEnum.DNI, document_number="30123456", email="ana@example.com")
db.add(victim)
db.flush()
_key, secret = issue_key(db, hotel_id=1, name="pii", purpose=APIKeyPurposeEnum.WEB_ENGINE, created_by_user_id=None, expires_at=None)
db.commit()
victim_id, category_id = victim.id, category.id
db.close()

client = TestClient(app)
headers = {"X-API-Key": secret}
start = date.today() + timedelta(days=30)
end = start + timedelta(days=2)
quote = client.get("/api/public/booking/rates", headers=headers, params={
    "category_id": category_id, "check_in_date": start.isoformat(), "check_out_date": end.isoformat()})
print("cotización:", quote.status_code)
token = quote.json().get("quote_token") if quote.status_code == 200 else None
if token:
    r = client.post("/api/public/booking/reservations", headers=headers, json={
        "guest_id": victim_id, "category_id": category_id, "check_in_date": start.isoformat(),
        "check_out_date": end.isoformat(), "quote_token": token})
    print("reserva a nombre de guest_id ajeno:", r.status_code)
    body = r.json()
    print("guest devuelto al portador de la clave:", body.get("guest"))
else:
    print(quote.text[:400])
