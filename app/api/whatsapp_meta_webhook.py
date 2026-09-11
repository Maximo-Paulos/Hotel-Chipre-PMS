"""Meta Cloud API webhook boundary.

The endpoint verifies Meta's signature before parsing and routes by the
provider phone-number index.  It is inert unless inbound provider events are
explicitly enabled in the runtime.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.whatsapp_crm import WhatsAppProviderRoute
from app.services.external_effects_policy import InboundProviderEventsDisabled, require_inbound_provider_events
from app.services.tenant_context import set_tenant_hotel_context
from app.services.whatsapp_crm_service import WhatsAppCRMError, ingest_inbound_message


router = APIRouter(prefix="/api/webhooks/meta", tags=["WhatsApp Meta Webhook"])


def _verify_token() -> str:
    return str(getattr(get_settings(), "META_WHATSAPP_VERIFY_TOKEN", "") or "").strip()


def _app_secret() -> str:
    return str(getattr(get_settings(), "META_WHATSAPP_APP_SECRET", "") or "").strip()


@router.get("/whatsapp")
def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if mode != "subscribe" or not challenge or not _verify_token() or not hmac.compare_digest(verify_token or "", _verify_token()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verificación de webhook inválida")
    return PlainTextResponse(challenge)


@router.post("/whatsapp")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        require_inbound_provider_events("whatsapp")
    except InboundProviderEventsDisabled as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    secret = _app_secret()
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook de WhatsApp no configurado")
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma de webhook inválida")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload de webhook inválido") from exc

    processed = 0
    for entry in payload.get("entry", []) if isinstance(payload, dict) else []:
        for change in entry.get("changes", []) if isinstance(entry, dict) else []:
            value = change.get("value", {}) if isinstance(change, dict) else {}
            metadata = value.get("metadata", {}) if isinstance(value, dict) else {}
            phone_number_id = str(metadata.get("phone_number_id") or "").strip()
            if not phone_number_id:
                continue
            route = db.query(WhatsAppProviderRoute).filter(WhatsAppProviderRoute.phone_number_id == phone_number_id).one_or_none()
            if route is None:
                continue
            set_tenant_hotel_context(db, route.hotel_id)
            contacts = {str(item.get("wa_id")): item for item in (value.get("contacts") or []) if isinstance(item, dict)}
            for message in value.get("messages", []) if isinstance(value, dict) else []:
                if not isinstance(message, dict) or not message.get("id"):
                    continue
                sender = str(message.get("from") or "")
                text_value = (message.get("text") or {}).get("body") if message.get("type") == "text" else None
                try:
                    result = ingest_inbound_message(
                        db,
                        hotel_id=route.hotel_id,
                        channel_id=route.channel_id,
                        from_phone=sender,
                        provider_message_id=str(message["id"]),
                        text=text_value,
                        message_type=str(message.get("type") or "unknown"),
                        display_name=((contacts.get(sender) or {}).get("profile") or {}).get("name"),
                    )
                except WhatsAppCRMError as exc:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
                processed += int(result.created)
    db.commit()
    return {"received": True, "processed": processed}
