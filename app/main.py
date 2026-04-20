"""
Hotel PMS — FastAPI Main Application.
Serves the API + bundled frontend files.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import init_db, get_db, Base
from app.config import get_settings, is_demo_mode, is_production_mode, validate_runtime_security
from app.api import (
    rooms,
    guests,
    reservations,
    payments,
    checkin,
    ota_webhooks,
    config,
    reports,
    bookings,
    onboarding,
    users,
    subscription,
    demo,
    auth,
    invitations,
    integrations,
    payment_link_tests,
    commercial,
    allocation_policy,
    gemma_chat,
)
from app.services.email_service import mailer

_startup_email_sent = False

def _is_demo_mode_enabled() -> bool:
    """Check whether demo-only utilities should be exposed."""
    return os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes", "on"}


def _require_demo_mode():
    if not _is_demo_mode_enabled():
        raise HTTPException(
            status_code=403,
            detail="Demo mode is disabled. Set DEMO_MODE=true to use this endpoint.",
        )


def _maybe_send_startup_email():
    """
    Sends a lightweight startup email to the configured SMTP user/from.
    Only fires if SMTP is configured AND SMTP_STARTUP_NOTIFY is True.
    Guards against multiple sends per process.
    """
    global _startup_email_sent
    if _startup_email_sent:
        return
    if not mailer.configured:
        return
    settings = get_settings()
    if not settings.SMTP_STARTUP_NOTIFY:
        return
    recipient = settings.SMTP_USER or settings.SMTP_FROM
    if not recipient:
        return
    subject = "Hotel PMS iniciado"
    body = (
        "Hola,\n\n"
        "El servicio Hotel PMS se inició correctamente.\n"
        "Si no esperabas este mensaje, revisá las credenciales SMTP.\n"
    )
    mailer.send(recipient, subject, body)
    _startup_email_sent = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on application startup."""
    validate_runtime_security()
    init_db()
    _maybe_send_startup_email()
    yield


app = FastAPI(
    title="Hotel PMS — Property Management System",
    description=(
        "Centralized PMS for multi-hotel operations with intelligent room allocation, "
        "multi-gateway payment processing, and OTA integration."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: local dev + production domains (add CORS_ORIGINS env var for extra origins)
_base_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_extra = os.getenv("CORS_ORIGINS", "")
_extra_entries = [o.strip() for o in _extra.split(",") if o.strip()]
# Wildcard is incompatible with allow_credentials=True in the browser spec
# (the server must echo a concrete Origin). When operators set CORS_ORIGINS=*
# we widen the regex instead of shipping a literal "*" that silently fails.
_wildcard = any(entry == "*" for entry in _extra_entries)
_extra_origins = [entry for entry in _extra_entries if entry != "*"]
allowed_origins = _base_origins + _extra_origins
_allow_origin_regex = r".*" if _wildcard else r"https://.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all API routers
app.include_router(onboarding.router)
app.include_router(rooms.router)
app.include_router(guests.router)
app.include_router(reservations.router)
app.include_router(bookings.router)
app.include_router(payments.router)
app.include_router(checkin.router)
app.include_router(ota_webhooks.router)
app.include_router(config.router)
app.include_router(reports.router)
app.include_router(subscription.router)
app.include_router(subscription.admin_router)
app.include_router(users.router)
if is_demo_mode() or not is_production_mode():
    app.include_router(demo.router, include_in_schema=is_demo_mode())
app.include_router(auth.router)
app.include_router(invitations.router)
app.include_router(integrations.router)
app.include_router(payment_link_tests.router)
app.include_router(commercial.router)
app.include_router(allocation_policy.router)
app.include_router(gemma_chat.router)

# Frontend build paths
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"

class SafeStaticFiles(StaticFiles):
    """StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on Windows)."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except OSError:
            # Invalid path (e.g., contains '*' after unquote on Windows). Return 404 instead of 500.
            raise HTTPException(status_code=404)


if ASSETS_DIR.exists():
    app.mount("/assets", SafeStaticFiles(directory=ASSETS_DIR), name="frontend-assets")


def _frontend_placeholder() -> HTMLResponse:
    """Fallback page shown when the Vite build is missing."""
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="es">
            <head>
                <meta charset="utf-8" />
                <title>Hotel PMS</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 2rem; color: #1f2933; }
                    code { background: #f3f4f6; padding: 0.15rem 0.35rem; border-radius: 4px; }
                </style>
            </head>
            <body>
                <h1>Frontend build no encontrado</h1>
                <p>Ejecutá <code>npm run build</code> dentro de <code>frontend/</code> para generar <code>frontend/dist</code>.</p>
                <p>Mientras tanto se muestra este placeholder.</p>
            </body>
        </html>
        """,
        status_code=200,
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "system": "Hotel PMS v1.0.0"}


@app.api_route(
    "/api/connections/{legacy_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
def legacy_connections_removed(legacy_path: str):
    raise HTTPException(
        status_code=410,
        detail="La API legacy /api/connections fue retirada. Usa /api/integrations.",
    )


@app.api_route(
    "/api/email/{legacy_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
@app.api_route(
    "/api/email",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
def legacy_email_routes_removed(legacy_path: str = ""):
    raise HTTPException(
        status_code=410,
        detail="La API publica /api/email fue retirada. Usa los flujos oficiales de /api/auth.",
    )


@app.get("/")
def serve_frontend(db: Session = Depends(get_db)):
    """
    Serve the SPA shell. We no longer block by onboarding here to avoid
    returning a 403 that would render the page en blanco. The UI ya consulta
    /api/onboarding/status y redirige según corresponda.
    """
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return _frontend_placeholder()


@app.get("/{full_path:path}")
def serve_spa(full_path: str, db: Session = Depends(get_db)):
    """
    SPA fallback for React Router.
    Skips API/asset paths to avoid shadowing.
    """
    if full_path.startswith(("api", "health", "assets", "docs", "openapi", "redoc")):
        raise HTTPException(status_code=404)
    candidate = (FRONTEND_DIST / full_path).resolve()
    if candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST):
        return FileResponse(candidate)
    return serve_frontend(db)



