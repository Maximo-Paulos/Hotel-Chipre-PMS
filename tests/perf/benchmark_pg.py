"""PostgreSQL performance benchmark for Hotel Chipre PMS critical queries.

This script is intentionally scoped to the PostgreSQL test database only.
It derives DATABASE_URL_TEST the same way tests/conftest.py does: read the
root .env DATABASE_URL and replace the trailing /postgres with
/hotel_chipre_test.
"""
from __future__ import annotations

import argparse
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from sqlalchemy import create_engine, delete, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.models  # noqa: E402,F401
from app.models.guest import DocumentTypeEnum, Guest  # noqa: E402
from app.models.hotel_config import HotelConfiguration  # noqa: E402
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum  # noqa: E402
from app.models.room import Room, RoomCategory, RoomStatusEnum  # noqa: E402
from app.models.room_block import RoomBlock, RoomBlockReasonEnum  # noqa: E402
from app.models.transaction import (  # noqa: E402
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.services.allocation_engine import build_slots_from_db  # noqa: E402
from app.services.guest_service import search_guests  # noqa: E402
from app.services.operational_report_service import daily_report  # noqa: E402
from app.services.payment_link_service import balance_due_from_transactions  # noqa: E402
from app.services.reservation_service import check_room_availability, find_available_rooms  # noqa: E402


HOTEL_ID = 90001
ITERATIONS = 25
BASE_DATE = date(2026, 1, 1)
ACTIVE_STATUSES = (
    ReservationStatusEnum.PENDING,
    ReservationStatusEnum.DEPOSIT_PAID,
    ReservationStatusEnum.FULLY_PAID,
    ReservationStatusEnum.PRE_CHECK_IN,
    ReservationStatusEnum.CHECKED_IN,
)


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    median_ms: float
    p95_ms: float
    index_used: bool


def derive_test_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL_TEST", "")
    if not dsn:
        prod_url = os.environ.get("DATABASE_URL", "")
        if not prod_url:
            for parent in Path(__file__).resolve().parents:
                env_file = parent / ".env"
                if not env_file.exists():
                    continue
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        prod_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
                if prod_url:
                    break
        if prod_url.startswith("postgresql"):
            dsn = re.sub(r"/postgres(\?.*)?$", r"/hotel_chipre_test\1", prod_url)

    parsed = urlparse(dsn)
    if not dsn.startswith("postgresql") or parsed.path.rstrip("/").split("/")[-1] != "hotel_chipre_test":
        raise SystemExit(
            "Refusing to run: DATABASE_URL_TEST must point at PostgreSQL database "
            "'hotel_chipre_test'. Production /postgres is not allowed."
        )
    return dsn


def run_alembic_upgrade(dsn: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = dsn
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    if completed.stdout.strip():
        print(completed.stdout.strip())


def cleanup(session: Session) -> None:
    session.execute(text("DELETE FROM reservation_additional_guests WHERE reservation_id IN (SELECT id FROM reservations WHERE hotel_id = :hotel_id)"), {"hotel_id": HOTEL_ID})
    session.execute(delete(Transaction).where(Transaction.hotel_id == HOTEL_ID))
    session.execute(delete(RoomBlock).where(RoomBlock.hotel_id == HOTEL_ID))
    session.execute(delete(Reservation).where(Reservation.hotel_id == HOTEL_ID))
    session.execute(delete(Room).where(Room.hotel_id == HOTEL_ID))
    session.execute(delete(RoomCategory).where(RoomCategory.hotel_id == HOTEL_ID))
    session.execute(delete(Guest).where(Guest.hotel_id == HOTEL_ID))
    session.execute(delete(HotelConfiguration).where(HotelConfiguration.id == HOTEL_ID))
    session.commit()


def seed(session: Session) -> dict[str, object]:
    cleanup(session)
    now = datetime.now(timezone.utc)

    session.add(
        HotelConfiguration(
            id=HOTEL_ID,
            hotel_name="Benchmark Hotel Chipre",
            deposit_percentage=30.0,
            subscription_active=True,
            default_currency="ARS",
        )
    )
    session.flush()

    categories = [
        RoomCategory(
            hotel_id=HOTEL_ID,
            name=f"Benchmark Category {idx}",
            code=f"BENCH{idx}",
            base_price_per_night=Decimal(str(80 + idx * 30)),
            variable_cost_per_night=Decimal("20.00"),
            max_occupancy=2 + (idx % 3),
        )
        for idx in range(1, 6)
    ]
    session.add_all(categories)
    session.flush()

    rooms = []
    for idx in range(40):
        category = categories[idx % len(categories)]
        rooms.append(
            Room(
                hotel_id=HOTEL_ID,
                room_number=f"B{idx + 1:03d}",
                floor=(idx // 10) + 1,
                category_id=category.id,
                status=RoomStatusEnum.AVAILABLE if idx % 7 else RoomStatusEnum.CLEANING,
                is_active=True,
                score=(idx % 10) + 1,
                is_accessible=idx % 8 == 0,
            )
        )
    session.add_all(rooms)
    session.flush()

    guests = [
        {
            "hotel_id": HOTEL_ID,
            "first_name": f"Guest{i:04d}",
            "last_name": f"BenchLast{i % 250:03d}",
            "document_type": DocumentTypeEnum.DNI,
            "document_number": f"BENCHDOC{i:06d}",
            "email": f"bench.guest{i:04d}@example.test",
            "phone": f"+5491100{i:06d}",
            "nationality": "AR",
            "terms_accepted": True,
            "created_at": now,
            "updated_at": now,
        }
        for i in range(1, 2001)
    ]
    session.bulk_insert_mappings(Guest, guests)
    session.flush()
    guest_ids = [row[0] for row in session.query(Guest.id).filter(Guest.hotel_id == HOTEL_ID).order_by(Guest.id.asc()).all()]

    reservations = []
    for i in range(2000):
        room = rooms[i % len(rooms)]
        category_id = room.category_id
        check_in = BASE_DATE + timedelta(days=i % 365)
        nights = 1 + (i % 6)
        status = ACTIVE_STATUSES[i % len(ACTIVE_STATUSES)]
        if i % 19 == 0:
            status = ReservationStatusEnum.CHECKED_OUT
        elif i % 23 == 0:
            status = ReservationStatusEnum.CANCELLED
        total = Decimal(str(120 + (i % 6) * 35)) * Decimal(nights)
        paid = total if status == ReservationStatusEnum.FULLY_PAID else (total * Decimal("0.30")).quantize(Decimal("0.01"))
        reservations.append(
            {
                "hotel_id": HOTEL_ID,
                "confirmation_code": f"BENCH-{i:06d}",
                "guest_id": guest_ids[i],
                "room_id": room.id,
                "category_id": category_id,
                "check_in_date": check_in,
                "check_out_date": check_in + timedelta(days=nights),
                "total_amount": total,
                "amount_paid": paid,
                "deposit_amount": (total * Decimal("0.30")).quantize(Decimal("0.01")),
                "subtotal_amount": total,
                "tax_amount": Decimal("0.00"),
                "fee_amount": Decimal("0.00"),
                "commission_amount": Decimal("0.00"),
                "net_amount": total,
                "currency_code": "ARS",
                "status": status,
                "source": ReservationSourceEnum.DIRECT,
                "num_adults": 1 + (i % 2),
                "num_children": i % 3,
                "requires_manual_review": i % 31 == 0,
                "allocation_locked": i % 41 == 0,
                "mobility_restriction": i % 53 == 0,
                "created_at": now,
                "updated_at": now,
            }
        )
    session.bulk_insert_mappings(Reservation, reservations)
    session.flush()
    reservation_rows = (
        session.query(Reservation.id, Reservation.total_amount)
        .filter(Reservation.hotel_id == HOTEL_ID)
        .order_by(Reservation.id.asc())
        .all()
    )

    tx_rows = []
    for idx, (reservation_id, total_amount) in enumerate(reservation_rows):
        if idx % 3 == 0:
            amount = (Decimal(total_amount) * Decimal("0.30")).quantize(Decimal("0.01"))
            tx_rows.append(
                {
                    "hotel_id": HOTEL_ID,
                    "reservation_id": reservation_id,
                    "amount": amount,
                    "currency": "ARS",
                    "gross_amount": amount,
                    "net_amount": amount,
                    "transaction_type": TransactionTypeEnum.PARTIAL_PAYMENT,
                    "payment_method": PaymentMethodEnum.CASH if idx % 2 == 0 else PaymentMethodEnum.MERCADO_PAGO,
                    "status": TransactionStatusEnum.COMPLETED,
                    "idempotency_key": f"bench-tx-{idx}",
                    "created_at": now,
                    "updated_at": now,
                    "processed_at": now,
                }
            )
    session.bulk_insert_mappings(Transaction, tx_rows)

    blocks = []
    for idx, room in enumerate(rooms[:12]):
        start = BASE_DATE + timedelta(days=(idx * 11) % 180)
        blocks.append(
            {
                "hotel_id": HOTEL_ID,
                "room_id": room.id,
                "reason_code": RoomBlockReasonEnum.MAINTENANCE,
                "reason_note": "benchmark maintenance block",
                "starts_at": start,
                "ends_at": start + timedelta(days=2 + (idx % 3)),
                "is_indefinite": False,
                "created_at": now,
                "updated_at": now,
            }
        )
    session.bulk_insert_mappings(RoomBlock, blocks)
    session.commit()

    sample_reservation = (
        session.query(Reservation)
        .filter(Reservation.hotel_id == HOTEL_ID, Reservation.status.in_(ACTIVE_STATUSES))
        .order_by(Reservation.id.asc())
        .first()
    )
    return {
        "category_id": categories[0].id,
        "room_id": rooms[0].id,
        "reservation_id": sample_reservation.id,
        "report_date": BASE_DATE + timedelta(days=120),
        "search_doc": "BENCHDOC001500",
        "search_last_name": "BenchLast050",
    }


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[idx]


def measure(name: str, fn: Callable[[], object], iterations: int) -> tuple[str, float, float]:
    for _ in range(3):
        fn()
    timings: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        fn()
        timings.append((time.perf_counter() - started) * 1000.0)
    return name, statistics.median(timings), percentile(timings, 95)


def explain(session: Session, label: str, sql: str, params: dict[str, object], large_tables: tuple[str, ...]) -> tuple[bool, str]:
    plan_rows = session.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}"), params).all()
    plan = "\n".join(row[0] for row in plan_rows)
    bad_seq = any(f"Seq Scan on {table}" in plan for table in large_tables)
    index_used = "Index Scan" in plan or "Bitmap Index Scan" in plan or "Index Only Scan" in plan
    print(f"\n--- EXPLAIN {label} ---")
    print(plan)
    if bad_seq:
        print(f"PLAN WARNING: unexpected Seq Scan on large table(s): {', '.join(large_tables)}")
    return index_used and not bad_seq, plan


def print_results(results: list[BenchmarkResult]) -> None:
    print("\nquery | median ms | p95 ms | index-used")
    print("--- | ---: | ---: | :---:")
    for result in results:
        print(f"{result.name} | {result.median_ms:.2f} | {result.p95_ms:.2f} | {'y' if result.index_used else 'n'}")


def run_benchmarks(session: Session, seed_info: dict[str, object], iterations: int) -> list[BenchmarkResult]:
    check_in = BASE_DATE + timedelta(days=180)
    check_out = check_in + timedelta(days=4)
    allocation_start = BASE_DATE + timedelta(days=90)
    allocation_end = allocation_start + timedelta(days=45)
    report_date = seed_info["report_date"]

    explain_results = {
        "availability": explain(
            session,
            "availability reservation overlap",
            """
            SELECT count(*)
            FROM reservations
            WHERE room_id = :room_id
              AND hotel_id = :hotel_id
              AND status NOT IN ('cancelled', 'checked_out')
              AND check_in_date < :check_out
              AND check_out_date > :check_in
            """,
            {"room_id": seed_info["room_id"], "hotel_id": HOTEL_ID, "check_in": check_in, "check_out": check_out},
            ("reservations",),
        )[0],
        "allocation": explain(
            session,
            "allocation reservation window",
            """
            SELECT id, category_id, check_in_date, check_out_date, room_id, status
            FROM reservations
            WHERE hotel_id = :hotel_id
              AND status NOT IN ('cancelled', 'checked_out')
              AND check_in_date < :end_date
              AND check_out_date > :start_date
            """,
            {"hotel_id": HOTEL_ID, "start_date": allocation_start, "end_date": allocation_end},
            ("reservations",),
        )[0],
        "balance": explain(
            session,
            "balance transactions",
            """
            SELECT amount, transaction_type
            FROM transactions
            WHERE hotel_id = :hotel_id
              AND reservation_id = :reservation_id
              AND status = 'completed'
            """,
            {"hotel_id": HOTEL_ID, "reservation_id": seed_info["reservation_id"]},
            ("transactions",),
        )[0],
        "daily report": explain(
            session,
            "daily report balance candidates",
            """
            SELECT id, check_in_date, check_out_date, status
            FROM reservations
            WHERE hotel_id = :hotel_id
              AND status IN ('pending', 'deposit_paid', 'fully_paid', 'pre_check_in', 'checked_in')
              AND check_out_date > :report_date
            ORDER BY check_in_date ASC, id ASC
            """,
            {"hotel_id": HOTEL_ID, "report_date": report_date},
            ("reservations",),
        )[0],
        "guest search": explain(
            session,
            "guest search last name",
            """
            SELECT id, first_name, last_name
            FROM guests
            WHERE hotel_id = :hotel_id
              AND (
                document_number ILIKE :pattern
                OR phone ILIKE :pattern
                OR email ILIKE :pattern
                OR last_name ILIKE :pattern
              )
            ORDER BY last_name ASC, first_name ASC, id ASC
            LIMIT 20
            """,
            {"hotel_id": HOTEL_ID, "pattern": f"%{seed_info['search_last_name']}%"},
            ("guests",),
        )[0],
    }

    measured = [
        measure(
            "availability.check_room_availability",
            lambda: check_room_availability(session, seed_info["room_id"], check_in, check_out, hotel_id=HOTEL_ID),
            iterations,
        ),
        measure(
            "availability.find_available_rooms",
            lambda: find_available_rooms(session, seed_info["category_id"], check_in, check_out, hotel_id=HOTEL_ID),
            iterations,
        ),
        measure(
            "allocation.build_slots_from_db",
            lambda: build_slots_from_db(session, allocation_start, allocation_end, HOTEL_ID),
            iterations,
        ),
        measure(
            "balance.balance_due_from_transactions",
            lambda: balance_due_from_transactions(session, HOTEL_ID, seed_info["reservation_id"]),
            iterations,
        ),
        measure(
            "daily_report",
            lambda: daily_report(session, HOTEL_ID, report_date),
            iterations,
        ),
        measure(
            "guest_search.document",
            lambda: search_guests(session, HOTEL_ID, seed_info["search_doc"], limit=20),
            iterations,
        ),
        measure(
            "guest_search.last_name",
            lambda: search_guests(session, HOTEL_ID, seed_info["search_last_name"], limit=20),
            iterations,
        ),
    ]

    return [
        BenchmarkResult(
            name=name,
            median_ms=median_ms,
            p95_ms=p95_ms,
            index_used=explain_results.get(
                "availability" if name.startswith("availability") else
                "allocation" if name.startswith("allocation") else
                "balance" if name.startswith("balance") else
                "daily report" if name.startswith("daily") else
                "guest search",
                False,
            ),
        )
        for name, median_ms, p95_ms in measured
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=ITERATIONS)
    parser.add_argument("--skip-alembic", action="store_true")
    args = parser.parse_args()

    dsn = derive_test_dsn()
    if args.iterations < 20:
        raise SystemExit("--iterations must be at least 20")
    if not args.skip_alembic:
        try:
            run_alembic_upgrade(dsn)
        except subprocess.CalledProcessError as exc:
            print(
                "PostgreSQL test database unreachable or migrations failed; "
                f"alembic exited with status {exc.returncode}.",
                file=sys.stderr,
            )
            stderr = (exc.stderr or "").strip()
            if stderr:
                print("\n".join(stderr.splitlines()[-8:]), file=sys.stderr)
            return exc.returncode

    engine: Engine = create_engine(dsn, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        with SessionLocal() as session:
            seed_info = seed(session)
            results = run_benchmarks(session, seed_info, args.iterations)
            print_results(results)
    except OperationalError as exc:
        parsed = urlparse(dsn)
        print(
            "PostgreSQL test database unreachable; "
            f"host={parsed.hostname} database={parsed.path.lstrip('/')}. "
            f"{exc.__class__.__name__}: {exc.orig}",
            file=sys.stderr,
        )
        return 2
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
