"""Seed a realistic one-hotel history for profiling (disposable local DB only).

Usage: DATABASE_URL=... python seed_profile.py [rooms] [guests] [reservations]
"""
import os, sys, random, string
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

os.environ.setdefault("APP_ENV", "development")
sys.path.insert(0, os.environ.get("REPO", "."))

url = os.environ["DATABASE_URL"]
assert "127.0.0.1:5440" in url, "refusing to seed anything but the local scratch Postgres"

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from app.database import get_engine
from app.models import (
    CategoryPricing, Guest, HotelConfiguration, HotelMembership, OnboardingState,
    Reservation, Room, RoomCategory, Subscription, TaxPolicy, User, Transaction,
)
from app.models.reservation import (
    ReservationChannelCodeEnum, ReservationGuestSegmentEnum, ReservationGuestSegmentSourceEnum,
    ReservationOutcomeEnum, ReservationSourceEnum, ReservationStatusEnum,
)
from app.models.transaction import PaymentMethodEnum, TransactionStatusEnum, TransactionTypeEnum
from app.services.security import hash_password

N_ROOMS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
N_GUESTS = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
N_RES = int(sys.argv[3]) if len(sys.argv) > 3 else 6500

random.seed(42)
engine = get_engine(url)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
now = datetime.now(timezone.utc).replace(tzinfo=None)
today = date.today()

FIRST = ["Juan", "Maria", "Pedro", "Lucia", "Carlos", "Ana", "Diego", "Sofia", "Martin", "Laura", "Jorge", "Paula", "Pablo", "Valeria", "Hernan", "Camila"]
LAST = ["Perez", "Gomez", "Rodriguez", "Fernandez", "Lopez", "Martinez", "Sanchez", "Romero", "Diaz", "Alvarez", "Torres", "Ruiz", "Suarez", "Acosta", "Benitez", "Molina"]


