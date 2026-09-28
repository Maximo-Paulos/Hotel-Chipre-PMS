"""Backfill legacy OTA credits and operational role defaults.

This data migration is intentionally separate from the schema expansion. It is
safe to retry: rows already marked with external-payment history are not
reprocessed. Inferred historical credits remain unconfirmed until an operator
reconciles them, and a downgrade refuses to discard that evidence.
"""

from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260927_ota_credit_data"
down_revision: Union[str, None] = "20260927_manual_payments_checkin_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def _has_columns(table_name: str, expected: set[str]) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names() and expected.issubset(
        {column["name"] for column in inspector.get_columns(table_name)}
    )


def _set_global_role_defaults(role: str, permission_codes: tuple[str, ...], allowed: bool) -> None:
    # Update persisted global defaults while preserving hotel-specific overrides.
    if not _has_columns("role_permission_defaults", {"role", "permission_code", "allowed"}):
        return
    statement = sa.text(
        "UPDATE role_permission_defaults SET allowed = :allowed "
        "WHERE role = :role AND permission_code IN :permission_codes"
    ).bindparams(sa.bindparam("permission_codes", expanding=True))
    op.get_bind().execute(
        statement,
        {"allowed": allowed, "role": role, "permission_codes": permission_codes},
    )


def _set_manager_operational_defaults(allowed: bool) -> None:
    _set_global_role_defaults("manager", ("reservation:charge", "cash:operate"), allowed)


def _set_housekeeping_whatsapp_defaults(allowed: bool) -> None:
    _set_global_role_defaults("housekeeping", ("whatsapp:inbox:view", "whatsapp:note:manage"), allowed)


def _backfill_external_ota_credits() -> None:
    required = {
        "id", "hotel_id", "amount_paid", "source_provider_code", "external_id",
        "external_paid_amount", "external_paid_reference", "external_paid_confirmed",
        "external_paid_ever_confirmed", "external_paid_confirmed_by_user_id",
        "external_paid_confirmed_at",
    }
    if not _has_columns("reservations", required):
        return

    connection = op.get_bind()
    has_transaction_ledger = _has_columns(
        "transactions", {"hotel_id", "reservation_id", "amount", "transaction_type", "status"}
    )
    rows = connection.execute(
        sa.text(
            "SELECT id, hotel_id FROM reservations "
            "WHERE (source_provider_code IS NOT NULL OR external_id IS NOT NULL) "
            "AND COALESCE(external_paid_amount, 0) = 0 "
            "AND external_paid_reference IS NULL "
            "AND external_paid_confirmed = FALSE "
            "AND external_paid_ever_confirmed = FALSE "
            "ORDER BY hotel_id, id"
        )
    ).all()

    # Payment processing locks the reservation before inserting/updating its
    # ledger rows. Match that ordering here, then calculate the ledger total in
    # a *subsequent statement* after the lock is acquired. A precomputed batch
    # aggregate can become stale while a payment is committing during a rolling
    # deploy, and overwriting amount_paid with that snapshot would lose the
    # cache update even though the immutable transaction remains intact.
    lock_clause = " FOR UPDATE" if connection.dialect.name in {"postgresql", "mysql"} else ""
    lock_candidate = sa.text(
        "SELECT id, hotel_id, amount_paid FROM reservations "
        "WHERE id = :reservation_id AND hotel_id = :hotel_id "
        "AND (source_provider_code IS NOT NULL OR external_id IS NOT NULL) "
        "AND COALESCE(external_paid_amount, 0) = 0 "
        "AND external_paid_reference IS NULL "
        "AND external_paid_confirmed = FALSE "
        "AND external_paid_ever_confirmed = FALSE" + lock_clause
    )
    completed_for_reservation = sa.text(
        "SELECT SUM(CASE WHEN transaction_type = 'refund' THEN -amount ELSE amount END) "
        "FROM transactions WHERE status = 'completed' "
        "AND hotel_id = :hotel_id AND reservation_id = :reservation_id"
    )
    update_legacy_credit = sa.text(
        "UPDATE reservations SET external_paid_amount = :external_paid_amount, "
        "external_paid_reference = NULL, external_paid_confirmed = FALSE, "
        "external_paid_ever_confirmed = :ever_confirmed, "
        "external_paid_confirmed_by_user_id = NULL, external_paid_confirmed_at = NULL, "
        "amount_paid = :amount_paid WHERE id = :reservation_id AND hotel_id = :hotel_id "
        "AND COALESCE(external_paid_amount, 0) = 0 "
        "AND external_paid_reference IS NULL "
        "AND external_paid_confirmed = FALSE "
        "AND external_paid_ever_confirmed = FALSE"
    ).bindparams(
        sa.bindparam("external_paid_amount", type_=sa.Numeric(12, 2)),
        sa.bindparam("amount_paid", type_=sa.Numeric(12, 2)),
    )
    for reservation_id, hotel_id in rows:
        locked_row = connection.execute(
            lock_candidate,
            {"reservation_id": reservation_id, "hotel_id": hotel_id},
        ).first()
        # Another transaction may have reconciled or confirmed this row while
        # the migration waited for its lock. Recheck the eligibility predicate
        # under the lock and leave such rows untouched.
        if locked_row is None:
            continue

        reservation_id, hotel_id, cached_paid = locked_row
        paid = Decimal(str(cached_paid or 0)).quantize(Decimal("0.01"))
        completed_ledger = Decimal("0.00")
        if has_transaction_ledger:
            completed_amount = connection.execute(
                completed_for_reservation,
                {"hotel_id": hotel_id, "reservation_id": reservation_id},
            ).scalar()
            completed_ledger = Decimal(str(completed_amount or 0)).quantize(Decimal("0.01"))
        external_legacy_credit = max(Decimal("0.00"), paid - completed_ledger).quantize(Decimal("0.01"))
        connection.execute(
            update_legacy_credit,
            {
                "external_paid_amount": external_legacy_credit,
                "ever_confirmed": False,
                "amount_paid": completed_ledger,
                "reservation_id": reservation_id,
                "hotel_id": hotel_id,
            },
        )


def upgrade() -> None:
    _backfill_external_ota_credits()
    _set_manager_operational_defaults(True)
    _set_housekeeping_whatsapp_defaults(False)


def downgrade() -> None:
    if _has_columns("reservations", {"external_paid_amount", "external_paid_reference", "external_paid_ever_confirmed"}):
        has_external_history = op.get_bind().execute(
            sa.text(
                "SELECT 1 FROM reservations WHERE external_paid_amount > 0 "
                "OR external_paid_reference IS NOT NULL "
                "OR external_paid_confirmed = TRUE "
                "OR external_paid_ever_confirmed = TRUE LIMIT 1"
            )
        ).first()
        if has_external_history:
            raise RuntimeError(
                "Refusing downgrade: external OTA payment evidence exists; restore a verified backup instead."
            )

    _set_manager_operational_defaults(False)
    _set_housekeeping_whatsapp_defaults(True)
