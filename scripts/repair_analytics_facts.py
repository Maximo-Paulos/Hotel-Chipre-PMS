"""Idempotently rebuild reservation and room analytics facts for a bounded scope.

Run after deploying a corrected fact-allocation algorithm, for example:

    python scripts/repair_analytics_facts.py --all-hotels

Or repair one tenant/date window explicitly. The command commits one hotel at
a time; rerunning the same scope is safe because both refresh services replace
the requested date range.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app.models  # noqa: F401 - ensure every mapped model is registered.
from app.database import get_session_factory
from app.models.analytics import FactReservationDaily, FactRoomOccupancyDaily
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.services.analytics_facts import (
    refresh_fact_reservation_daily,
    refresh_fact_room_occupancy_daily,
)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--hotel-id", type=int, help="Rebuild one hotel")
    scope.add_argument("--all-hotels", action="store_true", help="Rebuild all hotels with reservations")
    parser.add_argument("--date-from", type=_parse_date)
    parser.add_argument("--date-to", type=_parse_date)
    return parser


def _hotel_ranges(db, args: argparse.Namespace) -> list[tuple[int, date, date]]:
    if (args.date_from is None) != (args.date_to is None):
        raise ValueError("--date-from y --date-to deben enviarse juntos")
    if args.date_from and args.date_to and args.date_to < args.date_from:
        raise ValueError("--date-to debe ser igual o posterior a --date-from")

    if args.date_from is not None:
        if args.hotel_id is not None:
            if db.get(HotelConfiguration, args.hotel_id) is None:
                raise ValueError("No existe el hotel solicitado")
            return [(args.hotel_id, args.date_from, args.date_to)]
        hotel_ids = [row[0] for row in db.query(HotelConfiguration.id).order_by(HotelConfiguration.id).all()]
        return [(hotel_id, args.date_from, args.date_to) for hotel_id in hotel_ids]

    hotel_ids = [row[0] for row in db.query(HotelConfiguration.id).order_by(HotelConfiguration.id).all()]
    if args.hotel_id is not None:
        if args.hotel_id not in hotel_ids:
            raise ValueError("No existe el hotel solicitado")
        hotel_ids = [args.hotel_id]

    ranges_by_hotel: dict[int, tuple[date, date]] = {}

    def include_range(hotel_id: int, first: date | None, last: date | None) -> None:
        if first is None or last is None:
            return
        current = ranges_by_hotel.get(hotel_id)
        ranges_by_hotel[hotel_id] = (
            min(current[0], first) if current else first,
            max(current[1], last) if current else last,
        )

    reservation_query = db.query(
        Reservation.hotel_id,
        func.min(Reservation.check_in_date),
        func.max(Reservation.check_out_date),
    ).filter(
        Reservation.hotel_id.in_(hotel_ids),
        Reservation.deleted_at.is_(None),
        Reservation.check_out_date > Reservation.check_in_date,
    )
    for hotel_id, first_night, checkout in reservation_query.group_by(Reservation.hotel_id).all():
        include_range(hotel_id, first_night, checkout - timedelta(days=1))

    # Include existing fact bounds as well as current reservations. This also
    # clears stale rows left behind by reservations that were later deleted or
    # moved outside the currently active reservation range.
    for model in (FactReservationDaily, FactRoomOccupancyDaily):
        fact_query = db.query(model.hotel_id, func.min(model.stay_date), func.max(model.stay_date))
        if hotel_ids:
            fact_query = fact_query.filter(model.hotel_id.in_(hotel_ids))
        for hotel_id, first_fact_date, last_fact_date in fact_query.group_by(model.hotel_id).all():
            include_range(hotel_id, first_fact_date, last_fact_date)

    return [
        (hotel_id, ranges_by_hotel[hotel_id][0], ranges_by_hotel[hotel_id][1])
        for hotel_id in sorted(ranges_by_hotel)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    db = get_session_factory()()
    try:
        try:
            ranges = _hotel_ranges(db, args)
        except ValueError as exc:
            parser.error(str(exc))
        if args.hotel_id is not None and not ranges:
            parser.error("No hay reservas para el hotel solicitado")

        for hotel_id, date_from, date_to in ranges:
            try:
                reservations = refresh_fact_reservation_daily(
                    db,
                    hotel_id=hotel_id,
                    date_from=date_from,
                    date_to=date_to,
                )
                occupancy = refresh_fact_room_occupancy_daily(
                    db,
                    hotel_id=hotel_id,
                    date_from=date_from,
                    date_to=date_to,
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                print(
                    f"Hotel #{hotel_id} ({date_from}..{date_to}) falló: {type(exc).__name__}",
                    file=sys.stderr,
                )
                return 1
            print(
                f"Hotel #{hotel_id} {date_from}..{date_to}: "
                f"reservas {reservations.deleted} eliminadas/{reservations.inserted} creadas; "
                f"ocupación {occupancy.deleted} eliminadas/{occupancy.inserted} creadas"
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
