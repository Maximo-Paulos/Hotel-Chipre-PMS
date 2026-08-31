"""The rate calendar's "Hoy" must follow the hotel's timezone, not the server's.

Render runs in UTC. For a hotel in Argentina (UTC-3) every request between
21:00 and midnight local time saw `date.today()` return *tomorrow*, so the
Tarifas calendar highlighted Monday 31 as "Hoy" while it was still Sunday 30
in the hotel.
"""
import os
import time as time_module
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory
from app.services import timezones
from app.services.rate_calendar_service import get_daily_calendar

# 2026-08-31T00:23Z is still Sunday 2026-08-30 21:23 in Buenos Aires.
FROZEN_UTC = datetime(2026, 8, 31, 0, 23, tzinfo=timezone.utc)
BUENOS_AIRES = "America/Argentina/Buenos_Aires"
HOTEL_ID = 1


@pytest.fixture(autouse=True)
def utc_server_clock(monkeypatch):
    """Run the process in UTC like Render does, so a regression back to
    `date.today()` reads the server's date instead of the hotel's."""
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time_module.tzset()
    yield
    if previous is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = previous
    time_module.tzset()


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    class _FixedDatetime:
        @staticmethod
        def now(tz=None):
            return FROZEN_UTC.astimezone(tz) if tz else FROZEN_UTC

    monkeypatch.setattr(timezones, "datetime", _FixedDatetime)


def test_local_today_uses_the_hotel_timezone_not_the_server():
    assert FROZEN_UTC.date() == date(2026, 8, 31)  # what date.today() would give on Render
    assert timezones.local_today(BUENOS_AIRES) == date(2026, 8, 30)


@pytest.mark.parametrize("timezone_name", [None, "", "Not/AZone"])
def test_local_today_falls_back_to_utc(timezone_name):
    assert timezones.local_today(timezone_name) == date(2026, 8, 31)


@pytest.fixture
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'local_today.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    db.add(HotelConfiguration(id=HOTEL_ID, subscription_active=True, hotel_timezone=BUENOS_AIRES))
    db.flush()
    category = RoomCategory(
        hotel_id=HOTEL_ID, name="Doble", code="DBL", base_price_per_night=60000, max_occupancy=2
    )
    db.add(category)
    db.flush()
    db.add(Room(hotel_id=HOTEL_ID, room_number="101", floor=1, category_id=category.id))
    db.commit()

    yield db, category.id

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_calendar_marks_the_hotel_local_day_as_today(session):
    db, category_id = session

    calendar = get_daily_calendar(
        db,
        hotel_id=HOTEL_ID,
        category_id=category_id,
        date_from=date(2026, 8, 30),
        date_to=date(2026, 9, 3),
    )

    flagged = [day["date"] for day in calendar["days"] if day["is_today"]]
    assert flagged == [date(2026, 8, 30)]


def test_hotel_today_reads_the_configured_timezone(session):
    db, _category_id = session

    assert timezones.hotel_today(db, HOTEL_ID) == date(2026, 8, 30)


def test_hotel_today_falls_back_to_utc_for_an_unknown_hotel(session):
    db, _category_id = session

    assert timezones.hotel_today(db, 999) == date(2026, 8, 31)
