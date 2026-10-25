from types import SimpleNamespace

import pytest

from app.models.reservation import ReservationStatusEnum
from app.services.reservation_update_plan import build_reservation_update_plan


def test_plan_excludes_controls_noops_and_unassigned_room_values():
    reservation = SimpleNamespace(
        notes="Keep existing notes",
        room_id=12,
        check_out_date="2026-11-04",
    )

    plan = build_reservation_update_plan(
        reservation,
        {
            "client_version": 3,
            "notes": "Keep existing notes",
            "room_id": None,
            "check_out_date": "2026-11-05",
            "num_adults": 2,
        },
        control_fields={"client_version"},
    )

    assert dict(plan.changes) == {
        "check_out_date": "2026-11-05",
        "num_adults": 2,
    }
    assert plan.dates_changed is True
    assert plan.occupancy_changed is True
    assert plan.room_changed is False
    assert plan.mobility_restriction_changed is False
    with pytest.raises(TypeError):
        plan.changes["notes"] = "mutated"


def test_plan_preserves_route_specific_status_restricted_field_exemptions():
    reservation = SimpleNamespace(total_amount=200, notes="old")
    plan = build_reservation_update_plan(
        reservation,
        {"total_amount": 250, "notes": "new", "arrival_time_hint": "18:00"},
        control_fields=set(),
    )

    assert plan.status_restricted_fields(
        ReservationStatusEnum.CHECKED_OUT,
        metadata_fields={"arrival_time_hint"},
        additionally_allowed_fields={"total_amount"},
    ) == {"notes"}
    assert plan.status_restricted_fields(
        ReservationStatusEnum.CHECKED_OUT,
        metadata_fields={"arrival_time_hint"},
    ) == {"notes", "total_amount"}


@pytest.mark.parametrize(
    "reservation_status",
    [
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    ],
)
def test_plan_blocks_operational_fields_for_each_status_restricted_state(reservation_status):
    plan = build_reservation_update_plan(
        SimpleNamespace(notes="old"),
        {"notes": "new"},
        control_fields=set(),
    )

    assert plan.status_restricted_fields(
        reservation_status,
        metadata_fields={"arrival_time_hint", "reservation_comment"},
    ) == {"notes"}


@pytest.mark.parametrize(
    "reservation_status",
    [
        ReservationStatusEnum.PENDING,
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.PRE_CHECK_IN,
        ReservationStatusEnum.FULLY_PAID,
    ],
)
def test_plan_does_not_apply_status_restriction_to_editable_states(reservation_status):
    plan = build_reservation_update_plan(
        SimpleNamespace(notes="old"),
        {"notes": "new"},
        control_fields=set(),
    )

    assert plan.status_restricted_fields(
        reservation_status,
        metadata_fields={"arrival_time_hint", "reservation_comment"},
    ) == set()
