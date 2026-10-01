import csv
from datetime import date as date_type, timedelta
from io import StringIO

from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, authorize_permission, get_auth_context, require_permission
from app.models.cash_register import CashMovementTypeEnum
from app.models.reservation import Reservation
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum
from app.schemas.cash_register import (
    CashCloseReportRead,
    CashCustodyReceipt,
    CashMovementCreate,
    CashMovementRead,
    CashSessionClose,
    CashSessionOpen,
    CashSessionRead,
    CashSessionSummaryRead,
    CashDailySummaryRead,
)
from app.services.cash_register_service import (
    CashRegisterError,
    add_movement,
    approve_close_difference,
    close_session,
    confirm_cash_custody,
    enqueue_pending_difference_notification,
    get_close_report_for_session,
    get_latest_close_report,
    get_session_summary,
    list_pending_close_reports,
    list_pending_cash_custody_reports,
    list_movements,
    list_sessions,
    open_session,
)
from app.services.permission_service import (
    PERMISSION_CASH_APPROVE_DIFFERENCE,
    PERMISSION_CASH_CUSTODY_RECEIVE,
    PERMISSION_CASH_EXPENSE,
    PERMISSION_CASH_OPERATE,
    PERMISSION_CASH_VIEW,
)
from app.services.distributed_lock import DistributedLockBusy, DistributedLockUnavailable
from app.services.actor_label_service import resolve_hotel_actor_labels
from app.services.cash_daily_summary_service import ENTRY_LIMIT, get_daily_summary
from app.services.csv_export_safety import spreadsheet_safe_row


router = APIRouter(tags=["Cash Register"])


