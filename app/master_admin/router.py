from __future__ import annotations

import json
from datetime import datetime, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from json import JSONDecodeError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.hotel_config import HotelConfiguration
from app.models.subscription_v2 import Subscription
from app.models.user import User
from app.schemas.auth import MfaChallengeResponse, MfaEnrollmentResponse, MfaRecoveryCodesResponse
from app.services import mfa_service
from app.services.security import verify_password
from app.services.subscription_entitlements import get_subscription_snapshot
from .billing_policy import BillingDecision, evaluate_hotel_write_access, get_policy_payload, update_policy
from .email_provider import (
    MasterEmailConnectionError,
    get_system_email_status,
    send_system_email,
)
from .models import MasterAdminAuditEvent, MasterStripeWebhookEvent
from .schemas import (
    BillingPolicyPayload,
    BillingPolicyUpdateRequest,
    EmailTestRequest,
    MasterAdminLoginRequest,
    MasterAdminLoginResponse,
    MasterAdminMfaCodeRequest,
    MasterAdminMfaDisableRequest,
    MasterAdminMfaEnrollRequest,
    MasterAdminMfaLoginRequest,
    MasterAdminSessionResponse,
    MasterAdminUserPayload,
    MasterEmailStatusPayload,
    MasterStripeConfigPayload,
    MasterStripeConnectRequest,
)
from .security import (
    audit_master_action,
    allow_master_admin_mfa_attempt,
    authenticate_master_mfa_login,
    authenticate_master_login,
    clear_master_session_cookies,
    create_master_admin_mfa_challenge,
    create_master_session,
    MASTER_ADMIN_MFA_LOGIN_CHALLENGE_MINUTES,
    require_master_admin,
    redact_master_admin_audit_metadata_json,
    reset_master_admin_mfa_attempts,
    set_master_session_cookies,
)
from .stripe import clear_stripe_settings, get_stripe_status, save_stripe_settings, verify_stripe_signature
from app.services.external_effects_policy import (
    InboundProviderEventsDisabled,
    require_inbound_provider_events,
)

router = APIRouter(prefix="/api/master-admin", tags=["Master Admin"])


def _serialize_user(user: User) -> MasterAdminUserPayload:
    return MasterAdminUserPayload(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )


