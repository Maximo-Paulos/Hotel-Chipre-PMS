from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.cash_register import CashSession, CashSessionStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.schemas.reports import (
    ActiveRoomBlockItem,
    AvailableWithReviewItem,
    CashSessionStatusRead,
    DailyOperationalReportRead,
    NightlyOperationalSummaryRead,
    OperationalAlertRead,
    OperationalReservationGroup,
    OperationalReservationSummary,
)


ACTIVE_RESERVATION_STATUSES = (
    ReservationStatusEnum.PENDING,
    ReservationStatusEnum.DEPOSIT_PAID,
    ReservationStatusEnum.FULLY_PAID,
    ReservationStatusEnum.PRE_CHECK_IN,
    ReservationStatusEnum.CHECKED_IN,
)

ARRIVAL_PENDING_STATUSES = (
    ReservationStatusEnum.PENDING,
    ReservationStatusEnum.DEPOSIT_PAID,
    ReservationStatusEnum.FULLY_PAID,
    ReservationStatusEnum.PRE_CHECK_IN,
)


def _guest_name(reservation: Reservation) -> str | None:
    guest = reservation.guest
    if not guest:
        return None
    return guest.full_name


def _reservation_summary(reservation: Reservation) -> OperationalReservationSummary:
    room = reservation.room
    return OperationalReservationSummary(
        reservation_id=reservation.id,
        confirmation_code=reservation.confirmation_code,
        guest_id=reservation.guest_id,
        guest_name=_guest_name(reservation),
        room_id=reservation.room_id,
        room_number=room.room_number if room else None,
        status=reservation.status.value,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        total_amount=Decimal(reservation.total_amount or 0),
        amount_paid=Decimal(reservation.amount_paid or 0),
        balance_due=reservation.balance_due,
    )


def _group(reservations: Iterable[Reservation]) -> OperationalReservationGroup:
    items = [_reservation_summary(reservation) for reservation in reservations]
    return OperationalReservationGroup(count=len(items), reservations=items)


def _active_room_blocks(db: Session, hotel_id: int, report_date: date) -> list[ActiveRoomBlockItem]:
    blocks = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.hotel_id == hotel_id,
            RoomBlock.resolved_at.is_(None),
            RoomBlock.starts_at <= report_date,
            or_(RoomBlock.ends_at.is_(None), RoomBlock.ends_at > report_date),
        )
        .order_by(RoomBlock.starts_at.asc(), RoomBlock.id.asc())
        .all()
    )
    return [
        ActiveRoomBlockItem(
            room_block_id=block.id,
            room_id=block.room_id,
            room_number=block.room.room_number if block.room else None,
            reason_code=block.reason_code.value,
            reason_note=block.reason_note,
            starts_at=block.starts_at,
            ends_at=block.ends_at,
            is_indefinite=bool(block.is_indefinite),
        )
        for block in blocks
    ]


def _available_with_review(db: Session, hotel_id: int, report_date: date) -> list[AvailableWithReviewItem]:
    reservations = (
        db.query(Reservation)
        .outerjoin(Room, Reservation.room_id == Room.id)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.requires_manual_review.is_(True),
            Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
            Reservation.check_out_date > report_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )
    return [
        AvailableWithReviewItem(
            reservation_id=reservation.id,
            confirmation_code=reservation.confirmation_code,
            room_id=reservation.room_id,
            room_number=reservation.room.room_number if reservation.room else None,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
            allocation_status=reservation.allocation_status,
        )
        for reservation in reservations
    ]


def _cash_session(db: Session, hotel_id: int) -> CashSessionStatusRead:
    session = (
        db.query(CashSession)
        .filter(CashSession.hotel_id == hotel_id, CashSession.status == CashSessionStatusEnum.OPEN)
        .order_by(CashSession.opened_at.desc(), CashSession.id.desc())
        .first()
    )
    if session is None:
        return CashSessionStatusRead(status="closed")
    return CashSessionStatusRead(
        status=session.status.value,
        session_id=session.id,
        opened_at=session.opened_at,
        opened_by_user_id=session.opened_by_user_id,
        currency_code=session.currency_code,
    )


