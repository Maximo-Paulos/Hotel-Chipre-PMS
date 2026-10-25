import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.schemas.reservation import ReservationUpdate
from app.services import reservation_update_service


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
