from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased, joinedload, lazyload, load_only

from app.models.operations import BillingAdjustment, ReservationAdjustment, ReservationAdjustmentStatusEnum, RoomMoveEvent
from app.models.ota_core import OTAReservationLink, OTAReservationLifecycleEnum
from app.models.company import Company
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.models.guest import Guest
from app.services.payment_service import _recommended_financial_action, get_reservation_financial_summary
from app.services.financial_ledger import external_paid_balance_credit
from app.services.reservation_service import (
    active_reservations,
    active_reservations_select,
    deferred_company_reservation_ids,
)
from app.services.timezones import hotel_today


class ReservationActionError(Exception):
    """Raised when operational action state cannot be resolved."""


_PRIORITY_SCORE = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

# Mirrors the trigger conditions read by `_build_pending_actions` /
# `_recommended_financial_action` so the SQL-level prefilter below can't drift
# silently from the actual candidates for an action.
_REFUND_REVIEW_STATUSES = {ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW}
_TERMINAL_STATUSES = {
    ReservationStatusEnum.CANCELLED,
    ReservationStatusEnum.CHECKED_OUT,
    ReservationStatusEnum.NO_SHOW,
}
_PROBLEM_ALLOCATION_STATUSES = {"manual_review", "unassigned", "error"}
_PROBLEM_SETTLEMENT_STATUSES = {"manual_resolution_required", "pending_hotel_action", "review_cancellation"}
_PENDING_ADJUSTMENT_STATUSES = {ReservationAdjustmentStatusEnum.DRAFT, ReservationAdjustmentStatusEnum.PENDING}
_PENDING_ADJUSTMENT_EXTERNAL_STATUSES = {"manual_resolution_required", "pending_hotel_action"}
_ACTIVE_WINDOW_DAYS = 1


@dataclass(slots=True)
class _ActionCandidate:
    action_key: str
    code: str
    priority: str
    title: str
    detail: str
    reference_type: str | None = None
    reference_id: int | None = None



def get_reservation_operations_summary(db: Session, *, hotel_id: int, reservation_id: int) -> dict[str, Any]:
    reservation = _get_reservation_or_error(db, hotel_id=hotel_id, reservation_id=reservation_id)
    hotel_date = hotel_today(db, hotel_id)
    financial_summary = get_reservation_financial_summary(db, hotel_id, reservation.id)
    if (
        reservation.status == ReservationStatusEnum.CANCELLED
        and financial_summary.get("recommended_next_action") == "collect_from_guest"
    ):
        # ReservationsPage also renders this field as a suggested next action.
        financial_summary["recommended_next_action"] = None
    ota_link, related_adjustments, latest_room_move = _get_operations_related_data(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
    )
    pending_actions = _build_pending_actions(
        reservation=reservation,
        ota_link=ota_link,
        related_adjustments=related_adjustments,
        financial_summary=financial_summary,
        today=hotel_date,
    )

    return {
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "status": reservation.status.value,
        "source": reservation.source.value,
        "source_provider_code": reservation.source_provider_code,
        "allocation_status": reservation.allocation_status,
        "requires_manual_review": reservation.requires_manual_review,
        "payment_collection_model": reservation.payment_collection_model,
        "settlement_status": reservation.settlement_status,
        "pending_action_count": len(pending_actions),
        "pending_actions": pending_actions,
        "financial_summary": financial_summary,
        "ota_link": _serialize_ota_link(ota_link),
        "open_adjustments": [_serialize_adjustment(adjustment) for adjustment in related_adjustments],
        "latest_room_move": _serialize_room_move(latest_room_move),
    }


