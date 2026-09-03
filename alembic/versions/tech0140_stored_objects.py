"""Add tenant-scoped object metadata without deleting legacy file references."""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "tech0140_stored_objects"
down_revision: Union[str, None] = "tech0140_domain_event_outbox_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "stored_objects" in inspector.get_table_names():
        return
    op.create_table(
        "stored_objects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("backend", sa.String(length=20), nullable=False),
        sa.Column("content_type", sa.String(length=160), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_upload"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key", name="uq_stored_objects_object_key"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_stored_objects_hotel_id_id"),
        sa.CheckConstraint("byte_size >= 0", name="ck_stored_objects_byte_size_nonnegative"),
        sa.CheckConstraint("length(sha256_hex) = 64", name="ck_stored_objects_sha256_length"),
        sa.CheckConstraint("status IN ('pending_upload', 'ready', 'failed', 'deleted')", name="ck_stored_objects_status"),
    )
    op.create_index("ix_stored_objects_hotel_status", "stored_objects", ["hotel_id", "status"])
    op.create_index("ix_stored_objects_hotel_purpose", "stored_objects", ["hotel_id", "purpose"])
    if "stored_object_id" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("company_documents")}:
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table("company_documents", recreate="always") as batch:
                batch.add_column(sa.Column("stored_object_id", sa.String(length=36), nullable=True))
                batch.create_foreign_key(
                    "fk_company_documents_stored_object",
                    "stored_objects",
                    ["stored_object_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        else:
            op.add_column("company_documents", sa.Column("stored_object_id", sa.String(length=36), nullable=True))
            op.create_foreign_key(
                "fk_company_documents_stored_object",
                "company_documents",
                "stored_objects",
                ["stored_object_id"],
                ["id"],
                ondelete="SET NULL",
            )
        op.create_index("ix_company_documents_stored_object_id", "company_documents", ["stored_object_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "stored_objects" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "stored_objects" FORCE ROW LEVEL SECURITY')
        op.execute('''CREATE POLICY "tenant_isolation_stored_objects" ON "stored_objects"
            USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
            WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)''')


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "company_documents" in inspector.get_table_names() and "stored_object_id" in {column["name"] for column in inspector.get_columns("company_documents")}:
        if op.get_bind().dialect.name != "sqlite":
            op.drop_constraint("fk_company_documents_stored_object", "company_documents", type_="foreignkey")
            op.drop_index("ix_company_documents_stored_object_id", table_name="company_documents")
            op.drop_column("company_documents", "stored_object_id")
        else:
            op.drop_index("ix_company_documents_stored_object_id", table_name="company_documents")
            with op.batch_alter_table("company_documents", recreate="always") as batch:
                batch.drop_constraint("fk_company_documents_stored_object", type_="foreignkey")
                batch.drop_column("stored_object_id")
    if op.get_bind().dialect.name == "postgresql":
        op.execute('DROP POLICY IF EXISTS "tenant_isolation_stored_objects" ON "stored_objects"')
        op.execute('ALTER TABLE "stored_objects" NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "stored_objects" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_stored_objects_hotel_purpose", table_name="stored_objects")
    op.drop_index("ix_stored_objects_hotel_status", table_name="stored_objects")
    op.drop_table("stored_objects")
