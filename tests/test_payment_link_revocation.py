"""Deterministic coverage for best-effort Mercado Pago preference revocation."""
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
import requests
from sqlalchemy import text

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.notification import NotificationOutbox, NotificationPreference
from app.models.payment import PaymentLink
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.models.user import User
from app.services import payment_link_service
from app.services.payment_link_service import (
    cancel_active_links_for_reservation,
    cancel_link,
    process_payment_link_revocations,
)

_PREFERENCE_ID = "pref-test"
_ACCOUNT_ID = "acct-test"


@pytest.fixture(autouse=True)
def _enable_provider_revocation_calls(monkeypatch):
    monkeypatch.setattr(payment_link_service, "external_connections_enabled", lambda: True)


class _GatewayResponse:
    status_code = 200
    ok = True
    content = b"{}"

    def __init__(self, body):
        self._body = dict(body)

    def json(self):
        return dict(self._body)


def _preference_identity(link: PaymentLink, *, expired: bool) -> dict[str, object]:
    return {
        "id": _PREFERENCE_ID,
        "external_reference": link.external_reference,
        "collector_id": _ACCOUNT_ID,
        "preference_expired": expired,
    }


def _mock_revocation_http(monkeypatch, response_bodies):
    """Replace requests at the adapter boundary; never permit a real request."""
    from app.services import payment_link_test_service

    calls = []
    remaining = iter(response_bodies)
    credential_session = None

    def connection_payload(db, *_args, **kwargs):
        nonlocal credential_session
        credential_session = db
        assert kwargs.get("seed_catalog_entries") is False
        db.execute(text("SELECT 1"))
        assert db.in_transaction()
        return {"access_token": "synthetic-test-token", "user_id": _ACCOUNT_ID}

    def response_for(method, url, **kwargs):
        if credential_session is not None:
            assert not credential_session.in_transaction(), (
                "Mercado Pago HTTP must run after the credential-read transaction closes"
            )
        calls.append((method, url, kwargs))
        try:
            body = next(remaining)
        except StopIteration:
            pytest.fail(f"unexpected extra {method} request to provider")
        return _GatewayResponse(body)

    monkeypatch.setattr(
        payment_link_service, "require_external_connections", lambda *_args: None
    )
    monkeypatch.setattr(
        payment_link_test_service,
        "_mercadopago_connection_payload",
        connection_payload,
    )
    monkeypatch.setattr(requests, "get", lambda url, **kwargs: response_for("GET", url, **kwargs))
    monkeypatch.setattr(requests, "put", lambda url, **kwargs: response_for("PUT", url, **kwargs))
    monkeypatch.setattr(
        requests,
        "post",
        lambda *_args, **_kwargs: pytest.fail("revocation must not create a new preference"),
    )
    return calls