@router.post("/auth/login", response_model=MasterAdminLoginResponse | MfaChallengeResponse)
def login(payload: MasterAdminLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    user = authenticate_master_login(db, payload.email, payload.password, payload.pin)
    if mfa_service.get_active_mfa_secret(db, user.id):
        challenge = create_master_admin_mfa_challenge(user)
        db.commit()
        return MfaChallengeResponse(
            mfa_token=challenge,
            expires_in=MASTER_ADMIN_MFA_LOGIN_CHALLENGE_MINUTES * 60,
        )

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


@router.post("/auth/login/mfa", response_model=MasterAdminLoginResponse)
def complete_mfa_login(
    payload: MasterAdminMfaLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = authenticate_master_mfa_login(db, payload.mfa_token, payload.code)
    session, session_token, csrf_token = create_master_session(db, user, request)
    audit_master_action(
        db,
        actor_user_id=user.id,
        action="master_admin_login",
        metadata={"email": user.email, "method": "password+pin+mfa"},
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


@router.post("/mfa/enroll", response_model=MfaEnrollmentResponse)
def enroll_mfa(
    payload: MasterAdminMfaEnrollRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    if not verify_password(payload.password, context.user.password_hash):
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="master_admin_mfa_enroll",
            outcome="failure",
            metadata={"reason": "reauth_failed"},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reautenticacion invalida")

    try:
        _mfa_secret, secret = mfa_service.enroll_user(db, context.user.id)
    except ValueError as exc:
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="master_admin_mfa_enroll",
            outcome="failure",
            metadata={"reason": "already_active"},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_mfa_enroll",
        metadata={"factor": "totp"},
        request=request,
    )
    db.commit()
    issuer = (get_settings().HOTEL_NAME or "Hotel PMS").strip() or "Hotel PMS"
    otpauth_uri = pyotp.TOTP(secret).provisioning_uri(name=context.user.email, issuer_name=issuer)
    return MfaEnrollmentResponse(secret=secret, otpauth_uri=otpauth_uri)


@router.post("/mfa/enroll/confirm", response_model=MfaRecoveryCodesResponse)
def confirm_mfa_enrollment(
    payload: MasterAdminMfaCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    allow_master_admin_mfa_attempt(db, "enroll", context.user.id)
    try:
        recovery_codes = mfa_service.confirm_enrollment(db, context.user.id, payload.code)
    except mfa_service.MfaSecretUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="MFA no esta disponible temporalmente") from exc
    if recovery_codes is None:
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="master_admin_mfa_confirm",
            outcome="failure",
            metadata={"reason": "invalid_code"},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Codigo TOTP invalido o enrolamiento inexistente")

    reset_master_admin_mfa_attempts(db, "enroll", context.user.id)
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_mfa_confirm",
        metadata={"factor": "totp"},
        request=request,
    )
    db.commit()
    return MfaRecoveryCodesResponse(recovery_codes=recovery_codes)


@router.post("/mfa/disable")
def disable_mfa(
    payload: MasterAdminMfaDisableRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    if not mfa_service.get_active_mfa_secret(db, context.user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA no esta activo")
    if not verify_password(payload.password, context.user.password_hash):
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="master_admin_mfa_disable",
            outcome="failure",
            metadata={"reason": "reauth_failed"},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reautenticacion invalida")

    allow_master_admin_mfa_attempt(db, "disable", context.user.id)
    try:
        valid = mfa_service.consume_mfa_code(db, context.user.id, payload.code)
    except mfa_service.MfaSecretUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="MFA no esta disponible temporalmente") from exc
    if not valid:
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="master_admin_mfa_disable",
            outcome="failure",
            metadata={"reason": "invalid_code"},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codigo MFA invalido o ya utilizado")

    mfa_service.disable_user_mfa(db, context.user.id)
    reset_master_admin_mfa_attempts(db, "disable", context.user.id)
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_mfa_disable",
        metadata={"factor": "totp"},
        request=request,
    )
    db.commit()
    return {"disabled": True}


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


@router.post("/email/connect")
def email_connect(request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_email_connect",
        outcome="failed",
        metadata={"reason": "retired_endpoint"},
        request=request,
    )
    db.commit()
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Gmail OAuth para el mail del sistema fue retirado. Usa Resend.")


@router.get("/email/oauth/gmail/callback")
def email_oauth_callback(request: Request, db: Session = Depends(get_db)):
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Gmail OAuth para el mail del sistema fue retirado. Usa Resend.")


@router.post("/email/disconnect")
def email_disconnect(request: Request, db: Session = Depends(get_db)):
    context = require_master_admin(request=request, db=db, csrf_header=request.headers.get("X-CSRF-Token"), write=True)
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="master_admin_email_disconnect",
        outcome="failed",
        metadata={"reason": "retired_endpoint"},
        request=request,
    )
    db.commit()
    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Gmail OAuth para el mail del sistema fue retirado. Usa Resend.")


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
    try:
        # Before reading/parsing the request or loading the encrypted secret.
        require_inbound_provider_events("Stripe")
    except InboundProviderEventsDisabled as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
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

    # Stripe retries a webhook delivery whenever it doesn't get a fast 2xx ack
    # (e.g. our own timeout). A genuine retry redelivers the SAME event id and
    # must be a no-op, not a 500 from the unique constraint on event_id — an
    # unhandled 500 here would just make Stripe retry forever.
    existing = db.query(MasterStripeWebhookEvent).filter(MasterStripeWebhookEvent.event_id == event_id).first()
    if existing is not None:
        return {"received": True, "event_id": event_id, "duplicate": True}

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
                "metadata_json": redact_master_admin_audit_metadata_json(event.metadata_json),
            }
            for event in events
        ]
    }
