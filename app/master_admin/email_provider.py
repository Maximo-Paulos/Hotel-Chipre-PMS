from __future__ import annotations

import base64
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Iterable
from urllib.parse import urlencode

import requests
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.master_admin.models import MasterSystemEmailConnection
from app.services.integration_service import decrypt_payload, encrypt_payload, validate_gmail_credentials
from app.services.security import create_signed_token, decode_signed_token

GOOGLE_IDENTITY_SCOPES = ["openid", "email", "profile"]
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
SYSTEM_EMAIL_CONNECTION_KEY = "system"


class MasterEmailConnectionError(RuntimeError):
    pass


@dataclass
class SystemEmailStatus:
    configured: bool
    status: str
    provider: str
    connected_account_email: str | None = None
    connected_account_name: str | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None
    updated_at: datetime | None = None


def _normalize_account_email(value: str | None) -> str | None:
    return str(value or "").strip().lower() or None


def _get_connection(db: Session, *, create: bool = False) -> MasterSystemEmailConnection | None:
    connection = (
        db.query(MasterSystemEmailConnection)
        .filter(MasterSystemEmailConnection.connection_key == SYSTEM_EMAIL_CONNECTION_KEY)
        .first()
    )
    if connection or not create:
        return connection
    connection = MasterSystemEmailConnection(connection_key=SYSTEM_EMAIL_CONNECTION_KEY)
    db.add(connection)
    db.flush()
    return connection


