from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Iterable

import requests
from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.services.integration_service import (
    decrypt_payload,
    encrypt_payload,
    get_connection_record,
    validate_gmail_credentials,
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


def ensure_hotel_gmail_ready(db: Session, hotel_id: int) -> HotelOutboundIdentity:
    connection = get_connection_record(db, hotel_id, 'gmail')
    if not connection or connection.status != 'connected' or not connection.auth_payload:
        raise HotelOutboundEmailError(
            'Conecta Gmail en Configuracion > Conexiones para enviar correos desde el hotel.'
        )

    try:
        payload = decrypt_payload(connection.auth_payload)
        validated = validate_gmail_credentials(payload)
    except ValueError as exc:
        connection.status = 'error'
        connection.last_error = str(exc)
        connection.last_checked_at = datetime.now(timezone.utc)
        db.flush()
        raise HotelOutboundEmailError(str(exc)) from exc

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


def _build_message(
    *,
    sender_email: str,
    sender_name: str | None,
    recipients: Iterable[str],
    subject: str,
    body: str,
    hotel_name: str | None,
    reply_to: str | None = None,
) -> str:
    msg = EmailMessage()
    display_name = sender_name or hotel_name or sender_email
    msg['From'] = f'{display_name} <{sender_email}>' if display_name else sender_email
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    if reply_to:
        msg['Reply-To'] = reply_to
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip('=')
    return raw


def send_hotel_email(
    db: Session,
    hotel_id: int,
    *,
    to: Iterable[str] | str,
    subject: str,
    body: str,
) -> HotelOutboundSendResult:
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
    )
    response = requests.post(
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
        try:
            payload = response.json()
            detail = payload.get('error', {}).get('message') or payload.get('error_description') or payload.get('message')
        except Exception:
            detail = response.text
        connection.last_error = str(detail or 'Google rechazo el envio del correo del hotel.')
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
