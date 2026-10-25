"""Schemas for per-guest arrival tracking."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.reservation import ReservationStatusEnum


class ReservationGuestArrivalRead(BaseModel):
    id: int
    guest_id: int
    guest_name: str
    arrived_at: datetime
    actor_user_id: int | None
    actor_display_name: str | None = None
    actor_role: str

    model_config = ConfigDict(from_attributes=True)


class ReservationGuestArrivalListRead(BaseModel):
    reservation_id: int
    reservation_status: ReservationStatusEnum
    status_policy: Literal["partial_checkin", "checked_in_on_first_guest"]
    expected_guest_count: int
    registered_guest_count: int
    arrived_guest_count: int
    missing_profile_count: int
    arrivals: list[ReservationGuestArrivalRead]


class ReservationGuestArrivalMutationRead(BaseModel):
    reservation_id: int
    reservation_status: ReservationStatusEnum
    status_policy: Literal["partial_checkin", "checked_in_on_first_guest"]
    expected_guest_count: int
    registered_guest_count: int
    arrived_guest_count: int
    missing_profile_count: int
    already_recorded: bool
    arrival: ReservationGuestArrivalRead
