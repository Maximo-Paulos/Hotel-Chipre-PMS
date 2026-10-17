"""Repro: el registro de auditoría escrito DESPUÉS de db.commit() se pierde en PostgreSQL (persiste en SQLite por una rareza del SAVEPOINT).
Uso: REPO=<raíz> REPRO_DATABASE_URL=postgresql+psycopg2://... python audit_loss_repro.py  (sin la variable usa SQLite)."""
import os, sys, tempfile
os.environ["ANALYTICS_FACTS_SYNC_ON_WRITE"]="true"
sys.path.insert(0,os.environ.get("REPO",os.getcwd()))
from app.config import Settings
Settings.model_config["env_file"]=None
from datetime import date, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.audit_log import AuditLog
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User

tmp=tempfile.mkdtemp()
url=os.environ.get("REPRO_DATABASE_URL")  # p.ej. postgresql+psycopg2://USER@127.0.0.1:5440/auditexp (base DESCARTABLE)
engine=create_engine(url) if url else create_engine(f"sqlite:///{tmp}/t.db", connect_args={"check_same_thread":False})
SL=sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(engine)
db=SL()
db.add(HotelConfiguration(id=1,hotel_name="x",subscription_active=True))
db.add(User(id=10,email="o@example.test",password_hash="x",is_verified=True)); db.flush()
db.add(HotelMembership(hotel_id=1,user_id=10,role="owner",status="active"))
cat=RoomCategory(hotel_id=1,name="S",code="S",base_price_per_night=Decimal("100"),max_occupancy=2); db.add(cat); db.flush()
room=Room(hotel_id=1,category_id=cat.id,room_number="1",floor=1,status=RoomStatusEnum.AVAILABLE)
g=Guest(hotel_id=1,first_name="A",last_name="B"); db.add_all([room,g]); db.flush()
def mk(code, off):
    r=Reservation(hotel_id=1,guest_id=g.id,category_id=cat.id,room_id=room.id,confirmation_code=code,
      check_in_date=date.today()+timedelta(days=off),check_out_date=date.today()+timedelta(days=off+2),
      status=ReservationStatusEnum.PENDING,total_amount=Decimal("200"),num_adults=1)
    db.add(r); return r
r1=mk("C1",5); r2=mk("C2",20); db.commit()
ids=(r1.id,r2.id)
def override_db():
    s=SL()   # a fresh, real per-request session like get_db
    try: yield s
    finally: s.close()
def override_auth():
    return AuthContext(hotel_id=1,user_id=10,user_email="o@example.test",user_role="owner",is_verified=True,permissions=set())
app.dependency_overrides[get_db]=override_db
app.dependency_overrides[get_auth_context]=override_auth
c=TestClient(app)
def audits(rid):
    s=SL()
    try:
        return [(a.action.value if hasattr(a.action,'value') else a.action) for a in s.query(AuditLog).filter_by(table_name="reservations",record_id=rid).all()]
    finally: s.close()
resp=c.post(f"/api/reservations/{ids[0]}/cancel")
print("cancel", resp.status_code, "audit rows after cancel:", audits(ids[0]))
resp=c.post(f"/api/reservations/{ids[1]}/noshow", json={"client_version": 1})
print("noshow", resp.status_code, resp.text[:120], "audit rows after noshow:", audits(ids[1]))
