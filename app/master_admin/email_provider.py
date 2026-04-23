from __future__ import annotations

import json
import html
import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path

from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.services.email.providers import EmailProviderError, get_email_provider
from app.services.security import decode_signed_token
from app.config import is_production_mode


class MasterEmailConnectionError(RuntimeError):
    pass


LOGGER = logging.getLogger(__name__)


def _dev_outbox_path() -> Path:
    settings = get_settings()
    raw_path = (getattr(settings, "DEV_EMAIL_OUTBOX_PATH", "") or "").strip()
    if raw_path:
        return Path(raw_path)
    return Path(tempfile.gettempdir()) / "hotel-chipre-dev-email-outbox.jsonl"


def _record_dev_email(*, channel: str, to, subject: str, body: str, sender_email: str | None, reply_to: str | None) -> None:
    path = _dev_outbox_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "channel": channel,
        "to": [to] if isinstance(to, str) else list(to),
        "subject": subject,
        "body": body,
        "sender_email": sender_email,
        "reply_to": reply_to,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


@dataclass
class SystemEmailStatus:
    configured: bool
    status: str
    provider: str
    sender_email: str | None = None
    reply_to: str | None = None
    connected_account_email: str | None = None
    connected_account_name: str | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None
    updated_at: datetime | None = None


def _normalize_account_email(value: str | None) -> str | None:
    return str(value or "").strip().lower() or None


def _sender_parts() -> tuple[str | None, str | None]:
    raw_from = (get_settings().SYSTEM_EMAIL_FROM or "").strip()
    display_name, address = parseaddr(raw_from)
    sender_email = _normalize_account_email(address or raw_from)
    sender_name = display_name.strip() or None
    return sender_email, sender_name


def _build_unavailable_message() -> str:
    settings = get_settings()
    missing = []
    if (settings.EMAIL_PROVIDER or "").strip().lower() != "resend":
        missing.append("EMAIL_PROVIDER=resend")
    if not (settings.RESEND_API_KEY or "").strip():
        missing.append("RESEND_API_KEY")
    if not (settings.SYSTEM_EMAIL_FROM or "").strip():
        missing.append("SYSTEM_EMAIL_FROM")
    if not (settings.SYSTEM_EMAIL_REPLY_TO or "").strip():
        missing.append("SYSTEM_EMAIL_REPLY_TO")
    if not missing:
        return "El mail del sistema no esta disponible."
    return "Faltan variables de Resend: " + ", ".join(missing)


def _current_status() -> SystemEmailStatus:
    settings = get_settings()
    provider_name = (settings.EMAIL_PROVIDER or "resend").strip().lower()
    sender_email, sender_name = _sender_parts()
    configured = provider_name == "resend" and bool(
        (settings.RESEND_API_KEY or "").strip()
        and (settings.SYSTEM_EMAIL_FROM or "").strip()
        and (settings.SYSTEM_EMAIL_REPLY_TO or "").strip()
    )
    now = datetime.now(timezone.utc)
    return SystemEmailStatus(
        configured=configured,
        status="connected" if configured else "disconnected",
        provider=provider_name,
        sender_email=sender_email,
        reply_to=(settings.SYSTEM_EMAIL_REPLY_TO or "").strip() or None,
        connected_account_email=sender_email,
        connected_account_name=sender_name,
        last_checked_at=now,
        last_error=None if configured else _build_unavailable_message(),
        updated_at=now,
    )


def get_system_email_status(db=None) -> SystemEmailStatus:
    return _current_status()


def send_system_email(db, to, subject: str, body: str) -> dict[str, object]:
    provider = get_email_provider()
    settings = get_settings()
    dev_outbox_path = (getattr(settings, "DEV_EMAIL_OUTBOX_PATH", "") or "").strip()
    if not is_production_mode(settings) and dev_outbox_path:
        LOGGER.info("Email system using dev no-op delivery provider provider=%s", provider.provider_name)
        sender_email, _ = _sender_parts()
        _record_dev_email(
            channel="dev_noop",
            to=to,
            subject=subject,
            body=body,
            sender_email=sender_email,
            reply_to=(settings.SYSTEM_EMAIL_REPLY_TO or "").strip() or None,
        )
        return {
            "channel": "dev_noop",
            "provider": provider.provider_name or "null",
            "sender_email": sender_email,
            "reply_to": (settings.SYSTEM_EMAIL_REPLY_TO or "").strip() or None,
            "provider_message_id": None,
        }

    if provider.provider_name != "resend" or not provider.configured:
        raise MasterEmailConnectionError(_build_unavailable_message())

    try:
        result = provider.send(to, subject, body)
    except EmailProviderError as exc:
        raise MasterEmailConnectionError(str(exc)) from exc

    sender_email, _ = _sender_parts()
    return {
        "channel": "resend_system",
        "provider": "resend",
        "sender_email": sender_email,
        "reply_to": (settings.SYSTEM_EMAIL_REPLY_TO or "").strip() or None,
        "provider_message_id": result.get("id") if isinstance(result, dict) else None,
    }


def build_connect_redirect(*, state_payload: dict[str, object]) -> str:
    raise MasterEmailConnectionError("Gmail OAuth para el mail del sistema fue retirado. Usa Resend.")


def connect_system_email(db, code: str) -> SystemEmailStatus:
    raise MasterEmailConnectionError("Gmail OAuth para el mail del sistema fue retirado. Usa Resend.")


def disconnect_system_email(db) -> SystemEmailStatus:
    raise MasterEmailConnectionError("Gmail OAuth para el mail del sistema fue retirado. Usa Resend.")


def build_email_callback_page(*, status: str, message: str, web_origin: str) -> HTMLResponse:
    rendered_message = html.escape(message)
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="es">
          <head>
            <meta charset="utf-8" />
            <title>Email del sistema</title>
          </head>
          <body style="font-family: Arial, sans-serif; padding: 24px;">
            <p id="message">{rendered_message}</p>
          </body>
        </html>
        """.strip()
    )


def build_state_payload(*, web_origin: str) -> dict[str, object]:
    return {
        "type": "master_admin_email_oauth",
        "web_origin": web_origin,
    }


def decode_state(token: str) -> dict[str, object]:
    return decode_signed_token(token)
