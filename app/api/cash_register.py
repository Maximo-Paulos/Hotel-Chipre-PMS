import csv
from datetime import date as date_type, datetime, timedelta, timezone
from io import StringIO
from zoneinfo import ZoneInfo

from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, authorize_permission, get_auth_context, require_permission
from app.models.cash_register import CashMovementTypeEnum
from app.models.cash_expense import CashExpenseStatusEnum
from app.models.reservation import Reservation
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum
from app.schemas.cash_register import (
    CashCloseReportRead,
    CashExpenseCreate,
    CashExpenseRead,
    CashExpenseReject,
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
    PERMISSION_CASH_ADJUSTMENT_MANAGE,
    PERMISSION_CASH_APPROVE_DIFFERENCE,
    PERMISSION_CASH_CUSTODY_RECEIVE,
    PERMISSION_CASH_EXPENSE,
    PERMISSION_CASH_EXPENSE_APPROVE,
    PERMISSION_CASH_OPERATE,
    PERMISSION_CASH_VIEW,
)
from app.services.distributed_lock import DistributedLockBusy, DistributedLockUnavailable
from app.services.actor_label_service import resolve_hotel_actor_labels
from app.services.cash_daily_summary_service import ENTRY_LIMIT, get_daily_summary
from app.services.csv_export_safety import spreadsheet_safe_row
from app.services.cash_expense_service import (
    CashExpenseError,
    approve_cash_expense,
    create_cash_expense,
    get_cash_expense_receipt_bytes,
    list_cash_expenses,
    recover_failed_cash_expense_commit,
    reject_cash_expense,
)


router = APIRouter(tags=["Cash Register"])


def _close_report_read(db: Session, report) -> dict | None:
    if report is None:
        return None
    actor_ids = (
        report.closed_by_user_id,
        report.approved_by_user_id,
        report.successor_float_declared_by_user_id,
    )
    labels = resolve_hotel_actor_labels(db, hotel_id=report.hotel_id, user_ids=actor_ids)
    data = CashCloseReportRead.model_validate(report).model_dump()
    data["closed_by_name"] = labels.get(report.closed_by_user_id) if report.closed_by_user_id else None
    data["approved_by_name"] = labels.get(report.approved_by_user_id) if report.approved_by_user_id else None
    data["successor_float_declared_by_name"] = (
        labels.get(report.successor_float_declared_by_user_id)
        if report.successor_float_declared_by_user_id else None
    )
    return data


def _cash_expense_read(db: Session, expense, *, actor_labels: dict[int, str] | None = None) -> dict:
    labels = actor_labels
    if labels is None:
        actor_ids = (expense.recorded_by_user_id, expense.approved_by_user_id, expense.rejected_by_user_id)
        labels = resolve_hotel_actor_labels(db, hotel_id=expense.hotel_id, user_ids=actor_ids)
    return CashExpenseRead(
        id=expense.id,
        hotel_id=expense.hotel_id,
        session_id=expense.session_id,
        amount=expense.amount,
        currency_code=expense.currency_code,
        category=expense.category,
        vendor=expense.vendor,
        description=expense.description,
        receipt_reference=expense.receipt_reference,
        receipt_filename=expense.receipt_filename,
        has_receipt_image=bool(expense.receipt_object_id),
        status=expense.status,
        cash_movement_id=expense.cash_movement_id,
        recorded_by_user_id=expense.recorded_by_user_id,
        recorded_by_name=labels.get(expense.recorded_by_user_id) if expense.recorded_by_user_id else None,
        approved_by_user_id=expense.approved_by_user_id,
        approved_by_name=labels.get(expense.approved_by_user_id) if expense.approved_by_user_id else None,
        rejected_by_user_id=expense.rejected_by_user_id,
        rejected_by_name=labels.get(expense.rejected_by_user_id) if expense.rejected_by_user_id else None,
        rejection_reason=expense.rejection_reason,
        created_at=expense.created_at,
        approved_at=expense.approved_at,
        rejected_at=expense.rejected_at,
    ).model_dump()


def _csv_local_datetime(value: datetime | None, timezone_name: str) -> str:
    if value is None:
        return ""
    instant = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return instant.astimezone(ZoneInfo(timezone_name)).strftime("%d/%m/%Y %H:%M:%S")


def _csv_local_date(value: date_type | str | None) -> str:
    if value is None:
        return ""
    parsed = date_type.fromisoformat(value) if isinstance(value, str) else value
    return parsed.strftime("%d/%m/%Y")


