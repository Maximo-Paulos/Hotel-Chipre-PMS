"""Current hotel membership aliases label historical actor projections."""

from datetime import datetime, timezone

from sqlalchemy import event

from app.models.analytics import HotelAuditEvent
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.user import User
from app.services.operational_audit_service import list_operational_audit


def test_operational_audit_resolves_current_alias_in_one_tenant_scoped_batch(db):
    hotel_one = HotelConfiguration(id=61, hotel_name="Audit one", hotel_timezone="UTC")
    hotel_two = HotelConfiguration(id=62, hotel_name="Audit two", hotel_timezone="UTC")
    actor = User(
        email="actor-alias@example.test",
        password_hash="test-hash",
        display_name="Global name should not appear",
        is_active=True,
        is_verified=True,
    )
    db.add_all([hotel_one, hotel_two, actor])
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=61, user_id=actor.id, role="manager", status="active", alias="Night Lead", alias_key="night lead"),
            HotelMembership(hotel_id=62, user_id=actor.id, role="manager", status="active", alias="Other Hotel Alias", alias_key="other hotel alias"),
            HotelAuditEvent(
                hotel_id=61,
                user_id=actor.id,
                action_code="reservation.updated",
                entity_type="reservation",
                entity_id=1,
                created_at=datetime(2026, 9, 17, 10, tzinfo=timezone.utc),
            ),
            HotelAuditEvent(
                hotel_id=61,
                user_id=actor.id,
                action_code="reservation.note_added",
                entity_type="reservation",
                entity_id=2,
                created_at=datetime(2026, 9, 17, 11, tzinfo=timezone.utc),
            ),
            HotelAuditEvent(
                hotel_id=61,
                user_id=None,
                action_code="integration.synced",
                entity_type="reservations",
                entity_id=3,
                created_at=datetime(2026, 9, 17, 12, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()

    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many):
        if "hotel_memberships" in statement.lower() and "users" in statement.lower():
            statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", record_statement)
    try:
        rows, total = list_operational_audit(db, hotel_id=61, limit=20, offset=0)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record_statement)

    assert total == 3
    assert [row["actor_name"] for row in rows if row["actor_user_id"] == actor.id] == ["Night Lead", "Night Lead"]
    assert all(row["actor_user_id"] == actor.id for row in rows if row["actor_name"] == "Night Lead")
    assert next(row for row in rows if row["actor_user_id"] is None)["actor_name"] == "Sistema"
    assert len(statements) == 1

    membership = db.query(HotelMembership).filter_by(hotel_id=61, user_id=actor.id).one()
    membership.alias = "Current Alias"
    membership.alias_key = "current alias"
    db.commit()
    refreshed, _ = list_operational_audit(db, hotel_id=61, limit=20, offset=0)
    assert {row["actor_name"] for row in refreshed if row["actor_user_id"] == actor.id} == {"Current Alias"}


def test_operational_audit_falls_back_to_tenant_actor_email_without_alias(db):
    hotel = HotelConfiguration(id=63, hotel_name="Audit fallback", hotel_timezone="UTC")
    actor = User(
        email="fallback-actor@example.test",
        password_hash="test-hash",
        display_name="Unscoped Apple display name",
        is_active=True,
        is_verified=True,
    )
    db.add_all([hotel, actor])
    db.flush()
    db.add(HotelMembership(hotel_id=63, user_id=actor.id, role="manager", status="active"))
    db.add(
        HotelAuditEvent(
            hotel_id=63,
            user_id=actor.id,
            action_code="reservation.updated",
            entity_type="reservation",
            entity_id=1,
            created_at=datetime(2026, 9, 17, 10, tzinfo=timezone.utc),
        )
    )
    db.commit()

    rows, _ = list_operational_audit(db, hotel_id=63, limit=20, offset=0)

    assert rows[0]["actor_name"] == actor.email
