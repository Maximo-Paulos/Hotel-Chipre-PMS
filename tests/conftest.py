"""
Pytest configuration and fixtures.
Uses an in-memory SQLite database for isolated, fast testing.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest, GuestCompanion
from app.models.reservation import Reservation, ReservationStatusEnum, ReservationSourceEnum
from app.models.transaction import Transaction
from app.models.hotel_config import HotelConfiguration
from app.models.ota import OTAReservationMapping
from app.models.pricing import CategoryPricing


# â”€â”€ SQLite in-memory engine for tests â”€â”€

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite engine for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Ensure all mapped tables (including CategoryPricing) exist for tests
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db(db_engine) -> Session:
    """Provide a transactional database session for each test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# â”€â”€ Seed data fixtures â”€â”€

@pytest.fixture
def sample_categories(db: Session) -> list[RoomCategory]:
    """Create sample room categories."""
    categories = [
        RoomCategory(
            name="Standard Double",
            code="STD_DBL",
            base_price_per_night=100.0,
            max_occupancy=2,
            description="Standard room with double bed",
        ),
        RoomCategory(
            name="Superior Double",
            code="SUP_DBL",
            base_price_per_night=150.0,
            max_occupancy=3,
            description="Superior room with king bed and city view",
        ),
        RoomCategory(
            name="Suite Premium",
            code="SUITE_P",
            base_price_per_night=250.0,
            max_occupancy=4,
            description="Premium suite with living area and balcony",
        ),
    ]
    db.add_all(categories)
    db.flush()
    return categories


@pytest.fixture
def sample_rooms(db: Session, sample_categories: list[RoomCategory]) -> list[Room]:
    """Create the 38-room hotel layout."""
    rooms = []
    cat_std = sample_categories[0]  # STD_DBL
    cat_sup = sample_categories[1]  # SUP_DBL
    cat_suite = sample_categories[2]  # SUITE_P

    # Floor 1: 10 Standard rooms (101-110)
    for i in range(1, 11):
        rooms.append(Room(
            room_number=f"1{i:02d}",
            floor=1,
            category_id=cat_std.id,
            status=RoomStatusEnum.AVAILABLE,
        ))

    # Floor 2: 10 Standard rooms (201-210)
    for i in range(1, 11):
        rooms.append(Room(
            room_number=f"2{i:02d}",
            floor=2,
            category_id=cat_std.id,
            status=RoomStatusEnum.AVAILABLE,
        ))

    # Floor 3: 10 Superior rooms (301-310)
    for i in range(1, 11):
        rooms.append(Room(
            room_number=f"3{i:02d}",
            floor=3,
            category_id=cat_sup.id,
            status=RoomStatusEnum.AVAILABLE,
        ))

    # Floor 4: 5 Superior rooms (401-405) + 3 Suites (406-408)
    for i in range(1, 6):
        rooms.append(Room(
            room_number=f"4{i:02d}",
            floor=4,
            category_id=cat_sup.id,
            status=RoomStatusEnum.AVAILABLE,
        ))
    for i in range(6, 9):
        rooms.append(Room(
            room_number=f"4{i:02d}",
            floor=4,
            category_id=cat_suite.id,
            status=RoomStatusEnum.AVAILABLE,
        ))

    db.add_all(rooms)
    db.flush()
    assert len(rooms) == 38
    return rooms


@pytest.fixture
def sample_guest(db: Session) -> Guest:
    """Create a sample guest with full check-in data."""
    guest = Guest(
        first_name="Carlos",
        last_name="PÃ©rez",
        document_type="DNI",
        document_number="30456789",
        nationality="Argentina",
        email="carlos@email.com",
        phone="+54111234567",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    return guest


@pytest.fixture
def sample_guest_incomplete(db: Session) -> Guest:
    """Create a guest WITHOUT identity documents (for check-in validation tests)."""
    guest = Guest(
        first_name="MarÃ­a",
        last_name="LÃ³pez",
        email="maria@email.com",
        terms_accepted=False,
        # No document_type, no document_number
    )
    db.add(guest)
    db.flush()
    return guest


@pytest.fixture
def hotel_config(db: Session) -> HotelConfiguration:
    """Create default hotel configuration."""
    config = HotelConfiguration(
        id=1,
        deposit_percentage=30.0,
        enable_full_payment=True,
        enable_deposit_payment=True,
        enable_cash=True,
        enable_mercado_pago=True,
        enable_paypal=True,
        enable_credit_card=True,
        enable_debit_card=True,
        require_document_for_checkin=True,
        require_terms_acceptance=True,
    )
    db.add(config)
    db.flush()
    return config
