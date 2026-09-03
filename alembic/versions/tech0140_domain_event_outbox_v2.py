"""Add durable ids, cursor and retry state to the realtime outbox.

The migration is expand/backfill compatible with the v1 publisher. No legacy
columns are removed and recovery can continue to use ``id`` while a mixed
deployment is running.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "tech0140_domain_event_outbox_v2"
down_revision: Union[str, None] = "20260902_ota_lifecycle_enum_lowercase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _event_id_type(dialect: str):
    if dialect == "postgresql":
        return postgresql.UUID(as_uuid=False)
    return sa.String(length=36)


def _install_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    for table in ("domain_event_outbox_retention_watermarks",):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'DROP POLICY IF EXISTS "tenant_isolation_{table}" ON "{table}"'
        )
        op.execute(
            f'''CREATE POLICY "tenant_isolation_{table}"
               ON "{table}"
               USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
               WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
        )


def _remove_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    table = "domain_event_outbox_retention_watermarks"
    op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table}" ON "{table}"')
    op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    columns = {
        "event_id": sa.Column("event_id", _event_id_type(dialect), nullable=True),
        "schema_version": sa.Column("schema_version", sa.Integer(), nullable=True),
        "stream_cursor": sa.Column("stream_cursor", sa.BigInteger(), nullable=True),
        "entity_type": sa.Column("entity_type", sa.String(length=100), nullable=True),
        "resource_id": sa.Column("resource_id", sa.String(length=100), nullable=True),
        "deduplication_key": sa.Column("deduplication_key", sa.String(length=255), nullable=True),
        "status": sa.Column("status", sa.String(length=20), nullable=True),
        "next_attempt_at": sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        "dead_lettered_at": sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        "resolved_at": sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    }
    existing_columns = {column["name"] for column in sa.inspect(connection).get_columns("domain_event_outbox")}
    for name, column in columns.items():
        if name not in existing_columns:
            op.add_column("domain_event_outbox", column)

    rows = connection.execute(
        sa.text("SELECT id, published_at FROM domain_event_outbox ORDER BY id")
    ).mappings().all()
    for row in rows:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"hotel-pms-domain-event:{row['id']}"))
        status = "published" if row["published_at"] is not None else "pending"
        connection.execute(
            sa.text(
                """UPDATE domain_event_outbox
                   SET event_id=:event_id, schema_version=1, stream_cursor=:cursor,
                       deduplication_key=:dedupe, status=:status
                   WHERE id=:id"""
            ),
            {
                "event_id": event_id,
                "cursor": int(row["id"]),
                "dedupe": f"legacy:{row['id']}",
                "status": status,
                "id": int(row["id"]),
            },
        )

    inspector = sa.inspect(connection)
    indexes = {index["name"] for index in inspector.get_indexes("domain_event_outbox")}
    if "uq_domain_event_outbox_event_id" not in indexes:
        op.create_index(
            "uq_domain_event_outbox_event_id",
            "domain_event_outbox",
            ["event_id"],
            unique=True,
        )
    if "uq_domain_event_outbox_hotel_dedupe" not in indexes:
        op.create_index(
            "uq_domain_event_outbox_hotel_dedupe",
            "domain_event_outbox",
            ["hotel_id", "deduplication_key"],
            unique=True,
        )

    if "domain_event_outbox_retention_watermarks" not in inspector.get_table_names():
        op.create_table(
            "domain_event_outbox_retention_watermarks",
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("domain", sa.String(length=50), nullable=False),
            sa.Column("watermark", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("hotel_id", "domain"),
            sa.CheckConstraint("watermark >= 0", name="ck_domain_event_retention_watermark_nonnegative"),
        )
    _install_rls(connection)


def downgrade() -> None:
    connection = op.get_bind()
    _remove_rls(connection)
    if "domain_event_outbox_retention_watermarks" in sa.inspect(connection).get_table_names():
        op.drop_table("domain_event_outbox_retention_watermarks")
    indexes = {index["name"] for index in sa.inspect(connection).get_indexes("domain_event_outbox")}
    for name in ("uq_domain_event_outbox_hotel_dedupe", "uq_domain_event_outbox_event_id"):
        if name in indexes:
            op.drop_index(name, table_name="domain_event_outbox")
    for name in (
        "resolved_at", "dead_lettered_at", "next_attempt_at", "status",
        "deduplication_key", "resource_id", "entity_type", "stream_cursor",
        "schema_version", "event_id",
    ):
        if name in {column["name"] for column in sa.inspect(connection).get_columns("domain_event_outbox")}:
            op.drop_column("domain_event_outbox", name)
