import json
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.schemas.reservation import ReservationUpdate
from app.services import (
    reservation_operations_service,
    reservation_service,
    reservation_update_service,
)
from app.services.reservation_service import manual_override_total_for_nights


class _RecordingSession:
    def __init__(self, events):
        self.events = events

    def commit(self):
        self.events.append(("commit",))

    def refresh(self, entity):
        self.events.append(("refresh", entity))


def _install_recording_dependencies(monkeypatch, events):
    def snapshot(reservation):
        return {"total_amount": reservation.total_amount}

    def safe_create_audit_log(db, **kwargs):
        events.append(("audit", db, kwargs))

    monkeypatch.setattr(reservation_update_service.audit_log_service, "model_snapshot", snapshot)
    monkeypatch.setattr(
        reservation_update_service.audit_log_service,
        "safe_create_audit_log",
        safe_create_audit_log,
    )


def test_manual_total_update_mutation_and_audit_share_one_commit(monkeypatch):
    events = []
    db = _RecordingSession(events)
    reservation = SimpleNamespace(
        id=41,
        total_amount=Decimal("200.00"),
        pricing_snapshot=json.dumps(
            {
                "manual_total_adjustments": [
                    {
                        "manual_rate": {
                            "scope": "bounded",
                            "quote_total": "200.00",
                            "minimum_total": "150.00",
                            "maximum_total": "220.00",
                        }
                    }
                ]
            }
        ),
    )
    data = ReservationUpdate(
        total_amount=Decimal("150.00"),
        paid_total_change_reason="Corrección solicitada",
        client_version=3,
    )
    _install_recording_dependencies(monkeypatch, events)

    def mutate(db_arg, reservation_arg, data_arg, hotel_id, **kwargs):
        events.append(("mutate", db_arg, reservation_arg, data_arg, hotel_id, kwargs))
        reservation_arg.total_amount = data_arg.total_amount

    monkeypatch.setattr(reservation_update_service, "update_reservation_fields", mutate)

    result = reservation_update_service.apply_reservation_update(
        db,
        reservation,
        data,
        7,
        actor_user_id=12,
        actor_role="manager",
        total_adjustment_kind="manual",
        manual_rate_scope="bounded",
        confirmed_price_change_review_required=False,
    )

    assert result is reservation
    assert [event[0] for event in events] == ["mutate", "audit", "commit", "refresh"]
    mutation = events[0]
    assert mutation[1:5] == (db, reservation, data, 7)
    assert mutation[5] == {
        "changed_by_user_id": 12,
        "actor_role": "manager",
        "room_move_reason_code": "manual_update",
        "room_move_notes": "Cambio manual desde API de reservas",
        "client_version": 3,
        "preserve_unclassified_price": True,
        "recalculate_explicit_price": False,
        "total_adjustment_kind": "manual",
        "manual_rate_scope": "bounded",
        "confirmed_price_change_review_required": False,
    }

    _, audit_db, audit = events[1]
    assert audit_db is db
    assert audit["hotel_id"] == 7
    assert audit["record_id"] == 41
    assert audit["actor_user_id"] == 12
    assert audit["payload_before"] == {"total_amount": Decimal("200.00")}
    assert audit["payload_after"]["source"] == "reservations_api"
    assert audit["payload_after"]["total_adjustment"] == {
        "previous_total_amount": "200.00",
        "updated_total_amount": "150.00",
        "reason": "Corrección solicitada",
        "actor_user_id": 12,
        "manual_rate": {
            "scope": "bounded",
            "quote_total": "200.00",
            "minimum_total": "150.00",
            "maximum_total": "220.00",
        },
    }
    assert "paid_total_adjustment" not in audit["payload_after"]
    assert events[-1] == ("refresh", reservation)