def _csv_decimal(value) -> str:
    if value is None or value == "":
        return ""
    try:
        return format(Decimal(str(value)), ".2f").replace(".", ",")
    except (ValueError, ArithmeticError):
        return ""


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
            func.upper(func.coalesce(Transaction.tender_currency, Transaction.currency)) == selected_currency
        )
    prior_receipt_rows = prior_receipt_query.limit(ENTRY_LIMIT + 1).all()
    if len(prior_receipt_rows) > ENTRY_LIMIT:
        raise HTTPException(
            status_code=413,
            detail="El período excede el máximo de cobros previos exportables; acotá el período antes de exportar.",
        )
    currencies.update(
        str(transaction.tender_currency or transaction.currency or "ARS").upper()
        for transaction, _confirmation_code in prior_receipt_rows
        if transaction.tender_currency or transaction.currency
    )
    if selected_currency:
        currencies = {selected_currency}
    elif len(currencies) > 1:
        raise HTTPException(
            status_code=422,
            detail="Elegí una moneda para exportar: el sistema no convierte monedas automáticamente",
        )

    columns = [
        "fecha_local", "hotel_id", "moneda", "tipo", "fecha_hora_local", "responsable",
        "usuario_id", "reserva_id", "transaccion_id", "movimiento_id", "lote_grupal_id",
        "sesion_id", "importe", "importe_neto", "medio_pago", "tipo_transaccion",
        "tipo_movimiento", "proveedor", "descripcion", "apertura", "esperado",
        "contado", "diferencia", "estado_turno", "registrado_el",
    ]
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, delimiter=";", lineterminator="\r\n")
    writer.writeheader()
    export_entries: list[tuple[dict, dict]] = []
    for report in reports:
        export_entries.extend((report, entry) for entry in report.get("entries", []))

    # A group collection is one operator action. Keep the child transactions in
    # their ledgers, but show one reconciled line in the human-facing export.
    entries_by_batch: dict[int, list[tuple[dict, dict]]] = {}
    ordinary_entries: list[tuple[dict, dict]] = []
    for report, entry in export_entries:
        batch_id = entry.get("group_payment_batch_id")
        if batch_id and entry.get("entry_type") == "payment":
            entries_by_batch.setdefault(int(batch_id), []).append((report, entry))
        else:
            ordinary_entries.append((report, entry))
    for batch_id, batch_rows in entries_by_batch.items():
        first_report, first_entry = min(
            batch_rows,
            key=lambda item: item[1].get("occurred_at") or datetime.min.replace(tzinfo=timezone.utc),
        )
        grouped_entry = dict(first_entry)
        grouped_entry.update(
            {
                "transaction_id": None,
                "reservation_id": None,
                "amount": sum((Decimal(str(entry.get("amount") or 0)) for _report, entry in batch_rows), Decimal("0.00")),
                "signed_amount": sum((Decimal(str(entry.get("signed_amount") or 0)) for _report, entry in batch_rows), Decimal("0.00")),
                "description": f"Cobro grupal · {len(batch_rows)} reserva(s)",
                "group_payment_batch_id": batch_id,
            }
        )
        ordinary_entries.append((first_report, grouped_entry))

    for report, entry in sorted(
        ordinary_entries,
        key=lambda item: (
        item[1].get("occurred_at") or datetime.min.replace(tzinfo=timezone.utc),
        item[1].get("transaction_id") or item[1].get("cash_movement_id") or item[1].get("group_payment_batch_id") or 0,
        ),
    ):
        entry_currency = str(entry.get("currency_code") or "").upper()
        if selected_currency and entry_currency != selected_currency:
            continue
        occurred_at = entry.get("occurred_at")
        row = {
            "fecha_local": _csv_local_date(report["report_date"]),
            "hotel_id": report["hotel_id"],
            "moneda": entry_currency,
            "tipo": "cobro" if entry.get("entry_type") == "payment" else "movimiento_manual",
            "fecha_hora_local": _csv_local_datetime(occurred_at, report["timezone"]),
            "responsable": entry.get("actor_name"),
            "usuario_id": entry.get("actor_user_id"),
            "reserva_id": entry.get("reservation_id"),
            "transaccion_id": entry.get("transaction_id"),
            "movimiento_id": entry.get("cash_movement_id"),
            "lote_grupal_id": entry.get("group_payment_batch_id"),
            "sesion_id": "",
            "importe": entry.get("amount"),
            "importe_neto": entry.get("signed_amount"),
            "medio_pago": entry.get("payment_method"),
            "tipo_transaccion": entry.get("transaction_type"),
            "tipo_movimiento": entry.get("movement_type"),
            "proveedor": entry.get("provider_code"),
            "descripcion": entry.get("description"),
            "apertura": "",
            "esperado": "",
            "contado": "",
            "diferencia": "",
            "estado_turno": "",
            "registrado_el": "",
        }
        safe_row = spreadsheet_safe_row(row)
        safe_row["importe"] = _csv_decimal(entry.get("amount"))
        safe_row["importe_neto"] = _csv_decimal(entry.get("signed_amount"))
        writer.writerow(safe_row)

    # Include each turno's reconciliation once in the selected local date
    # range. Open sessions carry an expected balance with blank count fields.
    for report in reports:
        for shift in report.get("sessions", []):
            shift_currency = str(shift.get("currency_code") or report.get("currency_code") or "").upper()
            if selected_currency and shift_currency != selected_currency:
                continue
            occurred_at = shift.get("closed_at") or shift.get("opened_at")
            row = {
                "fecha_local": _csv_local_date(report["report_date"]),
                "hotel_id": report["hotel_id"],
                "moneda": shift_currency,
                "tipo": "conciliacion_turno",
                "fecha_hora_local": _csv_local_datetime(occurred_at, report["timezone"]),
                "responsable": shift.get("closed_by_name") or shift.get("opened_by_name"),
                "usuario_id": shift.get("closed_by_user_id") or shift.get("opened_by_user_id"),
                "reserva_id": "",
                "transaccion_id": "",
                "movimiento_id": "",
                "lote_grupal_id": "",
                "sesion_id": shift.get("session_id"),
                "importe": "",
                "importe_neto": "",
                "medio_pago": "",
                "tipo_transaccion": "",
                "tipo_movimiento": "",
                "proveedor": "",
                "descripcion": "",
                "apertura": shift.get("opening_balance"),
                "esperado": shift.get("expected_balance"),
                "contado": shift.get("declared_balance"),
                "diferencia": shift.get("difference"),
                "estado_turno": shift.get("status"),
                "registrado_el": "",
            }
            safe_row = spreadsheet_safe_row(row)
            for field in ("apertura", "esperado", "contado", "diferencia"):
                safe_row[field] = _csv_decimal(row[field])
            writer.writerow(safe_row)

    actor_labels = resolve_hotel_actor_labels(
        db,
        hotel_id=context.hotel_id,
        user_ids=(transaction.created_by_user_id for transaction, _ in prior_receipt_rows),
    )
    for transaction, _confirmation_code in prior_receipt_rows:
        receipt_currency = str(transaction.tender_currency or transaction.currency or "ARS").upper()
        if selected_currency and receipt_currency != selected_currency:
            continue
        occurred_at = transaction.created_at
        row = {
            "fecha_local": _csv_local_date(transaction.collected_on),
            "hotel_id": context.hotel_id,
            "moneda": receipt_currency,
            "tipo": "seña_previa",
            "fecha_hora_local": _csv_local_datetime(occurred_at, reports[0]["timezone"] if reports else "UTC"),
            "responsable": actor_labels.get(transaction.created_by_user_id, "Usuario") if transaction.created_by_user_id else "Sistema",
            "usuario_id": transaction.created_by_user_id,
            "reserva_id": transaction.reservation_id,
            "transaccion_id": transaction.id,
            "movimiento_id": "",
            "lote_grupal_id": "",
            "sesion_id": "",
            "importe": transaction.tender_amount if transaction.tender_amount is not None else transaction.amount,
            "importe_neto": transaction.tender_amount if transaction.tender_amount is not None else transaction.amount,
            "medio_pago": "cash",
            "tipo_transaccion": "",
            "tipo_movimiento": "",
            "proveedor": "",
            "descripcion": transaction.prior_receipt_note,
            "apertura": "",
            "esperado": "",
            "contado": "",
            "diferencia": "",
            "estado_turno": "",
            "registrado_el": _csv_local_datetime(transaction.created_at, reports[0]["timezone"] if reports else "UTC"),
        }
        safe_row = spreadsheet_safe_row(row)
        amount = transaction.tender_amount if transaction.tender_amount is not None else transaction.amount
        safe_row["importe"] = _csv_decimal(amount)
        safe_row["importe_neto"] = _csv_decimal(amount)
        writer.writerow(safe_row)

    filename = f"caja-{start.isoformat()}-{end.isoformat()}.csv"
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
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
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    return _close_report_read(
        db,
        get_latest_close_report(db, hotel_id=context.hotel_id, currency_code=currency),
    )