def _build_authorize_url(*, state: str) -> str:
    settings = get_settings()
    if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
        raise MasterEmailConnectionError("Faltan GMAIL_CLIENT_ID y/o GMAIL_CLIENT_SECRET en el backend.")
    redirect_uri = settings.MASTER_EMAIL_GMAIL_REDIRECT_URI
    if not redirect_uri:
        raise MasterEmailConnectionError("Falta MASTER_EMAIL_GMAIL_REDIRECT_URI en el backend.")
    scopes = " ".join(GOOGLE_IDENTITY_SCOPES + [GMAIL_SEND_SCOPE])
    params = urlencode(
        {
            "client_id": settings.GMAIL_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"


def build_connect_redirect(*, state_payload: dict[str, object]) -> str:
    state = create_signed_token(state_payload, expires_minutes=15)
    return _build_authorize_url(state=state)


def _exchange_code(code: str) -> dict[str, object]:
    settings = get_settings()
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "redirect_uri": settings.MASTER_EMAIL_GMAIL_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if not response.ok:
        raise MasterEmailConnectionError("Google rechazo la autorizacion de Gmail para el panel master.")
    payload = response.json()
    if not isinstance(payload, dict):
        raise MasterEmailConnectionError("Google devolvio una respuesta invalida al conectar Gmail.")
    return payload


def _account_label(payload: dict[str, object]) -> str | None:
    account_email = _normalize_account_email(payload.get("account_email") if isinstance(payload, dict) else None)
    account_name = str(payload.get("account_name") or "").strip() if isinstance(payload, dict) else ""
    if account_email and account_name and account_name != account_email:
        return f"{account_name} <{account_email}>"
    return account_email or (account_name or None)


def _serialize_connection(connection: MasterSystemEmailConnection | None) -> SystemEmailStatus:
    if not connection:
        return SystemEmailStatus(configured=False, status="disconnected", provider="gmail")
    payload = decrypt_payload(connection.auth_payload)
    return SystemEmailStatus(
        configured=connection.status == "connected" and bool(payload),
        status=connection.status,
        provider=connection.provider,
        connected_account_email=_normalize_account_email(payload.get("account_email")),
        connected_account_name=str(payload.get("account_name") or "").strip() or None,
        last_checked_at=connection.last_checked_at,
        last_error=connection.last_error,
        updated_at=connection.updated_at,
    )


def get_system_email_status(db: Session) -> SystemEmailStatus:
    return _serialize_connection(_get_connection(db))


def connect_system_email(db: Session, code: str) -> SystemEmailStatus:
    raw_payload = _exchange_code(code)
    existing = _get_connection(db)
    if existing and existing.auth_payload:
        previous = decrypt_payload(existing.auth_payload)
        if previous.get("refresh_token") and not raw_payload.get("refresh_token"):
            raw_payload["refresh_token"] = previous.get("refresh_token")
    validated = validate_gmail_credentials(raw_payload)
    connection = _get_connection(db, create=True)
    connection.provider = "gmail"
    connection.status = "connected"
    connection.auth_payload = encrypt_payload(validated)
    connection.connected_account_email = _normalize_account_email(validated.get("account_email"))
    connection.connected_account_name = str(validated.get("account_name") or "").strip() or None
    connection.last_checked_at = datetime.now(timezone.utc)
    connection.last_error = None
    db.flush()
    return _serialize_connection(connection)


def disconnect_system_email(db: Session) -> SystemEmailStatus:
    connection = _get_connection(db, create=True)
    connection.status = "disconnected"
    connection.auth_payload = None
    connection.connected_account_email = None
    connection.connected_account_name = None
    connection.last_error = None
    connection.last_checked_at = datetime.now(timezone.utc)
    db.flush()
    return _serialize_connection(connection)


def _refresh_connection(connection: MasterSystemEmailConnection) -> dict[str, object]:
    payload = decrypt_payload(connection.auth_payload)
    validated = validate_gmail_credentials(payload)
    connection.auth_payload = encrypt_payload(validated)
    connection.connected_account_email = _normalize_account_email(validated.get("account_email"))
    connection.connected_account_name = str(validated.get("account_name") or "").strip() or None
    connection.status = "connected"
    connection.last_checked_at = datetime.now(timezone.utc)
    connection.last_error = None
    return validated


def _build_message(
    *,
    sender_email: str,
    sender_name: str | None,
    recipients: Iterable[str],
    subject: str,
    body: str,
) -> str:
    msg = EmailMessage()
    display_name = sender_name or sender_email
    msg["From"] = f"{display_name} <{sender_email}>" if display_name else sender_email
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")


def send_system_email(db: Session, to: Iterable[str] | str, subject: str, body: str) -> dict[str, object]:
    connection = _get_connection(db)
    if not connection or connection.status != "connected" or not connection.auth_payload:
        raise MasterEmailConnectionError("Conecta Gmail desde /adminpmsmaster para habilitar los mails del sistema.")

    try:
        validated = _refresh_connection(connection)
    except ValueError as exc:
        connection.status = "error"
        connection.last_error = str(exc)
        connection.last_checked_at = datetime.now(timezone.utc)
        db.flush()
        raise MasterEmailConnectionError(str(exc)) from exc

    access_token = str(validated.get("access_token") or "").strip()
    if not access_token:
        raise MasterEmailConnectionError("La conexion de Gmail no devolvio un access token utilizable.")

    recipients = [to] if isinstance(to, str) else list(to)
    raw_message = _build_message(
        sender_email=_normalize_account_email(validated.get("account_email")) or "",
        sender_name=str(validated.get("account_name") or "").strip() or None,
        recipients=recipients,
        subject=subject,
        body=body,
    )
    response = requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"raw": raw_message},
        timeout=20,
    )
    if not response.ok:
        connection.status = "error"
        connection.last_checked_at = datetime.now(timezone.utc)
        try:
            payload = response.json()
            detail = payload.get("error", {}).get("message") or payload.get("error_description") or payload.get("message")
        except Exception:
            detail = response.text
        connection.last_error = str(detail or "Google rechazo el envio del correo del sistema.")
        db.flush()
        raise MasterEmailConnectionError(connection.last_error)

    connection.last_checked_at = datetime.now(timezone.utc)
    connection.last_error = None
    db.flush()
    provider_payload = response.json() if response.content else {}
    return {
        "channel": "gmail_system",
        "sender_email": _normalize_account_email(validated.get("account_email")),
        "provider_message_id": provider_payload.get("id") if isinstance(provider_payload, dict) else None,
    }


def build_email_callback_page(*, status: str, message: str, web_origin: str) -> HTMLResponse:
    safe_message = message.replace("\\", "\\\\").replace("'", "\\'")
    rendered_message = html.escape(message)
    target_origin = web_origin if web_origin.startswith(("http://", "https://")) else "*"
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
            <script>
              (function () {{
                var payload = {{
                  type: 'master-admin-email-oauth-result',
                  status: '{status}',
                  message: '{safe_message}'
                }};
                try {{
                  if (window.opener && !window.opener.closed) {{
                    window.opener.postMessage(payload, '{target_origin}');
                    window.close();
                    return;
                  }}
                }} catch (err) {{}}
                document.getElementById('message').textContent = payload.message;
              }})();
            </script>
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
