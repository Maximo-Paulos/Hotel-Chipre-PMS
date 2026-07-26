"""Store private transfer-proof bytes separately from searchable metadata."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260724_payment_proof_blobs"
down_revision: Union[str, None] = "20260724_cash_handoff_rotation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded because some production environments already created this
    # table out-of-band via an old startup self-heal pass while
    # alembic_version stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "payment_proof_blobs" not in inspector.get_table_names():
        op.create_table(
            "payment_proof_blobs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("proof_id", sa.Integer(), nullable=False),
            sa.Column("content", sa.LargeBinary(), nullable=False),
            sa.Column("content_type", sa.String(length=80), nullable=False),
            sa.Column("sha256_hex", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("length(content) > 0", name="ck_payment_proof_blobs_content_nonempty"),
            sa.CheckConstraint("length(sha256_hex) = 64", name="ck_payment_proof_blobs_sha256_length"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["proof_id"], ["payment_proofs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("proof_id"),
        )
    payment_proof_blobs_indexes = {ix["name"] for ix in inspector.get_indexes("payment_proof_blobs")} if inspector.has_table("payment_proof_blobs") else set()
    if "ix_payment_proof_blobs_hotel_id" not in payment_proof_blobs_indexes:
        op.create_index("ix_payment_proof_blobs_hotel_id", "payment_proof_blobs", ["hotel_id"], unique=False)
    if "ix_payment_proof_blobs_proof_id" not in payment_proof_blobs_indexes:
        op.create_index("ix_payment_proof_blobs_proof_id", "payment_proof_blobs", ["proof_id"], unique=False)
    if "ix_payment_proof_blobs_hotel_proof" not in payment_proof_blobs_indexes:
        op.create_index(
            "ix_payment_proof_blobs_hotel_proof",
            "payment_proof_blobs",
            ["hotel_id", "proof_id"],
            unique=False,
        )

    if bind.dialect.name == "postgresql":
        # ENABLE/FORCE ROW LEVEL SECURITY are idempotent (safe to re-run);
        # CREATE POLICY is not, so guard it against pg_policies.
        op.execute('ALTER TABLE "payment_proof_blobs" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "payment_proof_blobs" FORCE ROW LEVEL SECURITY')
        policy_exists = bind.execute(sa.text(
            "SELECT 1 FROM pg_policies WHERE tablename = 'payment_proof_blobs' "
            "AND policyname = 'tenant_isolation_payment_proof_blobs'"
        )).first()
        if not policy_exists:
            op.execute('''CREATE POLICY "tenant_isolation_payment_proof_blobs" ON "payment_proof_blobs"
                USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
                WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)''')


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute('DROP POLICY IF EXISTS "tenant_isolation_payment_proof_blobs" ON "payment_proof_blobs"')
        op.execute('ALTER TABLE "payment_proof_blobs" NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "payment_proof_blobs" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_payment_proof_blobs_hotel_proof", table_name="payment_proof_blobs")
    op.drop_index("ix_payment_proof_blobs_proof_id", table_name="payment_proof_blobs")
    op.drop_index("ix_payment_proof_blobs_hotel_id", table_name="payment_proof_blobs")
    op.drop_table("payment_proof_blobs")
