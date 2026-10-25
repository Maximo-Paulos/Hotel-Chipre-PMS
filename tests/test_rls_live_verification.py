"""Live PostgreSQL RLS behavioral verification.

Unlike tests/test_tenant_rls_contract.py (which only asserts the *text* of the
RLS migration), these tests execute real queries against a real PostgreSQL
server with RLS policies active, proving the isolation/bypass mechanisms in
app/services/tenant_context.py actually work at the database level -- not
just that the migration source code looks right.

Two connection-design requirements make these assertions meaningful instead
of silently proving nothing:

1. Verification queries run as a dedicated NOSUPERUSER/NOBYPASSRLS role, not
   as the DATABASE_URL_TEST role. PostgreSQL superusers and BYPASSRLS roles
   bypass row security unconditionally.
2. Seed data is inserted through a plain, genuinely-committing ORM session,
   not the pg_session fixture. pg_session wraps each test in an outer
   transaction that is always rolled back at teardown (the standard
   test-isolation pattern) -- rows inserted through it are only visible
   within that same connection, never to the separate app_test_role
   connection used for verification. Seeding via the ORM (not raw INSERT
   SQL) also picks up Column(default=...) values that only apply at the
   ORM layer, not as server-side defaults.

Setup (once per local Postgres instance): a NOSUPERUSER NOBYPASSRLS role with
full grants on the public schema, e.g.:
  CREATE ROLE app_test_role WITH LOGIN NOSUPERUSER NOBYPASSRLS;
  GRANT USAGE ON SCHEMA public TO app_test_role;
  GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_test_role;
  GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_test_role;

Run with the same env as tests/test_postgres_validation.py (see that file's
module docstring for the full variable list), plus:
  RLS_TEST_ROLE_DSN=postgresql://app_test_role@<host>:<port>/<database>
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from tests.postgres_test_safety import (
    PostgresTargetSafetyError,
    validate_postgres_test_target,
)

PG_DSN = os.getenv("DATABASE_URL_TEST", "")
IS_PG = PG_DSN.startswith("postgresql")
ROLE_DSN = os.getenv("RLS_TEST_ROLE_DSN", "")


def _target_safety_error() -> str | None:
    if not IS_PG:
        return "PostgreSQL DSN not configured"
    if not ROLE_DSN:
        return "RLS_TEST_ROLE_DSN not configured"
    try:
        validate_postgres_test_target(PG_DSN, os.environ)
    except PostgresTargetSafetyError:
        return "PostgreSQL target is not explicitly proven isolated"
    return None


_PG_TARGET_SAFETY_ERROR = _target_safety_error()
skip_if_no_pg = pytest.mark.skipif(
    _PG_TARGET_SAFETY_ERROR is not None,
    reason=_PG_TARGET_SAFETY_ERROR or "PostgreSQL target is unsafe",
)


def _role_connection():
    return create_engine(ROLE_DSN)


def _seed_engine():
    """A superuser engine whose commits are REAL, visible to other connections.

    See module docstring: pg_session's outer-transaction-rolled-back-at-teardown
    pattern makes it unsuitable for seeding data that a second, independent
    connection (the app_test_role one) needs to actually see.
    """
    safe_dsn = validate_postgres_test_target(PG_DSN, os.environ)
    return create_engine(safe_dsn)


def _seed_session(engine):
    return sessionmaker(bind=engine)()


@skip_if_no_pg
def test_invitation_token_resolves_its_custom_role_under_forced_rls():
    from app.models.hotel_config import HotelConfiguration
    from app.models.hotel_role import HotelRole
    from app.models.invitation import StaffInvitation
    from app.services.invitation_service import find_by_token, issue_invitation
    from app.services.permission_service import get_custom_role

    seed_engine = _seed_engine()
    role_engine = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        hotel_id = 88331
        seed.add(HotelConfiguration(id=hotel_id, hotel_name="RLS invitation capability", subscription_active=True))
        seed.flush()
        custom = HotelRole(
            hotel_id=hotel_id,
            code="cr_rls_invitation",
            name="Turno invitación",
            name_key="turno invitación",
            base_role="housekeeping",
            is_active=True,
        )
        seed.add(custom)
        invitation, raw_token, _reused = issue_invitation(
            seed,
            hotel_id=hotel_id,
            user_id=None,
            email="rls-invitation@example.test",
            role=custom.code,
            inviter_user_id=None,
            inviter_email="owner@example.test",
        )
        seed.commit()

        role_session = _seed_session(role_engine)
        try:
            found = find_by_token(role_session, raw_token)
            assert found is not None
            assert found.id == invitation.id
            assert found.hotel_id == hotel_id
            assert get_custom_role(role_session, hotel_id, custom.code) is not None
            assert role_session.query(HotelRole).filter(HotelRole.hotel_id != hotel_id).count() == 0
        finally:
            role_session.close()
    finally:
        seed.rollback()
        seed.query(StaffInvitation).filter_by(hotel_id=88331).delete(synchronize_session=False)
        seed.query(HotelRole).filter_by(hotel_id=88331).delete(synchronize_session=False)
        seed.query(HotelConfiguration).filter_by(id=88331).delete(synchronize_session=False)
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role_engine.dispose()


@skip_if_no_pg
def test_tenant_isolation_blocks_cross_hotel_reads():
    """With app.hotel_id set to hotel A, hotel B's rows are invisible -- as the
    unprivileged application role, not as a superuser (which always bypasses RLS)."""
    from app.models.hotel_config import HotelConfiguration
    from app.models.guest import Guest

    seed_engine = _seed_engine()
    role = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add_all([
            HotelConfiguration(id=88001, hotel_name="RLS-A", subscription_active=True),
            HotelConfiguration(id=88002, hotel_name="RLS-B", subscription_active=True),
        ])
        seed.flush()
        seed.add_all([
            Guest(hotel_id=88001, first_name="Alice", last_name="A",
                  document_type="DNI", document_number="88001001", terms_accepted=True),
            Guest(hotel_id=88002, first_name="Bob", last_name="B",
                  document_type="DNI", document_number="88002001", terms_accepted=True),
        ])
        seed.commit()

        with role.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.hotel_id = '88001'"))
                visible = conn.execute(
                    text("SELECT hotel_id, first_name FROM guests WHERE hotel_id IN (88001, 88002)")
                ).fetchall()
                assert visible == [(88001, "Alice")], f"Expected only hotel A's guest, saw: {visible}"

        with role.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.hotel_id = '88002'"))
                visible = conn.execute(
                    text("SELECT hotel_id, first_name FROM guests WHERE hotel_id IN (88001, 88002)")
                ).fetchall()
                assert visible == [(88002, "Bob")], f"Expected only hotel B's guest, saw: {visible}"
    finally:
        seed.rollback()
        seed.execute(text("DELETE FROM guests WHERE hotel_id IN (88001, 88002)"))
        seed.execute(text("DELETE FROM hotel_configuration WHERE id IN (88001, 88002)"))
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role.dispose()


@skip_if_no_pg
def test_payment_corrections_enforce_tenant_rls_for_read_and_write():
    """Correction history is isolated for a real NOSUPERUSER/NOBYPASSRLS role."""
    from datetime import date

    from app.models.guest import Guest
    from app.models.hotel_config import HotelConfiguration
    from app.models.payment_correction import PaymentCorrection
    from app.models.reservation import Reservation, ReservationStatusEnum
    from app.models.room import RoomCategory
    from app.models.transaction import (
        PaymentMethodEnum,
        Transaction,
        TransactionStatusEnum,
        TransactionTypeEnum,
    )

    hotel_ids = (88421, 88422)
    seed_engine = _seed_engine()
    role = _role_connection()
    seed = _seed_session(seed_engine)
    seeded = False
    try:
        if seed.query(HotelConfiguration.id).filter(HotelConfiguration.id.in_(hotel_ids)).first():
            pytest.skip("Synthetic payment-correction RLS hotel IDs are already in use")

        reservations = {}
        transactions = {}
        seed.add_all(
            [
                HotelConfiguration(id=hotel_id, hotel_name=f"RLS-Payment-{hotel_id}", subscription_active=True)
                for hotel_id in hotel_ids
            ]
        )
        seed.flush()

        for hotel_id in hotel_ids:
            guest = Guest(
                hotel_id=hotel_id,
                first_name="Synthetic",
                last_name="RLS Guest",
                terms_accepted=True,
            )
            category = RoomCategory(
                hotel_id=hotel_id,
                name=f"RLS Payment Category {hotel_id}",
                code=f"RLS-PC-{hotel_id}",
                base_price_per_night=100,
                max_occupancy=2,
            )
            seed.add_all([guest, category])
            seed.flush()
            reservation = Reservation(
                hotel_id=hotel_id,
                confirmation_code=f"RLS-PC-{hotel_id}",
                guest_id=guest.id,
                category_id=category.id,
                check_in_date=date(2030, 6, 1),
                check_out_date=date(2030, 6, 2),
                total_amount=100,
                amount_paid=10,
                deposit_amount=10,
                currency_code="ARS",
                status=ReservationStatusEnum.PENDING,
            )
            seed.add(reservation)
            seed.flush()
            reservations[hotel_id] = reservation

            tx_count = 2 if hotel_id == hotel_ids[1] else 1
            for index in range(tx_count):
                transaction = Transaction(
                    hotel_id=hotel_id,
                    reservation_id=reservation.id,
                    amount=10,
                    currency="ARS",
                    tender_amount=10,
                    tender_currency="ARS",
                    gross_amount=10,
                    net_amount=10,
                    transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
                    payment_method=PaymentMethodEnum.BANK_TRANSFER,
                    status=TransactionStatusEnum.COMPLETED,
                )
                seed.add(transaction)
                seed.flush()
                transactions[(hotel_id, index)] = transaction

            correction = PaymentCorrection(
                hotel_id=hotel_id,
                source_transaction_id=transactions[(hotel_id, 0)].id,
                source_reservation_id=reservation.id,
                correction_type="duplicate_reversal",
                reason="Synthetic tenant isolation verification",
                idempotency_key=f"rls-payment-correction-{hotel_id}",
            )
            seed.add(correction)
        seed.commit()
        seeded = True

        with role.connect() as conn, conn.begin():
            role_flags = conn.execute(
                text(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = current_user"
                )
            ).first()
            assert role_flags == (False, False)
            conn.execute(
                text("SELECT set_config('app.hotel_id', :hotel_id, true)"),
                {"hotel_id": str(hotel_ids[0])},
            )
            visible = conn.execute(
                text(
                    "SELECT hotel_id, source_transaction_id FROM payment_corrections "
                    "WHERE hotel_id IN (:hotel_a, :hotel_b) ORDER BY hotel_id"
                ),
                {"hotel_a": hotel_ids[0], "hotel_b": hotel_ids[1]},
            ).fetchall()
            assert visible == [(hotel_ids[0], transactions[(hotel_ids[0], 0)].id)]

        with role.connect() as conn, conn.begin():
            hidden_without_context = conn.execute(
                text("SELECT hotel_id FROM payment_corrections WHERE hotel_id IN (:a, :b)"),
                {"a": hotel_ids[0], "b": hotel_ids[1]},
            ).fetchall()
            assert hidden_without_context == []

        # All referenced rows exist in hotel B. A tenant A session must still
        # be unable to insert a correction whose hotel_id points at B.
        with pytest.raises(DBAPIError), role.begin() as conn:
            conn.execute(
                text("SELECT set_config('app.hotel_id', :hotel_id, true)"),
                {"hotel_id": str(hotel_ids[0])},
            )
            conn.execute(
                text(
                    "INSERT INTO payment_corrections "
                    "(hotel_id, source_transaction_id, source_reservation_id, correction_type, "
                    "reason, idempotency_key, created_at) "
                    "VALUES (:hotel_id, :transaction_id, :reservation_id, 'duplicate_reversal', "
                    "'Cross-tenant write probe', 'rls-cross-tenant-insert', NOW())"
                ),
                {
                    "hotel_id": hotel_ids[1],
                    "transaction_id": transactions[(hotel_ids[1], 1)].id,
                    "reservation_id": reservations[hotel_ids[1]].id,
                },
            )
    finally:
        seed.rollback()
        if seeded:
            for model in (PaymentCorrection, Transaction, Reservation, Guest, RoomCategory):
                seed.query(model).filter(model.hotel_id.in_(hotel_ids)).delete(synchronize_session=False)
            seed.query(HotelConfiguration).filter(HotelConfiguration.id.in_(hotel_ids)).delete(
                synchronize_session=False
            )
            seed.commit()
        seed.close()
        seed_engine.dispose()
        role.dispose()


@skip_if_no_pg
def test_no_tenant_context_hides_all_rows():
    """Without app.hotel_id set at all, RLS default-denies -- zero rows, not a leak."""
    from app.models.hotel_config import HotelConfiguration
    from app.models.guest import Guest

    seed_engine = _seed_engine()
    role = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add(HotelConfiguration(id=88003, hotel_name="RLS-NoCtx", subscription_active=True))
        seed.flush()
        seed.add(Guest(hotel_id=88003, first_name="Carol", last_name="C",
                        document_type="DNI", document_number="88003001", terms_accepted=True))
        seed.commit()

        with role.connect() as conn:
            with conn.begin():
                visible = conn.execute(text("SELECT hotel_id FROM guests WHERE hotel_id = 88003")).fetchall()
                assert visible == [], f"Expected zero rows with no tenant context set, saw: {visible}"
    finally:
        seed.rollback()
        seed.execute(text("DELETE FROM guests WHERE hotel_id = 88003"))
        seed.execute(text("DELETE FROM hotel_configuration WHERE id = 88003"))
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role.dispose()


@skip_if_no_pg
def test_master_admin_bypass_sees_all_hotels_subscriptions():
    """C2: with app.master_admin='true', subscriptions across hotels are visible.

    Without it, even a hotel-scoped context only sees its own hotel's row --
    proving the bypass is additive (opt-in), not a blanket disable of RLS.
    """
    from app.models.hotel_config import HotelConfiguration
    from app.models.subscription_v2 import Subscription

    seed_engine = _seed_engine()
    role = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add_all([
            HotelConfiguration(id=88101, hotel_name="MA-A", subscription_active=True),
            HotelConfiguration(id=88102, hotel_name="MA-B", subscription_active=True),
        ])
        seed.flush()
        seed.add_all([
            Subscription(hotel_id=88101, plan="starter", status="active"),
            Subscription(hotel_id=88102, plan="pro", status="active"),
        ])
        seed.commit()

        with role.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.hotel_id = '88101'"))
                scoped = conn.execute(
                    text("SELECT hotel_id FROM subscriptions WHERE hotel_id IN (88101, 88102)")
                ).fetchall()
                assert scoped == [(88101,)], f"Expected only the scoped hotel without master_admin, saw: {scoped}"

        with role.connect() as conn:
            with conn.begin():
                conn.execute(text("SET LOCAL app.hotel_id = '88101'"))
                conn.execute(text("SET LOCAL app.master_admin = 'true'"))
                all_visible = conn.execute(
                    text("SELECT hotel_id FROM subscriptions WHERE hotel_id IN (88101, 88102) ORDER BY hotel_id")
                ).fetchall()
                assert all_visible == [(88101,), (88102,)], (
                    f"Expected both hotels visible with master_admin bypass, saw: {all_visible}"
                )
    finally:
        seed.rollback()
        seed.execute(text("DELETE FROM subscriptions WHERE hotel_id IN (88101, 88102)"))
        seed.execute(text("DELETE FROM hotel_configuration WHERE id IN (88101, 88102)"))
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role.dispose()


@skip_if_no_pg
def test_after_commit_listener_reapplies_hotel_context():
    """C1: app.hotel_id must survive a commit within the same ORM session.

    Uses the real app session factory bound to the unprivileged role (so RLS
    is actually enforced) to prove the after_commit listener registered on
    the Session class in app/database.py genuinely reapplies lost context.
    """
    from app.models.hotel_config import HotelConfiguration
    from app.models.guest import Guest
    from app.services.tenant_context import set_tenant_hotel_context

    seed_engine = _seed_engine()
    role = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add(HotelConfiguration(id=88201, hotel_name="AfterCommit", subscription_active=True))
        seed.commit()

        RoleSession = sessionmaker(bind=role, expire_on_commit=False)
        session = RoleSession()
        try:
            set_tenant_hotel_context(session, 88201)
            session.add(Guest(hotel_id=88201, first_name="Dana", last_name="D",
                               document_type="DNI", document_number="88201001", terms_accepted=True))
            session.commit()  # Postgres SET LOCAL is transaction-scoped; this clears it server-side

            # If the after_commit listener didn't reapply app.hotel_id, this query
            # runs with no tenant context and RLS default-denies -- zero rows.
            visible = session.execute(
                text("SELECT first_name FROM guests WHERE hotel_id = 88201")
            ).fetchall()
            assert visible == [("Dana",)], (
                f"Expected the guest to still be visible after commit (listener should "
                f"have reapplied app.hotel_id), saw: {visible}"
            )
        finally:
            session.close()
    finally:
        seed.rollback()
        seed.execute(text("DELETE FROM guests WHERE hotel_id = 88201"))
        seed.execute(text("DELETE FROM hotel_configuration WHERE id = 88201"))
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role.dispose()


@skip_if_no_pg
def test_ota_webhook_credential_lookup_sets_tenant_context_under_rls():
    """The public OTA callback resolves its credential through forced RLS."""
    from app.models.hotel_config import HotelConfiguration
    from app.models.ota import OTAWebhookCredential
    from app.services.ota_service import OTAIntegrationService

    hotel_id = 88431
    raw_secret = "synthetic-ota-webhook-secret"
    seed_engine = _seed_engine()
    role_engine = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add(HotelConfiguration(id=hotel_id, hotel_name="RLS OTA callback", subscription_active=True))
        seed.flush()
        seed.add(
            OTAWebhookCredential(
                hotel_id=hotel_id,
                provider="booking",
                webhook_secret_hash=OTAIntegrationService._hash_secret(raw_secret),
                is_active=True,
            )
        )
        seed.commit()

        role_session = _seed_session(role_engine)
        try:
            assert role_session.query(OTAWebhookCredential).filter_by(hotel_id=hotel_id).first() is None
            credential = OTAIntegrationService._resolve_webhook_credential(
                role_session, hotel_id, "booking", raw_secret, {"hotel_id": hotel_id}
            )
            assert credential.hotel_id == hotel_id
        finally:
            role_session.close()
    finally:
        seed.query(OTAWebhookCredential).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        seed.query(HotelConfiguration).filter_by(id=hotel_id).delete(synchronize_session=False)
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role_engine.dispose()


@skip_if_no_pg
def test_payment_link_test_callback_updates_only_its_tenant_under_rls(monkeypatch):
    """The signed payment-test callback queries and updates its tenant row."""
    from app.models.hotel_config import HotelConfiguration
    from app.models.payment_link_test import PaymentLinkTest
    from app.services import payment_link_test_service
    from app.services.payment_link_test_service import PaymentLinkTestError

    hotel_id = 88432
    other_hotel_id = 88433
    external_reference = f"mp-test-{hotel_id}-0123456789abcdef01"
    monkeypatch.setattr(payment_link_test_service, "require_inbound_provider_events", lambda _provider: None)
    seed_engine = _seed_engine()
    role_engine = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add_all(
            [
                HotelConfiguration(id=hotel_id, hotel_name="RLS MP test callback", subscription_active=True),
                HotelConfiguration(id=other_hotel_id, hotel_name="RLS other hotel", subscription_active=True),
            ]
        )
        seed.flush()
        seed.add(
            PaymentLinkTest(
                hotel_id=hotel_id,
                provider="mercadopago",
                recipient_email="synthetic@example.test",
                amount=42.0,
                currency="ARS",
                description="Synthetic RLS test",
                external_reference=external_reference,
                status="pending",
            )
        )
        seed.commit()

        role_session = _seed_session(role_engine)
        try:
            assert role_session.query(PaymentLinkTest).filter_by(external_reference=external_reference).first() is None
            with pytest.raises(PaymentLinkTestError, match="no coincide con el hotel"):
                payment_link_test_service.refresh_mercadopago_payment_link_test_by_reference(
                    role_session,
                    external_reference,
                    hotel_id=other_hotel_id,
                    external_payment_id="synthetic-payment-88432",
                    payment_fetcher=lambda _db, _hotel_id, _payment_id: {},
                )

            record = payment_link_test_service.refresh_mercadopago_payment_link_test_by_reference(
                role_session,
                external_reference,
                hotel_id=hotel_id,
                external_payment_id="synthetic-payment-88432",
                payment_fetcher=lambda _db, scoped_hotel_id, payment_id: {
                    "id": payment_id,
                    "external_reference": external_reference,
                    "status": "approved",
                    "transaction_amount": 42.0,
                    "currency_id": "ARS",
                },
            )
            assert record is not None
            assert record.hotel_id == hotel_id
            assert record.status == "approved"
            role_session.commit()
        finally:
            role_session.close()
    finally:
        seed.query(PaymentLinkTest).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        seed.query(HotelConfiguration).filter(HotelConfiguration.id.in_([hotel_id, other_hotel_id])).delete(
            synchronize_session=False
        )
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role_engine.dispose()


@skip_if_no_pg
def test_payment_webhook_ingest_resolves_existing_event_under_forced_rls(monkeypatch):
    """The transactional provider callback must bind hotel context before its event lookup."""
    from datetime import date
    from decimal import Decimal

    from app.models.guest import Guest
    from app.models.hotel_config import HotelConfiguration
    from app.models.payment import Payment, PaymentWebhookEvent
    from app.models.reservation import Reservation, ReservationStatusEnum
    from app.models.room import RoomCategory
    from app.services import payment_webhook_service

    hotel_id = 88434
    webhook_id = "synthetic-existing-webhook-88434"
    monkeypatch.setattr(payment_webhook_service, "require_inbound_provider_events", lambda _provider: None)
    seed_engine = _seed_engine()
    role_engine = _role_connection()
    seed = _seed_session(seed_engine)
    try:
        seed.add(HotelConfiguration(id=hotel_id, hotel_name="RLS MP webhook", subscription_active=True))
        seed.flush()
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Webhook")
        category = RoomCategory(
            hotel_id=hotel_id,
            name="RLS webhook room",
            code="RLSMP88434",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        seed.add_all([guest, category])
        seed.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code="RLS-MP-88434",
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 10, 22),
            check_out_date=date(2026, 10, 23),
            total_amount=Decimal("100.00"),
            deposit_amount=Decimal("0.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
        )
        seed.add(reservation)
        seed.flush()
        payment = Payment(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            amount=Decimal("100.00"),
            currency="ARS",
            provider="mercado_pago",
            status="pending",
            external_payment_id="synthetic-payment-88434",
        )
        seed.add(payment)
        seed.flush()
        event = PaymentWebhookEvent(
            hotel_id=hotel_id,
            payment_id=payment.id,
            provider="mercado_pago",
            webhook_id=webhook_id,
            event_type="payment.updated",
            raw_payload={"synthetic": True},
        )
        seed.add(event)
        seed.commit()

        role_session = _seed_session(role_engine)
        try:
            assert (
                role_session.query(PaymentWebhookEvent)
                .filter_by(hotel_id=hotel_id, provider="mercado_pago", webhook_id=webhook_id)
                .first()
                is None
            )
            result = payment_webhook_service.ingest_webhook(
                role_session,
                hotel_id=hotel_id,
                provider="mercadopago",
                webhook_id=webhook_id,
                payload={},
            )
            assert result == {
                "status": "ignored",
                "duplicate": True,
                "event_id": event.id,
                "payment_id": payment.id,
            }
        finally:
            role_session.close()
    finally:
        seed.rollback()
        seed.query(PaymentWebhookEvent).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        seed.query(Payment).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        seed.query(Reservation).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        seed.query(Guest).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        seed.query(RoomCategory).filter_by(hotel_id=hotel_id).delete(synchronize_session=False)
        seed.query(HotelConfiguration).filter_by(id=hotel_id).delete(synchronize_session=False)
        seed.commit()
        seed.close()
        seed_engine.dispose()
        role_engine.dispose()