def _get_operations_related_data(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
) -> tuple[OTAReservationLink | None, list[ReservationAdjustment], RoomMoveEvent | None]:
    """Fetch the three detail-only histories in one tenant-scoped round trip.

    The latest OTA link and room move use the same timestamp/id tie-breakers as
    their standalone readers. Adjustments remain unbounded and newest-first,
    including rows where this reservation is the resulting reservation.
    Relationship eager loading is disabled because the serializers read only
    the columns on these three records.
    """
    latest_ota_link_id = (
        select(OTAReservationLink.id)
        .where(
            OTAReservationLink.hotel_id == hotel_id,
            OTAReservationLink.reservation_id == reservation_id,
        )
        .order_by(OTAReservationLink.updated_at.desc(), OTAReservationLink.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    latest_room_move_id = (
        select(RoomMoveEvent.id)
        .where(
            RoomMoveEvent.hotel_id == hotel_id,
            RoomMoveEvent.reservation_id == reservation_id,
        )
        .order_by(RoomMoveEvent.occurred_at.desc(), RoomMoveEvent.id.desc())
        .limit(1)
        .scalar_subquery()
    )

    ota_link = aliased(OTAReservationLink)
    adjustment = aliased(ReservationAdjustment)
    room_move = aliased(RoomMoveEvent)
    rows = (
        db.query(ota_link, adjustment, room_move)
        .select_from(Reservation)
        .outerjoin(ota_link, ota_link.id == latest_ota_link_id)
        .outerjoin(
            adjustment,
            and_(
                adjustment.hotel_id == hotel_id,
                or_(
                    adjustment.reservation_id == reservation_id,
                    adjustment.resulting_reservation_id == reservation_id,
                ),
            ),
        )
        .outerjoin(room_move, room_move.id == latest_room_move_id)
        .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
        .options(lazyload("*"))
        .order_by(adjustment.requested_at.desc(), adjustment.id.desc())
        .all()
    )

    if not rows:
        return None, [], None

    latest_ota_link = next((row[0] for row in rows if row[0] is not None), None)
    latest_room_move = next((row[2] for row in rows if row[2] is not None), None)
    related_adjustments: list[ReservationAdjustment] = []
    seen_adjustment_ids: set[int] = set()
    for _, row_adjustment, _ in rows:
        if row_adjustment is not None and row_adjustment.id not in seen_adjustment_ids:
            seen_adjustment_ids.add(row_adjustment.id)
            related_adjustments.append(row_adjustment)

    return latest_ota_link, related_adjustments, latest_room_move



def list_pending_reservation_actions(
    db: Session,
    *,
    hotel_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    # Rank actions only after building them: candidate-level date ordering does
    # not match action priority, so capping IDs here can hide a later critical
    # action behind older medium-priority candidates.
    hotel_date = hotel_today(db, hotel_id)
    candidate_ids = _candidate_reservation_ids(db, hotel_id=hotel_id, today=hotel_date)
    if not candidate_ids:
        return []

    reservations_by_id = _load_pending_action_reservations(
        db,
        hotel_id=hotel_id,
        reservation_ids=candidate_ids,
    )
    latest_ota_links = _latest_ota_links_by_reservation(
        db,
        hotel_id=hotel_id,
        reservation_ids=candidate_ids,
    )
    related_adjustments = _related_adjustments_by_reservation(
        db,
        hotel_id=hotel_id,
        reservation_ids=candidate_ids,
    )
    financial_inputs = _pending_action_financial_inputs(
        db,
        hotel_id=hotel_id,
        reservations_by_id=reservations_by_id,
    )

    actions: list[dict[str, Any]] = []
    for reservation_id in candidate_ids:
        reservation = reservations_by_id.get(reservation_id)
        if reservation is None:
            # Preserve the existing failure if a candidate is concurrently
            # removed or moved outside this hotel's active reservation set.
            raise ReservationActionError(f"Reservation {reservation_id} not found")
        actions.extend(
            _build_pending_actions(
                reservation=reservation,
                ota_link=latest_ota_links.get(reservation_id),
                related_adjustments=related_adjustments.get(reservation_id, []),
                financial_summary=financial_inputs[reservation_id],
                today=hotel_date,
            )
        )

    actions.sort(
        key=lambda item: (
            -_PRIORITY_SCORE.get(item["priority"], 0),
            item["check_in_date"],
            item["reservation_id"],
            item["action_key"],
        )
    )
    return actions[:limit]


def _load_pending_action_reservations(
    db: Session,
    *,
    hotel_id: int,
    reservation_ids: list[int],
) -> dict[int, Reservation]:
    """Load just the fields needed by action construction, including guest names.

    Reservation has several default joined/select-in relationships. The wildcard
    lazy option keeps this list path from loading transaction history and other
    detail-only relations while the explicit guest join avoids a name lookup per
    candidate.
    """
    rows = (
        active_reservations(db, hotel_id)
        .options(
            lazyload("*"),
            joinedload(Reservation.guest).load_only(
                Guest.id,
                Guest.first_name,
                Guest.last_name,
            ),
            load_only(
                Reservation.id,
                Reservation.hotel_id,
                Reservation.confirmation_code,
                Reservation.guest_id,
                Reservation.room_id,
                Reservation.check_in_date,
                Reservation.check_out_date,
                Reservation.total_amount,
                Reservation.amount_paid,
                Reservation.currency_code,
                Reservation.external_id,
                Reservation.source_provider_code,
                Reservation.external_paid_amount,
                Reservation.external_paid_currency,
                Reservation.external_paid_confirmed,
                Reservation.status,
                Reservation.source,
                Reservation.allocation_status,
                Reservation.requires_manual_review,
                Reservation.payment_collection_model,
                Reservation.settlement_status,
                Reservation.company_id,
            ),
        )
        .filter(Reservation.id.in_(reservation_ids))
        .all()
    )
    return {reservation.id: reservation for reservation in rows}


def _latest_ota_links_by_reservation(
    db: Session,
    *,
    hotel_id: int,
    reservation_ids: list[int],
) -> dict[int, OTAReservationLink]:
    if not reservation_ids:
        return {}

    ranked_link_ids = (
        select(
            OTAReservationLink.id.label("link_id"),
            OTAReservationLink.reservation_id.label("reservation_id"),
            func.row_number()
            .over(
                partition_by=OTAReservationLink.reservation_id,
                order_by=(OTAReservationLink.updated_at.desc(), OTAReservationLink.id.desc()),
            )
            .label("latest_rank"),
        )
        .where(
            OTAReservationLink.hotel_id == hotel_id,
            OTAReservationLink.reservation_id.in_(reservation_ids),
        )
        .subquery("ranked_ota_links")
    )
    rows = (
        db.query(OTAReservationLink)
        .join(ranked_link_ids, OTAReservationLink.id == ranked_link_ids.c.link_id)
        .filter(
            OTAReservationLink.hotel_id == hotel_id,
            ranked_link_ids.c.latest_rank == 1,
        )
        .options(lazyload("*"))
        .all()
    )
    return {row.reservation_id: row for row in rows}


def _related_adjustments_by_reservation(
    db: Session,
    *,
    hotel_id: int,
    reservation_ids: list[int],
) -> dict[int, list[ReservationAdjustment]]:
    if not reservation_ids:
        return {}

    candidate_ids = set(reservation_ids)
    grouped: dict[int, list[ReservationAdjustment]] = defaultdict(list)
    rows = (
        db.query(ReservationAdjustment)
        .filter(
            ReservationAdjustment.hotel_id == hotel_id,
            or_(
                ReservationAdjustment.reservation_id.in_(reservation_ids),
                ReservationAdjustment.resulting_reservation_id.in_(reservation_ids),
            ),
            or_(
                ReservationAdjustment.status.in_(_PENDING_ADJUSTMENT_STATUSES),
                ReservationAdjustment.external_resolution_status.in_(_PENDING_ADJUSTMENT_EXTERNAL_STATUSES),
            ),
        )
        .order_by(ReservationAdjustment.requested_at.desc(), ReservationAdjustment.id.desc())
        .all()
    )
    for adjustment in rows:
        if adjustment.reservation_id in candidate_ids:
            grouped[adjustment.reservation_id].append(adjustment)
        if (
            adjustment.resulting_reservation_id in candidate_ids
            and adjustment.resulting_reservation_id != adjustment.reservation_id
        ):
            grouped[adjustment.resulting_reservation_id].append(adjustment)
    return grouped


def _pending_action_financial_inputs(
    db: Session,
    *,
    hotel_id: int,
    reservations_by_id: dict[int, Reservation],
) -> dict[int, dict[str, Any]]:
    """Batch only the two financial facts consumed by pending-action rules.

    This mirrors the detail summary's legacy paid fallback, confirmed OTA
    credit, billing-adjustment balance, company deferral, recommendation
    precedence, and reconciliation threshold without materializing each full
    transaction/adjustment summary per reservation.
    """
    reservation_ids = list(reservations_by_id)
    if not reservation_ids:
        return {}

    signed_amount = case(
        (Transaction.transaction_type == TransactionTypeEnum.REFUND, -Transaction.amount),
        else_=Transaction.amount,
    )
    completed_amount = case(
        (Transaction.status == TransactionStatusEnum.COMPLETED, signed_amount),
        else_=Decimal("0.00"),
    )
    transaction_rows = db.execute(
        select(
            Transaction.reservation_id,
            func.sum(completed_amount).label("completed_paid_amount"),
        ).where(
            Transaction.hotel_id == hotel_id,
            Transaction.reservation_id.in_(reservation_ids),
        ).group_by(Transaction.reservation_id)
    ).all()
    reservations_with_transactions = {row.reservation_id for row in transaction_rows}
    completed_paid_by_reservation = {
        row.reservation_id: Decimal(str(row.completed_paid_amount or 0)).quantize(Decimal("0.01"))
        for row in transaction_rows
    }

    adjustments_by_reservation: dict[int, list[Decimal]] = defaultdict(list)
    for row in db.execute(
        select(BillingAdjustment.reservation_id, BillingAdjustment.total_amount)
        .where(
            BillingAdjustment.hotel_id == hotel_id,
            BillingAdjustment.reservation_id.in_(reservation_ids),
        )
        .order_by(BillingAdjustment.effective_at, BillingAdjustment.id)
    ):
        adjustments_by_reservation[row.reservation_id].append(row.total_amount)

    deferred_ids = deferred_company_reservation_ids(
        db,
        hotel_id=hotel_id,
        reservations=tuple(reservations_by_id.values()),
    )

    summaries: dict[int, dict[str, Any]] = {}
    for reservation_id, reservation in reservations_by_id.items():
        ledger_paid = completed_paid_by_reservation.get(reservation_id, Decimal("0.00"))
        is_ota_reservation = bool(reservation.source_provider_code or reservation.external_id)
        if is_ota_reservation:
            external_paid = external_paid_balance_credit(reservation)
            paid = (ledger_paid + external_paid).quantize(Decimal("0.01"))
        elif reservation_id in reservations_with_transactions:
            paid = ledger_paid
        else:
            paid = Decimal(str(reservation.amount_paid or 0)).quantize(Decimal("0.01"))

        # This is the source used by reconciled_paid_amounts_by_reservation:
        # completed local ledger plus only explicitly confirmed, currency-safe
        # OTA credit, with no legacy amount_paid fallback.
        evidenced_paid = ledger_paid
        if is_ota_reservation:
            evidenced_paid = (evidenced_paid + external_paid_balance_credit(reservation)).quantize(
                Decimal("0.01")
            )

        is_deferred = reservation_id in deferred_ids
        if is_deferred:
            recommended_next_action = None
            has_reconciliation_gap = False
        else:
            adjustment_total = Decimal(
                str(round(sum(adjustments_by_reservation.get(reservation_id, [])), 2))
            )
            operational_total = Decimal(str(reservation.total_amount or 0)) + adjustment_total
            operational_balance_due = max(Decimal("0"), operational_total - paid)
            recommended_next_action = _recommended_financial_action(
                reservation=reservation,
                operational_balance_due=operational_balance_due,
            )
            if (
                reservation.status == ReservationStatusEnum.CANCELLED
                and recommended_next_action == "collect_from_guest"
            ):
                # Preserve the detail-summary compatibility override exactly.
                recommended_next_action = None
            materialized_paid = Decimal(str(reservation.amount_paid or 0))
            has_reconciliation_gap = abs(materialized_paid - evidenced_paid) > Decimal("0.01")

        summaries[reservation_id] = {
            "amount_paid": None if is_deferred else paid,
            "company_billing_deferred": is_deferred,
            "recommended_next_action": recommended_next_action,
            "has_financial_reconciliation_gap": has_reconciliation_gap,
        }
    return summaries


def _candidate_reservation_ids(
    db: Session,
    *,
    hotel_id: int,
    limit: int | None = None,
    today: date | None = None,
) -> list[int]:
    """Bulk-compute reservation ids that could produce a pending action.

    The SQL predicate mirrors the pending-action builders and financial
    recommendation rules. It preserves actionable terminal history, but does not transfer
    clean terminal reservations or their financial/reconciliation inputs into
    Python. Callers that need a complete priority-sorted action list should omit
    ``limit``; the optional SQL limit is for callers that explicitly accept a
    check-in-date prefix instead of the globally ranked action list.
    """
    hotel_date = today or hotel_today(db, hotel_id)
    cutoff = hotel_date - timedelta(days=_ACTIVE_WINDOW_DAYS)
    is_terminal = Reservation.status.in_(_TERMINAL_STATUSES)
    is_active = Reservation.status.notin_(_TERMINAL_STATUSES)
    overdue_stay_review = and_(
        Reservation.status == ReservationStatusEnum.CHECKED_IN,
        Reservation.check_out_date < hotel_date,
    )
    is_ota = or_(
        func.coalesce(Reservation.source_provider_code, "") != "",
        func.coalesce(Reservation.external_id, "") != "",
    )

    ota_manual_resolution = (
        select(1)
        .select_from(OTAReservationLink)
        .where(
            OTAReservationLink.hotel_id == hotel_id,
            OTAReservationLink.reservation_id == Reservation.id,
            OTAReservationLink.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
        )
        .exists()
    )
    pending_adjustment = (
        select(1)
        .select_from(ReservationAdjustment)
        .where(
            ReservationAdjustment.hotel_id == hotel_id,
            or_(
                ReservationAdjustment.reservation_id == Reservation.id,
                ReservationAdjustment.resulting_reservation_id == Reservation.id,
            ),
            or_(
                ReservationAdjustment.status.in_(_PENDING_ADJUSTMENT_STATUSES),
                ReservationAdjustment.external_resolution_status.in_(_PROBLEM_SETTLEMENT_STATUSES),
            ),
        )
        .exists()
    )
    has_billing_adjustment = (
        select(1)
        .select_from(BillingAdjustment)
        .where(
            BillingAdjustment.hotel_id == hotel_id,
            BillingAdjustment.reservation_id == Reservation.id,
        )
        .exists()
    )

    # This mirrors reconciled_paid_amounts_by_reservation(): completed local
    # payments/refunds plus a confirmed same-currency OTA credit, without the
    # legacy amount_paid fallback. Keeping the arithmetic in SQL lets old
    # clean terminal history stay inside the database instead of becoming an
    # unbounded Python-side reconciliation batch.
    signed_completed_amount = func.coalesce(
        select(
            func.sum(
                case(
                    (Transaction.transaction_type == TransactionTypeEnum.REFUND, -Transaction.amount),
                    else_=Transaction.amount,
                )
            )
        )
        .where(
            Transaction.hotel_id == hotel_id,
            Transaction.reservation_id == Reservation.id,
            Transaction.status == TransactionStatusEnum.COMPLETED,
        )
        .correlate(Reservation)
        .scalar_subquery(),
        Decimal("0.00"),
    )
    reservation_currency_value = case(
        (
            or_(Reservation.currency_code.is_(None), Reservation.currency_code == ""),
            "ARS",
        ),
        else_=Reservation.currency_code,
    )
    reservation_currency = func.upper(func.trim(reservation_currency_value))
    external_paid_currency_value = case(
        (
            or_(Reservation.external_paid_currency.is_(None), Reservation.external_paid_currency == ""),
            reservation_currency_value,
        ),
        else_=Reservation.external_paid_currency,
    )
    external_paid_currency = func.upper(func.trim(external_paid_currency_value))
    confirmed_external_credit = case(
        (
            and_(
                is_ota,
                Reservation.external_paid_confirmed.is_(True),
                Reservation.external_paid_amount > Decimal("0.00"),
                external_paid_currency == reservation_currency,
            ),
            Reservation.external_paid_amount,
        ),
        else_=Decimal("0.00"),
    )
    has_financial_reconciliation_gap = (
        func.abs(
            func.coalesce(Reservation.amount_paid, Decimal("0.00"))
            - signed_completed_amount
            - confirmed_external_credit
        )
        > Decimal("0.01")
    )
    deferred_company = (
        select(1)
        .select_from(Company)
        .where(
            Company.hotel_id == hotel_id,
            Company.id == Reservation.company_id,
            Company.payment_deferred.is_(True),
        )
        .exists()
    )
    refund_review_action = and_(
        Reservation.status.in_(_REFUND_REVIEW_STATUSES),
        Reservation.source == ReservationSourceEnum.DIRECT,
        func.coalesce(Reservation.source_provider_code, "") == "",
        func.coalesce(Reservation.external_id, "") == "",
        Reservation.settlement_status.notin_({"deferred", "settled"}),
        ~deferred_company,
        or_(
            func.coalesce(Reservation.amount_paid, Decimal("0.00")) > Decimal("0.00"),
            signed_completed_amount > Decimal("0.00"),
        ),
    )

    has_operational_action = or_(
        Reservation.requires_manual_review.is_(True),
        overdue_stay_review,
        and_(
            is_active,
            or_(
                Reservation.room_id.is_(None),
                Reservation.allocation_status.in_(_PROBLEM_ALLOCATION_STATUSES),
            ),
        ),
        and_(
            Reservation.status == ReservationStatusEnum.CANCELLED,
            Reservation.source != ReservationSourceEnum.DIRECT,
        ),
        Reservation.settlement_status.in_(_PROBLEM_SETTLEMENT_STATUSES),
        and_(
            Reservation.payment_collection_model == "ota_prepaid",
            Reservation.settlement_status.in_({"pending", "unknown"}),
        ),
        and_(
            Reservation.status != ReservationStatusEnum.CANCELLED,
            Reservation.payment_collection_model == "hotel_collect",
            or_(
                func.coalesce(Reservation.amount_paid, Decimal("0.00"))
                < func.coalesce(Reservation.total_amount, Decimal("0.00")),
                has_billing_adjustment,
            ),
        ),
        ota_manual_resolution,
        pending_adjustment,
        has_financial_reconciliation_gap,
        refund_review_action,
    )

    query = (
        active_reservations_select(hotel_id)
        .with_only_columns(Reservation.id)
        .where(
            or_(Reservation.check_out_date >= cutoff, is_terminal, overdue_stay_review),
            has_operational_action,
        )
        .order_by(Reservation.check_in_date, Reservation.id)
    )
    if limit is not None:
        query = query.limit(max(0, limit))

    return [reservation_id for (reservation_id,) in db.execute(query).all()]



def resolve_external_channel_follow_up(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    resolved_by_user_id: int | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    reservation = _get_reservation_or_error(db, hotel_id=hotel_id, reservation_id=reservation_id)
    ota_link = _get_latest_ota_link(db, hotel_id=hotel_id, reservation_id=reservation.id)
    adjustments = _get_related_adjustments(db, hotel_id=hotel_id, reservation_id=reservation.id)

    changed_adjustments = 0
    for adjustment in adjustments:
        if adjustment.external_resolution_status in {"manual_resolution_required", "pending_hotel_action"}:
            adjustment.external_resolution_status = "resolved"
            adjustment.resolved_at = datetime.now(timezone.utc)
            if notes:
                adjustment.notes = ((adjustment.notes or "").strip() + f"\n[RESOLVED] {notes}").strip()
            changed_adjustments += 1

    ota_link_resolved = False
    if ota_link and (
        ota_link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED
        or ota_link.sync_status == "manual_resolution_required"
    ):
        if reservation.status == ReservationStatusEnum.CANCELLED:
            ota_link.provider_state = OTAReservationLifecycleEnum.CANCELLED
        ota_link.sync_status = "resolved"
        ota_link.error_message = notes or None
        ota_link_resolved = True

    if reservation.settlement_status in {"manual_resolution_required", "pending_hotel_action"}:
        reservation.settlement_status = "resolved"

    db.flush()
    return {
        "reservation_id": reservation.id,
        "changed_adjustments": changed_adjustments,
        "ota_link_resolved": ota_link_resolved,
        "settlement_status": reservation.settlement_status,
        "resolved_by_user_id": resolved_by_user_id,
    }



def clear_reservation_manual_review(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    reviewed_by_user_id: int | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    reservation = _get_reservation_or_error(db, hotel_id=hotel_id, reservation_id=reservation_id)
    reservation.requires_manual_review = False
    if reservation.allocation_status == "manual_review":
        reservation.allocation_status = "assigned" if reservation.room_id is not None else "unassigned"
    if notes:
        reservation.notes = ((reservation.notes or "").strip() + f"\n[MANUAL REVIEW CLEARED] {notes}").strip()
    db.flush()
    return {
        "reservation_id": reservation.id,
        "requires_manual_review": reservation.requires_manual_review,
        "allocation_status": reservation.allocation_status,
        "reviewed_by_user_id": reviewed_by_user_id,
    }



def _guest_display_name(reservation: Reservation) -> str:
    """B6.2: hotel-vocabulary titles need a human name, not a system code."""
    guest = reservation.guest
    return guest.full_name if guest is not None else f"Huésped #{reservation.guest_id}"


def _fmt_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _build_pending_actions(
    *,
    reservation: Reservation,
    ota_link: OTAReservationLink | None,
    related_adjustments: list[ReservationAdjustment],
    financial_summary: dict[str, Any],
    today: date | None = None,
) -> list[dict[str, Any]]:
    candidates: list[_ActionCandidate] = []
    guest_name = _guest_display_name(reservation)
    check_in = _fmt_date(reservation.check_in_date)
    check_out = _fmt_date(reservation.check_out_date)

    def add(candidate: _ActionCandidate) -> None:
        candidates.append(candidate)

    active_reservation = reservation.status not in _TERMINAL_STATUSES

    if reservation.requires_manual_review:
        add(
            _ActionCandidate(
                action_key="manual_review_required",
                code="manual_review_required",
                priority="critical",
                title=f"Revisar reserva de {guest_name} — llega {check_in}",
                detail="La reserva quedo marcada para revision manual antes de seguir operando.",
            )
        )

    if (
        today is not None
        and reservation.status == ReservationStatusEnum.CHECKED_IN
        and reservation.check_out_date < today
    ):
        add(
            _ActionCandidate(
                action_key="overdue_stay_review",
                code="overdue_stay_review",
                priority="high",
                title=f"Revisar estadía vencida de {guest_name} — check-out {check_out}",
                detail=(
                    "La fecha prevista de check-out ya pasó y la reserva sigue en curso. "
                    "Abrí la ficha para que un operador revise la situación."
                ),
            )
        )

    if active_reservation and reservation.room_id is None:
        add(
            _ActionCandidate(
                action_key="assign_room",
                code="assign_room",
                priority="high" if reservation.check_in_date <= reservation.check_out_date else "medium",
                title=f"Asignar habitación a {guest_name} — llega {check_in}",
                detail="La reserva sigue sin habitacion asignada y requiere confirmacion operativa.",
            )
        )

    if active_reservation and reservation.allocation_status in {"manual_review", "unassigned", "error"}:
        add(
            _ActionCandidate(
                action_key=f"allocation:{reservation.allocation_status}",
                code="allocation_follow_up",
                priority="critical" if reservation.allocation_status == "error" else "high",
                title=f"Revisar asignación de habitación de {guest_name} — llega {check_in}",
                detail=f"El motor de asignacion dejo la reserva en estado '{reservation.allocation_status}'.",
            )
        )

    recommended_next_action = financial_summary.get("recommended_next_action")
    if recommended_next_action == "resolve_external_channel":
        add(
            _ActionCandidate(
                action_key="resolve_external_channel",
                code="resolve_external_channel",
                priority="critical",
                title=f"Resolver pago pendiente con el canal de {guest_name} — sale {check_out}",
                detail="La reserva requiere una accion pendiente contra la OTA o una resolucion manual del settlement.",
                reference_type="ota_link" if ota_link else None,
                reference_id=ota_link.id if ota_link else None,
            )
        )
    elif (
        recommended_next_action == "collect_from_guest"
        and reservation.status != ReservationStatusEnum.CANCELLED
    ):
        add(
            _ActionCandidate(
                action_key="collect_from_guest",
                code="collect_from_guest",
                priority="high",
                title=f"Cobrar saldo pendiente a {guest_name} — sale {check_out}",
                detail="Queda saldo operativo por cobrar directamente en el hotel.",
            )
        )
    elif recommended_next_action == "await_channel_settlement":
        add(
            _ActionCandidate(
                action_key="await_channel_settlement",
                code="await_channel_settlement",
                priority="medium",
                title=f"Esperar liquidación del canal de {guest_name} — sale {check_out}",
                detail="La reserva esta marcada como OTA prepaga y todavia falta confirmar el settlement del canal.",
            )
        )
    elif recommended_next_action == "review_cancellation_settlement":
        add(
            _ActionCandidate(
                action_key="review_cancellation_settlement",
                code="review_cancellation_settlement",
                priority="high",
                title=f"Revisar cancelación y liquidación de {guest_name} — sale {check_out}",
                detail="La reserva fue cancelada pero todavia requiere revisar el settlement o devolucion con el canal.",
            )
        )

    net_paid_amount = financial_summary.get("amount_paid")
    if (
        reservation.status in _REFUND_REVIEW_STATUSES
        and reservation.source == ReservationSourceEnum.DIRECT
        and not reservation.source_provider_code
        and not reservation.external_id
        and not financial_summary.get("company_billing_deferred")
        and net_paid_amount is not None
        and Decimal(str(net_paid_amount)) > Decimal("0.00")
    ):
        net_paid = Decimal(str(net_paid_amount)).quantize(Decimal("0.01"))
        currency = str(reservation.currency_code or "ARS").strip().upper()
        add(
            _ActionCandidate(
                action_key="refund_deposit",
                code="refund_deposit",
                priority="high",
                title=f"Revisar devolución pendiente de {guest_name} — sale {check_out}",
                detail=(
                    f"Hay {currency} {net_paid} de pagos netos registrados. Revisá las condiciones de "
                    "cancelación o no-show y definí manualmente si corresponde devolver el depósito; "
                    "esta alerta no ejecuta ningún movimiento."
                ),
            )
        )

    if financial_summary.get("has_financial_reconciliation_gap"):
        add(
            _ActionCandidate(
                action_key="financial_reconciliation_gap",
                code="financial_reconciliation_gap",
                priority="critical",
                title=f"Conciliar diferencia de pagos de {guest_name} — sale {check_out}",
                detail="El monto pagado en la reserva no coincide con la suma de transacciones registradas.",
            )
        )

    if ota_link and ota_link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED:
        add(
            _ActionCandidate(
                action_key=f"ota_link:{ota_link.id}:manual_resolution_required",
                code="resolve_external_channel",
                priority="critical",
                title=f"Cerrar estado en el canal externo de {guest_name} — sale {check_out}",
                detail="El vinculo OTA quedo en resolucion manual requerida y necesita cierre operativo.",
                reference_type="ota_link",
                reference_id=ota_link.id,
            )
        )

    for adjustment in related_adjustments:
        if adjustment.status in {ReservationAdjustmentStatusEnum.DRAFT, ReservationAdjustmentStatusEnum.PENDING}:
            add(
                _ActionCandidate(
                    action_key=f"adjustment:{adjustment.id}:review",
                    code="review_adjustment",
                    priority="high",
                    title=f"Revisar ajuste operativo de {guest_name} — sale {check_out}",
                    detail=f"Hay un ajuste '{adjustment.kind.value}' todavia en estado '{adjustment.status.value}'.",
                    reference_type="reservation_adjustment",
                    reference_id=adjustment.id,
                )
            )
        if adjustment.external_resolution_status in {"manual_resolution_required", "pending_hotel_action"}:
            add(
                _ActionCandidate(
                    action_key=f"adjustment:{adjustment.id}:external_resolution",
                    code="resolve_adjustment_external_action",
                    priority="high",
                    title=f"Resolver acción externa del ajuste de {guest_name} — sale {check_out}",
                    detail="El ajuste operativo requiere una accion pendiente sobre el canal o una confirmacion manual del hotel.",
                    reference_type="reservation_adjustment",
                    reference_id=adjustment.id,
                )
            )

    return [
        _decorate_action(reservation=reservation, candidate=candidate, guest_name=guest_name)
        for candidate in _dedupe_candidates(candidates)
    ]



def _decorate_action(*, reservation: Reservation, candidate: _ActionCandidate, guest_name: str) -> dict[str, Any]:
    return {
        "action_key": candidate.action_key,
        "code": candidate.code,
        "priority": candidate.priority,
        "title": candidate.title,
        "detail": candidate.detail,
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "guest_name": guest_name,
        "reservation_status": reservation.status.value,
        "source": reservation.source.value,
        "source_provider_code": reservation.source_provider_code,
        "payment_collection_model": reservation.payment_collection_model,
        "settlement_status": reservation.settlement_status,
        "check_in_date": reservation.check_in_date,
        "check_out_date": reservation.check_out_date,
        "reference_type": candidate.reference_type,
        "reference_id": candidate.reference_id,
    }



def _dedupe_candidates(candidates: list[_ActionCandidate]) -> list[_ActionCandidate]:
    deduped: dict[str, _ActionCandidate] = {}
    for candidate in candidates:
        existing = deduped.get(candidate.action_key)
        if existing is None or _PRIORITY_SCORE[candidate.priority] > _PRIORITY_SCORE[existing.priority]:
            deduped[candidate.action_key] = candidate
    return list(deduped.values())



def _get_reservation_or_error(db: Session, *, hotel_id: int, reservation_id: int) -> Reservation:
    reservation = active_reservations(db, hotel_id).filter(Reservation.id == reservation_id).first()
    if reservation is None:
        raise ReservationActionError(f"Reservation {reservation_id} not found")
    return reservation



def _get_latest_ota_link(db: Session, *, hotel_id: int, reservation_id: int) -> OTAReservationLink | None:
    return (
        db.query(OTAReservationLink)
        .filter(
            OTAReservationLink.hotel_id == hotel_id,
            OTAReservationLink.reservation_id == reservation_id,
        )
        .order_by(OTAReservationLink.updated_at.desc(), OTAReservationLink.id.desc())
        .first()
    )



def _get_related_adjustments(db: Session, *, hotel_id: int, reservation_id: int) -> list[ReservationAdjustment]:
    return (
        db.query(ReservationAdjustment)
        .filter(
            ReservationAdjustment.hotel_id == hotel_id,
            or_(
                ReservationAdjustment.reservation_id == reservation_id,
                ReservationAdjustment.resulting_reservation_id == reservation_id,
            ),
        )
        .order_by(ReservationAdjustment.requested_at.desc(), ReservationAdjustment.id.desc())
        .all()
    )



def _get_latest_room_move(db: Session, *, hotel_id: int, reservation_id: int) -> RoomMoveEvent | None:
    return (
        db.query(RoomMoveEvent)
        .filter(RoomMoveEvent.hotel_id == hotel_id, RoomMoveEvent.reservation_id == reservation_id)
        .order_by(RoomMoveEvent.occurred_at.desc(), RoomMoveEvent.id.desc())
        .first()
    )



def _serialize_ota_link(ota_link: OTAReservationLink | None) -> dict[str, Any] | None:
    if ota_link is None:
        return None
    return {
        "id": ota_link.id,
        "provider_id": ota_link.provider_id,
        "external_reservation_id": ota_link.external_reservation_id,
        "external_confirmation_code": ota_link.external_confirmation_code,
        "provider_state": ota_link.provider_state.value if hasattr(ota_link.provider_state, "value") else str(ota_link.provider_state),
        "sync_status": ota_link.sync_status,
        "error_message": ota_link.error_message,
    }



def _serialize_adjustment(adjustment: ReservationAdjustment) -> dict[str, Any]:
    return {
        "id": adjustment.id,
        "kind": adjustment.kind.value if hasattr(adjustment.kind, "value") else str(adjustment.kind),
        "status": adjustment.status.value if hasattr(adjustment.status, "value") else str(adjustment.status),
        "reason_code": adjustment.reason_code,
        "request_source": adjustment.request_source,
        "amount_delta": adjustment.amount_delta,
        "currency_code": adjustment.currency_code,
        "external_resolution_status": adjustment.external_resolution_status,
        "resulting_reservation_id": adjustment.resulting_reservation_id,
        "ota_reservation_link_id": adjustment.ota_reservation_link_id,
        "notes": adjustment.notes,
    }



def _serialize_room_move(room_move: RoomMoveEvent | None) -> dict[str, Any] | None:
    if room_move is None:
        return None
    return {
        "id": room_move.id,
        "move_type": room_move.move_type.value if hasattr(room_move.move_type, "value") else str(room_move.move_type),
        "reason_code": room_move.reason_code,
        "from_room_id": room_move.from_room_id,
        "to_room_id": room_move.to_room_id,
        "notes": room_move.notes,
        "occurred_at": room_move.occurred_at.isoformat() if room_move.occurred_at else None,
    }
