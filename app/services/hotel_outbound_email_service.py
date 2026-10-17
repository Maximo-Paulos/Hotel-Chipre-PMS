from __future__ import annotations

import base64
import fcntl
import json
import os
import stat
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
import re
from typing import Iterable, Sequence

import requests
from app.config import get_settings
from app.services.outbound_http_telemetry import observed_http_call
from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.services.integration_service import (
    decrypt_payload,
    encrypt_payload,
    get_connection_record,
    redact_integration_error,
    validate_gmail_credentials,
)
from app.services.external_effects_policy import (
    ExternalEffectsDisabled,
    require_external_connections,
)


class HotelOutboundEmailError(Exception):
    pass


@dataclass
class HotelOutboundIdentity:
    hotel_id: int
    account_email: str
    account_name: str | None = None


@dataclass
class HotelOutboundSendResult:
    channel: str
    sender_email: str
    provider_message_id: str | None = None


@dataclass(frozen=True)
class HotelEmailAttachment:
    """Bytes attached to a hotel email without re-rendering the document."""

    filename: str
    content_type: str
    content: bytes


def ensure_hotel_gmail_ready(db: Session, hotel_id: int) -> HotelOutboundIdentity:
    # Before querying/loading the encrypted credential record.
    try:
        require_external_connections("Gmail hotel email")
    except ExternalEffectsDisabled as exc:
        raise HotelOutboundEmailError(str(exc)) from exc
    connection = get_connection_record(db, hotel_id, 'gmail')
    if not connection or connection.status != 'connected' or not connection.auth_payload:
        raise HotelOutboundEmailError(
            'Conecta Gmail en Configuracion > Conexiones para enviar correos desde el hotel.'
        )

    try:
        payload = decrypt_payload(connection.auth_payload)
        validated = validate_gmail_credentials(payload)
    except ValueError as exc:
        safe_error = redact_integration_error(exc)
        connection.status = 'error'
        connection.last_error = safe_error
        connection.last_checked_at = datetime.now(timezone.utc)
        db.flush()
        raise HotelOutboundEmailError(safe_error) from exc

    connection.auth_payload = encrypt_payload(validated)
    connection.status = 'connected'
    connection.last_error = None
    connection.last_checked_at = datetime.now(timezone.utc)
    db.flush()

    account_email = str(validated.get('account_email') or '').strip().lower()
    if not account_email:
        raise HotelOutboundEmailError('La conexion Gmail no devolvio un email utilizable para este hotel.')

    account_name = str(validated.get('account_name') or '').strip() or None
    return HotelOutboundIdentity(hotel_id=hotel_id, account_email=account_email, account_name=account_name)


def _build_email_message(
    *,
    sender_email: str,
    sender_name: str | None,
    recipients: Iterable[str],
    subject: str,
    body: str,
    hotel_name: str | None,
    reply_to: str | None = None,
    attachments: Sequence[HotelEmailAttachment] = (),
    message_id: str | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    display_name = re.sub(r"[\r\n\x00]+", " ", sender_name or hotel_name or sender_email).strip()
    msg['From'] = formataddr((display_name, sender_email)) if display_name else sender_email
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    if reply_to:
        msg['Reply-To'] = reply_to
    if message_id:
        msg['Message-ID'] = message_id
    msg.set_content(body)
    for attachment in attachments:
        if not attachment.filename or Path(attachment.filename).name != attachment.filename:
            raise HotelOutboundEmailError('El archivo adjunto no tiene un nombre válido.')
        if "\r" in attachment.filename or "\n" in attachment.filename:
            raise HotelOutboundEmailError('El archivo adjunto no tiene un nombre válido.')
        parts = attachment.content_type.split("/", maxsplit=1)
        if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9.+-]+", part) for part in parts):
            raise HotelOutboundEmailError('El tipo de archivo adjunto no es válido.')
        msg.add_attachment(
            attachment.content,
            maintype=parts[0],
            subtype=parts[1],
            filename=attachment.filename,
        )
    return msg


def _build_message(
    *,
    sender_email: str,
    sender_name: str | None,
    recipients: Iterable[str],
    subject: str,
    body: str,
    hotel_name: str | None,
    reply_to: str | None = None,
    attachments: Sequence[HotelEmailAttachment] = (),
) -> str:
    message = _build_email_message(
        sender_email=sender_email,
        sender_name=sender_name,
        recipients=recipients,
        subject=subject,
        body=body,
        hotel_name=hotel_name,
        reply_to=reply_to,
        attachments=attachments,
    )
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip('=')
    return raw