def _reservation(db, hotel_id: int, suffix: str) -> Reservation:
    if db.get(HotelConfiguration, hotel_id) is None:
        db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
        db.flush()

    guest = Guest(
        hotel_id=hotel_id,
        first_name="QA",
        last_name="Guest",
        email=f"revocation-{hotel_id}-{suffix}@example.test",
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Revocation {suffix}",
        code=f"REV-{hotel_id}-{suffix}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"REV-{hotel_id}-{suffix}",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 11, 1),
        check_out_date=date(2026, 11, 3),
        total_amount=Decimal("200.00"),
        deposit_amount=Decimal("60.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _link(
    db,
    reservation: Reservation,
    code: str,
    *,
    provider: str = "mercado_pago",
    execution_mode: str = "provider",
    payable: bool = True,
    preference_id: str | None = "pref-test",
    status: str = "pending",
    collected_amount: Decimal = Decimal("0.00"),
) -> PaymentLink:
    link = PaymentLink(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        provider=provider,
        link_code=code,
        requested_amount=Decimal("100.00"),
        collected_amount=collected_amount,
        recipient_email="synthetic-guest@example.test",
        status=status,
        execution_mode=execution_mode,
        payable=payable,
        external_checkout_url="https://checkout.example.test/synthetic",
        external_reference=f"signed-{code}",
        gateway_response={"preference_id": preference_id} if preference_id else {},
    )
    db.add(link)
    db.flush()
    return link


def _management_member(db, *, hotel_id: int, user_id: int, role: str) -> User:
    user = User(
        id=user_id,
        email=f"synthetic-{user_id}@example.test",
        password_hash="test-only",
        is_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(HotelMembership(hotel_id=hotel_id, user_id=user.id, role=role, status="active"))
    db.flush()
    return user


def test_cancel_link_queues_only_payable_mercado_pago_preferences(db):
    reservation = _reservation(db, 1, "eligibility")
    eligible = _link(db, reservation, "eligible")
    local_only = _link(db, reservation, "local", execution_mode="local_only", payable=False)
    not_payable = _link(db, reservation, "not-payable", payable=False)
    other_provider = _link(db, reservation, "other", provider="paypal")
    missing_preference = _link(db, reservation, "no-pref", preference_id=None)

    for link in (eligible, local_only, not_payable, other_provider, missing_preference):
        cancel_link(db, reservation.hotel_id, link.id, reason="guest cancellation")

    db.flush()
    assert eligible.status == "cancelled"
    assert eligible.provider_revocation_status == "pending"
    assert eligible.provider_revocation_attempts == 0
    assert local_only.provider_revocation_status == "not_required"
    assert not_payable.provider_revocation_status == "not_required"
    assert other_provider.provider_revocation_status == "not_required"
    assert missing_preference.provider_revocation_status == "not_required"


def test_cancel_active_links_queues_revocation_for_eligible_links_only(db):
    reservation = _reservation(db, 1, "reservation-cancel")
    payable = _link(db, reservation, "reservation-payable", status="partially_paid")
    local_only = _link(
        db,
        reservation,
        "reservation-local",
        execution_mode="local_only",
        payable=False,
    )
    not_payable = _link(db, reservation, "reservation-not-payable", payable=False)
    other_provider = _link(db, reservation, "reservation-paypal", provider="paypal")
    legacy_active = _link(db, reservation, "reservation-active", status="active")
    missing_preference = _link(
        db, reservation, "reservation-no-pref", preference_id=None
    )

    cancelled = cancel_active_links_for_reservation(
        db,
        reservation.hotel_id,
        reservation.id,
        reason="reservation cancelled",
    )

    assert cancelled == 6
    assert payable.status == "cancelled"
    assert payable.provider_revocation_status == "pending"
    assert local_only.provider_revocation_status == "not_required"
    assert not_payable.provider_revocation_status == "not_required"
    assert other_provider.provider_revocation_status == "not_required"
    assert missing_preference.provider_revocation_status == "not_required"
    assert legacy_active.status == "cancelled"
    assert legacy_active.provider_revocation_status == "pending"


def test_revocation_stays_pending_when_provider_connections_are_disabled(db, monkeypatch):
    reservation = _reservation(db, 1, "disabled-provider-lane")
    link = _link(db, reservation, "disabled-provider-lane")
    cancel_link(db, reservation.hotel_id, link.id, reason="reservation cancelled")
    gateway_calls = []
    monkeypatch.setattr(payment_link_service, "external_connections_enabled", lambda: False)

    result = process_payment_link_revocations(
        db,
        reservation.hotel_id,
        reservation_id=reservation.id,
        revoke_gateway=lambda *_args: gateway_calls.append(True),
    )

    assert result == {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 1}
    assert gateway_calls == []
    assert link.provider_revocation_status == "pending"
    assert link.provider_revocation_attempts == 0
    assert (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.hotel_id == reservation.hotel_id,
            NotificationOutbox.event_type == "payment_link.revocation_failed",
        )
        .count()
        == 0
    )


def test_revocation_processing_is_tenant_and_reservation_scoped_and_idempotent(db):
    target_reservation = _reservation(db, 1, "target")
    other_reservation = _reservation(db, 1, "other-reservation")
    other_hotel_reservation = _reservation(db, 2, "other-hotel")
    target = _link(db, target_reservation, "target-link")
    same_hotel_other_reservation = _link(db, other_reservation, "other-reservation-link")
    other_hotel = _link(db, other_hotel_reservation, "other-hotel-link")
    for link in (target, same_hotel_other_reservation, other_hotel):
        cancel_link(db, link.hotel_id, link.id)

    gateway_calls = []

    def expire_preference(session, hotel_id, link):
        gateway_calls.append((session, hotel_id, link.id))
        return {"preference_expired": True}

    result = process_payment_link_revocations(
        db,
        target_reservation.hotel_id,
        reservation_id=target_reservation.id,
        limit=10,
        revoke_gateway=expire_preference,
    )

    assert result == {"processed": 1, "succeeded": 1, "failed": 0, "skipped": 0}
    assert gateway_calls == [(db, target_reservation.hotel_id, target.id)]
    target_after = db.get(PaymentLink, target.id)
    same_hotel_other_after = db.get(PaymentLink, same_hotel_other_reservation.id)
    other_hotel_after = db.get(PaymentLink, other_hotel.id)
    assert target_after.provider_revocation_status == "succeeded"
    assert target_after.provider_revocation_attempts == 1
    assert target_after.provider_revocation_last_attempt_at is not None
    assert same_hotel_other_after.provider_revocation_status == "pending"
    assert other_hotel_after.provider_revocation_status == "pending"

    # Replaying the worker must not call the provider or increment attempts.
    replay = process_payment_link_revocations(
        db,
        target_reservation.hotel_id,
        reservation_id=target_reservation.id,
        limit=10,
        revoke_gateway=expire_preference,
    )
    assert replay == {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0}
    assert len(gateway_calls) == 1
    assert db.get(PaymentLink, target.id).provider_revocation_attempts == 1


@pytest.mark.parametrize(
    "gateway_result",
    [
        {"preference_expired": False},
        {"preference_expired": "true"},
    ],
)
def test_unconfirmed_revocation_failure_alerts_management_without_refund(
    db, gateway_result
):
    reservation = _reservation(db, 1, f"failure-{gateway_result['preference_expired']}")
    link = _link(
        db,
        reservation,
        f"failure-{gateway_result['preference_expired']}",
        status="partially_paid",
        collected_amount=Decimal("35.00"),
    )
    users_by_role = {
        role: _management_member(db, hotel_id=reservation.hotel_id, user_id=user_id, role=role)
        for role, user_id in (("owner", 8101), ("co_owner", 8102), ("manager", 8103))
    }
    receptionist = _management_member(
        db, hotel_id=reservation.hotel_id, user_id=8104, role="receptionist"
    )
    db.add(
        NotificationPreference(
            hotel_id=reservation.hotel_id,
            user_id=users_by_role["manager"].id,
            event_type="payment_link.revocation_failed",
            in_app_enabled=False,
        )
    )

    collected = Transaction(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        amount=Decimal("35.00"),
        currency="ARS",
        transaction_type=TransactionTypeEnum.DEPOSIT,
        payment_method=PaymentMethodEnum.MERCADO_PAGO,
        status=TransactionStatusEnum.COMPLETED,
        external_payment_id="synthetic-payment-id",
    )
    db.add(collected)
    db.flush()
    cancel_link(db, reservation.hotel_id, link.id, reason="reservation cancelled")
    transactions_before = db.query(Transaction).count()

    result = process_payment_link_revocations(
        db,
        reservation.hotel_id,
        reservation_id=reservation.id,
        revoke_gateway=lambda *_args: gateway_result,
    )

    assert result == {"processed": 1, "succeeded": 0, "failed": 1, "skipped": 0}
    link_after = db.get(PaymentLink, link.id)
    assert link_after.provider_revocation_status == "failed"
    assert link_after.provider_revocation_attempts == 1
    assert link_after.provider_revocation_last_attempt_at is not None
    assert link_after.provider_revocation_error
    assert link_after.status == "cancelled"
    assert link_after.payable is False

    alerts = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.hotel_id == reservation.hotel_id,
            NotificationOutbox.event_type == "payment_link.revocation_failed",
        )
        .all()
    )
    assert {row.recipient_user_id for row in alerts} == {
        users_by_role["owner"].id,
        users_by_role["co_owner"].id,
        users_by_role["manager"].id,
    }
    assert receptionist.id not in {row.recipient_user_id for row in alerts}
    assert {row.channel.value for row in alerts} == {"in_app"}
    assert all(row.severity.value in {"warning", "critical"} for row in alerts)
    assert all(json.loads(row.payload) == {
        "payment_link_id": link.id,
        "reservation_id": reservation.id,
    } for row in alerts)

    # Failed link revocation is an operational alert only: payments stay intact
    # and no automatic refund transaction is added.
    db.refresh(collected)
    assert collected.status == TransactionStatusEnum.COMPLETED
    assert db.query(Transaction).count() == transactions_before
    assert (
        db.query(Transaction)
        .filter(
            Transaction.reservation_id == reservation.id,
            Transaction.transaction_type == TransactionTypeEnum.REFUND,
        )
        .count()
        == 0
    )

    # A worker replay must not resend the same failure alert or retry a failed
    # preference implicitly; retries require an explicit state transition.
    replay = process_payment_link_revocations(
        db,
        reservation.hotel_id,
        reservation_id=reservation.id,
        revoke_gateway=lambda *_args: pytest.fail("failed revocation must not retry implicitly"),
    )
    assert replay == {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0}
    assert (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.hotel_id == reservation.hotel_id,
            NotificationOutbox.event_type == "payment_link.revocation_failed",
        )
        .count()
        == len(alerts)
    )