def _require_cash_difference_approval_when_requested(
    request: Request,
    payload: CashSessionClose,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Apply the separate approval capability only when closing requires it."""
    if not payload.approve_difference:
        return context
    return authorize_permission(request, db, context, PERMISSION_CASH_APPROVE_DIFFERENCE)


@router.get("/api/cash-register/daily-summary", response_model=CashDailySummaryRead)
@router.get("/cash-register/daily-summary", response_model=CashDailySummaryRead)
def cash_daily_summary(
    date: str,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    try:
        report_date = date_type.fromisoformat(date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date debe tener formato YYYY-MM-DD") from exc
    try:
        return get_daily_summary(
            db,
            hotel_id=context.hotel_id,
            report_date=report_date,
            currency_code=currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/cash-register/export.csv")
@router.get("/cash-register/export.csv")
def export_cash_ledger_csv(
    date: str | None = Query(default=None, description="Día único YYYY-MM-DD"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    """Export the existing transaction/cash ledger without creating a second balance."""
    try:
        if date:
            start = date_type.fromisoformat(date)
            end = start
        else:
            start = date_type.fromisoformat(from_date) if from_date else date_type.today()
            end = date_type.fromisoformat(to_date) if to_date else start
        if end < start:
            raise ValueError("El período de caja es inválido")
        if (end - start).days > 366:
            raise ValueError("El período máximo de exportación es de 367 días")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="El período debe usar fechas YYYY-MM-DD válidas") from exc

    selected_currency = currency.strip().upper() if currency else None
    reports = []
    currencies: set[str] = set()
    current = start
    while current <= end:
        try:
            report = get_daily_summary(
                db,
                hotel_id=context.hotel_id,
                report_date=current,
                currency_code=selected_currency,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if report.get("entries_truncated"):
            raise HTTPException(
                status_code=413,
                detail="La jornada excede el máximo de movimientos del informe; acotá el período antes de exportar.",
            )
        reports.append(report)
        currencies.update(
            str(entry.get("currency_code") or "").upper()
            for entry in report.get("entries", [])
            if entry.get("currency_code")
        )
        current += timedelta(days=1)

    prior_receipt_query = (
        db.query(Transaction, Reservation.confirmation_code)
        .join(
            Reservation,
            and_(
                Reservation.hotel_id == Transaction.hotel_id,
                Reservation.id == Transaction.reservation_id,
            ),
        )
        .filter(
            Transaction.hotel_id == context.hotel_id,
            Transaction.status == TransactionStatusEnum.COMPLETED,
            Transaction.payment_method == PaymentMethodEnum.CASH,
            Transaction.collected_before.is_(True),
            Transaction.collected_on >= start,
            Transaction.collected_on <= end,
        )
        .order_by(Transaction.collected_on.asc(), Transaction.id.asc())
    )
    if selected_currency:
        prior_receipt_query = prior_receipt_query.filter(
            func.upper(Transaction.currency) == selected_currency
        )
    prior_receipt_rows = prior_receipt_query.limit(ENTRY_LIMIT + 1).all()
    if len(prior_receipt_rows) > ENTRY_LIMIT:
        raise HTTPException(
            status_code=413,
            detail="El período excede el máximo de cobros previos exportables; acotá el período antes de exportar.",
        )
    currencies.update(
        str(transaction.currency or "ARS").upper()
        for transaction, _confirmation_code in prior_receipt_rows
        if transaction.currency
    )
    if selected_currency:
        currencies = {selected_currency}
    elif len(currencies) > 1:
        raise HTTPException(
            status_code=422,
            detail="Elegí una moneda para exportar: el sistema no convierte monedas automáticamente",
        )

    columns = [
        "report_date", "hotel_id", "currency_code", "entry_type", "occurred_at",
        "actor", "actor_user_id", "reservation_id", "transaction_id", "cash_movement_id",
        "amount", "signed_amount", "payment_method", "transaction_type", "movement_type",
        "provider_code", "description", "recorded_at",
    ]
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for report in reports:
        for entry in report.get("entries", []):
            entry_currency = str(entry.get("currency_code") or "").upper()
            if selected_currency and entry_currency != selected_currency:
                continue
            writer.writerow(
                spreadsheet_safe_row({
                    "report_date": report["report_date"],
                    "hotel_id": report["hotel_id"],
                    "currency_code": entry_currency,
                    "entry_type": entry.get("entry_type"),
                    "occurred_at": entry.get("occurred_at").isoformat() if entry.get("occurred_at") else "",
                    "actor": entry.get("actor_name"),
                    "actor_user_id": entry.get("actor_user_id"),
                    "reservation_id": entry.get("reservation_id"),
                    "transaction_id": entry.get("transaction_id"),
                    "cash_movement_id": entry.get("cash_movement_id"),
                    "amount": entry.get("amount"),
                    "signed_amount": entry.get("signed_amount"),
                    "payment_method": entry.get("payment_method"),
                    "transaction_type": entry.get("transaction_type"),
                    "movement_type": entry.get("movement_type"),
                    "provider_code": entry.get("provider_code"),
                    "description": entry.get("description"),
                    "recorded_at": "",
                })
            )
    actor_labels = resolve_hotel_actor_labels(
        db,
        hotel_id=context.hotel_id,
        user_ids=(transaction.created_by_user_id for transaction, _ in prior_receipt_rows),
    )
    for transaction, confirmation_code in prior_receipt_rows:
        receipt_currency = str(transaction.currency or "ARS").upper()
        if selected_currency and receipt_currency != selected_currency:
            continue
        writer.writerow(
            spreadsheet_safe_row({
                "report_date": transaction.collected_on.isoformat(),
                "hotel_id": context.hotel_id,
                "currency_code": receipt_currency,
                "entry_type": "prior_receipt",
                "occurred_at": transaction.collected_on.isoformat(),
                "actor": actor_labels.get(transaction.created_by_user_id, "Usuario") if transaction.created_by_user_id else "Sistema",
                "actor_user_id": transaction.created_by_user_id,
                "reservation_id": transaction.reservation_id,
                "transaction_id": transaction.id,
                "cash_movement_id": "",
                "amount": transaction.amount,
                "signed_amount": transaction.amount,
                "payment_method": "cash",
                "transaction_type": "",
                "movement_type": "",
                "provider_code": "",
                "description": transaction.prior_receipt_note,
                "recorded_at": transaction.created_at.isoformat() if transaction.created_at else "",
            })
        )
    filename = f"caja-{start.isoformat()}-{end.isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/cash-register/sessions", response_model=CashSessionRead, status_code=status.HTTP_201_CREATED)
@router.post("/cash-register/sessions", response_model=CashSessionRead, status_code=status.HTTP_201_CREATED)
def open_cash_session(
    payload: CashSessionOpen,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    try:
        session = open_session(
            db,
            hotel_id=context.hotel_id,
            opened_by_user_id=context.user_id,
            opening_balance=payload.opening_balance,
            currency_code=payload.currency_code,
            notes=payload.notes,
        )
        db.commit()
        db.refresh(session)
        return session
    except CashRegisterError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/cash-register/sessions", response_model=list[CashSessionRead])
@router.get("/cash-register/sessions", response_model=list[CashSessionRead])
def list_cash_sessions(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    return list_sessions(db, hotel_id=context.hotel_id)


@router.get("/api/cash-register/close-reports/latest", response_model=CashCloseReportRead | None)
@router.get("/cash-register/close-reports/latest", response_model=CashCloseReportRead | None)
def latest_cash_close_report(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    return get_latest_close_report(db, hotel_id=context.hotel_id)


@router.get("/api/cash-register/close-reports/pending", response_model=list[CashCloseReportRead])
@router.get("/cash-register/close-reports/pending", response_model=list[CashCloseReportRead])
def pending_cash_close_reports(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    return list_pending_close_reports(db, hotel_id=context.hotel_id)


@router.get(
    "/api/cash-register/close-reports/custody/pending",
    response_model=list[CashCloseReportRead],
)
@router.get(
    "/cash-register/close-reports/custody/pending",
    response_model=list[CashCloseReportRead],
)
def pending_cash_custody_reports(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    return list_pending_cash_custody_reports(db, hotel_id=context.hotel_id)


@router.get(
    "/api/cash-register/sessions/{session_id}/close-report",
    response_model=CashCloseReportRead | None,
)
@router.get(
    "/cash-register/sessions/{session_id}/close-report",
    response_model=CashCloseReportRead | None,
)
def cash_session_close_report(
    session_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    return get_close_report_for_session(db, hotel_id=context.hotel_id, session_id=session_id)


@router.post(
    "/api/cash-register/sessions/{session_id}/movements",
    response_model=CashMovementRead,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/cash-register/sessions/{session_id}/movements",
    response_model=CashMovementRead,
    status_code=status.HTTP_201_CREATED,
)
def add_cash_movement(
    session_id: int,
    payload: CashMovementCreate,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    try:
        if payload.movement_type == CashMovementTypeEnum.EXPENSE:
            authorize_permission(request, db, context, PERMISSION_CASH_EXPENSE)
        movement = add_movement(
            db,
            hotel_id=context.hotel_id,
            session_id=session_id,
            recorded_by_user_id=context.user_id,
            movement_type=payload.movement_type,
            amount=payload.amount,
            description=payload.description,
            reservation_id=payload.reservation_id,
            transaction_id=payload.transaction_id,
        )
        db.commit()
        db.refresh(movement)
        return movement
    except CashRegisterError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/cash-register/sessions/{session_id}/summary", response_model=CashSessionSummaryRead)
@router.get("/cash-register/sessions/{session_id}/summary", response_model=CashSessionSummaryRead)
def cash_session_summary(
    session_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    try:
        return get_session_summary(db, hotel_id=context.hotel_id, session_id=session_id)
    except CashRegisterError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/api/cash-register/sessions/{session_id}/movements", response_model=list[CashMovementRead])
@router.get("/cash-register/sessions/{session_id}/movements", response_model=list[CashMovementRead])
def list_cash_movements(
    session_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    return list_movements(db, hotel_id=context.hotel_id, session_id=session_id)


@router.post("/api/cash-register/sessions/{session_id}/close", response_model=CashCloseReportRead)
@router.post("/cash-register/sessions/{session_id}/close", response_model=CashCloseReportRead)
def close_cash_session(
    session_id: int,
    payload: CashSessionClose,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
    _approval_context: AuthContext = Depends(_require_cash_difference_approval_when_requested),
):
    try:
        report = close_session(
            db,
            hotel_id=context.hotel_id,
            session_id=session_id,
            closed_by_user_id=context.user_id,
            counted_balance=payload.counted_balance,
            notes=payload.notes,
            approved_by_user_id=context.user_id if payload.approve_difference else None,
        )
        enqueue_pending_difference_notification(db, report)
        db.commit()
        db.refresh(report)
        return report
    except CashRegisterError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except DistributedLockBusy:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya hay otro arqueo de esta caja en curso")
    except DistributedLockUnavailable:
        db.rollback()
        raise HTTPException(status_code=503, detail="El control de concurrencia no está disponible")


@router.post(
    "/api/cash-register/close-reports/{report_id}/custody/confirm",
    response_model=CashCloseReportRead,
)
@router.post(
    "/cash-register/close-reports/{report_id}/custody/confirm",
    response_model=CashCloseReportRead,
)
def confirm_cash_custody_receipt(
    report_id: int,
    payload: CashCustodyReceipt | None = Body(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_CUSTODY_RECEIVE)),
):
    try:
        report = confirm_cash_custody(
            db,
            hotel_id=context.hotel_id,
            report_id=report_id,
            received_by_user_id=context.user_id or 0,
            successor_float_amount=(payload.successor_float_amount if payload else Decimal("0.00")),
        )
        db.commit()
        db.refresh(report)
        return report
    except CashRegisterError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/cash-register/close-reports/{report_id}/approve", response_model=CashCloseReportRead)
@router.post("/cash-register/close-reports/{report_id}/approve", response_model=CashCloseReportRead)
def approve_cash_close_difference(
    report_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_APPROVE_DIFFERENCE)),
):
    try:
        report = approve_close_difference(
            db,
            hotel_id=context.hotel_id,
            report_id=report_id,
            approved_by_user_id=context.user_id,
        )
        db.commit()
        db.refresh(report)
        return report
    except CashRegisterError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