def test_checkout_extension_recalculates_manual_nightly_price_without_touching_paid_ledger(monkeypatch):
    events = []
    db = _RecordingSession(events)
    reservation = SimpleNamespace(
        id=47,
        check_in_date=date(2026, 11, 4),
        check_out_date=date(2026, 11, 5),
        total_amount=Decimal("60000.00"),
        amount_paid=Decimal("3000.00"),
        pricing_snapshot=json.dumps(
            {"pricing_source": "manual_total_override", "nightly_rate": "60000.00"}
        ),
    )
    data = ReservationUpdate(
        check_out_date=date(2026, 11, 6),
        client_version=4,
    )
    _install_recording_dependencies(monkeypatch, events)
    captured = {}

    def mutate(_db, reservation_arg, data_arg, _hotel_id, **kwargs):
        captured.update(kwargs)
        # The service passes the opt-in to the existing repricer. Simulate its
        # expected two-night result while asserting the prior payment remains.
        if kwargs["recalculate_explicit_price"]:
            reservation_arg.total_amount = manual_override_total_for_nights(
                reservation_arg,
                nights=2,
            )
        reservation_arg.check_out_date = data_arg.check_out_date

    monkeypatch.setattr(reservation_update_service, "update_reservation_fields", mutate)

    reservation_update_service.apply_reservation_update(
        db,
        reservation,
        data,
        7,
        actor_user_id=12,
        actor_role="manager",
        total_adjustment_kind=None,
        manual_rate_scope=None,
        confirmed_price_change_review_required=False,
    )

    assert captured["recalculate_explicit_price"] is True
    assert captured["preserve_unclassified_price"] is True
    assert reservation.total_amount == Decimal("120000.00")
    assert reservation.amount_paid == Decimal("3000.00")
    assert reservation.check_out_date == date(2026, 11, 6)


def test_checkout_extension_does_not_reprice_non_manual_reservation(monkeypatch):
    events = []
    db = _RecordingSession(events)
    reservation = SimpleNamespace(
        id=48,
        check_in_date=date(2026, 11, 4),
        check_out_date=date(2026, 11, 5),
        total_amount=Decimal("60000.00"),
        amount_paid=Decimal("3000.00"),
        pricing_snapshot=json.dumps({"pricing_source": "rate_plan_quote"}),
    )
    data = ReservationUpdate(check_out_date=date(2026, 11, 6), client_version=4)
    _install_recording_dependencies(monkeypatch, events)
    captured = {}

    def mutate(_db, _reservation, _data, _hotel_id, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(reservation_update_service, "update_reservation_fields", mutate)

    reservation_update_service.apply_reservation_update(
        db,
        reservation,
        data,
        7,
        actor_user_id=12,
        actor_role="manager",
        total_adjustment_kind=None,
        manual_rate_scope=None,
        confirmed_price_change_review_required=False,
    )

    assert captured["recalculate_explicit_price"] is False


@pytest.mark.parametrize(
    ("pricing_source", "recalculate_explicit_price"),
    [
        ("rate_plan_quote", False),
        ("manual_total_override", True),
    ],
)
@pytest.mark.parametrize(
    ("nightly_rate", "current_total", "current_nights", "expected_total"),
    [
        ("60000.00", Decimal("60000.00"), 1, Decimal("120000.00")),
        (None, Decimal("120000.00"), 2, Decimal("180000.00")),
    ],
)
def test_date_reprice_without_active_rate_carries_historical_nightly_amount(
    monkeypatch,
    pricing_source,
    recalculate_explicit_price,
    nightly_rate,
    current_total,
    current_nights,
    expected_total,
):
    class _CategoryQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def enable_eagerloads(self, _enabled):
            return self

        def first(self):
            return SimpleNamespace(id=9, hotel_id=7)

    class _Session:
        def query(self, *_args, **_kwargs):
            return _CategoryQuery()

    db = _Session()
    old_checkout = date(2026, 11, 4) + timedelta(days=current_nights)
    new_checkout = old_checkout + timedelta(days=1)
    snapshot = {"pricing_source": pricing_source}
    if nightly_rate is not None:
        snapshot["nightly_rate"] = nightly_rate
    reservation = SimpleNamespace(
        id=49,
        hotel_id=7,
        guest_id=11,
        category_id=9,
        room_id=1,
        company_id=None,
        check_in_date=date(2026, 11, 4),
        check_out_date=old_checkout,
        total_amount=current_total,
        amount_paid=Decimal("3000.00"),
        subtotal_amount=current_total,
        tax_amount=Decimal("0.00"),
        fee_amount=Decimal("0.00"),
        commission_amount=Decimal("0.00"),
        net_amount=current_total,
        deposit_amount=Decimal("3000.00"),
        currency_code="ARS",
        fx_rate_snapshot=None,
        sellable_product_id=None,
        rate_plan_id=12,
        tax_policy_id=None,
        source_provider_code=None,
        source=SimpleNamespace(value="direct"),
        num_adults=1,
        num_children=0,
        pricing_snapshot=json.dumps(snapshot),
    )
    monkeypatch.setattr(
        reservation_service,
        "calculate_reservation_pricing",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            reservation_service.ReservationError("No active prices found for rate plan")
        ),
    )
    monkeypatch.setattr(reservation_service, "_require_deposit_policy_configured", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        reservation_service,
        "_resolve_reservation_commercial_context",
        lambda *_args, **_kwargs: (None, SimpleNamespace(id=12), None),
    )
    monkeypatch.setattr(reservation_service, "_get_hotel_default_currency", lambda *_args, **_kwargs: "ARS")
    monkeypatch.setattr(reservation_service, "_compute_deposit_amount", lambda *_args, **_kwargs: 0.0)

    reservation_service._apply_date_change_pricing(
        db,
        reservation,
        hotel_id=7,
        check_in_date=reservation.check_in_date,
        check_out_date=new_checkout,
        occupancy=1,
        recalculate_pricing=True,
        recalculate_explicit_price=recalculate_explicit_price,
        preserve_unclassified_price=True,
    )

    assert reservation.total_amount == float(expected_total)
    assert reservation.amount_paid == Decimal("3000.00")
    assert reservation.total_amount - float(reservation.amount_paid) == float(expected_total - Decimal("3000.00"))
    assert reservation.check_out_date == old_checkout
    assert reservation.rate_plan_id == 12
    assert json.loads(reservation.pricing_snapshot)["nightly_rate"] == 60000.0