def _cancelled_provider_link(db, suffix: str) -> PaymentLink:
    reservation = _reservation(db, 1, suffix)
    link = _link(db, reservation, suffix, preference_id=_PREFERENCE_ID)
    cancel_link(db, reservation.hotel_id, link.id, reason="synthetic test cancellation")
    return link


def test_mp_revocation_preflights_updates_and_verifies_in_order(db, monkeypatch):
    link = _cancelled_provider_link(db, "adapter-success")
    response_bodies = [
        _preference_identity(link, expired=False),
        _preference_identity(link, expired=False),
        _preference_identity(link, expired=True),
    ]
    calls = _mock_revocation_http(monkeypatch, response_bodies)

    result = process_payment_link_revocations(db, link.hotel_id, reservation_id=link.reservation_id)

    expected_url = "https://api.mercadopago.com/checkout/preferences/pref-test"
    assert result == {"processed": 1, "succeeded": 1, "failed": 0, "skipped": 0}
    assert [(method, url) for method, url, _kwargs in calls] == [
        ("GET", expected_url),
        ("PUT", expected_url),
        ("GET", expected_url),
    ]
    update_payload = calls[1][2]["json"]
    assert update_payload["expires"] is True
    assert update_payload["external_reference"] == link.external_reference
    assert update_payload["expiration_date_to"]
    assert db.get(PaymentLink, link.id).provider_revocation_status == "succeeded"


