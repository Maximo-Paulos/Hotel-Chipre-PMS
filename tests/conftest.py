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
    """Create sample room categories for hotel 1."""
    # Ensure hotel configuration exists for FK integrity
    if not db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first():
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
            subscription_active=True,
        )
        db.add(config)
        db.flush()

    categories = [
        RoomCategory(
            name="Standard Double",
            code="STD_DBL",
            base_price_per_night=100.0,
            max_occupancy=2,
            description="Standard room with double bed",
            hotel_id=1,
        ),
        RoomCategory(
            name="Superior Double",
            code="SUP_DBL",
            base_price_per_night=150.0,
            max_occupancy=3,
            description="Superior room with king bed and city view",
            hotel_id=1,
        ),
        RoomCategory(
            name="Suite Premium",
            code="SUITE_P",
            base_price_per_night=250.0,
            max_occupancy=4,
            description="Premium suite with living area and balcony",
            hotel_id=1,
        ),
    ]
    db.add_all(categories)
    db.flush()
    return categories


@pytest.fixture
def sample_categories_hotel2(db: Session) -> list[RoomCategory]:
    """Minimal categories for a second hotel to verify isolation."""
    if not db.query(HotelConfiguration).filter(HotelConfiguration.id == 2).first():
        db.add(HotelConfiguration(id=2, deposit_percentage=20.0, subscription_active=True))
        db.flush()

    cats = [
        RoomCategory(
            name="Standard H2",
            code="STD_H2",
            base_price_per_night=80.0,
            max_occupancy=2,
            description="Standard room hotel 2",
            hotel_id=2,
        ),
        RoomCategory(
            name="Suite H2",
            code="STE_H2",
            base_price_per_night=180.0,
            max_occupancy=4,
            description="Suite hotel 2",
            hotel_id=2,
        ),
    ]
    db.add_all(cats)
    db.flush()
    return cats


@pytest.fixture
def sample_rooms(db: Session, sample_categories: list[RoomCategory]) -> list[Room]:
    """Create the 38-room hotel layout for hotel 1."""
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
            hotel_id=1,
        ))

    # Floor 2: 10 Standard rooms (201-210)
    for i in range(1, 11):
        rooms.append(Room(
            room_number=f"2{i:02d}",
            floor=2,
            category_id=cat_std.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        ))

    # Floor 3: 10 Superior rooms (301-310)
    for i in range(1, 11):
        rooms.append(Room(
            room_number=f"3{i:02d}",
            floor=3,
            category_id=cat_sup.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        ))

    # Floor 4: 5 Superior rooms (401-405) + 3 Suites (406-408)
    for i in range(1, 6):
        rooms.append(Room(
            room_number=f"4{i:02d}",
            floor=4,
            category_id=cat_sup.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        ))
    for i in range(6, 9):
        rooms.append(Room(
            room_number=f"4{i:02d}",
            floor=4,
            category_id=cat_suite.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        ))

    db.add_all(rooms)
    db.flush()
    assert len(rooms) == 38
    return rooms


@pytest.fixture
def sample_rooms_hotel2(db: Session, sample_categories_hotel2: list[RoomCategory]) -> list[Room]:
    """Create a small room layout for hotel 2 to test multi-hotel isolation."""
    rooms = [
        Room(room_number="201", floor=2, category_id=sample_categories_hotel2[0].id, status=RoomStatusEnum.AVAILABLE, hotel_id=2),
        Room(room_number="202", floor=2, category_id=sample_categories_hotel2[1].id, status=RoomStatusEnum.AVAILABLE, hotel_id=2),
    ]
    db.add_all(rooms)
    db.flush()
    return rooms


@pytest.fixture
def sample_guest(db: Session) -> Guest:
    """Create a sample guest with full check-in data."""
    if not db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first():
        db.add(HotelConfiguration(id=1, subscription_active=True))
        db.flush()
    guest = Guest(
        first_name="Carlos",
        last_name="Pérez",
        document_type="DNI",
        document_number="30456789",
        nationality="Argentina",
        email="carlos@email.com",
        phone="+54111234567",
        terms_accepted=True,
        hotel_id=1,
    )
    db.add(guest)
    db.flush()
    return guest


@pytest.fixture
def sample_guest_incomplete(db: Session) -> Guest:
    """Create a guest WITHOUT identity documents (for check-in validation tests)."""
    if not db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first():
        db.add(HotelConfiguration(id=1, subscription_active=True))
        db.flush()
    guest = Guest(
        first_name="María",
        last_name="López",
        email="maria@email.com",
        terms_accepted=False,
        hotel_id=1,
        # No document_type, no document_number
    )
    db.add(guest)
    db.flush()
    return guest


@pytest.fixture
def hotel_config(db: Session) -> HotelConfiguration:
    """Create default hotel configuration."""
    existing = db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first()
    if existing:
        # Normalize to expected test defaults
        existing.deposit_percentage = 30.0
        existing.enable_full_payment = True
        existing.enable_deposit_payment = True
        existing.enable_cash = True
        existing.enable_mercado_pago = True
        existing.enable_paypal = True
        existing.enable_credit_card = True
        existing.enable_debit_card = True
        existing.require_document_for_checkin = True
        existing.require_terms_acceptance = True
        existing.subscription_active = True
        db.flush()
        return existing

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
        subscription_active=True,
    )
    db.add(config)
    db.flush()
    return config
