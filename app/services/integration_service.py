from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import base64
import hashlib
import json
from urllib.parse import urlencode
import requests

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import get_settings, is_production_mode
from app.models.integration import IntegrationCatalog, IntegrationConnection, IntegrationEvent

GOOGLE_IDENTITY_SCOPES = ["openid", "email", "profile"]
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def _fernet() -> Fernet:
    raw_key = get_settings().INTEGRATIONS_ENCRYPTION_KEY.encode()
    try:
        return Fernet(raw_key)
    except ValueError:
        if is_production_mode():
            raise ValueError("INTEGRATIONS_ENCRYPTION_KEY must be a valid Fernet key in production")
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
        if is_production_mode():
            raise ValueError("Stored integration credentials are corrupted or cannot be decrypted")
        return {}


def seed_catalog(db: Session):
    defaults = [
        ("booking", "Booking.com", "api_key", "content,availability", "https://developers.booking.com/connectivity"),
        ("expedia", "Expedia", "signature", "content,availability", "https://developers.expediagroup.com/"),
        ("mercadopago", "MercadoPago", "oauth_code", "payments,offline_access", "https://www.mercadopago.com.ar/developers/en"),
        ("paypal", "PayPal", "oauth_code", "payments,openid,email,offline_access", "https://developer.paypal.com/docs/api/overview/"),
        (
            "gmail",
            "Gmail",
            "oauth_code",
            "openid email profile https://www.googleapis.com/auth/gmail.send",
            "https://developers.google.com/workspace/gmail/api/guides/sending",
        ),
        ("whatsapp", "WhatsApp Business", "bearer_token", "messages", "https://developers.facebook.com/docs/whatsapp/"),
    ]
    existing_rows = {c.provider: c for c in db.execute(select(IntegrationCatalog)).scalars()}
    for provider, name, auth_type, scopes, doc_url in defaults:
        existing = existing_rows.get(provider)
        if existing:
            existing.display_name = name
            existing.auth_type = auth_type
            existing.scopes = scopes
            existing.doc_url = doc_url
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


def _is_expired(payload: Dict[str, Any], skew_seconds: int = 120) -> bool:
    expires_at_raw = payload.get("expires_at")
    if expires_at_raw:
        expires_at = _parse_datetime(expires_at_raw)
        if expires_at and expires_at <= datetime.now(timezone.utc) + timedelta(seconds=skew_seconds):
            return True

    expires_in = payload.get("expires_in")
    issued_at_raw = payload.get("issued_at")
    if isinstance(expires_in, (int, float)) and issued_at_raw:
        issued_at = _parse_datetime(issued_at_raw)
        if issued_at:
            computed = issued_at + timedelta(seconds=int(expires_in))
            return computed <= datetime.now(timezone.utc) + timedelta(seconds=skew_seconds)
    return False


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _google_userinfo(access_token: str) -> Dict[str, Any]:
    response = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    if not response.ok:
        raise ValueError("Google no pudo validar la cuenta de Gmail conectada.")
    return response.json()


def refresh_gmail_access_token(payload: Dict[str, Any]) -> Dict[str, Any]:
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if not refresh_token:
        raise ValueError(
            "La conexion de Gmail no tiene refresh token. Vuelve a conectar Gmail para completar el acceso offline."
        )
    settings = get_settings()
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if not response.ok:
        raise ValueError("Google rechazo la renovacion del token de Gmail. Vuelve a conectar la cuenta.")
    refreshed = response.json()
    merged = dict(payload)
    merged.update(refreshed)
    merged["refresh_token"] = refresh_token
    merged["issued_at"] = datetime.now(timezone.utc).isoformat()
    expires_at = derive_expires_at(merged)
    if expires_at:
        merged["expires_at"] = expires_at.isoformat()
    return merged


def validate_gmail_credentials(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload or {})
    access_token = str(normalized.get("access_token") or "").strip()
    if not access_token and normalized.get("token"):
        access_token = str(normalized["token"]).strip()
        normalized["access_token"] = access_token
    if not access_token:
        raise ValueError("Google no devolvio un access token valido para Gmail.")
    refresh_token = str(normalized.get("refresh_token") or "").strip()
    if not refresh_token:
        raise ValueError(
            "Google no devolvio un refresh token para Gmail. Vuelve a conectar la cuenta y acepta el acceso offline."
        )

    if _is_expired(normalized):
        normalized = refresh_gmail_access_token(normalized)
        access_token = str(normalized.get("access_token") or "").strip()

    userinfo = _google_userinfo(access_token)
    connected_email = str(userinfo.get("email") or "").strip().lower()
    if not connected_email:
        raise ValueError("Google no devolvio el email de la cuenta conectada.")

    granted_scope = str(normalized.get("scope") or "").strip()
    if granted_scope:
        granted_scopes = set(granted_scope.split())
        if GMAIL_SEND_SCOPE not in granted_scopes:
            raise ValueError("La cuenta de Gmail no otorgo permiso de envio. Acepta el scope gmail.send.")

    normalized["access_token"] = access_token
    normalized["account_email"] = connected_email
    normalized["account_name"] = str(userinfo.get("name") or "").strip() or connected_email
    normalized["account_sub"] = str(userinfo.get("sub") or "").strip() or None
    normalized["issued_at"] = datetime.now(timezone.utc).isoformat()
    expires_at = derive_expires_at(normalized)
    if expires_at:
        normalized["expires_at"] = expires_at.isoformat()
    return normalized