@pytest.mark.parametrize("stage", ["preflight", "update", "verification"])
@pytest.mark.parametrize(
    "identity_field,bad_value",
    [
        ("id", None),
        ("id", "different-preference"),
        ("external_reference", None),
        ("external_reference", "different-reference"),
        ("collector_id", None),
        ("collector_id", "different-account"),
    ],
    ids=[
        "missing-id",
        "mismatched-id",
        "missing-reference",
        "mismatched-reference",
        "missing-account",
        "mismatched-account",
    ],
)
def test_mp_revocation_identity_mismatch_never_marks_succeeded(
    db, monkeypatch, stage, identity_field, bad_value
):
    link = _cancelled_provider_link(db, f"identity-{stage}-{identity_field}-{bad_value}")
    response_bodies = [
        _preference_identity(link, expired=False),
        _preference_identity(link, expired=False),
        _preference_identity(link, expired=True),
    ]
    bad_response_index = {"preflight": 0, "update": 1, "verification": 2}[stage]
    if bad_value is None:
        response_bodies[bad_response_index].pop(identity_field)
    else:
        response_bodies[bad_response_index][identity_field] = bad_value
    calls = _mock_revocation_http(monkeypatch, response_bodies)

    result = process_payment_link_revocations(db, link.hotel_id, reservation_id=link.reservation_id)

    expected_methods = {
        "preflight": ["GET"],
        "update": ["GET", "PUT"],
        "verification": ["GET", "PUT", "GET"],
    }[stage]
    assert result == {"processed": 1, "succeeded": 0, "failed": 1, "skipped": 0}
    assert [method for method, _url, _kwargs in calls] == expected_methods
    assert all(url.endswith("/checkout/preferences/pref-test") for _method, url, _kwargs in calls)
    link_after = db.get(PaymentLink, link.id)
    assert link_after.provider_revocation_status == "failed"
    assert link_after.provider_revocation_status != "succeeded"
    assert link_after.provider_revocation_attempts == 1


def test_revocation_worker_recovers_only_stale_processing_claims(db):
    reservation = _reservation(db, 1, "stale-claim")
    stale = _link(db, reservation, "stale-claim")
    recent = _link(db, reservation, "recent-claim")
    cancel_link(db, reservation.hotel_id, stale.id)
    cancel_link(db, reservation.hotel_id, recent.id)

    now = datetime.now(UTC).replace(tzinfo=None)
    stale.provider_revocation_status = "processing"
    stale.provider_revocation_attempts = 1
    stale.provider_revocation_last_attempt_at = now - timedelta(minutes=6)
    recent.provider_revocation_status = "processing"
    recent.provider_revocation_attempts = 1
    recent.provider_revocation_last_attempt_at = now
    db.flush()

    processed_ids = []

    def expire_link(_session, _hotel_id, link):
        processed_ids.append(link.id)
        return {"preference_expired": True}

    result = process_payment_link_revocations(
        db,
        reservation.hotel_id,
        reservation_id=reservation.id,
        revoke_gateway=expire_link,
    )

    stale_after = db.get(PaymentLink, stale.id)
    recent_after = db.get(PaymentLink, recent.id)
    assert result == {"processed": 1, "succeeded": 1, "failed": 0, "skipped": 0}
    assert processed_ids == [stale.id]
    assert stale_after.provider_revocation_status == "succeeded"
    assert stale_after.provider_revocation_attempts == 2
    assert recent_after.provider_revocation_status == "processing"
    assert recent_after.provider_revocation_attempts == 1
