"""
Database engine and session management.
Supports both PostgreSQL (production) and SQLite (testing).
"""
import logging
import time

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from typing import Generator

from app.config import get_settings, is_preview_qa_mode, is_production_mode

LOGGER = logging.getLogger(__name__)
_SLOW_QUERY_START_KEY = "_slow_query_start_times"


def _slow_query_threshold_ms() -> float:
    try:
        return max(float(getattr(get_settings(), "SLOW_QUERY_LOG_MS", 0) or 0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _install_slow_query_listener(engine) -> None:
    """Log slow SQL without echoing bound values or changing normal runs."""

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault(_SLOW_QUERY_START_KEY, []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        starts = conn.info.get(_SLOW_QUERY_START_KEY)
        started = starts.pop() if starts else None
        if started is None:
            return
        threshold_ms = _slow_query_threshold_ms()
        if threshold_ms <= 0:
            return
        duration_ms = (time.perf_counter() - started) * 1000.0
        if duration_ms >= threshold_ms:
            # Deliberately omit ``parameters``: SQL values can contain guest PII.
            LOGGER.warning(
                "slow query duration_ms=%.2f statement=%s",
                duration_ms,
                statement,
            )

    @event.listens_for(engine, "handle_error")
    def _handle_query_error(exception_context):
        # ``after_cursor_execute`` is not called for failed statements; avoid
        # carrying an old start time into the next statement on this connection.
        starts = exception_context.connection.info.get(_SLOW_QUERY_START_KEY)
        if starts:
            starts.pop()


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


@event.listens_for(Session, "after_begin")
def _reapply_tenant_context(session: Session, transaction, connection) -> None:
    """Reapply RLS tenant context lost when a commit ends the transaction.

    ``app.services.tenant_context`` sets PostgreSQL settings with
    ``set_config(..., is_local=true)`` -- transaction-scoped by design, so a
    commit silently clears ``app.hotel_id``/``app.user_id``/
    ``app.master_admin``. Any service that commits mid-request and then
    issues another query on the same session would otherwise run that query
    with no tenant context, which the RLS policies (NULL-comparison) treat
    as fail-closed: zero rows, not a cross-tenant leak, but silently broken.

    This listener fires when a new transaction begins on the session --
    including the implicit one SQLAlchemy autobegins right after a commit --
    and is handed the raw ``Connection`` for that transaction directly.
    That's deliberate: an ``after_commit`` listener would receive only the
    ``Session``, which SQLAlchemy considers to be in a transitional
    "committed" state where ``session.execute()`` raises
    ``InvalidRequestError`` (no new transaction has been opened yet).
    Executing on the ``Connection`` here sidesteps that entirely. It is a
    clean no-op for sessions that never set tenant context (nothing stashed
    on ``session.info``) and for SQLite (tenant_context's own dialect check
    short-circuits there).
    """
    from app.services.tenant_context import reapply_tenant_context_on_connection

    reapply_tenant_context_on_connection(session, connection)


@event.listens_for(Session, "after_commit")
def _publish_realtime_events_after_commit(session: Session) -> None:
    """Publish only after the database accepted the transaction.

    Redis is an invalidation transport, never the source of truth. The
    publisher catches its own failures so an unavailable realtime backend
    cannot make an already-committed hotel operation look unsuccessful.
    """

    # SQLAlchemy emits ``after_commit`` for a SAVEPOINT as well as for the
    # root transaction.  A SAVEPOINT commit is still reversible by the outer
    # rollback, so defer publication until the root commit callback.
    if session.get_nested_transaction() is not None:
        return
    from app.services.domain_events import publish_queued_domain_changes

    publish_queued_domain_changes(session)


@event.listens_for(Session, "after_flush")
def _collect_realtime_events_after_flush(session: Session, flush_context) -> None:
    """Collect model changes while the transaction can still be rolled back."""

    from app.services.domain_events import queue_model_changes

    queue_model_changes(session)


@event.listens_for(Session, "after_rollback")
def _discard_realtime_events_after_rollback(session: Session) -> None:
    """Ensure rolled-back writes never leak to another browser/device."""

    # SQLAlchemy also emits ``after_rollback`` for a failed SAVEPOINT.  The
    # outer transaction may still commit (payment idempotency and other
    # services use nested transactions), so retain its pending signals until
    # the root transaction ends.
    if session.get_nested_transaction() is not None:
        return
    from app.services.domain_events import discard_queued_domain_changes

    discard_queued_domain_changes(session)


@event.listens_for(Session, "after_soft_rollback")
def _discard_realtime_events_after_root_soft_rollback(session: Session, previous_transaction) -> None:
    """Prune a failed SAVEPOINT or clear a completed root rollback."""

    from app.services.domain_events import discard_queued_domain_changes

    if getattr(previous_transaction, "nested", False):
        discard_queued_domain_changes(session, id(previous_transaction))
        return
    if session.in_transaction():
        return
    discard_queued_domain_changes(session)


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
        # PostgreSQL / Supabase: use a bounded, configurable pool suitable for
        # web workers. Defaults are the API budget in TECH-0140 (5 + 2).
        settings = get_settings()
        pool_size = max(1, min(int(getattr(settings, "DB_POOL_SIZE", 5)), 50))
        max_overflow = max(0, min(int(getattr(settings, "DB_MAX_OVERFLOW", 2)), 50))
        pool_timeout = max(float(getattr(settings, "DB_POOL_TIMEOUT_SECONDS", 5.0)), 0.1)
        connect_timeout = max(int(getattr(settings, "DB_CONNECT_TIMEOUT_SECONDS", 5)), 1)
        pool_recycle = max(int(getattr(settings, "DB_POOL_RECYCLE_SECONDS", 1800)), 60)
        engine = create_engine(
            url,
            echo=False,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,   # drop stale connections
            pool_recycle=pool_recycle,
            connect_args={"connect_timeout": connect_timeout},
        )
        statement_timeout_ms = max(int(getattr(settings, "DB_STATEMENT_TIMEOUT_SECONDS", 15) * 1000), 100)

        @event.listens_for(engine, "connect")
        def _set_postgres_statement_timeout(dbapi_connection, connection_record):
            del connection_record
            cursor = dbapi_connection.cursor()
            cursor.execute(f"SET statement_timeout = {statement_timeout_ms}")
            cursor.close()

    _install_slow_query_listener(engine)
    return engine


# Default engine and session factory
_engine = None
_SessionLocal = None


def _render_server_default(column) -> str | None:
    """Return the SQL text of a column's server_default, if it has one.

    Boolean columns frequently carry a SQLite-style "0"/"1" server_default that
    postgres rejects (boolean vs integer). Map those to proper boolean literals
    so the column can be added WITH a default — which also backfills existing
    rows, avoiding NULLs that would break NOT NULL constraints or response
    serialization.
    """
    from sqlalchemy import Boolean

    server_default = column.server_default
    if server_default is None:
        return None
    arg = getattr(server_default, "arg", None)
    if arg is None:
        return None
    try:
        text = getattr(arg, "text", None)
        rendered = text if text is not None else str(arg)
    except Exception:  # pragma: no cover - defensive
        return None
    if isinstance(column.type, Boolean):
        stripped = rendered.strip().strip("'\"").lower()
        if stripped in ("0", "false", "f"):
            return "false"
        if stripped in ("1", "true", "t"):
            return "true"
    return rendered


def _column_fill_value(column):
    """Best concrete default value for a NOT-NULL column, or None if unknown.

    Prefers the model's Python-side ``default=`` (scalar), since many columns
    (e.g. version=0, is_wait_listed=False) carry only that and no
    ``server_default``. Falls back to parsing a scalar ``server_default``,
    mapping SQLite-style boolean "0"/"1" to real booleans. Callable/sequence
    defaults (e.g. timestamps) return None — those columns aren't backfilled.
    """
    from sqlalchemy import Boolean

    default = column.default
    if default is not None and getattr(default, "is_scalar", False):
        return default.arg
    server_default = column.server_default
    if server_default is not None:
        arg = getattr(server_default, "arg", None)
        if arg is not None:
            text = getattr(arg, "text", None)
            raw = (text if text is not None else str(arg)).strip().strip("'\"")
            if isinstance(column.type, Boolean):
                low = raw.lower()
                if low in ("0", "false", "f"):
                    return False
                if low in ("1", "true", "t"):
                    return True
            return raw
    return None


def _backfill_not_null_nulls(engine) -> None:
    """Fill NULLs in NOT-NULL model columns that carry a default.

    A column added in an earlier self-heal pass without a usable default exists
    as NULLable and may hold NULLs. ``ADD COLUMN IF NOT EXISTS`` won't revisit
    it, yet those NULLs break response serialization (the Pydantic schema
    expects a non-null value). This backfills such NULLs with the model default,
    passed as a bound parameter so the driver handles typing/quoting. Idempotent:
    a no-op once filled.
    """
    from sqlalchemy import text as sa_text

    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        try:
            if not insp.has_table(table.name):
                continue
        except Exception:  # pragma: no cover - defensive
            continue
        for col in table.columns:
            if col.nullable:
                continue
            value = _column_fill_value(col)
            if value is None:
                continue
            update = sa_text(
                f'UPDATE "{table.name}" SET "{col.name}" = :v '
                f'WHERE "{col.name}" IS NULL'
            )
            try:
                with engine.begin() as conn:
                    result = conn.execute(update, {"v": value})
                if getattr(result, "rowcount", 0):
                    LOGGER.warning(
                        "schema self-heal: backfilled %s NULLs in %s.%s",
                        result.rowcount, table.name, col.name,
                    )
            except Exception as exc:
                LOGGER.warning(
                    "schema self-heal: could not backfill %s.%s error_type=%s",
                    table.name, col.name, type(exc).__name__,
                )


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
            base_ddl = (
                f'ALTER TABLE "{table.name}" '
                f'ADD COLUMN IF NOT EXISTS "{col.name}" {coltype}'
            )
            default_sql = _render_server_default(col)
            ddl = base_ddl + (f" DEFAULT {default_sql}" if default_sql is not None else "")
            try:
                with engine.begin() as conn:
                    conn.exec_driver_sql(ddl)
                LOGGER.warning(
                    "schema self-heal: added missing column %s.%s",
                    table.name, col.name,
                )
                continue
            except Exception as exc:
                # A SQLite-style default (e.g. "0" for a boolean) can be rejected
                # by postgres as a type mismatch. Adding the column without the
                # default still heals the drift, so retry once without it.
                if default_sql is None:
                    LOGGER.warning(
                        "schema self-heal: could not add %s.%s error_type=%s",
                        table.name, col.name, type(exc).__name__,
                    )
                    continue
            try:
                with engine.begin() as conn:
                    conn.exec_driver_sql(base_ddl)
                LOGGER.warning(
                    "schema self-heal: added missing column %s.%s (without default)",
                    table.name, col.name,
                )
            except Exception as exc:
                LOGGER.warning(
                    "schema self-heal: could not add %s.%s error_type=%s",
                    table.name, col.name, type(exc).__name__,
                )


def init_db(database_url: str | None = None):
    """Initialize the database engine.

    Local development and tests may bootstrap SQLite with ``create_all``. In
    production and isolated preview/QA environments, schema ownership belongs
    exclusively to Alembic and the process must fail closed when migrations
    were not applied before startup.
    """
    global _engine, _SessionLocal
    _engine = get_engine(database_url)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    settings = get_settings()
    managed_schema_runtime = is_production_mode(settings) or is_preview_qa_mode(settings)
    if managed_schema_runtime:
        if _engine.dialect.name != "postgresql":
            raise RuntimeError(
                "Managed environments require PostgreSQL with Alembic migrations; "
                "automatic schema creation is disabled"
            )
        inspector = inspect(_engine)
        if not inspector.has_table("alembic_version"):
            raise RuntimeError(
                "Database schema is not migrated: alembic_version is missing"
            )
        with _engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar_one_or_none()
        if not revision:
            raise RuntimeError(
                "Database schema is not migrated: alembic_version has no revision"
            )
        return _engine

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
        _backfill_not_null_nulls(_engine)
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
