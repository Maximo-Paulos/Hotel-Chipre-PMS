from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import base64
import hashlib
import json
import requests

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import get_settings
from app.models.integration import IntegrationCatalog, IntegrationConnection, IntegrationEvent


def _fernet() -> Fernet:
    raw_key = get_settings().INTEGRATIONS_ENCRYPTION_KEY.encode()
    try:
        return Fernet(raw_key)
    except ValueError:
        # Keep local/dev setups stable even if the env value is not already a Fernet key.
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key).digest())
        return Fernet(derived)


def encrypt_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload is None:
        return {}
    token = _fernet().encrypt(json.dumps(payload).encode())
    return {"ciphertext": token.decode()}


def decrypt_payload(encrypted: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not encrypted or "ciphertext" not in encrypted:
        return {}
    try:
        data = _fernet().decrypt(encrypted["ciphertext"].encode())
        return json.loads(data.decode())
    except InvalidToken:
        return {}


def seed_catalog(db: Session):
    defaults = [
        ("booking", "Booking.com", "api_key", "content,availability", "https://developers.booking.com/connectivity"),
        ("expedia", "Expedia", "signature", "content,availability", "https://developers.expediagroup.com/"),
        ("mercadopago", "MercadoPago", "oauth_code", "payments,offline_access", "https://www.mercadopago.com.ar/developers/en"),
        ("paypal", "PayPal", "oauth_code", "payments,openid,email,offline_access", "https://developer.paypal.com/docs/api/overview/"),
        ("gmail", "Gmail", "oauth_code", "gmail.send gmail.readonly", "https://developers.google.com/gmail/api"),
        ("whatsapp", "WhatsApp Business", "bearer_token", "messages", "https://developers.facebook.com/docs/whatsapp/"),
    ]
    existing = {c.provider for c in db.execute(select(IntegrationCatalog)).scalars()}
    for provider, name, auth_type, scopes, doc_url in defaults:
        if provider in existing:
            continue
        db.add(
            IntegrationCatalog(
                provider=provider,
                display_name=name,
                auth_type=auth_type,
                scopes=scopes,
                doc_url=doc_url,
            )
        )
    db.flush()


def list_catalog_with_status(db: Session, hotel_id: int) -> tuple[List[IntegrationCatalog], List[IntegrationConnection]]:
    seed_catalog(db)
    catalog = db.execute(select(IntegrationCatalog)).scalars().all()
    connections = (
        db.execute(
            select(IntegrationConnection).where(IntegrationConnection.hotel_id == hotel_id)
        )
        .scalars()
        .all()
    )
    return catalog, connections


def get_provider_connection_payload(db: Session, hotel_id: int, provider: str) -> Dict[str, Any]:
    seed_catalog(db)
    integration = (
        db.execute(select(IntegrationCatalog).where(IntegrationCatalog.provider == provider))
        .scalars()
        .first()
    )
    if not integration:
        return {}
    connection = (
        db.execute(
            select(IntegrationConnection).where(
                IntegrationConnection.hotel_id == hotel_id,
                IntegrationConnection.integration_id == integration.id,
                IntegrationConnection.status == "connected",
            )
        )
        .scalars()
        .first()
    )
    if not connection:
        return {}
    return decrypt_payload(connection.auth_payload)


def get_connection_payload(db: Session, hotel_id: int, provider: str) -> Dict[str, Any]:
    seed_catalog(db)
    connection = (
        db.execute(
            select(IntegrationConnection)
            .join(IntegrationCatalog, IntegrationCatalog.id == IntegrationConnection.integration_id)
            .where(
                IntegrationConnection.hotel_id == hotel_id,
                IntegrationConnection.status == "connected",
                IntegrationCatalog.provider == provider,
            )
        )
        .scalars()
        .first()
    )
    if not connection:
        return {}
    return decrypt_payload(connection.auth_payload)


def derive_expires_at(payload: Optional[Dict[str, Any]]) -> Optional[datetime]:
    if not payload:
        return None
    expires_in = payload.get("expires_in")
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    return None


def _mercadopago_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    message = ""
    if isinstance(payload, dict):
        message = str(payload.get("message") or payload.get("error") or "").strip()
        blocked_by = payload.get("blocked_by")
        code = payload.get("code")
        if response.status_code in {401, 403} and (
            blocked_by == "PolicyAgent" or code == "PA_UNAUTHORIZED_RESULT_FROM_POLICIES"
        ):
            return (
                "El access_token de Mercado Pago es invalido, esta incompleto o no tiene permisos para "
                "crear links de cobro. Vuelve a conectar Mercado Pago con un Access Token real de tu cuenta."
            )
    return message or response.text[:250] or "Mercado Pago rechazo las credenciales."


def validate_mercadopago_credentials(payload: Dict[str, Any]) -> Dict[str, Any]:
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise ValueError("Ingresa un access_token de Mercado Pago para conectar este hotel.")

    response = requests.get(
        "https://api.mercadopago.com/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    if not response.ok:
        raise ValueError(_mercadopago_error_message(response))

    data = response.json()
    enriched = dict(payload)
    if data.get("id") and not enriched.get("user_id"):
        enriched["user_id"] = str(data["id"])
    if data.get("nickname") and not enriched.get("account_nickname"):
        enriched["account_nickname"] = str(data["nickname"])
    if data.get("email") and not enriched.get("account_email"):
        enriched["account_email"] = str(data["email"])
    return enriched


def _account_label_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    if not payload:
        return None
    account_email = str(payload.get("account_email") or "").strip()
    account_nickname = str(payload.get("account_nickname") or "").strip()
    user_id = str(payload.get("user_id") or "").strip()
    if account_email:
        return account_email
    if account_nickname and user_id:
        return f"{account_nickname} (ID {user_id})"
    if account_nickname:
        return account_nickname
    if user_id:
        return f"ID {user_id}"
    return None


def connection_account_label(connection: IntegrationConnection) -> Optional[str]:
    return _account_label_from_payload(decrypt_payload(connection.auth_payload))


def verify_connection_health(
    db: Session,
    hotel_id: int,
    integration_id: int,
) -> tuple[IntegrationConnection, str]:
    seed_catalog(db)
    connection = (
        db.execute(
            select(IntegrationConnection).where(
                IntegrationConnection.hotel_id == hotel_id,
                IntegrationConnection.integration_id == integration_id,
            )
        )
        .scalars()
        .first()
    )
    if not connection:
        raise ValueError("Conexion no encontrada")

    integration = (
        db.execute(select(IntegrationCatalog).where(IntegrationCatalog.id == integration_id))
        .scalars()
        .first()
    )
    if not integration:
        raise ValueError("Integracion no encontrada")

    payload = decrypt_payload(connection.auth_payload)
    now = datetime.now(timezone.utc)

    if integration.provider == "mercadopago":
        try:
            enriched = validate_mercadopago_credentials(payload)
            connection.auth_payload = encrypt_payload(enriched)
            connection.status = "connected"
            connection.last_error = None
            connection.last_checked_at = now
            db.flush()
            label = _account_label_from_payload(enriched)
            if label:
                return connection, f"Conexion verificada correctamente con Mercado Pago ({label})."
            return connection, "Conexion verificada correctamente con Mercado Pago."
        except ValueError as exc:
            connection.status = "error"
            connection.last_error = str(exc)
            connection.last_checked_at = now
            db.flush()
            return connection, str(exc)

    connection.last_checked_at = now
    connection.last_error = None
    db.flush()
    return connection, "La conexion se actualizo, pero este proveedor todavia no tiene chequeo de salud profundo."


def upsert_connection(
    db: Session,
    hotel_id: int,
    integration_id: int,
    payload: Dict[str, Any],
    status: str = "connected",
    expires_at: Optional[datetime] = None,
    last_error: Optional[str] = None,
) -> IntegrationConnection:
    conn = (
        db.execute(
            select(IntegrationConnection).where(
                IntegrationConnection.hotel_id == hotel_id,
                IntegrationConnection.integration_id == integration_id,
            )
        )
        .scalars()
        .first()
    )
    encrypted = encrypt_payload(payload or {})
    now = datetime.now(timezone.utc)
    if conn:
        conn.auth_payload = encrypted
        conn.status = status
        conn.last_checked_at = now
        conn.last_error = last_error
        conn.expires_at = expires_at
    else:
        conn = IntegrationConnection(
            hotel_id=hotel_id,
            integration_id=integration_id,
            status=status,
            auth_payload=encrypted,
            expires_at=expires_at,
            last_checked_at=now,
            last_error=last_error,
        )
        db.add(conn)
    db.flush()
    return conn


def revoke_connection(db: Session, hotel_id: int, integration_id: int):
    conn = (
        db.execute(
            select(IntegrationConnection).where(
                IntegrationConnection.hotel_id == hotel_id,
                IntegrationConnection.integration_id == integration_id,
            )
        )
        .scalars()
        .first()
    )
    if not conn:
        return
    conn.status = "revoked"
    conn.auth_payload = None
    conn.last_error = None
    db.flush()


def record_event(db: Session, connection_id: int, kind: str, payload: Optional[Dict[str, Any]] = None):
    db.add(IntegrationEvent(connection_id=connection_id, kind=kind, payload=payload or {}))
    db.flush()


def build_redirect_url(integration: IntegrationCatalog, redirect_uri: Optional[str] = None) -> str:
    settings = get_settings()
    if integration.provider == "mercadopago":
        if not settings.MERCADOPAGO_CLIENT_ID or not settings.MERCADOPAGO_CLIENT_SECRET:
            raise ValueError(
                "OAuth de Mercado Pago no esta configurado en este entorno. Usa access_token manual o configura la app del PMS."
            )
        target_redirect = redirect_uri or settings.MERCADOPAGO_REDIRECT_URI
        return (
            "https://auth.mercadopago.com/authorization?"
            f"client_id={settings.MERCADOPAGO_CLIENT_ID}"
            f"&response_type=code&platform_id=mp&redirect_uri={target_redirect}"
        )
    if integration.provider == "paypal":
        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
            raise ValueError(
                "OAuth de PayPal no esta configurado en este entorno. Usa credenciales manuales o configura la app del PMS."
            )
        base = "https://www.sandbox.paypal.com/signin/authorize" if settings.PAYPAL_MODE == "sandbox" else "https://www.paypal.com/signin/authorize"
        scopes = integration.scopes or "openid profile email https://uri.paypal.com/services/paypalattributes offline_access"
        target_redirect = redirect_uri or settings.PAYPAL_REDIRECT_URI
        return (
            f"{base}?client_id={settings.PAYPAL_CLIENT_ID}"
            f"&response_type=code&scope={scopes.replace(' ', '%20')}&redirect_uri={target_redirect}"
        )
    if integration.provider == "gmail":
        if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
            raise ValueError(
                "OAuth de Gmail no esta configurado en este entorno. Configura la app del PMS antes de autorizar."
            )
        scopes = integration.scopes or "gmail.send gmail.readonly"
        target_redirect = redirect_uri or settings.GMAIL_REDIRECT_URI
        return (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={settings.GMAIL_CLIENT_ID}"
            f"&response_type=code&redirect_uri={target_redirect}"
            f"&scope={scopes.replace(' ', '%20')}&access_type=offline&prompt=consent"
        )
    return f"https://example.com/oauth/{integration.provider}/authorize"


def exchange_token(provider: str, code: str) -> Dict[str, Any]:
    settings = get_settings()
    if provider == "mercadopago":
        resp = requests.post(
            "https://api.mercadopago.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.MERCADOPAGO_CLIENT_ID,
                "client_secret": settings.MERCADOPAGO_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.MERCADOPAGO_REDIRECT_URI,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    if provider == "paypal":
        token_url = "https://api-m.sandbox.paypal.com/v1/oauth2/token" if settings.PAYPAL_MODE == "sandbox" else "https://api-m.paypal.com/v1/oauth2/token"
        resp = requests.post(
            token_url,
            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.PAYPAL_REDIRECT_URI},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    if provider == "gmail":
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "redirect_uri": settings.GMAIL_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    return {"code": code}
