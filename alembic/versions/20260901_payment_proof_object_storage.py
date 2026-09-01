"""Move payment-proof bytes off Postgres, into object storage.

`payment_proof_blobs.content` (a LargeBinary column) is ephemeral-container-
proof but not redeploy-proof for the container that *reads* it back through
Render/Cloud Run -- more importantly, per plan section 6.2, it bloats the
tenant DB with binary payloads that belong in object storage instead. New
proofs (app.services.payment_proof_service) now upload their bytes via
app.services.object_storage and store only `object_key` + `byte_size` here;
`content` becomes nullable and stays populated only for rows written before
this migration -- no backfill/deletion of that old data happens here (a
separate, explicitly-approved step per the plan).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260901_payment_proof_object_storage"
down_revision: Union[str, None] = "20260901_interface_language"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_CHECK = "ck_payment_proof_blobs_content_nonempty"
_NEW_CHECK = "ck_payment_proof_blobs_content_or_object_key"
_NEW_CHECK_SQL = "(content IS NOT NULL AND length(content) > 0) OR (object_key IS NOT NULL)"


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    existing = _columns("payment_proof_blobs")

    if dialect == "sqlite":
        with op.batch_alter_table("payment_proof_blobs", recreate="always") as batch:
            if "object_key" not in existing:
                batch.add_column(sa.Column("object_key", sa.String(length=255), nullable=True))
            if "byte_size" not in existing:
                batch.add_column(sa.Column("byte_size", sa.Integer(), nullable=True))
            batch.alter_column("content", existing_type=sa.LargeBinary(), nullable=True)
            batch.create_unique_constraint("uq_payment_proof_blobs_object_key", ["object_key"])
            batch.drop_constraint(_OLD_CHECK, type_="check")
            batch.create_check_constraint(_NEW_CHECK, _NEW_CHECK_SQL)
        return

    # PostgreSQL (and any other non-SQLite dialect ALTER TABLE supports directly).
    if "object_key" not in existing:
        op.add_column("payment_proof_blobs", sa.Column("object_key", sa.String(length=255), nullable=True))
    if "byte_size" not in existing:
        op.add_column("payment_proof_blobs", sa.Column("byte_size", sa.Integer(), nullable=True))
    op.alter_column("payment_proof_blobs", "content", existing_type=sa.LargeBinary(), nullable=True)
    op.create_unique_constraint("uq_payment_proof_blobs_object_key", "payment_proof_blobs", ["object_key"])
    op.drop_constraint(_OLD_CHECK, "payment_proof_blobs", type_="check")
    op.create_check_constraint(_NEW_CHECK, "payment_proof_blobs", _NEW_CHECK_SQL)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("payment_proof_blobs", recreate="always") as batch:
            batch.drop_constraint(_NEW_CHECK, type_="check")
            batch.create_check_constraint(_OLD_CHECK, "length(content) > 0")
            batch.drop_constraint("uq_payment_proof_blobs_object_key", type_="unique")
            batch.alter_column("content", existing_type=sa.LargeBinary(), nullable=False)
            batch.drop_column("byte_size")
            batch.drop_column("object_key")
        return

    op.drop_constraint(_NEW_CHECK, "payment_proof_blobs", type_="check")
    op.create_check_constraint(_OLD_CHECK, "payment_proof_blobs", "length(content) > 0")
    op.drop_constraint("uq_payment_proof_blobs_object_key", "payment_proof_blobs", type_="unique")
    op.alter_column("payment_proof_blobs", "content", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_column("payment_proof_blobs", "byte_size")
    op.drop_column("payment_proof_blobs", "object_key")