def test_date_change_does_not_use_historical_rate_for_other_pricing_errors(monkeypatch):
    reservation = SimpleNamespace(
        check_in_date=date(2026, 11, 4),
        check_out_date=date(2026, 11, 5),
        company_id=None,
        pricing_snapshot=json.dumps(
            {"pricing_source": "rate_plan_quote", "nightly_rate": "60000.00"}
        ),
        source_provider_code=None,
        source=SimpleNamespace(value="direct"),
        category_id=9,
        sellable_product_id=None,
        rate_plan_id=12,
        tax_policy_id=None,
        currency_code="ARS",
        num_adults=1,
        num_children=0,
        guest_id=11,
    )
    monkeypatch.setattr(
        reservation_service,
        "calculate_reservation_pricing",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            reservation_service.ReservationError("Rate plan is inactive")
        ),
    )

    with pytest.raises(reservation_service.ReservationError, match="Rate plan is inactive"):
        reservation_service._apply_date_change_pricing(
            object(),
            reservation,
            hotel_id=7,
            check_in_date=reservation.check_in_date,
            check_out_date=date(2026, 11, 6),
            occupancy=1,
            recalculate_pricing=True,
            recalculate_explicit_price=False,
            preserve_unclassified_price=True,
        )


def test_dedicated_extension_uses_saved_nightly_rate_when_added_dates_have_no_active_rate(monkeypatch):
    reservation = SimpleNamespace(
        id=50,
        category_id=9,
        check_in_date=date(2026, 11, 4),
        check_out_date=date(2026, 11, 5),
        total_amount=Decimal("60000.00"),
        currency_code="ARS",
        sellable_product_id=None,
        rate_plan_id=12,
        tax_policy_id=None,
        source_provider_code=None,
        source=SimpleNamespace(value="direct"),
        num_adults=1,
        num_children=0,
        company_id=None,
        pricing_snapshot=json.dumps(
            {"pricing_source": "rate_plan_quote", "nightly_rate": "60000.00"}
        ),
    )
    monkeypatch.setattr(
        reservation_operations_service,
        "calculate_reservation_pricing",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            reservation_service.ReservationError("No active prices found for rate plan")
        ),
    )

    amount = reservation_operations_service._extension_amount(
        object(),
        reservation=reservation,
        hotel_id=7,
        new_checkout_date=date(2026, 11, 6),
        pricing_mode="current_rate",
    )

    assert amount == Decimal("60000.00")