def _alerts(
    *,
    pending_payments: OperationalReservationGroup,
    late_arrivals: list[OperationalReservationSummary],
    available_with_review: list[AvailableWithReviewItem],
    active_room_blocks: list[ActiveRoomBlockItem],
    cash_session: CashSessionStatusRead,
) -> list[OperationalAlertRead]:
    alerts: list[OperationalAlertRead] = []
    for item in pending_payments.reservations:
        alerts.append(
            OperationalAlertRead(
                code="pending_payment",
                severity="warning",
                message=f"Reservation {item.confirmation_code} has balance due.",
                reservation_id=item.reservation_id,
                room_id=item.room_id,
            )
        )
    for item in late_arrivals:
        alerts.append(
            OperationalAlertRead(
                code="late_arrival",
                severity="warning",
                message=f"Reservation {item.confirmation_code} has not checked in after its arrival date.",
                reservation_id=item.reservation_id,
                room_id=item.room_id,
            )
        )
    for item in available_with_review:
        alerts.append(
            OperationalAlertRead(
                code="available_with_review",
                severity="warning",
                message=f"Room {item.room_number or item.room_id} is assigned to a reservation requiring review.",
                reservation_id=item.reservation_id,
                room_id=item.room_id,
            )
        )
    for item in active_room_blocks:
        alerts.append(
            OperationalAlertRead(
                code="active_room_block",
                severity="info",
                message=f"Room {item.room_number or item.room_id} has an active block.",
                room_id=item.room_id,
                room_block_id=item.room_block_id,
            )
        )
    if cash_session.status != "open":
        alerts.append(
            OperationalAlertRead(
                code="cash_session_closed",
                severity="info",
                message="No open cash session is active for this hotel.",
            )
        )
    return alerts


def daily_report(db: Session, hotel_id: int, report_date: date) -> DailyOperationalReportRead:
    reservation_scope = db.query(Reservation).filter(Reservation.hotel_id == hotel_id)

    arrivals = (
        reservation_scope.filter(
            Reservation.check_in_date == report_date,
            Reservation.status != ReservationStatusEnum.CANCELLED,
        )
        .order_by(Reservation.id.asc())
        .all()
    )
    departures = (
        reservation_scope.filter(
            Reservation.check_out_date == report_date,
            Reservation.status != ReservationStatusEnum.CANCELLED,
        )
        .order_by(Reservation.id.asc())
        .all()
    )
    balance_candidates = (
        reservation_scope.filter(
            Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
            Reservation.check_out_date > report_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )
    pending_payments = [reservation for reservation in balance_candidates if reservation.balance_due > 0]
    late_arrivals = (
        reservation_scope.filter(
            Reservation.check_in_date < report_date,
            Reservation.check_out_date > report_date,
            Reservation.status.in_(ARRIVAL_PENDING_STATUSES),
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )

    pending_group = _group(pending_payments)
    late_items = [_reservation_summary(reservation) for reservation in late_arrivals]
    review_items = _available_with_review(db, hotel_id, report_date)
    block_items = _active_room_blocks(db, hotel_id, report_date)
    cash_session = _cash_session(db, hotel_id)

    return DailyOperationalReportRead(
        hotel_id=hotel_id,
        report_date=report_date,
        generated_at=datetime.now(timezone.utc),
        arrivals=_group(arrivals),
        departures=_group(departures),
        pending_payments=pending_group,
        late_arrivals=late_items,
        available_with_review=review_items,
        active_room_blocks=block_items,
        cash_session=cash_session,
        alerts=_alerts(
            pending_payments=pending_group,
            late_arrivals=late_items,
            available_with_review=review_items,
            active_room_blocks=block_items,
            cash_session=cash_session,
        ),
    )


def nightly_summary(db: Session, hotel_id: int, report_date: date) -> NightlyOperationalSummaryRead:
    report = daily_report(db, hotel_id, report_date)
    return NightlyOperationalSummaryRead(
        hotel_id=hotel_id,
        report_date=report.report_date,
        generated_at=report.generated_at,
        alert_count=len(report.alerts),
        pending_payment_count=report.pending_payments.count,
        late_arrival_count=len(report.late_arrivals),
        available_with_review_count=len(report.available_with_review),
        active_room_block_count=len(report.active_room_blocks),
        cash_session_status=report.cash_session.status,
        alerts=report.alerts,
    )


def operational_report_recipients(db: Session, hotel_id: int) -> list[str]:
    hotel = db.get(HotelConfiguration, hotel_id)
    if not hotel:
        return []
    recipients: list[str] = []
    try:
        policies = hotel.get_extra_policies()
    except (TypeError, ValueError, json.JSONDecodeError):
        policies = {}
    configured = policies.get("operational_report_recipients") if isinstance(policies, dict) else None
    if isinstance(configured, list):
        recipients.extend(str(item).strip().lower() for item in configured if str(item).strip())
    if hotel.owner_email:
        recipients.append(hotel.owner_email.strip().lower())
    return sorted(set(recipients))


def nightly_summary_email_body(summary: NightlyOperationalSummaryRead) -> str:
    lines = [
        f"Nightly operational summary for hotel {summary.hotel_id}",
        f"Date: {summary.report_date.isoformat()}",
        "",
        f"Alerts: {summary.alert_count}",
        f"Pending payments: {summary.pending_payment_count}",
        f"Late arrivals: {summary.late_arrival_count}",
        f"Available with review: {summary.available_with_review_count}",
        f"Active room blocks: {summary.active_room_block_count}",
        f"Cash session: {summary.cash_session_status}",
    ]
    if summary.alerts:
        lines.append("")
        lines.append("Alerts")
        for alert in summary.alerts:
            lines.append(f"- [{alert.severity}] {alert.code}: {alert.message}")
    return "\n".join(lines)
