from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context, require_roles
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
    list_catalog_with_status,
    record_event,
    revoke_connection,
    upsert_connection,
    validate_mercadopago_credentials,
    verify_connection_health,
)

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


def _find_integration(db: Session, hotel_id: int, integration_id: int):
    catalog, _ = list_catalog_with_status(db, hotel_id)
    integration = next((item for item in catalog if item.id == integration_id), None)
    if not integration:
        raise HTTPException(status_code=404, detail="Integracion no encontrada")
    return integration, catalog


def _store_oauth_code(db: Session, hotel_id: int, integration_id: int, provider: str, code: str):
    try:
        token_payload = exchange_token(provider, code)
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
    context: AuthContext = Depends(get_auth_context),
):
    _ensure_enabled()
    catalog, connections = list_catalog_with_status(db, context.hotel_id)
    response_connections = []
    for conn in connections:
        for cat in catalog:
            if cat.id == conn.integration_id:
                conn.integration = cat  # type: ignore[attr-defined]
                break
        conn.account_label = connection_account_label(conn)  # type: ignore[attr-defined]
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
            if integration.provider == "mercadopago":
                try:
                    oauth_payload = validate_mercadopago_credentials(oauth_payload)
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

        callback_url = str(request.url_for("oauth_callback", integration_id=integration_id))
        try:
            redirect = build_redirect_url(integration, redirect_uri=callback_url)
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


@router.get("/{integration_id}/callback")
def oauth_callback(
    integration_id: int,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
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
