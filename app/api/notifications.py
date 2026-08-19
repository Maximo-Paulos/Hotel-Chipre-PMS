"""
FastAPI routes for the notification backend: inbox, push subscriptions,
preferences, and (owner/co-owner only) daily-report scheduling.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context, require_roles
from app.schemas.notification import (
    DailyReportScheduleRead,
    DailyReportScheduleUpdate,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationPreferenceRead,
    NotificationPreferenceUpdate,
    NotificationRead,
    PushSubscriptionRegisterRequest,
    PushSubscriptionUnregisterRequest,
)
from app.services import notification_service
from app.services.permission_service import ROLE_CO_OWNER, ROLE_OWNER

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
def list_my_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    items = notification_service.list_notifications(
        db, hotel_id=context.hotel_id, user_id=context.user_id,
        unread_only=unread_only, limit=limit, offset=offset,
    )
    unread_count = notification_service.unread_notification_count(db, hotel_id=context.hotel_id, user_id=context.user_id)
    return NotificationListResponse(items=items, unread_count=unread_count)


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification_id: int,
    data: NotificationMarkReadRequest = NotificationMarkReadRequest(),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        notification = notification_service.mark_notification_read(
            db, hotel_id=context.hotel_id, user_id=context.user_id,
            notification_id=notification_id, read=data.read,
        )
    except notification_service.NotificationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    db.commit()
    db.refresh(notification)
    return notification


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    count = notification_service.mark_all_notifications_read(db, hotel_id=context.hotel_id, user_id=context.user_id)
    db.commit()
    return {"marked_read": count}


@router.post("/push-subscriptions", status_code=status.HTTP_201_CREATED)
def register_push_subscription(
    data: PushSubscriptionRegisterRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    notification_service.register_push_subscription(
        db, hotel_id=context.hotel_id, user_id=context.user_id,
        endpoint=data.endpoint, p256dh=data.p256dh, auth=data.auth,
    )
    db.commit()
    return {"registered": True}


@router.post("/push-subscriptions/unregister")
def unregister_push_subscription(
    data: PushSubscriptionUnregisterRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    removed = notification_service.unregister_push_subscription(
        db, hotel_id=context.hotel_id, user_id=context.user_id, endpoint=data.endpoint,
    )
    db.commit()
    return {"removed": removed}


@router.get("/preferences", response_model=list[NotificationPreferenceRead])
def list_preferences(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    return notification_service.list_notification_preferences(db, hotel_id=context.hotel_id, user_id=context.user_id)


@router.put("/preferences", response_model=NotificationPreferenceRead)
def update_preference(
    data: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        row = notification_service.set_notification_preference(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            event_type=data.event_type,
            in_app_enabled=data.in_app_enabled,
            push_enabled=data.push_enabled,
            email_enabled=data.email_enabled,
            quiet_hours_start=data.quiet_hours_start,
            quiet_hours_end=data.quiet_hours_end,
            clear_quiet_hours=data.clear_quiet_hours,
        )
    except notification_service.NotificationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.commit()
    db.refresh(row)
    return row


def _schedule_to_read(hotel_id: int, row) -> DailyReportScheduleRead:
    if row is None:
        return DailyReportScheduleRead(
            hotel_id=hotel_id, hour=7, recipient_user_ids=[], recipient_roles=[],
            channels=["in_app"], sections=notification_service.DEFAULT_DAILY_REPORT_SECTIONS, enabled=False,
        )
    return DailyReportScheduleRead(
        hotel_id=hotel_id,
        hour=row.hour,
        recipient_user_ids=json.loads(row.recipient_user_ids or "[]"),
        recipient_roles=json.loads(row.recipient_roles or "[]"),
        channels=json.loads(row.channels or '["in_app"]'),
        sections=json.loads(row.sections or "[]"),
        enabled=row.enabled,
    )


@router.get("/daily-report-schedule", response_model=DailyReportScheduleRead)
def get_daily_report_schedule(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(ROLE_OWNER, ROLE_CO_OWNER)),
):
    row = notification_service.get_daily_report_schedule(db, hotel_id=context.hotel_id)
    return _schedule_to_read(context.hotel_id, row)


@router.put("/daily-report-schedule", response_model=DailyReportScheduleRead)
def update_daily_report_schedule(
    data: DailyReportScheduleUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(ROLE_OWNER, ROLE_CO_OWNER)),
):
    try:
        row = notification_service.upsert_daily_report_schedule(
            db,
            hotel_id=context.hotel_id,
            hour=data.hour,
            recipient_user_ids=data.recipient_user_ids,
            recipient_roles=data.recipient_roles,
            channels=data.channels,
            sections=data.sections,
            enabled=data.enabled,
        )
    except notification_service.NotificationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.commit()
    return _schedule_to_read(context.hotel_id, row)
