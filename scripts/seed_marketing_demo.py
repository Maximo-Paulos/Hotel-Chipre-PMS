"""Seed a demo hotel that looks like a real one, for marketing screenshots.

The E2E seed exists to make assertions pass, so it ships two rooms, one guest
called "Huesped E2E" and a hotel named "Hotel Chipre E2E con un nombre
operacionalmente largo". None of that can go on a public page. This builds a
plausible Bariloche hotel instead: four categories, twenty rooms, a week of
reservations across every state, an open cash session with real movements,
stock and laundry.

It refuses to touch anything but its own SQLite file, so it can never be
pointed at a real database.

    python scripts/seed_marketing_demo.py
"""
from __future__ import annotations

import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEMO_DATABASE_PATH = ROOT_DIR / "demo-marketing.db"
DEMO_DATABASE_URL = f"sqlite:///{DEMO_DATABASE_PATH.as_posix()}"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

OWNER_EMAIL = "ana@hotelchipre.com.ar"
OWNER_PASSWORD = "DemoChipre1234!"

# Deterministic so re-running produces the same screenshots.
random.seed(20260910)


def _prepare_environment() -> str:
    os.environ["APP_ENV"] = "test"
    os.environ["DATABASE_URL"] = DEMO_DATABASE_URL
    os.environ.setdefault("JWT_SECRET", "demo-marketing-jwt-secret-32-chars-min")
    os.environ.setdefault("SUBSCRIPTION_ENFORCEMENT", "false")
    return DEMO_DATABASE_URL


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    config.set_main_option("prepend_sys_path", str(ROOT_DIR))
    command.upgrade(config, "head")


CATEGORIES = [
    ("STD", "Standard", 78_000, 2),
    ("SUP", "Superior con vista", 96_000, 2),
    ("FAM", "Familiar", 128_000, 4),
    ("SUI", "Suite", 175_000, 2),
]

# room number -> category code
ROOMS = (
    [(f"10{n}", "STD") for n in range(1, 7)]
    + [(f"20{n}", "SUP") for n in range(1, 6)]
    + [(f"21{n}", "FAM") for n in range(1, 4)]
    + [(f"30{n}", "SUI") for n in range(1, 3)]
)

GUESTS = [
    ("Valentina", "Ferrari", "San Isidro", "valentina.ferrari@example.com"),
    ("Martín", "Quiroga", "Rosario", "m.quiroga@example.com"),
    ("Lucía", "Benítez", "Córdoba", "lucia.benitez@example.com"),
    ("Diego", "Lombardi", "La Plata", "d.lombardi@example.com"),
    ("Sofía", "Arrieta", "Mendoza", "sofia.arrieta@example.com"),
    ("Nicolás", "Cabrera", "Bahía Blanca", "n.cabrera@example.com"),
    ("Camila", "Ruiz Díaz", "Posadas", "camila.ruizdiaz@example.com"),
    ("Julián", "Sosa", "Neuquén", "julian.sosa@example.com"),
    ("Agustina", "Ojeda", "Santa Fe", "a.ojeda@example.com"),
    ("Federico", "Villalba", "Tucumán", "f.villalba@example.com"),
    ("Paula", "Genovese", "Mar del Plata", "paula.genovese@example.com"),
    ("Ignacio", "Peralta", "Salta", "i.peralta@example.com"),
]

CHANNELS = ["website_direct", "booking", "whatsapp", "phone", "expedia", "walk_in"]