def validate_provider_credentials(provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if provider == "mercadopago":
        return validate_mercadopago_credentials(payload)
    if provider == "gmail":
        return validate_gmail_credentials(payload)
    return payload


def ensure_provider_payload(
    db: Session,
    hotel_id: int,
    provider: str,
    *,
    require_connected: bool = True,
) -> Dict[str, Any]:
    connection = get_connection_record(db, hotel_id, provider)
    if not connection:
        if require_connected:
            raise ValueError(f"No hay una conexion activa de {provider} para este hotel.")
        return {}
    if require_connected and connection.status != "connected":
        raise ValueError(f"La conexion de {provider} no esta activa para este hotel.")

    payload = decrypt_payload(connection.auth_payload)
    if provider == "gmail":
        payload = validate_gmail_credentials(payload)
        connection.auth_payload = encrypt_payload(payload)
        connection.status = "connected"
        connection.expires_at = derive_expires_at(payload)
        connection.last_checked_at = datetime.now(timezone.utc)
        connection.last_error = None
        db.flush()
    return payload


def _account_label_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    if not payload:
        return None
    account_email = str(payload.get("account_email") or "").strip()
    account_name = str(payload.get("account_name") or "").strip()
    account_nickname = str(payload.get("account_nickname") or "").strip()
    user_id = str(payload.get("user_id") or "").strip()
    if account_email:
        return f"{account_name} <{account_email}>" if account_name and account_name != account_email else account_email
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

    now = datetime.now(timezone.utc)
    try:
        payload = decrypt_payload(connection.auth_payload)
    except ValueError as exc:
        connection.status = "error"
        connection.last_error = str(exc)
        connection.last_checked_at = now
        db.flush()
        return connection, str(exc)

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

    if integration.provider == "gmail":
        try:
            enriched = validate_gmail_credentials(payload)
            connection.auth_payload = encrypt_payload(enriched)
            connection.status = "connected"
            connection.expires_at = derive_expires_at(enriched)
            connection.last_error = None
            connection.last_checked_at = now
            db.flush()
            return connection, f"Gmail verificado correctamente para {enriched.get('account_email')}."
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


def get_connection_record(db: Session, hotel_id: int, provider: str) -> Optional[IntegrationConnection]:
    seed_catalog(db)
    return (
        db.execute(
            select(IntegrationConnection)
            .join(IntegrationCatalog, IntegrationCatalog.id == IntegrationConnection.integration_id)
            .where(
                IntegrationConnection.hotel_id == hotel_id,
                IntegrationCatalog.provider == provider,
            )
        )
        .scalars()
        .first()
    )


def build_redirect_url(
    integration: IntegrationCatalog,
    redirect_uri: Optional[str] = None,
    *,
    state: Optional[str] = None,
) -> str:
    settings = get_settings()
    if integration.provider == "mercadopago":
        if not settings.MERCADOPAGO_CLIENT_ID or not settings.MERCADOPAGO_CLIENT_SECRET:
            raise ValueError(
                "OAuth de Mercado Pago no esta configurado en este entorno. Usa access_token manual o configura la app del PMS."
            )
        target_redirect = redirect_uri or settings.MERCADOPAGO_REDIRECT_URI
        params = {
            "client_id": settings.MERCADOPAGO_CLIENT_ID,
            "response_type": "code",
            "platform_id": "mp",
            "redirect_uri": target_redirect,
        }
        if state:
            params["state"] = state
        return f"https://auth.mercadopago.com/authorization?{urlencode(params)}"
    if integration.provider == "paypal":
        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
            raise ValueError(
                "OAuth de PayPal no esta configurado en este entorno. Usa credenciales manuales o configura la app del PMS."
            )
        base = "https://www.sandbox.paypal.com/signin/authorize" if settings.PAYPAL_MODE == "sandbox" else "https://www.paypal.com/signin/authorize"
        scopes = integration.scopes or "openid profile email https://uri.paypal.com/services/paypalattributes offline_access"
        target_redirect = redirect_uri or settings.PAYPAL_REDIRECT_URI
        params = {
            "client_id": settings.PAYPAL_CLIENT_ID,
            "response_type": "code",
            "scope": scopes,
            "redirect_uri": target_redirect,
        }
        if state:
            params["state"] = state
        return f"{base}?{urlencode(params)}"
    if integration.provider == "gmail":
        if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
            raise ValueError(
                "OAuth de Gmail no esta configurado en este entorno. Faltan GOOGLE_OAUTH_CLIENT_ID y/o GOOGLE_OAUTH_CLIENT_SECRET en la app del PMS."
            )
        scopes = integration.scopes or f"{' '.join(GOOGLE_IDENTITY_SCOPES)} {GMAIL_SEND_SCOPE}"
        target_redirect = redirect_uri or settings.GMAIL_REDIRECT_URI
        params = urlencode(
            {
                "client_id": settings.GMAIL_CLIENT_ID,
                "response_type": "code",
                "redirect_uri": target_redirect,
                "scope": scopes,
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
            }
        )
        if state:
            params += f"&{urlencode({'state': state})}"
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
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
