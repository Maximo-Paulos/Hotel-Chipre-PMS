"""
Hotel PMS — FastAPI Main Application.
Serves the API + static frontend files.
"""
import os
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

from app.database import init_db, get_db
from app.api import rooms, guests, reservations, payments, checkin, ota_webhooks, config, reports
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.hotel_config import HotelConfiguration


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on application startup."""
    init_db()
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
app.include_router(rooms.router)
app.include_router(guests.router)
app.include_router(reservations.router)
app.include_router(payments.router)
app.include_router(checkin.router)
app.include_router(ota_webhooks.router)
app.include_router(config.router)
app.include_router(reports.router)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health")
def health_check():
    return {"status": "ok", "system": "Hotel PMS v1.0.0"}


@app.get("/")
def serve_frontend():
    """Serve the main frontend page."""
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.post("/api/reset")
def reset_db(db: Session = Depends(get_db)):
    """Hard reset of development database."""
    from app.database import engine, Base
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db.commit()
    return {"status": "reset", "message": "Database wiped and recreated. Please call /api/seed"}

@app.post("/api/seed")
def seed_database(db: Session = Depends(get_db)):
    """Populate the database with initial hotel data (categories, rooms, config)."""
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
