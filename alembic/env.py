import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure app is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env for local development (no-op if DATABASE_URL already in environment,
# which is the case in Render/production where env vars are injected by the platform)
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)  # override=False: system env vars take precedence
except ImportError:
    pass

from app.database import Base, get_engine  # noqa: E402
import app.models  # noqa: F401,E402
import app.master_admin.models  # noqa: F401,E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return os.environ.get("DATABASE_URL", "sqlite:///./dev.db")


def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Revision IDs in this project exceed the default VARCHAR(32)
        version_table_pk_length=128,
    )

    with context.begin_transaction():
        context.run_migrations()


def _ensure_wide_version_table(engine) -> None:
    """
    Alembic creates alembic_version with version_num VARCHAR(32) by default.
    Some revision IDs in this project exceed 32 chars (e.g. 34-char names).
    Pre-create or widen the column in a SEPARATE committed transaction so
    Alembic's own transaction management is not disturbed.
    """
    from sqlalchemy import text, inspect as sa_inspect
    with engine.begin() as conn:
        inspector = sa_inspect(conn)
        if "alembic_version" in inspector.get_table_names():
            cols = {c["name"]: c for c in inspector.get_columns("alembic_version")}
            col = cols.get("version_num")
            if col is not None:
                length = getattr(col["type"], "length", None)
                if length is not None and length < 128:
                    conn.execute(text(
                        "ALTER TABLE alembic_version "
                        "ALTER COLUMN version_num TYPE VARCHAR(128)"
                    ))
        else:
            conn.execute(text(
                "CREATE TABLE alembic_version ("
                "  version_num VARCHAR(128) NOT NULL, "
                "  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                ")"
            ))
    # engine.begin() auto-commits on clean exit


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Widen alembic_version before Alembic opens its own connection/transaction
    _ensure_wide_version_table(connectable)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
