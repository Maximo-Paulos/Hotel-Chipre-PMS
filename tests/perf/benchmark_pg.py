"""PostgreSQL performance benchmark for Hotels-PMS critical queries.

This script requires an explicit loopback DATABASE_URL_TEST pointing to an
isolated PostgreSQL database named hotel_chipre_test. It never derives a test
target from DATABASE_URL or reads a local .env file.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
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

from sqlalchemy import create_engine, delete, event, func, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reservation creation emits durable domain events. Mirror the intended local
# SQL-only profile so this benchmark never attempts to contact Redis/Valkey.
os.environ.setdefault("REALTIME_EVENTS_TRANSPORT", "postgresql")
os.environ.setdefault("DISTRIBUTED_LOCK_BACKEND", "postgresql")
os.environ.setdefault("COLLABORATION_BACKEND", "process")

import app.models  # noqa: E402,F401
from app.models.analytics import FactReservationDaily, FactRoomOccupancyDaily  # noqa: E402
from app.models.commercial import TaxPolicy  # noqa: E402
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
from app.schemas.reservation import ReservationCreate  # noqa: E402
from app.services.allocation_engine import build_slots_from_db  # noqa: E402
from app.services.guest_service import search_guests  # noqa: E402
from app.services.operational_report_service import (  # noqa: E402
    _daily_report_balance_candidate_query,
    daily_report,
)
from app.services.payment_link_service import balance_due_from_transactions  # noqa: E402
from app.services.reservation_service import (  # noqa: E402
    check_room_availability,
    create_reservation,
    find_available_rooms,
)


HOTEL_ID = 2_000_000_000 + secrets.randbelow(100_000_000)
ITERATIONS = 25
SEQ_SCAN_REVIEW_ROW_THRESHOLD = 10_000
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
    median_queries: int
    index_used: bool | None


EXPLAIN_PLAN_BY_OPERATION = {
    "availability.check_room_availability": "availability",
    "allocation.build_slots_from_db": "allocation",
    "balance.balance_due_from_transactions": "balance",
    "daily_report": "daily report direct balance summary",
    "guest_search.last_name": "guest search",
}


def index_usage_for_operation(
    operation_name: str,
    explain_results: dict[str, bool],
) -> bool | None:
    """Return an index signal only when this operation has a matching plan."""
    plan_name = EXPLAIN_PLAN_BY_OPERATION.get(operation_name)
    return explain_results.get(plan_name) if plan_name is not None else None


def derive_test_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL_TEST", "")
    parsed = urlparse(dsn)
    if (
        not dsn.startswith("postgresql")
        or parsed.path.rstrip("/").split("/")[-1] != "hotel_chipre_test"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise SystemExit(
            "Refusing to run: set DATABASE_URL_TEST explicitly to a loopback PostgreSQL "
            "database named 'hotel_chipre_test'. Remote/shared databases are not allowed."
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
    session.execute(delete(FactReservationDaily).where(FactReservationDaily.hotel_id == HOTEL_ID))
    session.execute(delete(FactRoomOccupancyDaily).where(FactRoomOccupancyDaily.hotel_id == HOTEL_ID))
    session.execute(delete(Transaction).where(Transaction.hotel_id == HOTEL_ID))
    session.execute(delete(RoomBlock).where(RoomBlock.hotel_id == HOTEL_ID))
    session.execute(delete(Reservation).where(Reservation.hotel_id == HOTEL_ID))
    session.execute(delete(Room).where(Room.hotel_id == HOTEL_ID))
    session.execute(delete(RoomCategory).where(RoomCategory.hotel_id == HOTEL_ID))
    session.execute(delete(Guest).where(Guest.hotel_id == HOTEL_ID))
    session.execute(delete(HotelConfiguration).where(HotelConfiguration.id == HOTEL_ID))
    session.commit()


def seed(session: Session) -> dict[str, object]:
    if session.get(HotelConfiguration, HOTEL_ID) is not None:
        raise RuntimeError("Random benchmark hotel id unexpectedly already exists")
    now = datetime.now(timezone.utc)

    session.add(
        HotelConfiguration(
            id=HOTEL_ID,
            hotel_name="Benchmark Hotel Chipre",
            deposit_percentage=30.0,
            # This synthetic hotel has explicitly confirmed its policy so the
            # benchmark exercises reservation creation under the current rules.
            deposit_policy_configured=True,
            free_cancellation_hours=48,
            cancellation_penalty_percentage=0.0,
            subscription_active=True,
            default_currency="ARS",
        )
    )
    session.flush()
    session.add(
        TaxPolicy(
            hotel_id=HOTEL_ID,
            code="BENCHMARK_NO_TAX",
            name="Explicit zero-tax benchmark policy",
            taxes_included=True,
            apply_vat_by_default=False,
            vat_rate=0.0,
            is_active=True,
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
    # Bulk inserts bypass normal autovacuum thresholds on this small synthetic
    # profile. Refresh planner statistics before reading EXPLAIN plans.
    for table_name in ("guests", "reservations", "transactions", "room_blocks", "room_categories"):
        session.execute(text(f"ANALYZE {table_name}"))

    sample_reservation = (
        session.query(Reservation)
        .filter(Reservation.hotel_id == HOTEL_ID, Reservation.status.in_(ACTIVE_STATUSES))
        .order_by(Reservation.id.asc())
        .first()
    )
    if sample_reservation is None:
        raise RuntimeError("Synthetic benchmark seed did not create an active reservation")
    sample_reservation_id = sample_reservation.id
    session.commit()
    return {
        "category_id": categories[0].id,
        "room_id": rooms[0].id,
        "guest_id": guest_ids[0],
        "reservation_id": sample_reservation_id,
        "report_date": BASE_DATE + timedelta(days=120),
        "search_doc": "BENCHDOC001500",
        "search_last_name": "BenchLast050",
    }


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[idx]


def measure(
    engine: Engine,
    name: str,
    fn: Callable[[], object],
    iterations: int,
) -> tuple[str, float, float, int]:
    statement_count = 0
    query_counts: list[int] = []

    def count_statement(*_args) -> None:
        nonlocal statement_count
        statement_count += 1

    event.listen(engine, "before_cursor_execute", count_statement)
    try:
        for _ in range(3):
            statement_count = 0
            fn()
        timings: list[float] = []
        for _ in range(iterations):
            statement_count = 0
            started = time.perf_counter()
            fn()
            timings.append((time.perf_counter() - started) * 1000.0)
            query_counts.append(statement_count)
    finally:
        event.remove(engine, "before_cursor_execute", count_statement)
    return name, statistics.median(timings), percentile(timings, 95), int(statistics.median(query_counts))


def _walk_plan_nodes(node: object):
    if not isinstance(node, dict):
        return
    yield node
    children = node.get("Plans", [])
    if isinstance(children, list):
        for child in children:
            yield from _walk_plan_nodes(child)


def _plan_document(raw_plan: object) -> dict[str, object]:
    document = json.loads(raw_plan) if isinstance(raw_plan, str) else raw_plan
    if isinstance(document, list) and document:
        document = document[0]
    return document if isinstance(document, dict) else {}


def _format_plan_nodes(node: object, depth: int = 0) -> list[str]:
    if not isinstance(node, dict):
        return []
    node_type = str(node.get("Node Type", "Unknown"))
    relation = node.get("Relation Name")
    index_name = node.get("Index Name")
    label = node_type
    if relation:
        label += f" on {relation}"
    if index_name:
        label += f" using {index_name}"
    estimated_rows = node.get("Plan Rows")
    actual_rows = node.get("Actual Rows")
    loops = node.get("Actual Loops")
    total_time = node.get("Actual Total Time")
    details = []
    if estimated_rows is not None:
        details.append(f"estimated rows={estimated_rows}")
    if actual_rows is not None:
        details.append(f"actual rows={actual_rows} loops={loops or 1}")
    if total_time is not None:
        details.append(f"time={total_time}ms")
    removed = node.get("Rows Removed by Filter")
    if removed is not None:
        details.append(f"rows removed by filter={removed}")
    hits = int(node.get("Shared Hit Blocks", 0) or 0)
    reads = int(node.get("Shared Read Blocks", 0) or 0)
    if hits or reads:
        details.append(f"shared buffers hit={hits} read={reads}")
    suffix = f" ({'; '.join(details)})" if details else ""
    lines = [f"{'  ' * depth}{label}{suffix}"]
    children = node.get("Plans", [])
    if isinstance(children, list):
        for child in children:
            lines.extend(_format_plan_nodes(child, depth + 1))
    return lines


def _report_explain_plan(
    label: str,
    raw_plan: object,
    large_tables: tuple[str, ...],
) -> tuple[bool, str]:
    document = _plan_document(raw_plan)
    root = document.get("Plan", {})
    nodes = list(_walk_plan_nodes(root))
    plan = "\n".join(_format_plan_nodes(root))
    target_tables = set(large_tables)
    index_used = any(
        node.get("Node Type") in {"Index Scan", "Index Only Scan", "Bitmap Index Scan"}
        for node in nodes
    )
    seq_scans = [
        node for node in nodes
        if node.get("Node Type") == "Seq Scan" and node.get("Relation Name") in target_tables
    ]

    print(f"\n--- EXPLAIN {label} ---")
    print(plan)
    for node in seq_scans:
        actual_rows = max(0, int(node.get("Actual Rows", 0) or 0))
        rows_removed = max(0, int(node.get("Rows Removed by Filter", 0) or 0))
        loops = max(1, int(node.get("Actual Loops", 1) or 1))
        rows_examined = (actual_rows + rows_removed) * loops
        table_name = str(node["Relation Name"])
        if rows_examined >= SEQ_SCAN_REVIEW_ROW_THRESHOLD:
            print(
                "PLAN REVIEW: sequential scan on "
                f"{table_name} examined about {rows_examined:,} rows "
                f"(review threshold {SEQ_SCAN_REVIEW_ROW_THRESHOLD:,}); inspect selectivity "
                "and the plan before considering an index."
            )
        else:
            print(
                "PLAN NOTE: sequential scan on "
                f"{table_name} examined about {rows_examined:,} rows, below the "
                f"{SEQ_SCAN_REVIEW_ROW_THRESHOLD:,}-row review threshold; it is not treated "
                "as an unexpected scan at this fixture size."
            )
    return index_used, plan


def explain(session: Session, label: str, sql: str, params: dict[str, object], large_tables: tuple[str, ...]) -> tuple[bool, str]:
    raw_plan = session.execute(text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"), params).scalar_one()
    return _report_explain_plan(label, raw_plan, large_tables)


def explain_query(
    session: Session,
    engine: Engine,
    label: str,
    query,
    large_tables: tuple[str, ...],
) -> tuple[bool, str]:
    compiled = query.statement.compile(
        dialect=engine.dialect,
        compile_kwargs={"literal_binds": True},
    )
    raw_plan = session.execute(text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {compiled}")).scalar_one()
    return _report_explain_plan(label, raw_plan, large_tables)


def print_results(results: list[BenchmarkResult]) -> None:
    print("\nquery | median ms | p95 ms | median SQL statements | index-used")
    print("--- | ---: | ---: | ---: | :---:")
    for result in results:
        index_used = "n/a" if result.index_used is None else "y" if result.index_used else "n"
        print(
            f"{result.name} | {result.median_ms:.2f} | {result.p95_ms:.2f} | "
            f"{result.median_queries} | {index_used}"
        )


def run_benchmarks(
    session: Session,
    session_factory: Callable[[], Session],
    engine: Engine,
    seed_info: dict[str, object],
    iterations: int,
) -> list[BenchmarkResult]:
    def in_fresh_session(operation: Callable[[Session], object]) -> object:
        with session_factory() as operation_session:
            return operation(operation_session)

    check_in = BASE_DATE + timedelta(days=180)
    check_out = check_in + timedelta(days=4)
    allocation_start = BASE_DATE + timedelta(days=90)
    allocation_end = allocation_start + timedelta(days=45)
    report_date = seed_info["report_date"]
    reservation_data = ReservationCreate(
        guest_id=seed_info["guest_id"],
        category_id=seed_info["category_id"],
        room_id=seed_info["room_id"],
        check_in_date=date(2030, 6, 1),
        check_out_date=date(2030, 6, 3),
        total_amount=Decimal("160.00"),
    )
    auto_priced_reservation_data = ReservationCreate(
        guest_id=seed_info["guest_id"],
        category_id=seed_info["category_id"],
        room_id=seed_info["room_id"],
        check_in_date=date(2030, 6, 1),
        check_out_date=date(2030, 6, 3),
    )

    direct_pending_query = _daily_report_balance_candidate_query(
        session,
        hotel_id=HOTEL_ID,
        report_date=report_date,
        mode="direct_pending",
    )
    direct_pending_projection = direct_pending_query.order_by(None).subquery(
        "daily_report_direct_pending"
    )
    direct_pending_summary_query = (
        session.query(
            direct_pending_projection.c.balance_currency_code,
            func.count(direct_pending_projection.c.id),
            func.sum(direct_pending_projection.c.direct_balance),
        )
        .group_by(direct_pending_projection.c.balance_currency_code)
    )

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
        "daily report flags": explain_query(
            session,
            engine,
            "daily report actionable flags (production path)",
            _daily_report_balance_candidate_query(
                session,
                hotel_id=HOTEL_ID,
                report_date=report_date,
                mode="flags",
            ),
            ("reservations", "transactions", "billing_adjustments"),
        )[0],
        "daily report direct balance summary": explain_query(
            session,
            engine,
            "daily report exact direct-balance summary (production path)",
            direct_pending_summary_query,
            ("reservations", "transactions", "billing_adjustments"),
        )[0],
        "daily report direct balance page": explain_query(
            session,
            engine,
            "daily report paginated direct-balance detail (production path)",
            direct_pending_query.offset(0).limit(50),
            ("reservations", "transactions", "billing_adjustments"),
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
            engine,
            "reservation.create_service",
            lambda: in_fresh_session(
                lambda db: create_reservation(db, reservation_data, hotel_id=HOTEL_ID)
            ),
            iterations,
        ),
        measure(
            engine,
            "reservation.create_auto_priced_service",
            lambda: in_fresh_session(
                lambda db: create_reservation(db, auto_priced_reservation_data, hotel_id=HOTEL_ID)
            ),
            iterations,
        ),
        measure(
            engine,
            "availability.check_room_availability",
            lambda: in_fresh_session(
                lambda db: check_room_availability(
                    db, seed_info["room_id"], check_in, check_out, hotel_id=HOTEL_ID
                )
            ),
            iterations,
        ),
        measure(
            engine,
            "availability.find_available_rooms",
            lambda: in_fresh_session(
                lambda db: find_available_rooms(
                    db, seed_info["category_id"], check_in, check_out, hotel_id=HOTEL_ID
                )
            ),
            iterations,
        ),
        measure(
            engine,
            "allocation.build_slots_from_db",
            lambda: in_fresh_session(
                lambda db: build_slots_from_db(db, allocation_start, allocation_end, HOTEL_ID)
            ),
            iterations,
        ),
        measure(
            engine,
            "balance.balance_due_from_transactions",
            lambda: in_fresh_session(
                lambda db: balance_due_from_transactions(db, HOTEL_ID, seed_info["reservation_id"])
            ),
            iterations,
        ),
        measure(
            engine,
            "daily_report",
            lambda: in_fresh_session(lambda db: daily_report(db, HOTEL_ID, report_date)),
            iterations,
        ),
        measure(
            engine,
            "guest_search.document",
            lambda: in_fresh_session(
                lambda db: search_guests(db, HOTEL_ID, seed_info["search_doc"], limit=20)
            ),
            iterations,
        ),
        measure(
            engine,
            "guest_search.last_name",
            lambda: in_fresh_session(
                lambda db: search_guests(db, HOTEL_ID, seed_info["search_last_name"], limit=20)
            ),
            iterations,
        ),
    ]

    return [
        BenchmarkResult(
            name=name,
            median_ms=median_ms,
            p95_ms=p95_ms,
            median_queries=median_queries,
            index_used=index_usage_for_operation(name, explain_results),
        )
        for name, median_ms, p95_ms, median_queries in measured
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
            seeded = False
            try:
                seed_info = seed(session)
                seeded = True
                results = run_benchmarks(session, SessionLocal, engine, seed_info, args.iterations)
                print_results(results)
            finally:
                session.rollback()
                if seeded:
                    cleanup(session)
                    print("Synthetic benchmark rows cleaned up.")
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
        try:
            with SessionLocal() as cleanup_session:
                cleanup(cleanup_session)
        except Exception as cleanup_error:
            print(
                "WARNING: failed to clean the synthetic hotel from hotel_chipre_test; "
                f"error_type={type(cleanup_error).__name__}",
                file=sys.stderr,
            )
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