def seed_hotel(H):
    with Session() as db:
        db.execute(text("SELECT set_config('app.master_admin','true',false)"))
        hotel = db.get(HotelConfiguration, H) or HotelConfiguration(id=H)
        db.add(hotel)
        hotel.hotel_name = "Hotel Perfil"; hotel.owner_email = f"owner{H}@perf.test"; hotel.subscription_active = True
        hotel.default_currency = "ARS"; hotel.hotel_timezone = "America/Argentina/Buenos_Aires"
        hotel.enable_bank_transfer = True; hotel.deposit_percentage = 30.0; hotel.deposit_policy_configured = True
        hotel.free_cancellation_hours = 48; hotel.cancellation_penalty_percentage = 0.0; hotel.updated_at = now
        db.flush()
        db.add(TaxPolicy(hotel_id=H, code="NOTAX", name="No tax", taxes_included=True, apply_vat_by_default=False, vat_rate=0.0, is_active=True))
        sub = Subscription(hotel_id=H, plan="pro", status="active", room_limit=80, staff_limit=20, can_write_cache=True, updated_at=now)
        db.add(sub)
        users = {}
        for role in ("owner", "manager", "reception", "housekeeping"):
            u = User(email=f"{role}{H}@perf.test", password_hash=hash_password("PerfPass1234!"), is_active=True, is_verified=True, role=role)
            db.add(u); db.flush(); users[role] = u
            db.add(HotelMembership(hotel_id=H, user_id=u.id, role=role, status="active"))
        ob = OnboardingState(hotel_id=H, owner_name="Owner", owner_email=f"owner{H}@perf.test", owner_phone="1", owner_role="owner",
                             identity_set=True, policy_set=True, payments_set=True, ota_set=True, subscription_set=True, finished=True,
                             hotel_identity_json='{"name": "Hotel Perfil", "address": "Calle 1", "city": "BA", "country": "AR"}',
                             deposit_policy_json='{"deposit_percentage": 30, "enable_full_payment": true}',
                             payment_methods_json='{"cash": {"enabled": true}}', ota_channels_json='{"booking": {"enabled": false}}',
                             subscription_choice_json='{"plan": "pro"}', staff_json="[]", updated_at=now)
        db.add(ob)
        cats = []
        for code, name, price in (("DBL", "Doble", 85000), ("TWN", "Twin", 85000), ("SUP", "Superior", 120000), ("FAM", "Familiar", 165000)):
            c = RoomCategory(hotel_id=H, code=code, name=name, base_price_per_night=price, max_occupancy=3)
            db.add(c); db.flush(); db.add(CategoryPricing(category_id=c.id, price_cash=price)); cats.append(c)
        rooms = []
        for i in range(N_ROOMS):
            r = Room(hotel_id=H, room_number=str(100 * (1 + i // 10) + (i % 10) + 1), floor=1 + i // 10, category_id=cats[i % 4].id, status="available", is_active=True)
            db.add(r); rooms.append(r)
        db.flush()
        guests = []
        for i in range(N_GUESTS):
            g = Guest(hotel_id=H, first_name=random.choice(FIRST), last_name=random.choice(LAST) + str(i % 50), document_type="DNI",
                      document_number=f"{20000000 + i}", email=f"g{i}@mail.test", phone=f"+54911{random.randint(10000000, 99999999)}",
                      terms_accepted=True, nationality="AR", city="CABA", country="AR")
            guests.append(g)
        db.add_all(guests); db.flush()
        db.commit()

    # reservations, bulk, spread over the previous ~2 years and next ~60 days
    with Session() as db:
        db.execute(text("SELECT set_config('app.master_admin','true',false)"))
        rooms = db.query(Room).filter(Room.hotel_id == H).all()
        guest_ids = [g.id for g in db.query(Guest.id).filter(Guest.hotel_id == H).all()]
        guest_ids = [g[0] if isinstance(g, tuple) else g for g in guest_ids]
        cat_price = {c.id: Decimal(str(c.base_price_per_night)) for c in db.query(RoomCategory).filter(RoomCategory.hotel_id == H).all()}
        start_window = today - timedelta(days=730)
        res_objs = []
        codes = set()
        for i in range(N_RES):
            room = random.choice(rooms)
            nights = random.choice([1, 2, 2, 3, 3, 4, 5, 7])
            ci = start_window + timedelta(days=random.randint(0, 790))
            co = ci + timedelta(days=nights)
            if co < today - timedelta(days=1):
                status = random.choices([ReservationStatusEnum.CHECKED_OUT, ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW], [88, 9, 3])[0]
            elif ci > today:
                status = random.choices([ReservationStatusEnum.PENDING, ReservationStatusEnum.DEPOSIT_PAID, ReservationStatusEnum.FULLY_PAID, ReservationStatusEnum.CANCELLED], [20, 40, 35, 5])[0]
            else:
                status = ReservationStatusEnum.CHECKED_IN
            total = cat_price[room.category_id] * nights
            while True:
                code = f"H{H}-" + "".join(random.choices(string.digits, k=8))
                if code not in codes:
                    codes.add(code); break
            paid = Decimal(0)
            if status in (ReservationStatusEnum.CHECKED_OUT, ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.FULLY_PAID):
                paid = total
            elif status == ReservationStatusEnum.DEPOSIT_PAID:
                paid = (total * Decimal("0.3")).quantize(Decimal("0.01"))
            outcome = {ReservationStatusEnum.CHECKED_OUT: ReservationOutcomeEnum.COMPLETED, ReservationStatusEnum.CANCELLED: ReservationOutcomeEnum.CANCELLED,
                       ReservationStatusEnum.NO_SHOW: ReservationOutcomeEnum.NO_SHOW, ReservationStatusEnum.CHECKED_IN: ReservationOutcomeEnum.CHECKED_IN}.get(status, ReservationOutcomeEnum.PENDING)
            res_objs.append(Reservation(
                confirmation_code=code, hotel_id=H, guest_id=random.choice(guest_ids), room_id=room.id, category_id=room.category_id,
                check_in_date=ci, check_out_date=co, total_amount=total, amount_paid=paid, subtotal_amount=total, net_amount=total,
                deposit_amount=(total * Decimal("0.3")).quantize(Decimal("0.01")), status=status, outcome=outcome,
                guest_segment=ReservationGuestSegmentEnum.LEISURE, guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
                channel_code=random.choice(list(ReservationChannelCodeEnum)), source=ReservationSourceEnum.DIRECT,
                num_adults=2, num_children=0, created_at=datetime.combine(ci, datetime.min.time()) - timedelta(days=random.randint(1, 60)),
                updated_at=now))
        db.bulk_save_objects(res_objs, return_defaults=True)
        db.flush()
        n_tx = 0
        tx_objs = []
        for r in res_objs:
            if r.amount_paid and r.amount_paid > 0:
                tx_objs.append(Transaction(hotel_id=H, reservation_id=r.id, amount=r.amount_paid, currency="ARS",
                                           transaction_type=TransactionTypeEnum.FULL_PAYMENT if r.amount_paid >= r.total_amount else TransactionTypeEnum.DEPOSIT,
                                           payment_method=random.choice([PaymentMethodEnum.CASH, PaymentMethodEnum.BANK_TRANSFER, PaymentMethodEnum.CREDIT_CARD]),
                                           status=TransactionStatusEnum.COMPLETED, created_at=r.created_at, updated_at=now))
        db.bulk_save_objects(tx_objs)
        db.commit()
        print(f"seeded rooms={len(rooms)} guests={len(guest_ids)} reservations={len(res_objs)} transactions={len(tx_objs)}")

for H in range(int(sys.argv[4]), int(sys.argv[5])+1):
    seed_hotel(H)
