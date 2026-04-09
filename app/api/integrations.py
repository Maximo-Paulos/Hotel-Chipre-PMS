import html
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.integration import (
    IntegrationConnectRequest,
    IntegrationConnectResponse,
    IntegrationRefreshResponse,
    IntegrationStatusResponse,
)
from app.services.integration_service import (
    build_redirect_url,
    connection_account_label,
    derive_expires_at,
    exchange_token,
    get_connection_record,
    list_catalog_with_status,
    record_event,
    revoke_connection,
    upsert_connection,
    validate_provider_credentials,
    verify_connection_health,
)
from app.services.security import create_signed_token, decode_signed_token

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


def _ensure_enabled():
    if not get_settings().CONNECTIONS_ENABLED:
        raise HTTPException(status_code=403, detail="Conexiones deshabilitadas")


def _connection_error_message(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = payload.get("message") or payload.get("error_description") or payload.get("error")
                if isinstance(message, str) and message.strip():
                    return message.strip()
        except Exception:
            pass
        if getattr(response, "text", None):
            return response.text[:250]
    return str(exc)[:250] or "No se pudo guardar la conexion."


def _origin_for_popup(request: Request) -> str:
    origin = (request.headers.get("origin") or "").strip()
    if origin.startswith(("http://", "https://")):
        return origin
    referer = (request.headers.get("referer") or "").strip()
    if referer.startswith(("http://", "https://")):
        parsed = urlparse(referer)
        return f"{parsed.scheme}://{parsed.netloc}"
    return get_settings().APP_BASE_URL.rstrip("/")


def _oauth_state_token(request: Request, integration_id: int, context: AuthContext, provider: str) -> str:
    return create_signed_token(
        {
            "type": "integration_oauth",
            "integration_id": integration_id,
            "hotel_id": context.hotel_id,
            "user_id": context.user_id,
            "provider": provider,
            "web_origin": _origin_for_popup(request),
        },
        expires_minutes=15,
    )


def _oauth_callback_page(*, status: str, message: str, provider: str, integration_id: int, web_origin: str) -> HTMLResponse:
    safe_message = message.replace("\\", "\\\\").replace("'", "\\'")
    rendered_message = html.escape(message)
    target_origin = web_origin if web_origin.startswith(("http://", "https://")) else "*"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="es">
          <head>
            <meta charset="utf-8" />
            <title>Conexión {provider}</title>
          </head>
          <body style="font-family: Arial, sans-serif; padding: 24px;">
            <p id="message">{rendered_message}</p>
            <script>
              (function () {{
                var payload = {{
                  type: 'integration-oauth-result',
                  provider: '{provider}',
                  integrationId: {integration_id},
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


def _find_integration(db: Session, hotel_id: int, integration_id: int):
    catalog, _ = list_catalog_with_status(db, hotel_id)
    integration = next((item for item in catalog if item.id == integration_id), None)
    if not integration:
        raise HTTPException(status_code=404, detail="Integracion no encontrada")
    return integration, catalog


def _store_oauth_code(db: Session, hotel_id: int, integration_id: int, provider: str, code: str):
    try:
        token_payload = exchange_token(provider, code)
        existing = get_connection_record(db, hotel_id, provider)
        if existing:
            try:
                existing_payload = existing.auth_payload or {}
                if isinstance(existing_payload, dict):
                    existing_cipher = existing_payload
                else:
                    existing_cipher = {}
            except Exception:
                existing_cipher = {}
            # Preserve refresh_token if Google does not return a new one on reconsent-less exchanges.
            from app.services.integration_service import decrypt_payload
            previous = decrypt_payload(existing_cipher) if existing_cipher else {}
            if provider == "gmail" and previous.get("refresh_token") and not token_payload.get("refresh_token"):
                token_payload["refresh_token"] = previous.get("refresh_token")
        token_payload = validate_provider_credentials(provider, token_payload)
        conn = upsert_connection(
            db,
            hotel_id,
            integration_id,
            token_payload,
            status="connected",
            expires_at=derive_expires_at(token_payload),
        )
        record_event(
            db,
            conn.id,
            "connect",
            {"auth_type": "oauth_code", "provider": provider, "mode": "authorization_code"},
        )
        db.commit()
        return conn
    except Exception as exc:
        message = _connection_error_message(exc)
        conn = upsert_connection(
            db,
            hotel_id,
            integration_id,
            {"code": code},
            status="error",
            last_error=message,
        )
        record_event(
            db,
            conn.id,
            "failure",
            {"auth_type": "oauth_code", "provider": provider, "message": message},
        )
        db.commit()
        raise HTTPException(status_code=400, detail=message)


@router.get("/", response_model=IntegrationStatusResponse)
@router.get("", response_model=IntegrationStatusResponse)
def get_status(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    _ensure_enabled()
    catalog, connections = list_catalog_with_status(db, context.hotel_id)
    response_connections = []
    for conn in connections:
        for cat in catalog:
            if cat.id == conn.integration_id:
                conn.integration = cat  # type: ignore[attr-defined]
                break
        try:
            conn.account_label = connection_account_label(conn)  # type: ignore[attr-defined]
        except ValueError as exc:
            conn.account_label = None  # type: ignore[attr-defined]
            conn.last_error = str(exc)
        response_connections.append(conn)
    return IntegrationStatusResponse(catalog=catalog, connections=response_connections)


@router.post("/{integration_id}/connect", response_model=IntegrationConnectResponse)
def connect_integration(
    integration_id: int,
    payload: IntegrationConnectRequest,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    _ensure_enabled()
    integration, _ = _find_integration(db, context.hotel_id, integration_id)

    if integration.auth_type == "oauth_code":
        oauth_payload = payload.payload or {}
        manual_keys = {"access_token", "refresh_token", "public_key", "user_id", "merchant_id"}
        if any(oauth_payload.get(key) for key in manual_keys):
            try:
                oauth_payload = validate_provider_credentials(integration.provider, oauth_payload)
            except ValueError as exc:
                conn = upsert_connection(
                    db,
                    context.hotel_id,
                    integration_id,
                    oauth_payload,
                    status="error",
                    last_error=str(exc),
                )
                record_event(
                    db,
                    conn.id,
                    "failure",
                    {"auth_type": integration.auth_type, "provider": integration.provider, "message": str(exc)},
                )
                db.commit()
                raise HTTPException(status_code=400, detail=str(exc))
            conn = upsert_connection(
                db,
                context.hotel_id,
                integration_id,
                oauth_payload,
                status="connected",
                expires_at=derive_expires_at(oauth_payload),
            )
            record_event(
                db,
                conn.id,
                "connect",
                {"auth_type": integration.auth_type, "provider": integration.provider, "mode": "manual_credentials"},
            )
            db.commit()
            return IntegrationConnectResponse(redirect_url=None, status="connected")

        code = oauth_payload.get("code")
        if isinstance(code, str) and code.strip():
            _store_oauth_code(db, context.hotel_id, integration_id, integration.provider, code.strip())
            return IntegrationConnectResponse(redirect_url=None, status="connected")

        state = _oauth_state_token(request, integration_id, context, integration.provider)
        try:
            redirect = build_redirect_url(integration, state=state)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        conn = upsert_connection(
            db,
            context.hotel_id,
            integration_id,
            {"authorization_started": True},
            status="pending",
        )
        record_event(
            db,
            conn.id,
            "connect",
            {"auth_type": integration.auth_type, "provider": integration.provider, "mode": "authorization_started"},
        )
        db.commit()
        return IntegrationConnectResponse(redirect_url=redirect, status="pending")

    conn = upsert_connection(db, context.hotel_id, integration_id, payload.payload or {}, status="connected")
    record_event(db, conn.id, "connect", {"auth_type": integration.auth_type, "provider": integration.provider})
    db.commit()
    return IntegrationConnectResponse(redirect_url=None, status="connected")


@router.get("/oauth/{provider}/callback", name="oauth_provider_callback")
def oauth_provider_callback(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _ensure_enabled()
    state = request.query_params.get("state")
    if not state:
        raise HTTPException(status_code=400, detail="state requerido")
    state_payload = decode_signed_token(state)
    if state_payload.get("type") != "integration_oauth":
        raise HTTPException(status_code=400, detail="state invalido")
    integration_id = int(state_payload.get("integration_id") or 0)
    if provider.strip() != str(state_payload.get("provider") or "").strip():
        raise HTTPException(status_code=400, detail="state invalido para esta integracion")

    hotel_id = int(state_payload.get("hotel_id") or 0)
    web_origin = str(state_payload.get("web_origin") or "").strip()
    error = request.query_params.get("error")
    if error:
        description = request.query_params.get("error_description") or error
        return _oauth_callback_page(
            status="error",
            message=f"No se pudo completar la autorizacion: {description}",
            provider=provider or "oauth",
            integration_id=integration_id,
            web_origin=web_origin,
        )
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code requerido")
    integration, _ = _find_integration(db, hotel_id, integration_id)
    try:
        _store_oauth_code(db, hotel_id, integration_id, integration.provider, code)
    except HTTPException as exc:
        return _oauth_callback_page(
            status="error",
            message=str(exc.detail),
            provider=integration.provider,
            integration_id=integration_id,
            web_origin=web_origin,
        )
    return _oauth_callback_page(
        status="connected",
        message=f"{integration.display_name} quedo conectado correctamente para este hotel.",
        provider=integration.provider,
        integration_id=integration_id,
        web_origin=web_origin,
    )


@router.get("/{integration_id}/callback")
def oauth_callback_manual(
    integration_id: int,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    _ensure_enabled()
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code requerido")
    integration, _ = _find_integration(db, context.hotel_id, integration_id)
    _store_oauth_code(db, context.hotel_id, integration_id, integration.provider, code)
    return {"status": "connected"}


@router.post("/{integration_id}/revoke")
def revoke(
    integration_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    _ensure_enabled()
    revoke_connection(db, context.hotel_id, integration_id)
    db.commit()
    return {"status": "revoked"}


@router.post("/{integration_id}/refresh", response_model=IntegrationRefreshResponse)
def refresh(
    integration_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    _ensure_enabled()
    try:
        conn, message = verify_connection_health(db, context.hotel_id, integration_id)
        db.commit()
        return IntegrationRefreshResponse(
            status=conn.status,
            message=message,
            last_checked_at=conn.last_checked_at,
            last_error=conn.last_error,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"No se pudo verificar la conexion: {exc}")
