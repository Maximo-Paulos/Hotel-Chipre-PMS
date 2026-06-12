"""
PostgreSQL test configuration.

Usage:
  Set DATABASE_URL_TEST to a PostgreSQL DSN, then run:
    pytest tests/ --db=postgres

This file is NOT loaded by default (SQLite is used for local dev).
For CI or PostgreSQL validation, set env var and use pytest --db=postgres.

Example DSN:
  postgresql+psycopg2://postgres:password@localhost:5432/hotel_chipre_test

How to provision a temporary instance (Docker):
  docker run -d --name pg-test \
    -e POSTGRES_PASSWORD=testpass \
    -e POSTGRES_DB=hotel_chipre_test \
    -p 5432:5432 \
    postgres:16-alpine

Then run:
  DATABASE_URL_TEST=postgresql+psycopg2://postgres:testpass@localhost:5432/hotel_chipre_test \
    pytest tests/ -v
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base


PG_DSN = os.getenv("DATABASE_URL_TEST", "")


@pytest.fixture(scope="session")
def pg_engine():
    """Create PostgreSQL engine — skip all tests if DATABASE_URL_TEST not set."""
    if not PG_DSN or not PG_DSN.startswith("postgresql"):
        pytest.skip("DATABASE_URL_TEST not set to a PostgreSQL DSN — skipping PostgreSQL tests")
    engine = create_engine(PG_DSN, echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def pg_session(pg_engine):
    """PostgreSQL session with rollback isolation per test."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
