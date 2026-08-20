"""
TDD tests for the AuditLog model.

Invariants:
  - AuditLog is hotel-scoped (hotel_id FK with RESTRICT).
  - actor_user_id is nullable (system-triggered actions have no human actor).
  - payload_before / payload_after are raw JSON text — no ORM coercion.
  - Rows are append-only: no update route exists at the model level.
  - The composite index (hotel_id, created_at) supports retention pruning.
  - The composite index (hotel_id, table_name, record_id) supports per-record history.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa

from app.database import Base
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.user import User


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------

def test_audit_log_table_registered():
    assert "audit_logs" in Base.metadata.tables


def test_audit_log_has_required_columns():
    cols = {c.name for c in Base.metadata.tables["audit_logs"].columns}
    required = {
        "id", "hotel_id", "table_name", "record_id", "action",
        "actor_user_id", "payload_before", "payload_after", "created_at",
    }
    assert required.issubset(cols), f"Missing columns: {required - cols}"


def test_audit_log_has_retention_index():
    table = Base.metadata.tables["audit_logs"]
    index_cols = {
        frozenset(idx.columns.keys())
        for idx in table.indexes
    }
    assert frozenset(["hotel_id", "created_at"]) in index_cols, (
        "Missing (hotel_id, created_at) index for retention pruning"
    )


def test_audit_log_has_record_lookup_index():
    table = Base.metadata.tables["audit_logs"]
    index_cols = {
        frozenset(idx.columns.keys())
        for idx in table.indexes
    }
    assert frozenset(["hotel_id", "table_name", "record_id"]) in index_cols, (
        "Missing (hotel_id, table_name, record_id) index for per-record history"
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_audit_log_persists_create_action(db):
    hotel = HotelConfiguration(id=501, hotel_name="Audit Hotel", subscription_active=True)
    user = User(email="admin501@test.com", password_hash="h", role="owner", is_verified=True)
    db.add(hotel)
    db.flush()
    db.add(user)
    db.flush()

    log = AuditLog(
        hotel_id=501,
        table_name="reservations",
        record_id=999,
        action=AuditActionEnum.CREATE,
        actor_user_id=user.id,
        payload_before=None,
        payload_after=json.dumps({"status": "pending", "total": 50_000}),
    )
    db.add(log)
    db.commit()

    saved = db.get(AuditLog, log.id)
    assert saved is not None
    assert saved.hotel_id == 501
    assert saved.table_name == "reservations"
    assert saved.record_id == 999
    assert saved.action == AuditActionEnum.CREATE
    assert saved.actor_user_id == user.id
    assert saved.payload_before is None
    assert json.loads(saved.payload_after)["status"] == "pending"
    assert saved.created_at is not None


def test_audit_log_actor_nullable_for_system_actions(db):
    """System-triggered events (e.g. OTA sync) have no human actor."""
    hotel = HotelConfiguration(id=502, hotel_name="Sys Hotel", subscription_active=True)
    db.add(hotel)
    db.flush()

    log = AuditLog(
        hotel_id=502,
        table_name="ota_sync_jobs",
        record_id=1,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=None,
        payload_before=json.dumps({"status": "pending"}),
        payload_after=json.dumps({"status": "completed"}),
    )
    db.add(log)
    db.commit()

    saved = db.get(AuditLog, log.id)
    assert saved.actor_user_id is None
    assert saved.action == AuditActionEnum.STATUS_CHANGE


def test_audit_log_hotel_delete_is_restricted(db):
    """Deleting a hotel cannot destroy its audit-log evidence."""
    hotel = HotelConfiguration(id=503, hotel_name="Restricted Hotel", subscription_active=True)
    db.add(hotel)
    db.flush()

    for i in range(3):
        db.add(AuditLog(
            hotel_id=503,
            table_name="reservations",
            record_id=i,
            action=AuditActionEnum.UPDATE,
        ))
    db.commit()

    count_before = db.query(AuditLog).filter_by(hotel_id=503).count()
    assert count_before == 3

    db.delete(hotel)
    with pytest.raises(sa.exc.IntegrityError):
        db.commit()
    db.rollback()

    assert db.get(HotelConfiguration, 503) is not None
    count_after = db.query(AuditLog).filter_by(hotel_id=503).count()
    assert count_after == 3


def test_audit_log_all_actions_persist(db):
    """All AuditActionEnum values can be stored."""
    hotel = HotelConfiguration(id=504, hotel_name="Enum Hotel", subscription_active=True)
    db.add(hotel)
    db.flush()

    for action in AuditActionEnum:
        db.add(AuditLog(
            hotel_id=504,
            table_name="rooms",
            record_id=1,
            action=action,
        ))
    db.commit()

    count = db.query(AuditLog).filter_by(hotel_id=504).count()
    assert count == len(AuditActionEnum)


def test_audit_log_created_at_defaults_to_utc_now(db):
    hotel = HotelConfiguration(id=505, hotel_name="TS Hotel", subscription_active=True)
    db.add(hotel)
    db.flush()

    before = datetime.now(timezone.utc)
    log = AuditLog(hotel_id=505, table_name="guests", record_id=7, action=AuditActionEnum.DELETE)
    db.add(log)
    db.commit()
    after = datetime.now(timezone.utc)

    saved = db.get(AuditLog, log.id)
    ts = saved.created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    assert before <= ts <= after


# ---------------------------------------------------------------------------
# Transaction.hotel_id FK
# ---------------------------------------------------------------------------

def test_transaction_hotel_id_has_fk_constraint():
    """Regression: hotel_id on transactions must have a DB-level FK."""
    from app.models.transaction import Transaction
    col = Base.metadata.tables["transactions"].c.hotel_id
    fks = col.foreign_keys
    assert fks, "transactions.hotel_id must have a FK to hotel_configuration.id"
    targets = {fk.target_fullname for fk in fks}
    assert "hotel_configuration.id" in targets


# ---------------------------------------------------------------------------
# Production incident 2026-07-28: a failed audit_logs insert must never
# discard the caller's real, already-flushed change in the same session.
# ---------------------------------------------------------------------------

def test_failed_audit_log_insert_does_not_roll_back_callers_change(db):
    """Reproduces the DELETE /api/stock/items/{id} incident: a stray NOT
    NULL column on audit_logs (left over from old schema drift in
    production, see alembic ebd2db08c7d0) made every audit insert fail. The
    old safe_create_audit_log() called db.rollback() on that failure, which
    -- sharing the same session/transaction as the caller -- also wiped out
    the item's already-flushed soft-delete, so the API returned 204 while
    the item was never actually deleted. Forces the exact same failure mode
    here (an extra NOT NULL column with no default) and asserts the item's
    delete survives the commit regardless.
    """
    from app.models.hotel_config import HotelConfiguration
    from app.services import stock_service

    db.add(HotelConfiguration(id=601, hotel_name="Audit Incident Hotel", subscription_active=True))
    db.flush()
    item = stock_service.create_stock_item(db, hotel_id=601, name="Bolsas", unit="unidad")
    db.commit()

    # Simulate the production schema drift: an extra NOT NULL column with no
    # default that the AuditLog model never populates. audit_logs has zero
    # rows at this point (create_stock_item doesn't audit-log), so SQLite
    # accepts NOT NULL with no DEFAULT here, same as the real stray column.
    db.execute(sa.text("ALTER TABLE audit_logs ADD COLUMN resource_type VARCHAR(100) NOT NULL"))
    db.commit()

    stock_service.delete_stock_item(db, hotel_id=601, item_id=item.id, deleted_by_user_id=None)
    db.commit()

    db.expire_all()
    reloaded = db.get(type(item), item.id)
    assert reloaded.deleted_at is not None, (
        "Item must actually be soft-deleted even though the audit log insert "
        "failed on the stray column -- the audit failure must not roll back "
        "the caller's real change"
    )
