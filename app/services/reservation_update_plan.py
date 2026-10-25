"""Pure planning helpers for reservation PATCH endpoints.

The primary reservations API and the legacy bookings API share the mechanics
for identifying fields that actually change. Keeping that classification here
lets each transport preserve its own authorization and HTTP contract.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.models.reservation import ReservationStatusEnum


_UPDATE_RESTRICTED_STATUSES = frozenset(
    {
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    }
)


@dataclass(frozen=True)
class ReservationUpdatePlan:
    """An immutable view of the effective fields in a reservation PATCH."""

    changes: Mapping[str, Any]

    @property
    def dates_changed(self) -> bool:
        return bool({"check_in_date", "check_out_date"}.intersection(self.changes))

    @property
    def occupancy_changed(self) -> bool:
        return bool({"num_adults", "num_children"}.intersection(self.changes))

    @property
    def room_changed(self) -> bool:
        return "room_id" in self.changes

    @property
    def mobility_restriction_changed(self) -> bool:
        return "mobility_restriction" in self.changes

    def status_restricted_fields(
        self,
        reservation_status: ReservationStatusEnum,
        *,
        metadata_fields: Collection[str],
        additionally_allowed_fields: Collection[str] = (),
    ) -> set[str]:
        """Return fields blocked by a status-restricted reservation edit.

        The two PATCH routes have a legacy difference in which fields they
        exempt from this check. Requiring the caller to pass those exemptions
        keeps that contract explicit instead of silently merging policies.
        """
        if reservation_status not in _UPDATE_RESTRICTED_STATUSES:
            return set()
        return set(self.changes) - set(metadata_fields) - set(additionally_allowed_fields)


def build_reservation_update_plan(
    reservation: Any,
    submitted_fields: Mapping[str, Any],
    *,
    control_fields: Collection[str],
) -> ReservationUpdatePlan:
    """Classify a validated PATCH payload without changing the reservation."""
    changes = {
        field: value
        for field, value in submitted_fields.items()
        if field not in control_fields
        and not (field == "room_id" and value is None)
        and getattr(reservation, field, None) != value
    }
    return ReservationUpdatePlan(changes=MappingProxyType(changes))
