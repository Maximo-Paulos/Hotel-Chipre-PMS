from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from json import JSONDecodeError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.hotel_config import HotelConfiguration
from app.models.subscription_v2 import Subscription
from app.models.user import User
from app.services.email_service import mailer
from app.services.subscription_entitlements import get_subscription_snapshot
from .billing_policy import BillingDecision, evaluate_hotel_write_access, get_policy_payload, update_policy
from .models import MasterAdminAuditEvent, MasterStripeWebhookEvent
from .schemas import (
    BillingPolicyPayload,
    BillingPolicyUpdateRequest,
    EmailTestRequest,
    MasterAdminLoginRequest,
    MasterAdminLoginResponse,
    MasterAdminUserPayload,
    StripeWebhookConfigPayload,
)
from .security import (
    audit_master_action,
    authenticate_master_login,
    clear_master_session_cookies,
    create_master_session,
    require_master_admin,
    set_master_session_cookies,
)
from .stripe import DEFAULT_TOLERANCE_SECONDS, stripe_secret_configured, verify_stripe_signature

router = APIRouter(prefix="/api/master-admin", tags=["Master Admin"])


def _serialize_user(user: User) -> MasterAdminUserPayload:
    return MasterAdminUserPayload(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )


@router.post("/auth/login", response_model=MasterAdminLoginResponse)
def login(payload: MasterAdminLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = authenticate_master_login(db, payload.email, payload.password, payload.pin)
    session, session_token, csrf_token = create_master_session(db, user, request)
    audit_master_action(
        db,
        actor_user_id=user.id,
        action="master_admin_login",
        metadata={"email": user.email},
        request=request,
    )
    db.commit()
    set_master_session_cookies(response, session_token, csrf_token)
    return MasterAdminLoginResponse(user=_serialize_user(user), csrf_token=csrf_token, expires_at=session.expires_at)


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    context.session.revoked_at = datetime.now(timezone.utc)
    clear_master_session_cookies(response)
    audit_master_action(db, actor_user_id=context.user.id, action="master_admin_logout", request=request)
    db.commit()
    return {"ok": True}


@router.get("/auth/me", response_model=MasterAdminUserPayload)
def me(request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, write=False)
    return _serialize_user(context.user)


@router.get("/dashboard/summary")
def dashboard_summary(request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, write=False)
    hotels = db.query(HotelConfiguration).count()
    active_subscriptions = db.query(Subscription).filter(Subscription.status == "active").count()
    trialing = db.query(Subscription).filter(Subscription.status == "trialing").count()
    comped = db.query(Subscription).filter(Subscription.status == "comped").count()
    past_due = db.query(Subscription).filter(Subscription.status == "past_due").count()
    policy = get_policy_payload(db)
    recent_events = db.query(MasterAdminAuditEvent).order_by(MasterAdminAuditEvent.id.desc()).limit(10).all()
    return {
        "operator": _serialize_user(context.user).model_dump(),
        "counts": {
            "hotels": hotels,
            "active_subscriptions": active_subscriptions,
            "trialing": trialing,
            "comped": comped,
            "past_due": past_due,
        },
        "policy": policy,
        "recent_events": [
            {
                "id": event.id,
                "action": event.action,
                "outcome": event.outcome,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "created_at": event.created_at,
            }
            for event in recent_events
        ],
    }


@router.get("/dashboard/hotels")
def dashboard_hotels(request: Request, db: Session = Depends(get_db)):
    require_master_admin(request=request, db=db, write=False)
    hotels = db.query(HotelConfiguration).order_by(HotelConfiguration.id.asc()).all()
    result = []
    for hotel in hotels:
        snapshot = get_subscription_snapshot(db, hotel.id)
        decision: BillingDecision = evaluate_hotel_write_access(db, hotel.id, snapshot=snapshot)
        result.append(
            {
                "hotel_id": hotel.id,
                "hotel_name": hotel.hotel_name,
                "owner_email": hotel.owner_email,
                "plan": snapshot.get("plan"),
                "status": snapshot.get("status"),
                "can_write": decision.can_write,
                "reason": decision.reason,
                "room_limit": snapshot.get("room_limit"),
                "staff_limit": snapshot.get("staff_limit"),
                "exempt": decision.exempt,
                "updated_at": hotel.updated_at,
            }
        )
    return {"items": result}


@router.get("/billing/policy", response_model=BillingPolicyPayload)
def get_billing_policy(request: Request, db: Session = Depends(get_db)):
    require_master_admin(request=request, db=db, write=False)
    return BillingPolicyPayload(**get_policy_payload(db))


@router.put("/billing/policy", response_model=BillingPolicyPayload)
def put_billing_policy(
    payload: BillingPolicyUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    policy = update_policy(db, payload.model_dump(), actor_user_id=context.user.id)
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_update_billing_policy",
        metadata=policy,
        request=request,
    )
    db.commit()
    return BillingPolicyPayload(**policy)


@router.get("/email/providers")
def email_providers(request: Request, db: Session = Depends(get_db)):
    require_master_admin(request=request, db=db, write=False)
    return {
        "current_provider": mailer.provider_name,
        "configured": mailer.configured,
        "available": mailer.available_providers(),
    }


@router.post("/email/test")
def email_test(payload: EmailTestRequest, request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    ok = mailer.send(payload.recipient, payload.subject, payload.body)
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_email_test",
        outcome="success" if ok else "failed",
        metadata={"recipient": str(payload.recipient), "provider": mailer.provider_name},
        request=request,
    )
    db.commit()
    return {"ok": ok, "provider": mailer.provider_name}


@router.get("/stripe/config", response_model=StripeWebhookConfigPayload)
def stripe_config(request: Request, db: Session = Depends(get_db)):
    require_master_admin(request=request, db=db, write=False)
    configured = stripe_secret_configured()
    return StripeWebhookConfigPayload(
        configured=configured,
        secret_source="MASTER_STRIPE_WEBHOOK_SECRET" if configured else "unset",
        tolerance_seconds=DEFAULT_TOLERANCE_SECONDS,
    )


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    verify_stripe_signature(body, signature)

    try:
        event_data = json.loads(body.decode("utf-8"))
    except JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload de Stripe invalido") from exc

    event_id = str(event_data.get("id") or "")
    if not event_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe event sin id")

    event = MasterStripeWebhookEvent(
        event_id=event_id,
        event_type=str(event_data.get("type") or "unknown"),
        signature_header=signature or "",
        payload_json=body.decode("utf-8"),
        delivery_status="processed",
        processed_at=datetime.now(timezone.utc),
    )
    db.add(event)
    audit_master_action(
        db,
        actor_user_id=None,
        action="stripe_webhook_received",
        target_type="stripe_event",
        target_id=event_id,
        metadata={"event_type": event.event_type},
        request=request,
    )
    db.commit()
    return {"received": True, "event_id": event_id}


@router.get("/audit/events")
def audit_events(request: Request, db: Session = Depends(get_db)):
    require_master_admin(request=request, db=db, write=False)
    events = db.query(MasterAdminAuditEvent).order_by(MasterAdminAuditEvent.id.desc()).limit(50).all()
    return {
        "items": [
            {
                "id": event.id,
                "actor_user_id": event.actor_user_id,
                "action": event.action,
                "outcome": event.outcome,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "request_path": event.request_path,
                "request_method": event.request_method,
                "created_at": event.created_at,
                "metadata_json": event.metadata_json,
            }
            for event in events
        ]
    }

