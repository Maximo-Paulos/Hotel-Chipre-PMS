"""Live smoke tests for the optional Mongo, Neo4j, and Cassandra projections.

Each test uses a real local datastore when available and skips independently when
the corresponding driver or service is unavailable. The Cassandra test first
drops the projection keyspace to exercise the bootstrap deadlock regression.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def reset_projection_clients(monkeypatch: pytest.MonkeyPatch):
    """Avoid reusing a client created by another test or stale .env flags."""
    import app.db.cassandra as cassandra_module
    import app.db.mongo as mongo_module
    import app.db.neo4j as neo4j_module
    import app.services.timeseries_projection as timeseries_module

    for name in ("MONGO_ENABLED", "CASSANDRA_ENABLED", "NEO4J_ENABLED"):
        monkeypatch.setenv(name, "false")
    get_settings.cache_clear()
    _close_clients()
    cassandra_module._cassandra_session = None
    mongo_module._mongo_db = None
    neo4j_module._neo4j_driver = None
    timeseries_module._schema_initialized = False
    yield
    _close_clients()
    cassandra_module._cassandra_session = None
    mongo_module._mongo_db = None
    neo4j_module._neo4j_driver = None
    timeseries_module._schema_initialized = False
    get_settings.cache_clear()


def _close_clients() -> None:
    import app.db.cassandra as cassandra_module
    import app.db.mongo as mongo_module
    import app.db.neo4j as neo4j_module

    db = mongo_module._mongo_db
    if db is not None:
        db.client.close()

    session = cassandra_module._cassandra_session
    if session is not None:
        session.shutdown()
        session.cluster.shutdown()

    driver = neo4j_module._neo4j_driver
    if driver is not None:
        driver.close()


def _enable(monkeypatch: pytest.MonkeyPatch, backend: str) -> None:
    monkeypatch.setenv("MONGO_ENABLED", "true" if backend == "mongo" else "false")
    monkeypatch.setenv("CASSANDRA_ENABLED", "true" if backend == "cassandra" else "false")
    monkeypatch.setenv("NEO4J_ENABLED", "true" if backend == "neo4j" else "false")
    get_settings.cache_clear()


def test_mongo_audit_projection_lands_document(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("pymongo")
    _enable(monkeypatch, "mongo")
    monkeypatch.setenv("MONGO_URL", os.getenv("NOSQL_SMOKE_MONGO_URL", "mongodb://127.0.0.1:27017"))
    monkeypatch.setenv("MONGO_DB", os.getenv("NOSQL_SMOKE_MONGO_DB", "hotel_pms_smoke"))
    get_settings.cache_clear()

    from app.db.mongo import get_mongo_db, mongo_healthcheck
    from app.services.audit_projection import project_audit_to_mongo

    health = mongo_healthcheck()
    if not health["connected"]:
        pytest.skip("MongoDB is not reachable")

    marker = str(uuid4())
    db = get_mongo_db()
    assert db is not None
    try:
        project_audit_to_mongo(
            {
                "hotel_id": 990001,
                "action": "integration.nosql_smoke",
                "at": datetime.now(timezone.utc).isoformat(),
                "smoke_id": marker,
            }
        )
        landed = db.audit_logs.find_one({"smoke_id": marker})
        assert landed is not None
        assert landed["action"] == "integration.nosql_smoke"
    finally:
        db.audit_logs.delete_many({"smoke_id": marker})


def test_neo4j_reservation_assignment_lands_nodes(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("neo4j")
    _enable(monkeypatch, "neo4j")
    monkeypatch.setenv("NEO4J_URI", os.getenv("NOSQL_SMOKE_NEO4J_URI", "bolt://127.0.0.1:7687"))
    monkeypatch.setenv("NEO4J_USER", os.getenv("NOSQL_SMOKE_NEO4J_USER", "neo4j"))
    monkeypatch.setenv("NEO4J_PASSWORD", os.getenv("NOSQL_SMOKE_NEO4J_PASSWORD", "neo4j"))
    get_settings.cache_clear()

    from app.db.neo4j import get_neo4j_driver, neo4j_healthcheck
    from app.services.graph_projection import project_reservation_assignment

    health = neo4j_healthcheck()
    if not health["connected"]:
        pytest.skip("Neo4j is not reachable")

    hotel_id = 990002
    reservation_id = 9900021
    room_id = 9900022
    guest_id = 9900023
    driver = get_neo4j_driver()
    assert driver is not None
    try:
        project_reservation_assignment(
            hotel_id=hotel_id,
            reservation_id=reservation_id,
            room_id=room_id,
            guest_id=guest_id,
            status="confirmed",
        )
        with driver.session() as session:
            rows = session.run(
                "MATCH (n) WHERE n.hotel_id = $hotel_id RETURN labels(n) AS labels",
                hotel_id=hotel_id,
            ).data()
        assert len(rows) == 3
        assert {label for row in rows for label in row["labels"]} == {"Reservation", "Room", "Guest"}
    finally:
        with driver.session() as session:
            session.run("MATCH (n) WHERE n.hotel_id = $hotel_id DETACH DELETE n", hotel_id=hotel_id).consume()


def _cassandra_probe():
    pytest.importorskip("cassandra.cluster")
    from cassandra.cluster import Cluster

    hosts = [
        host.strip()
        for host in os.getenv("NOSQL_SMOKE_CASSANDRA_HOSTS", "127.0.0.1").split(",")
        if host.strip()
    ]
    cluster = Cluster(contact_points=hosts, connect_timeout=2, control_connection_timeout=2)
    try:
        session = cluster.connect()
        session.execute("SELECT now() FROM system.local")
        session.shutdown()
        return cluster
    except Exception:
        cluster.shutdown()
        pytest.skip("Cassandra is not reachable")


def test_cassandra_bootstraps_missing_keyspace_and_lands_room_event(monkeypatch: pytest.MonkeyPatch):
    cluster = _cassandra_probe()
    keyspace = os.getenv("NOSQL_SMOKE_CASSANDRA_KEYSPACE", "hotel_pms")
    monkeypatch.setenv("CASSANDRA_HOSTS", os.getenv("NOSQL_SMOKE_CASSANDRA_HOSTS", "127.0.0.1"))
    monkeypatch.setenv("CASSANDRA_KEYSPACE", keyspace)
    _enable(monkeypatch, "cassandra")

    import app.db.cassandra as cassandra_module
    import app.services.timeseries_projection as timeseries_module
    from app.services.timeseries_projection import project_room_state_event

    try:
        cluster.connect().execute(f"DROP KEYSPACE IF EXISTS {keyspace}")
    finally:
        cluster.shutdown()
    cassandra_module._cassandra_session = None
    timeseries_module._schema_initialized = False

    from app.db.cassandra import get_cassandra_session

    session = get_cassandra_session()
    assert session is not None
    assert session.keyspace == keyspace
    occurred_at = datetime.now(timezone.utc).replace(microsecond=0)
    hotel_id = 990003
    room_id = 9900031
    try:
        project_room_state_event(
            hotel_id=hotel_id,
            room_id=room_id,
            event_type="clean",
            occurred_at=occurred_at,
            payload={"source": "integration_smoke"},
        )
        rows = list(
            session.execute(
                "SELECT hotel_id, room_id, event_type FROM room_state_events "
                "WHERE hotel_id = %s AND event_date = %s",
                (hotel_id, occurred_at.date()),
            )
        )
        assert any(row.room_id == room_id and row.event_type == "clean" for row in rows)
    finally:
        try:
            session.execute(
                "DELETE FROM room_state_events WHERE hotel_id = %s AND event_date = %s",
                (hotel_id, occurred_at.date()),
            )
        finally:
            session.shutdown()
            session.cluster.shutdown()
            cassandra_module._cassandra_session = None