@router.get("/api/cash-register/close-reports/pending", response_model=list[CashCloseReportRead])
@router.get("/cash-register/close-reports/pending", response_model=list[CashCloseReportRead])
def pending_cash_close_reports(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    return [
        _close_report_read(db, report)
        for report in list_pending_close_reports(db, hotel_id=context.hotel_id)
    ]


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
    return [
        _close_report_read(db, report)
        for report in list_pending_cash_custody_reports(db, hotel_id=context.hotel_id)
    ]


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
    return _close_report_read(
        db,
        get_close_report_for_session(db, hotel_id=context.hotel_id, session_id=session_id),
    )


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
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Los gastos manuales requieren categoría, proveedor y comprobante; usá el registro de gastos pendientes.",
            )
        elif payload.movement_type == CashMovementTypeEnum.ADJUSTMENT:
            authorize_permission(request, db, context, PERMISSION_CASH_ADJUSTMENT_MANAGE)
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


@router.post(
    "/api/cash-register/sessions/{session_id}/expenses",
    response_model=CashExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/cash-register/sessions/{session_id}/expenses",
    response_model=CashExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
def record_cash_expense(
    session_id: int,
    payload: CashExpenseCreate,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    authorized = authorize_permission(request, db, context, PERMISSION_CASH_EXPENSE)
    try:
        expense = create_cash_expense(
            db,
            hotel_id=authorized.hotel_id,
            session_id=session_id,
            recorded_by_user_id=authorized.user_id,
            amount=payload.amount,
            category=payload.category,
            vendor=payload.vendor,
            description=payload.description,
            receipt_reference=payload.receipt_reference,
            receipt_image_base64=payload.receipt_image_base64,
            receipt_filename=payload.receipt_filename,
        )
        try:
            db.commit()
        except Exception:
            persisted, resolved = recover_failed_cash_expense_commit(db, expense)
            if persisted is not None and resolved:
                expense = persisted
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No se pudo confirmar el registro del gasto; verificá la lista antes de reintentar.",
                )
        db.refresh(expense)
        return _cash_expense_read(db, expense)
    except CashExpenseError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.get("/api/cash-register/expenses", response_model=list[CashExpenseRead])
@router.get("/cash-register/expenses", response_model=list[CashExpenseRead])
def read_cash_expenses(
    expense_status: str | None = Query(default=None, alias="status", max_length=20),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    try:
        expenses = list_cash_expenses(db, hotel_id=context.hotel_id, status=expense_status)
        actor_ids = {
            user_id
            for expense in expenses
            for user_id in (
                expense.recorded_by_user_id,
                expense.approved_by_user_id,
                expense.rejected_by_user_id,
            )
            if user_id is not None
        }
        actor_labels = resolve_hotel_actor_labels(db, hotel_id=context.hotel_id, user_ids=actor_ids)
        return [_cash_expense_read(db, expense, actor_labels=actor_labels) for expense in expenses]
    except CashExpenseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post(
    "/api/cash-register/expenses/{expense_id}/approve",
    response_model=CashExpenseRead,
)
@router.post(
    "/cash-register/expenses/{expense_id}/approve",
    response_model=CashExpenseRead,
)
def approve_cash_expense_route(
    expense_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_EXPENSE_APPROVE)),
):
    try:
        expense = approve_cash_expense(
            db,
            hotel_id=context.hotel_id,
            expense_id=expense_id,
            approved_by_user_id=context.user_id or 0,
        )
        db.commit()
        db.refresh(expense)
        return _cash_expense_read(db, expense)
    except CashExpenseError as exc:
        db.rollback()
        status_code = status.HTTP_404_NOT_FOUND if str(exc) == "Gasto no encontrado" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.post(
    "/api/cash-register/expenses/{expense_id}/reject",
    response_model=CashExpenseRead,
)
@router.post(
    "/cash-register/expenses/{expense_id}/reject",
    response_model=CashExpenseRead,
)
def reject_cash_expense_route(
    expense_id: int,
    payload: CashExpenseReject,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_EXPENSE_APPROVE)),
):
    try:
        expense = reject_cash_expense(
            db,
            hotel_id=context.hotel_id,
            expense_id=expense_id,
            rejected_by_user_id=context.user_id or 0,
            reason=payload.reason,
        )
        db.commit()
        db.refresh(expense)
        return _cash_expense_read(db, expense)
    except CashExpenseError as exc:
        db.rollback()
        status_code = status.HTTP_404_NOT_FOUND if str(exc) == "Gasto no encontrado" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.get("/api/cash-register/expenses/{expense_id}/receipt")
@router.get("/cash-register/expenses/{expense_id}/receipt")
def read_cash_expense_receipt(
    expense_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_VIEW)),
):
    try:
        content, content_type, _filename = get_cash_expense_receipt_bytes(
            db,
            hotel_id=context.hotel_id,
            expense_id=expense_id,
        )
        safe_extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(content_type)
        if safe_extension is None:
            raise CashExpenseError("Comprobante no encontrado")
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="comprobante.{safe_extension}"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except CashExpenseError as exc:
        db.rollback()
        status_code = status.HTTP_404_NOT_FOUND if "no encontrado" in str(exc).lower() else status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


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
        return _close_report_read(db, report)
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
        return _close_report_read(db, report)
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
        return _close_report_read(db, report)
    except CashRegisterError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