def seed() -> None:
    database_url = _prepare_environment()

    from app.database import get_session_factory, init_db
    from app.models import (
        CategoryPricing,
        Guest,
        HotelConfiguration,
        HotelMembership,
        OnboardingState,
        Reservation,
        Room,
        RoomCategory,
        StockItem,
        StockLocation,
        StockMovement,
        Subscription,
        User,
    )
    from app.models.cash_register import CashMovement, CashSession
    from app.services.security import hash_password

    init_db(database_url)
    session_factory = get_session_factory()

    with session_factory() as db:
        now = datetime.now(timezone.utc)
        today = date.today()

        hotel = db.get(HotelConfiguration, 1) or HotelConfiguration(id=1)
        hotel.hotel_name = "Hotel Chipre"
        hotel.owner_email = OWNER_EMAIL
        hotel.subscription_active = True
        hotel.default_currency = "ARS"
        hotel.hotel_timezone = "America/Argentina/Buenos_Aires"
        hotel.enable_bank_transfer = True
        hotel.updated_at = now
        db.add(hotel)

        subscription = db.query(Subscription).filter(Subscription.hotel_id == 1).first()
        if subscription is None:
            subscription = Subscription(hotel_id=1)
            db.add(subscription)
        subscription.plan = "pro"
        subscription.status = "active"
        subscription.room_limit = 40
        subscription.staff_limit = 8
        subscription.can_write_cache = True
        subscription.updated_at = now

        owner = db.query(User).filter(User.email.ilike(OWNER_EMAIL)).first()
        if owner is None:
            owner = User(email=OWNER_EMAIL)
            db.add(owner)
        owner.password_hash = hash_password(OWNER_PASSWORD)
        owner.is_active = True
        owner.is_verified = True
        owner.role = "owner"
        db.flush()

        membership = (
            db.query(HotelMembership)
            .filter(HotelMembership.hotel_id == 1, HotelMembership.user_id == owner.id)
            .first()
        )
        if membership is None:
            membership = HotelMembership(hotel_id=1, user_id=owner.id)
            db.add(membership)
        membership.role = "owner"
        membership.status = "active"

        # Onboarding already finished: a screenshot must open on the dashboard,
        # never on the setup wizard. Every gate in
        # onboarding_service._status_from_state has to be satisfied, so each
        # step gets both its payload and its boolean.
        onboarding = db.get(OnboardingState, 1)
        if onboarding is None:
            onboarding = OnboardingState(hotel_id=1)
            db.add(onboarding)
        onboarding.owner_name = "Ana Lauría"
        onboarding.owner_email = OWNER_EMAIL
        onboarding.owner_phone = "+54 9 294 460 1180"
        onboarding.owner_role = "Dueña"
        onboarding.set_hotel_identity(
            {
                "legal_name": "Hotel Chipre S.R.L.",
                "tax_id": "30-71234567-9",
                "address": "Av. Bustillo 2400",
                "city": "San Carlos de Bariloche",
                "country": "Argentina",
                "timezone": "America/Argentina/Buenos_Aires",
                "currency": "ARS",
            }
        )
        onboarding.identity_set = True
        onboarding.set_deposit_policy(
            {"deposit_percentage": 30, "cancellation_hours": 48, "no_show_policy": "charge_first_night"}
        )
        onboarding.policy_set = True
        onboarding.set_payment_methods(
            {"cash": True, "bank_transfer": True, "mercadopago": True, "card": True}
        )
        onboarding.payments_set = True
        onboarding.set_ota_channels(
            {"booking": {"enabled": True}, "expedia": {"enabled": True}, "despegar": {"enabled": False}}
        )
        onboarding.ota_set = True
        onboarding.set_subscription_choice({"plan": "pro"})
        onboarding.subscription_set = True
        onboarding.set_staff(
            [
                {"name": "Ana Lauría", "email": OWNER_EMAIL, "role": "owner"},
                {"name": "Marcos Iriarte", "email": "marcos@hotelchipre.com.ar", "role": "receptionist"},
                {"name": "Rosa Aguirre", "email": "rosa@hotelchipre.com.ar", "role": "housekeeping"},
            ]
        )
        onboarding.finished = True
        onboarding.updated_at = now

        categories: dict[str, RoomCategory] = {}
        for code, name, price, occupancy in CATEGORIES:
            category = (
                db.query(RoomCategory)
                .filter(RoomCategory.hotel_id == 1, RoomCategory.code == code)
                .first()
            )
            if category is None:
                category = RoomCategory(hotel_id=1, code=code)
                db.add(category)
            category.name = name
            category.base_price_per_night = price
            category.max_occupancy = occupancy
            db.flush()
            if db.get(CategoryPricing, category.id) is None:
                db.add(CategoryPricing(category_id=category.id, price_cash=price))
            categories[code] = category

        rooms: dict[str, Room] = {}
        for number, category_code in ROOMS:
            room = db.query(Room).filter(Room.hotel_id == 1, Room.room_number == number).first()
            if room is None:
                room = Room(hotel_id=1, room_number=number)
                db.add(room)
            room.floor = int(number[0])
            room.category_id = categories[category_code].id
            room.status = "available"
            room.is_active = True
            db.flush()
            rooms[number] = room

        guests: list[Guest] = []
        for index, (first, last, city, email) in enumerate(GUESTS, start=1):
            guest = (
                db.query(Guest)
                .filter(Guest.hotel_id == 1, Guest.document_number == f"3{index:07d}")
                .first()
            )
            if guest is None:
                guest = Guest(hotel_id=1, document_number=f"3{index:07d}")
                db.add(guest)
            guest.first_name = first
            guest.last_name = last
            guest.document_type = "DNI"
            guest.email = email
            guest.phone = f"+54 9 11 {4000 + index} {1000 + index * 7}"
            guest.city = city
            guest.country = "Argentina"
            guest.terms_accepted = True
            db.flush()
            guests.append(guest)

        # A week of stays spread across states, so the occupancy grid and the
        # reservation list both look like a hotel mid-season.
        if db.query(Reservation).filter(Reservation.hotel_id == 1).count() == 0:
            room_numbers = [number for number, _ in ROOMS]
            plan = [
                # (room, guest index, offset from today, nights, status)
                ("101", 0, -2, 4, "checked_in"),
                ("102", 1, -1, 5, "checked_in"),
                ("103", 2, 0, 2, "deposit_paid"),
                ("104", 3, 1, 3, "fully_paid"),
                ("105", 4, -3, 3, "checked_out"),
                ("106", 5, 2, 4, "deposit_paid"),
                ("201", 6, -1, 6, "checked_in"),
                ("202", 7, 0, 3, "checked_in"),
                ("203", 8, 3, 2, "pending"),
                ("204", 9, 1, 4, "deposit_paid"),
                ("211", 10, -2, 5, "checked_in"),
                ("301", 11, 0, 4, "fully_paid"),
                ("205", 0, 4, 3, "pending"),
                ("212", 2, 2, 2, "deposit_paid"),
                ("302", 4, 1, 5, "checked_in"),
            ]
            for index, (room_number, guest_index, offset, nights, status) in enumerate(plan):
                room = rooms[room_number]
                guest = guests[guest_index % len(guests)]
                category = db.get(RoomCategory, room.category_id)
                nightly = Decimal(str(category.base_price_per_night or 80_000))
                total = nightly * nights
                paid = {
                    "checked_in": total,
                    "checked_out": total,
                    "fully_paid": total,
                    "deposit_paid": (total * Decimal("0.3")).quantize(Decimal("0.01")),
                    "pending": Decimal("0.00"),
                }[status]
                check_in = today + timedelta(days=offset)
                db.add(
                    Reservation(
                        confirmation_code=f"CHP-{2600 + index}",
                        hotel_id=1,
                        guest_id=guest.id,
                        room_id=room.id,
                        category_id=room.category_id,
                        check_in_date=check_in,
                        check_out_date=check_in + timedelta(days=nights),
                        actual_check_in=now if status in ("checked_in", "checked_out") else None,
                        actual_check_out=now if status == "checked_out" else None,
                        total_amount=total,
                        amount_paid=paid,
                        subtotal_amount=total,
                        net_amount=total,
                        currency_code="ARS",
                        status=status,
                        channel_code=CHANNELS[index % len(CHANNELS)],
                        source="booking" if CHANNELS[index % len(CHANNELS)] == "booking" else "direct",
                        num_adults=2 if (category.max_occupancy or 2) <= 2 else 3,
                        num_children=0,
                    )
                )
                if status in ("checked_in", "checked_out"):
                    room.status = "occupied"
            db.flush()

        # An open shift with movements, so /caja is not an empty form.
        if db.query(CashSession).filter(CashSession.hotel_id == 1).count() == 0:
            session = CashSession(
                hotel_id=1,
                opened_by_user_id=owner.id,
                status="open",
                opening_balance=Decimal("45000.00"),
                currency_code="ARS",
                opened_at=now - timedelta(hours=6),
                notes="Turno mañana",
            )
            db.add(session)
            db.flush()
            movements = [
                ("income", "128400.00", "Cobro reserva CHP-2600 · efectivo"),
                ("income", "96000.00", "Cobro reserva CHP-2606 · transferencia"),
                ("income", "78000.00", "Seña reserva CHP-2603 · MercadoPago"),
                ("expense", "18500.00", "Compra de amenities"),
                ("income", "175000.00", "Cobro reserva CHP-2611 · tarjeta"),
                ("expense", "22000.00", "Retiro de proveedor de lavandería"),
            ]
            for offset, (movement_type, amount, description) in enumerate(movements):
                db.add(
                    CashMovement(
                        hotel_id=1,
                        session_id=session.id,
                        recorded_by_user_id=owner.id,
                        movement_type=movement_type,
                        amount=Decimal(amount),
                        description=description,
                        recorded_at=now - timedelta(hours=5 - offset * 0.7),
                    )
                )

        if db.query(StockLocation).filter(StockLocation.hotel_id == 1).count() == 0:
            deposit = StockLocation(hotel_id=1, name="Depósito central")
            db.add(deposit)
            db.flush()
            # Stock levels are derived from movements, not stored on the item,
            # so each item gets an opening entry the same way the app records it.
            for name, unit, quantity, minimum in [
                ("Toallón blanco 70x140", "unidad", 148, 60),
                ("Sábana plaza y media", "unidad", 96, 48),
                ("Shampoo 30 ml", "unidad", 320, 150),
                ("Papel higiénico", "rollo", 240, 120),
                ("Café en grano", "kg", 12, 8),
                ("Detergente industrial", "litro", 34, 20),
            ]:
                item = StockItem(hotel_id=1, name=name, unit=unit, min_quantity=minimum, active=True)
                db.add(item)
                db.flush()
                db.add(
                    StockMovement(
                        hotel_id=1,
                        item_id=item.id,
                        location_id=deposit.id,
                        movement_type="in",
                        quantity=Decimal(str(quantity)),
                        reason="Carga inicial de temporada",
                        created_by_user_id=owner.id,
                        created_at=now - timedelta(days=9),
                    )
                )

        db.commit()

    print(f"Demo hotel seeded at {DEMO_DATABASE_PATH}")
    print(f"  login: {OWNER_EMAIL} / {OWNER_PASSWORD}")


if __name__ == "__main__":
    _prepare_environment()
    run_migrations()
    seed()