def test_paid_total_adjustment_keeps_legacy_audit_key(monkeypatch):
    events = []
    db = _RecordingSession(events)
    reservation = SimpleNamespace(id=52, total_amount=Decimal("190.00"), pricing_snapshot=None)
    data = ReservationUpdate(
        total_amount=Decimal("180.00"),
        paid_total_change_reason="Ajuste aprobado",
        client_version=4,
    )
    _install_recording_dependencies(monkeypatch, events)

    def mutate(_db, reservation_arg, data_arg, _hotel_id, **_kwargs):
        reservation_arg.total_amount = data_arg.total_amount

    monkeypatch.setattr(reservation_update_service, "update_reservation_fields", mutate)

    reservation_update_service.apply_reservation_update(
        db,
        reservation,
        data,
        8,
        actor_user_id=3,
        actor_role="owner",
        total_adjustment_kind="paid",
        manual_rate_scope=None,
        confirmed_price_change_review_required=False,
    )

    after = events[0][2]["payload_after"]
    assert after["source"] == "reservations_api"
    assert after["total_adjustment"] == after["paid_total_adjustment"]
    assert after["paid_total_adjustment"]["previous_total_amount"] == "190.00"
    assert after["paid_total_adjustment"]["updated_total_amount"] == "180.00"


def test_mutator_failure_propagates_without_audit_or_commit(monkeypatch):
    events = []
    db = _RecordingSession(events)
    reservation = SimpleNamespace(id=63, total_amount=Decimal("100.00"), pricing_snapshot=None)
    _install_recording_dependencies(monkeypatch, events)

    def fail(*_args, **_kwargs):
        events.append(("mutate",))
        raise RuntimeError("synthetic mutation failure")

    monkeypatch.setattr(reservation_update_service, "update_reservation_fields", fail)

    with pytest.raises(RuntimeError, match="synthetic mutation failure"):
        reservation_update_service.apply_reservation_update(
            db,
            reservation,
            ReservationUpdate(notes="change", client_version=1),
            9,
            actor_user_id=4,
            actor_role="manager",
            total_adjustment_kind=None,
            manual_rate_scope=None,
            confirmed_price_change_review_required=False,
        )

    assert events == [("mutate",)]


def _authorization(events):
    return reservation_update_service.ReservationUpdateAuthorization(
        company_management=lambda: events.append("company_permission"),
        paid_total_adjustment=lambda: events.append("paid_total_permission"),
        manual_rate_scope=lambda: events.append("manual_rate_permission") or "bounded",
        room_move=lambda: events.append("room_move_permission"),
    )


