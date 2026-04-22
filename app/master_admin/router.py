from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from json import JSONDecodeError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.hotel_config import HotelConfiguration
from app.models.subscription_v2 import Subscription
from app.models.user import User
from app.services.subscription_entitlements import get_subscription_snapshot
from app.services.security import decode_signed_token
from .billing_policy import BillingDecision, evaluate_hotel_write_access, get_policy_payload, update_policy
from .email_provider import (
    MasterEmailConnectionError,
    build_connect_redirect,
    build_email_callback_page,
    build_state_payload,
    connect_system_email,
    disconnect_system_email,
    get_system_email_status,
    send_system_email,
)
from .models import MasterAdminAuditEvent, MasterStripeWebhookEvent
from .schemas import (
    BillingPolicyPayload,
    BillingPolicyUpdateRequest,
    MasterEmailConnectResponse,
    EmailTestRequest,
    MasterAdminLoginRequest,
    MasterAdminLoginResponse,
    MasterAdminSessionResponse,
    MasterAdminUserPayload,
    MasterEmailStatusPayload,
    MasterStripeConfigPayload,
    MasterStripeConnectRequest,
)
from .security import (
    audit_master_action,
    authenticate_master_login,
    clear_master_session_cookies,
    create_master_session,
    require_master_admin,
    set_master_session_cookies,
)
from .stripe import clear_stripe_settings, get_stripe_status, save_stripe_settings, verify_stripe_signature

router = APIRouter(prefix="/api/master-admin", tags=["Master Admin"])


def _popup_origin(request: Request) -> str:
    origin = (request.headers.get("origin") or "").strip()
    if origin.startswith(("http://", "https://")):
        return origin
    referer = (request.headers.get("referer") or "").strip()
    if referer.startswith(("http://", "https://")):
        return referer.rsplit("/", 1)[0]
    return get_settings().APP_BASE_URL.rstrip("/")


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


@router.get("/auth/me", response_model=MasterAdminSessionResponse)
def me(request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, write=False)
    return MasterAdminSessionResponse(user=_serialize_user(context.user), csrf_token=context.csrf_token)


@router.get("/dashboard/summary")
def dashboard_summary(request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, write=False)
    hotels = db.query(HotelConfiguration).count()
    active_subscriptions = db.query(Subscription).filter(Subscription.status == "active").count()
    trialing = db.query(Subscription).filter(Subscription.status == "trialing").count()
    past_due = db.query(Subscription).filter(Subscription.status == "past_due").count()
    policy = get_policy_payload(db)
    recent_events = db.query(MasterAdminAuditEvent).order_by(MasterAdminAuditEvent.id.desc()).limit(10).all()
    return {
        "operator": _serialize_user(context.user).model_dump(),
        "counts": {
            "hotels": hotels,
            "active_subscriptions": active_subscriptions,
            "trialing": trialing,
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


@router.get("/email/status", response_model=MasterEmailStatusPayload)
@router.get("/email/providers", response_model=MasterEmailStatusPayload)
def email_providers(request: Request, db: Session = Depends(get_db)):
    require_master_admin(request=request, db=db, write=False)
    status_payload = get_system_email_status(db)
    return MasterEmailStatusPayload(**status_payload.__dict__)


@router.post("/email/connect", response_model=MasterEmailConnectResponse)
def email_connect(request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    origin = _popup_origin(request)
    state_payload = build_state_payload(web_origin=origin)
    try:
        redirect_url = build_connect_redirect(state_payload=state_payload)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_email_connect_started",
        metadata={"provider": "gmail"},
        request=request,
    )
    db.commit()
    return MasterEmailConnectResponse(redirect_url=redirect_url, status="pending")


@router.get("/email/oauth/gmail/callback")
def email_oauth_callback(request: Request, db: Session = Depends(get_db)):
    state = request.query_params.get("state")
    if not state:
        raise HTTPException(status_code=400, detail="state requerido")
    state_payload = decode_signed_token(state)
    if state_payload.get("type") != "master_admin_email_oauth":
        raise HTTPException(status_code=400, detail="state invalido")
    web_origin = str(state_payload.get("web_origin") or "").strip()
    error = request.query_params.get("error")
    if error:
        description = request.query_params.get("error_description") or error
        return build_email_callback_page(status="error", message=f"No se pudo conectar Gmail: {description}", web_origin=web_origin)

    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code requerido")

    try:
        status_payload = connect_system_email(db, code)
        db.commit()
        audit_master_action(
            db,
            actor_user_id=None,
            action="master_admin_email_connected",
            metadata=status_payload.__dict__,
            request=request,
        )
        db.commit()
    except MasterEmailConnectionError as exc:
        db.rollback()
        return build_email_callback_page(status="error", message=str(exc), web_origin=web_origin)
    except Exception as exc:
        db.rollback()
        return build_email_callback_page(status="error", message=str(exc), web_origin=web_origin)

    message = "Gmail quedo conectado correctamente para los mails del sistema."
    return build_email_callback_page(status="connected", message=message, web_origin=web_origin)


@router.post("/email/disconnect", response_model=MasterEmailStatusPayload)
def email_disconnect(request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    status_payload = disconnect_system_email(db)
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_email_disconnected",
        metadata=status_payload.__dict__,
        request=request,
    )
    db.commit()
    return MasterEmailStatusPayload(**status_payload.__dict__)


@router.post("/email/test")
def email_test(payload: EmailTestRequest, request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    try:
        result = send_system_email(db, payload.recipient, payload.subject, payload.body)
        db.commit()
    except MasterEmailConnectionError as exc:
        db.rollback()
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="master_admin_email_test",
            outcome="failed",
            metadata={"recipient": str(payload.recipient), "error": str(exc)},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_email_test",
        outcome="success",
        metadata={"recipient": str(payload.recipient), **result},
        request=request,
    )
    db.commit()
    return {"ok": True, **result}


@router.get("/stripe/config", response_model=MasterStripeConfigPayload)
def stripe_config(request: Request, db: Session = Depends(get_db)):
    require_master_admin(request=request, db=db, write=False)
    return MasterStripeConfigPayload(**get_stripe_status(db))


@router.post("/stripe/connect", response_model=MasterStripeConfigPayload)
def stripe_connect(payload: MasterStripeConnectRequest, request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    try:
        status_payload = save_stripe_settings(
            db,
            {
                "stripe_secret_key": payload.stripe_secret_key,
                "webhook_secret": payload.webhook_secret,
                "enabled": payload.enabled,
            },
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_stripe_connected",
        metadata=status_payload,
        request=request,
    )
    db.commit()
    return MasterStripeConfigPayload(**status_payload)


@router.post("/stripe/disconnect", response_model=MasterStripeConfigPayload)
def stripe_disconnect(request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    status_payload = clear_stripe_settings(db)
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_stripe_disconnected",
        metadata=status_payload,
        request=request,
    )
    db.commit()
    return MasterStripeConfigPayload(**status_payload)


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    verify_stripe_signature(db, body, signature)

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

