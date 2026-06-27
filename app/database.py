"""
Database engine and session management.
Supports both PostgreSQL (production) and SQLite (testing).
"""
import logging

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from typing import Generator

from app.config import get_settings

LOGGER = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def get_engine(database_url: str | None = None):
    """Create a SQLAlchemy engine for SQLite (dev) or PostgreSQL (prod)."""
    url = database_url or get_settings().DATABASE_URL
    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    else:
        # PostgreSQL / Supabase: use a bounded pool suitable for web workers.
        # For serverless (Render free tier, etc.) pool_size=5 prevents exhaustion.
        engine = create_engine(
            url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,   # drop stale connections
            pool_recycle=1800,    # recycle every 30 min
        )

    return engine


# Default engine and session factory
_engine = None
_SessionLocal = None


def _render_server_default(column) -> str | None:
    """Return the SQL text of a column's server_default, if it has one."""
    server_default = column.server_default
    if server_default is None:
        return None
    arg = getattr(server_default, "arg", None)
    if arg is None:
        return None
    try:
        text = getattr(arg, "text", None)
        return text if text is not None else str(arg)
    except Exception:  # pragma: no cover - defensive
        return None


def _sync_missing_columns(engine) -> None:
    """Additively add model columns that are missing from existing tables.

    create_all() only creates missing *tables*; it never ALTERs an existing
    table to add new *columns*. A production DB that predates a model column
    therefore raises ``UndefinedColumn`` at query time (schema drift, since
    deploys here run create_all() rather than Alembic). This patches that drift
    idempotently: it only ADDs columns, never drops or alters existing ones.
    New columns are added NULLable (even when the model marks them NOT NULL) so
    existing rows don't violate the constraint; a server_default is included
    when the model defines one. Each ALTER runs in its own transaction and
    failures are logged, never raised, so a single odd column can't block boot.
    """
    insp = inspect(engine)
    dialect = engine.dialect
    for table in Base.metadata.sorted_tables:
        try:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
        except Exception:  # pragma: no cover - defensive
            continue
        for col in table.columns:
            if col.name in existing:
                continue
            try:
                coltype = col.type.compile(dialect=dialect)
            except Exception:
                LOGGER.warning(
                    "schema self-heal: cannot render type for %s.%s; skipping",
                    table.name, col.name,
                )
                continue
            ddl = (
                f'ALTER TABLE "{table.name}" '
                f'ADD COLUMN IF NOT EXISTS "{col.name}" {coltype}'
            )
            default_sql = _render_server_default(col)
            if default_sql is not None:
                ddl += f" DEFAULT {default_sql}"
            try:
                with engine.begin() as conn:
                    conn.exec_driver_sql(ddl)
                LOGGER.warning(
                    "schema self-heal: added missing column %s.%s",
                    table.name, col.name,
                )
            except Exception as exc:
                LOGGER.warning(
                    "schema self-heal: could not add %s.%s: %s",
                    table.name, col.name, exc,
                )


def init_db(database_url: str | None = None):
    """Initialize the database engine and create all tables."""
    global _engine, _SessionLocal
    _engine = get_engine(database_url)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    # Import models so Base.metadata is fully populated (e.g., CategoryPricing)
    import app.models  # noqa: F401
    # Self-heal: on an existing PostgreSQL DB, create_all() never ALTERs the
    # already-present `reservations` table, so the composite unique key that
    # newer tables (e.g. payment_links) reference via FK may be missing. Add it
    # idempotently before create_all, otherwise creating those tables fails with
    # "no unique constraint matching given keys for referenced table".
    if _engine.dialect.name == "postgresql":
        insp = inspect(_engine)
        if insp.has_table("reservations"):
            with _engine.begin() as conn:
                conn.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_reservation_hotel_id_id "
                    "ON reservations (hotel_id, id)"
                )
    Base.metadata.create_all(bind=_engine)
    # Patch column-level schema drift on existing PostgreSQL tables (create_all
    # only handles missing tables, not missing columns).
    if _engine.dialect.name == "postgresql":
        _sync_missing_columns(_engine)
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
