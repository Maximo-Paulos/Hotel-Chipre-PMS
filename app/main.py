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
from sqlalchemy.orm import Session

from app.database import init_db, get_db, Base
from app.config import get_settings
from app.api import (
    rooms,
    guests,
    reservations,
    payments,
    checkin,
    ota_webhooks,
    config,
    reports,
    connections,
    bookings,
    onboarding,
    email,
)
from app.services.email_service import mailer
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.pricing import CategoryPricing
from app.models.hotel_config import HotelConfiguration
from app.services import onboarding_service

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
    init_db()
    _maybe_send_startup_email()
    yield


app = FastAPI(
    title="Hotel PMS — Property Management System",
    description=(
        "Centralized PMS for a 38-room hotel with intelligent room allocation, "
        "multi-gateway payment processing, and OTA integration."
    ),
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(connections.router)
app.include_router(email.router)

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


@app.post("/api/reset")
def reset_db(db: Session = Depends(get_db)):
    """Hard reset of development database."""
    _require_demo_mode()
    engine = db.get_bind()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db.commit()
    return {"status": "reset", "message": "Database wiped and recreated. Please call /api/seed"}


@app.post("/api/seed")
def seed_database(db: Session = Depends(get_db)):
    """Populate the database with initial hotel data (categories, rooms, config)."""
    _require_demo_mode()
    # Check if already seeded
    existing = db.query(RoomCategory).first()
    if existing:
        return {"status": "already_seeded", "message": "Database already has data"}

    # Create categories based on exact user specification
    cat_dict = {
        "DBC": RoomCategory(name="Doble Baño Compartido", code="DBC", base_price_per_night=40.0, max_occupancy=2, description="Habitación Doble con baño compartido"),
        "CBP": RoomCategory(name="Cuádruple Baño Privado", code="CBP", base_price_per_night=80.0, max_occupancy=4, description="Habitación Cuádruple con baño privado"),
        "TBP": RoomCategory(name="Triple Baño Privado", code="TBP", base_price_per_night=60.0, max_occupancy=3, description="Habitación Triple con baño privado"),
        "DBP": RoomCategory(name="Doble Baño Privado", code="DBP", base_price_per_night=50.0, max_occupancy=2, description="Habitación Doble con baño privado"),
        "TBC": RoomCategory(name="Triple Baño Compartido", code="TBC", base_price_per_night=50.0, max_occupancy=3, description="Habitación Triple con baño compartido"),
        "CBC": RoomCategory(name="Cuádruple Baño Compartido", code="CBC", base_price_per_night=70.0, max_occupancy=4, description="Habitación Cuádruple con baño compartido"),
    }
    categories = list(cat_dict.values())
    db.add_all(categories)
    db.flush()

    # Exact room mapping from user input, grouped by an inferred floor (1, 2, 3) based on format
    rooms_data = [
        ("1", "DBC", 1), ("2", "DBC", 1), ("3", "DBC", 1), ("4", "DBC", 1), ("5", "DBC", 1),
        ("6", "CBP", 1), ("7", "TBP", 1), ("9", "DBP", 1), ("10", "TBC", 1), ("11", "DBC", 1),
        ("101", "DBP", 2), ("102", "DBC", 2), ("103", "TBP", 2), ("104", "DBP", 2),
        ("105", "TBP", 2), ("106", "DBC", 2), ("107", "DBC", 2), ("108", "DBC", 2),
        ("109", "TBC", 2), ("110", "DBP", 2), ("111", "TBP", 2), ("112", "TBC", 2),
        ("113", "DBP", 2), ("114", "DBP", 2), ("115", "DBP", 2), ("116", "DBC", 2),
        ("201", "CBP", 3), ("202", "TBC", 3), ("203", "CBP", 3), ("204", "TBP", 3),
        ("205", "DBC", 3), ("206", "DBC", 3), ("207", "TBP", 3), ("208", "CBP", 3),
        ("209", "TBC", 3), ("210", "TBP", 3), ("211", "CBC", 3), ("212", "TBC", 3)
    ]

    rooms_list = [
        Room(room_number=r[0], floor=r[2], category_id=cat_dict[r[1]].id)
        for r in rooms_data
    ]
    db.add_all(rooms_list)

    # Create hotel configuration
    hotel_config = HotelConfiguration(
        id=1,
        deposit_percentage=30.0,
        hotel_name="Grand Hotel PMS",
        default_currency="ARS",
    )
    db.add(hotel_config)
    db.commit()

    return {"status": "seeded", "rooms_created": len(rooms_list), "categories_created": len(categories)}
