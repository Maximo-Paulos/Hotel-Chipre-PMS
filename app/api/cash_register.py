from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.cash_register import (
    CashCloseReportRead,
    CashMovementCreate,
    CashMovementRead,
    CashSessionClose,
    CashSessionOpen,
    CashSessionRead,
)
from app.services.cash_register_service import (
    CashRegisterError,
    add_movement,
    approve_close_difference,
    close_session,
    list_movements,
    list_sessions,
    open_session,
)
from app.services.permission_service import PERMISSION_CASH_APPROVE_DIFFERENCE, PERMISSION_CASH_OPERATE


router = APIRouter(tags=["Cash Register"])


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
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    return list_sessions(db, hotel_id=context.hotel_id)


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
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    try:
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


@router.get("/api/cash-register/sessions/{session_id}/movements", response_model=list[CashMovementRead])
@router.get("/cash-register/sessions/{session_id}/movements", response_model=list[CashMovementRead])
def list_cash_movements(
    session_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    return list_movements(db, hotel_id=context.hotel_id, session_id=session_id)


@router.post("/api/cash-register/sessions/{session_id}/close", response_model=CashCloseReportRead)
@router.post("/cash-register/sessions/{session_id}/close", response_model=CashCloseReportRead)
def close_cash_session(
    session_id: int,
    payload: CashSessionClose,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    if payload.approve_difference:
        if not context.permissions or PERMISSION_CASH_APPROVE_DIFFERENCE not in context.permissions:
            # Force the permission dependency through a local resolution so callers
            # cannot approve a difference with operate-only access.
            from app.services.permission_service import audit_permission_denied, resolve

            if not resolve(db, context.hotel_id, context.user_role, PERMISSION_CASH_APPROVE_DIFFERENCE):
                audit_permission_denied(
                    db,
                    hotel_id=context.hotel_id,
                    user_id=context.user_id,
                    role=context.user_role,
                    permission_code=PERMISSION_CASH_APPROVE_DIFFERENCE,
                )
                raise HTTPException(status_code=403, detail="No tenes permisos para aprobar diferencias de caja")

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
