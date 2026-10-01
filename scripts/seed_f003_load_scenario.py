"""Load the synthetic 30-room, 45-reservation F-003 PostgreSQL fixture.

This scenario is intentionally separate from the shared E2E seed. It can only
run against a fresh, explicitly isolated loopback PostgreSQL database reserved
for the F-003 load run.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import MutableMapping
from zoneinfo import ZoneInfo

from scripts import seed_e2e_backend


F003_LOAD_OPT_IN = "E2E_F003_LOAD"
F003_DATABASE_PATTERN = re.compile(r"hotel_chipre_e2e_f003_load_[a-z0-9_]+\Z")
HOTEL_TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


def _validated_target(env: MutableMapping[str, str]) -> tuple[str, dict[str, object], str, dict[str, object]]:
    """Validate opt-in and both isolated PostgreSQL identities before DB imports."""
    if (env.get(F003_LOAD_OPT_IN) or "").strip().casefold() not in {"1", "true", "yes", "on"}:
        raise seed_e2e_backend.E2ESafetyError("F-003 scenario seed requires E2E_F003_LOAD=true")

    database_url = seed_e2e_backend.prepare_e2e_environment(env)
    if not database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise seed_e2e_backend.E2ESafetyError("F-003 scenario seed requires isolated local PostgreSQL 16")

    app_parameters = seed_e2e_backend._postgres_e2e_connection(database_url, env)
    if not F003_DATABASE_PATTERN.fullmatch(str(app_parameters["dbname"])):
        raise seed_e2e_backend.E2ESafetyError("F-003 scenario seed requires its dedicated disposable database name")
    if not str(app_parameters["user"]).endswith("_app_runner"):
        raise seed_e2e_backend.E2ESafetyError("F-003 scenario seed requires the isolated application role")

    seed_url, seed_parameters = seed_e2e_backend._postgres_e2e_seed_connection(
        database_url, app_parameters, env
    )
    return database_url, app_parameters, seed_url, seed_parameters


def seed_f003_load_scenario(env: MutableMapping[str, str] | None = None) -> None:
    target = os.environ if env is None else env
    _database_url, app_parameters, seed_url, seed_parameters = _validated_target(target)

    # Import database and domain modules only after the loopback/database/role
    # allowlist has passed. The fixture role is never used by the API process.
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from app.database import get_engine
    from app.models import (
        Guest,
        HotelConfiguration,
        Reservation,
        Room,
        RoomCategory,
    )
    from app.models.reservation import (
        ReservationChannelCodeEnum,
        ReservationGuestSegmentEnum,
        ReservationGuestSegmentSourceEnum,
        ReservationOutcomeEnum,
        ReservationSourceEnum,
        ReservationStatusEnum,
    )
    from app.models.room import RoomHousekeepingStatusEnum, RoomStatusEnum

    seed_engine = get_engine(seed_url)
    try:
        with seed_engine.connect() as connection:
            seed_bypass = connection.execute(
                text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
            ).scalar_one_or_none()
            app_bypass = connection.execute(
                text("SELECT rolbypassrls FROM pg_roles WHERE rolname = :role_name"),
                {"role_name": app_parameters["user"]},
            ).scalar_one_or_none()
            if seed_bypass is not True:
                raise seed_e2e_backend.E2ESafetyError("F-003 fixture role must have isolated fixture-only BYPASSRLS")
            if app_bypass is not False:
                raise seed_e2e_backend.E2ESafetyError("F-003 application role must keep PostgreSQL RLS enabled")

        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=seed_engine)
        with session_factory() as db:
            hotels = db.query(HotelConfiguration).all()
            categories = db.query(RoomCategory).all()
            rooms = db.query(Room).all()
            guests = db.query(Guest).all()
            reservations = db.query(Reservation).count()

            safe_fixture = (
                len(hotels) == 1
                and hotels[0].id == 1
                and len(categories) == 1
                and categories[0].hotel_id == 1
                and categories[0].code == "STD"
                and len(rooms) == 2
                and {room.room_number for room in rooms} == {"101", "102"}
                and all(room.hotel_id == 1 and room.category_id == categories[0].id for room in rooms)
                and len(guests) == 1
                and guests[0].hotel_id == 1
                and guests[0].document_number == "E2E-1"
                and reservations == 0
            )
            if not safe_fixture:
                raise seed_e2e_backend.E2ESafetyError(
                    "F-003 scenario seed requires the untouched standard E2E fixture with zero reservations"
                )

            hotel = hotels[0]
            hotel.hotel_name = "Hotel Mirador del Lago"
            hotel.hotel_timezone = "America/Argentina/Buenos_Aires"
            hotel.default_currency = "ARS"
            hotel.check_in_time = "14:00"
            hotel.check_out_time = "10:00"
            hotel.deposit_percentage = 30
            hotel.free_cancellation_hours = 48
            hotel.enable_cash = True
            hotel.enable_bank_transfer = True
            hotel.enable_mercado_pago = False
            hotel.enable_paypal = False
            hotel.enable_credit_card = False
            hotel.enable_debit_card = False

            category_by_code: dict[str, RoomCategory] = {}
            category_specs = (
                ("DBL", "Doble Estándar", Decimal("85000"), 2),
                ("TWN", "Twin", Decimal("85000"), 2),
                ("SUP", "Superior Vista al Lago", Decimal("120000"), 2),
                ("FAM", "Suite Familiar", Decimal("165000"), 4),
            )
            standard_category = categories[0]
            for code, name, nightly_price, occupancy in category_specs:
                category = standard_category if code == "DBL" else RoomCategory(hotel_id=1)
                category.code = code
                category.name = name
                category.base_price_per_night = nightly_price
                category.variable_cost_per_night = Decimal("0")
                category.max_occupancy = occupancy
                if code != "DBL":
                    db.add(category)
                category_by_code[code] = category
            db.flush()

            from app.models.pricing import CategoryPricing

            legacy_price = db.get(CategoryPricing, standard_category.id)
            if legacy_price is not None:
                legacy_price.price_cash = 85000

            room_category_codes: dict[str, str] = {}
            room_floor: dict[str, int] = {}
            for number in (*map(str, range(101, 109)), *map(str, range(201, 205))):
                room_category_codes[number] = "DBL"
            for number in ("109", "110", *map(str, range(205, 211))):
                room_category_codes[number] = "TWN"
            for number in map(str, range(301, 307)):
                room_category_codes[number] = "SUP"
            for number in map(str, range(307, 311)):
                room_category_codes[number] = "FAM"
            for number in room_category_codes:
                room_floor[number] = int(number[0])

            existing_rooms = {room.room_number: room for room in rooms}
            for number, code in room_category_codes.items():
                room = existing_rooms.get(number)
                if room is None:
                    room = Room(hotel_id=1, room_number=number)
                    db.add(room)
                room.floor = room_floor[number]
                room.category_id = category_by_code[code].id
                room.status = RoomStatusEnum.AVAILABLE
                room.housekeeping_status = RoomHousekeepingStatusEnum.CLEAN
                room.is_active = True
            db.flush()

            scenario_guests = [guests[0]]
            for index in range(1, 45):
                guest = Guest(
                    hotel_id=1,
                    first_name=f"Pasajero F003 {index:03d}",
                    last_name="Prueba",
                    document_type="DNI",
                    document_number=f"F003-{index:03d}",
                    email=f"f003-guest-{index:03d}@example.test",
                    phone=f"+54-351-555-{index:04d}",
                    nationality="Argentina",
                    country="Argentina",
                    terms_accepted=True,
                )
                db.add(guest)
                scenario_guests.append(guest)
            db.flush()

            rooms_by_number = {room.room_number: room for room in db.query(Room).all()}
            room_numbers = sorted(rooms_by_number, key=lambda value: (int(value[0]), int(value)))
            today = datetime.now(HOTEL_TIMEZONE).date()
            reservation_count = 0
            for index in range(45):
                room = rooms_by_number[room_numbers[index % 30]]
                code = next(code for code, category in category_by_code.items() if category.id == room.category_id)
                nightly_price = Decimal(str(category_by_code[code].base_price_per_night))
                if index < 6:
                    check_in = today
                    status = ReservationStatusEnum.CHECKED_IN
                    outcome = ReservationOutcomeEnum.CHECKED_IN
                elif index < 30:
                    check_in = today + timedelta(days=2 + ((index - 6) % 14))
                    status = ReservationStatusEnum.PENDING
                    outcome = ReservationOutcomeEnum.PENDING
                else:
                    check_in = today + timedelta(days=30 + ((index - 30) % 7))
                    status = ReservationStatusEnum.PENDING
                    outcome = ReservationOutcomeEnum.PENDING

                if index < 6:
                    room.status = RoomStatusEnum.OCCUPIED
                reservation = Reservation(
                    confirmation_code=f"F003-{index + 1:04d}",
                    hotel_id=1,
                    guest_id=scenario_guests[index].id,
                    room_id=room.id,
                    category_id=room.category_id,
                    check_in_date=check_in,
                    check_out_date=check_in + timedelta(days=2),
                    total_amount=nightly_price * 2,
                    subtotal_amount=nightly_price * 2,
                    currency_code="ARS",
                    status=status,
                    outcome=outcome,
                    guest_segment=ReservationGuestSegmentEnum.LEISURE,
                    guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
                    channel_code=ReservationChannelCodeEnum.PHONE,
                    source=ReservationSourceEnum.DIRECT,
                    num_adults=2,
                    actual_check_in=datetime.now(timezone.utc) if index < 6 else None,
                    allocation_status="assigned",
                )
                db.add(reservation)
                reservation_count += 1

            db.commit()

        print(
            "F003_LOAD_FIXTURE "
            "{\"hotel\":\"Hotel Mirador del Lago\",\"rooms\":30,\"categories\":4,"
            "\"guests\":45,\"reservations\":45,\"checked_in\":6,\"currency\":\"ARS\"}",
            flush=True,
        )
    finally:
        seed_engine.dispose()


if __name__ == "__main__":
    seed_f003_load_scenario()
