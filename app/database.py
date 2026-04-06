"""
Database engine and session management.
Supports both PostgreSQL (production) and SQLite (testing).
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from typing import Generator

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def get_engine(database_url: str | None = None):
    """Create a SQLAlchemy engine.
    
    Args:
        database_url: Optional override URL. Uses settings if not provided.
    """
    url = database_url or get_settings().DATABASE_URL
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, echo=False, connect_args=connect_args)

    # Enable WAL mode and foreign keys for SQLite
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


# Default engine and session factory
_engine = None
_SessionLocal = None


def init_db(database_url: str | None = None):
    """Initialize the database engine and create all tables."""
    global _engine, _SessionLocal
    _engine = get_engine(database_url)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    # Import models so Base.metadata is fully populated (e.g., CategoryPricing)
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=_engine)
    return _engine


def get_session_factory(database_url: str | None = None) -> sessionmaker:
    """Get or create a session factory."""
    global _SessionLocal, _engine
    if _SessionLocal is None:
        init_db(database_url)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a database session."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