def _reservation_for_preparation(**overrides):
    fields = {
        "id": 77,
        "version": 3,
        "status": reservation_update_service.ReservationStatusEnum.PENDING,
        "company_id": None,
        "room_id": None,
        "total_amount": Decimal("100.00"),
        "check_in_date": date(2026, 11, 1),
        "check_out_date": date(2026, 11, 3),
        "num_adults": 1,
        "num_children": 0,
        "mobility_restriction": False,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_prepare_update_preserves_permission_and_financial_policy_order(monkeypatch):
    events = []
    reservation = _reservation_for_preparation(company_id=18)
    data = ReservationUpdate(
        total_amount=Decimal("150.00"),
        paid_total_change_reason="Corrección acordada",
        room_id=12,
        check_in_date=date(2026, 11, 2),
        num_adults=2,
        client_version=3,
    )

    monkeypatch.setattr(
        reservation_update_service,
        "reservation_has_deferred_company_billing",
        lambda _db, _reservation, **_kwargs: events.append("deferred_billing") or False,
    )
    payment_checks = iter((True, True))
    monkeypatch.setattr(
        reservation_update_service,
        "reservation_has_payment_or_deposit",
        lambda *_args, **_kwargs: events.append("payment_state") or next(payment_checks),
    )
    monkeypatch.setattr(
        reservation_update_service,
        "validate_direct_individual_manual_rate_target",
        lambda *_args, **_kwargs: pytest.fail("paid adjustment must not use manual-rate validation"),
    )

    prepared = reservation_update_service.prepare_reservation_update(
        object(),
        reservation,
        data,
        5,
        actor_is_manager=True,
        authorization=_authorization(events),
    )

    assert events == [
        "company_permission",
        "deferred_billing",
        "payment_state",
        "paid_total_permission",
        "room_move_permission",
        "payment_state",
    ]
    assert prepared.plan.dates_changed is True
    assert prepared.plan.occupancy_changed is True
    assert prepared.plan.room_changed is True
    assert prepared.total_adjustment_kind == "paid"
    assert prepared.manual_rate_scope is None
    assert prepared.confirmed_price_change_review_required is False
    assert prepared.update_data is not None
    assert prepared.update_data.client_version == 3
    assert prepared.update_data.paid_total_change_reason == "Corrección acordada"
    assert prepared.previous_allocation_interval == (date(2026, 11, 1), date(2026, 11, 3))


def test_prepare_manual_total_uses_authorized_manual_rate_scope(monkeypatch):
    events = []
    monkeypatch.setattr(
        reservation_update_service,
        "reservation_has_deferred_company_billing",
        lambda *_args, **_kwargs: events.append("deferred_billing") or False,
    )
    monkeypatch.setattr(
        reservation_update_service,
        "reservation_has_payment_or_deposit",
        lambda *_args, **_kwargs: events.append("payment_state") or False,
    )
    monkeypatch.setattr(
        reservation_update_service,
        "validate_direct_individual_manual_rate_target",
        lambda *_args, **_kwargs: events.append("manual_target_validated"),
    )

    prepared = reservation_update_service.prepare_reservation_update(
        object(),
        _reservation_for_preparation(),
        ReservationUpdate(
            total_amount=Decimal("120.00"),
            paid_total_change_reason="Ajuste manual",
            client_version=3,
        ),
        5,
        actor_is_manager=False,
        authorization=_authorization(events),
    )

    assert events == [
        "deferred_billing",
        "payment_state",
        "manual_target_validated",
        "manual_rate_permission",
    ]
    assert prepared.total_adjustment_kind == "manual"
    assert prepared.manual_rate_scope == "bounded"
    assert prepared.update_data is not None


def test_prepare_deferred_billing_conflict_precedes_payment_and_later_checks(monkeypatch):
    events = []
    monkeypatch.setattr(
        reservation_update_service,
        "reservation_has_deferred_company_billing",
        lambda *_args, **_kwargs: events.append("deferred_billing") or True,
    )
    monkeypatch.setattr(
        reservation_update_service,
        "reservation_has_payment_or_deposit",
        lambda *_args, **_kwargs: pytest.fail("deferred billing conflict must short-circuit"),
    )

    with pytest.raises(reservation_update_service.ReservationUpdatePreparationError) as error:
        reservation_update_service.prepare_reservation_update(
            object(),
            _reservation_for_preparation(company_id=18),
            ReservationUpdate(
                total_amount=Decimal("120.00"),
                paid_total_change_reason="Ajuste manual",
                notes="also changed",
                client_version=3,
            ),
            5,
            actor_is_manager=False,
            authorization=_authorization(events),
        )

    assert error.value.code == "deferred_company_billing"
    assert error.value.detail == (
        "El alojamiento de esta empresa se factura fuera del PMS y no admite correcciones de importe aquí."
    )
    assert events == ["company_permission", "deferred_billing"]


def test_prepare_noop_keeps_stale_version_check_before_noop_return():
    events = []

    prepared = reservation_update_service.prepare_reservation_update(
        object(),
        _reservation_for_preparation(),
        ReservationUpdate(),
        5,
        actor_is_manager=False,
        authorization=_authorization(events),
    )

    assert prepared.update_data is None
    assert events == []

    with pytest.raises(reservation_update_service.ReservationVersionConflict):
        reservation_update_service.prepare_reservation_update(
            object(),
            _reservation_for_preparation(),
            ReservationUpdate(client_version=2),
            5,
            actor_is_manager=False,
            authorization=_authorization(events),
        )