def _dev_outbox_path() -> Path:
    configured = (getattr(get_settings(), "DEV_EMAIL_OUTBOX_PATH", "") or "").strip()
    if configured:
        return Path(configured).expanduser()
    # Keep the default outbox in its own private directory; never put captured
    # recipient MIME directly under a shared temp directory such as /tmp.
    return Path(tempfile.gettempdir()) / "hotel-chipre-dev-email-outbox" / "outbox.jsonl"


def capture_hotel_email(
    db: Session,
    hotel_id: int,
    *,
    to: Iterable[str] | str,
    subject: str,
    body: str,
    attachments: Sequence[HotelEmailAttachment] = (),
) -> HotelOutboundSendResult:
    """Append a complete MIME message to the protected local development outbox.

    This adapter never reads Gmail credentials or opens a network connection.
    Recipient addresses appear only inside the captured MIME payload.
    """
    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        raise HotelOutboundEmailError("El correo requiere al menos un destinatario.")
    hotel = db.get(HotelConfiguration, hotel_id)
    hotel_name = hotel.hotel_name if hotel and hotel.hotel_name else "Hotel Chipre"
    capture_id = uuid.uuid4().hex
    sender_email = "no-reply@hotel-chipre.test"
    message = _build_email_message(
        sender_email=sender_email,
        sender_name=hotel_name,
        recipients=recipients,
        subject=subject,
        body=body,
        hotel_name=hotel_name,
        attachments=attachments,
        message_id=f"<local-{capture_id}@hotel-chipre.test>",
    )
    mime = message.as_bytes()
    row = {
        "channel": "payment_receipt_local_simulation",
        "capture_id": capture_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "mime_base64": base64.b64encode(mime).decode("ascii"),
    }
    encoded_row = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    outbox = _dev_outbox_path()
    descriptor = None
    try:
        outbox.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        directory_mode = stat.S_IMODE(outbox.parent.stat().st_mode)
        if directory_mode != 0o700:
            raise HotelOutboundEmailError("El directorio del outbox local debe tener permisos 0700.")
        open_flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        open_flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(outbox, open_flags, 0o600)
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
            raise HotelOutboundEmailError("El archivo del outbox local debe ser un archivo privado regular.")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        with os.fdopen(descriptor, "ab", closefd=True) as handle:
            descriptor = None
            handle.write(encoded_row)
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise HotelOutboundEmailError("No se pudo guardar el correo en el outbox local.") from exc
    return HotelOutboundSendResult(
        channel="local_simulation",
        sender_email=sender_email,
        provider_message_id=f"local-simulation:{capture_id}",
    )


def send_hotel_email(
    db: Session,
    hotel_id: int,
    *,
    to: Iterable[str] | str,
    subject: str,
    body: str,
    attachments: Sequence[HotelEmailAttachment] = (),
) -> HotelOutboundSendResult:
    # This stays before readiness checks and credential decryption.
    try:
        require_external_connections("Gmail hotel email send")
    except ExternalEffectsDisabled as exc:
        raise HotelOutboundEmailError(str(exc)) from exc
    identity = ensure_hotel_gmail_ready(db, hotel_id)
    if isinstance(to, str):
        recipients = [to]
    else:
        recipients = list(to)
    hotel = db.get(HotelConfiguration, hotel_id)
    hotel_name = hotel.hotel_name if hotel else None

    connection = get_connection_record(db, hotel_id, 'gmail')
    if not connection or not connection.auth_payload:
        raise HotelOutboundEmailError('La conexion Gmail no esta disponible para este hotel.')
    payload = decrypt_payload(connection.auth_payload)
    access_token = str(payload.get('access_token') or '').strip()
    if not access_token:
        raise HotelOutboundEmailError('La conexion Gmail no tiene un access token valido. Reconecta Gmail.')

    raw_message = _build_message(
        sender_email=identity.account_email,
        sender_name=identity.account_name,
        recipients=recipients,
        subject=subject,
        body=body,
        hotel_name=hotel_name,
        reply_to=identity.account_email,
        attachments=attachments,
    )
    response = observed_http_call("google.gmail_send", requests.post,
        'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        json={'raw': raw_message},
        timeout=20,
    )
    if not response.ok:
        connection.status = 'error'
        connection.last_checked_at = datetime.now(timezone.utc)
        connection.last_error = 'Google rechazo el envio del correo del hotel.'
        db.flush()
        raise HotelOutboundEmailError(connection.last_error)

    connection.last_checked_at = datetime.now(timezone.utc)
    connection.last_error = None
    db.flush()
    provider_payload = response.json()
    return HotelOutboundSendResult(
        channel='gmail_hotel',
        sender_email=identity.account_email,
        provider_message_id=provider_payload.get('id'),
    )
