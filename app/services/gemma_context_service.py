from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.allocation import ManualOverrideReason
from app.models.hotel_config import HotelConfiguration
from app.models.operations import RoomMoveEvent
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room
from app.services.allocation_policy_service import get_active_policy_settings
from app.services.reservation_action_service import list_pending_reservation_actions


_ACTIVE_RESERVATION_STATUSES = (
    ReservationStatusEnum.PENDING,
    ReservationStatusEnum.DEPOSIT_PAID,
    ReservationStatusEnum.FULLY_PAID,
    ReservationStatusEnum.CHECKED_IN,
)


def build_gemma_hotel_context(
    db: Session,
    *,
    hotel_id: int,
    intent_type: str,
    lookback_days: int = 30,
    horizon_days: int = 14,
) -> dict[str, Any]:
    hotel = db.get(HotelConfiguration, hotel_id)
    if hotel is None:
        raise ValueError(f"Hotel {hotel_id} not found")

    today = date.today()
    lookback_start = today - timedelta(days=lookback_days)
    horizon_end = today + timedelta(days=horizon_days)

    policy = get_active_policy_settings(db, hotel_id)

    total_rooms = db.query(Room).filter(Room.hotel_id == hotel_id, Room.is_active == True).count()
    room_status_rows = (
        db.query(Room.status, func.count(Room.id))
        .filter(Room.hotel_id == hotel_id, Room.is_active == True)
        .group_by(Room.status)
        .all()
    )
    room_status_counts = {_enum_value(status): int(count) for status, count in room_status_rows}

    recent_reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.check_in_date >= lookback_start,
            Reservation.check_in_date <= today,
            Reservation.status != ReservationStatusEnum.CANCELLED,
        )
        .all()
    )
    upcoming_reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.check_out_date > today,
            Reservation.check_in_date <= horizon_end,
            Reservation.status.in_(_ACTIVE_RESERVATION_STATUSES),
        )
        .all()
    )

    recent_source_mix = Counter(_enum_value(reservation.source) for reservation in recent_reservations)
    upcoming_source_mix = Counter(_enum_value(reservation.source) for reservation in upcoming_reservations)
    unassigned_count = sum(1 for reservation in upcoming_reservations if reservation.room_id is None)
    manual_review_count = sum(1 for reservation in upcoming_reservations if reservation.requires_manual_review)

    pending_actions = list_pending_reservation_actions(db, hotel_id=hotel_id, limit=25)
    pending_action_counter = Counter(action["code"] for action in pending_actions)

    recent_override_rows = (
        db.query(ManualOverrideReason.override_type, ManualOverrideReason.reason_code)
        .filter(ManualOverrideReason.hotel_id == hotel_id)
        .order_by(ManualOverrideReason.created_at.desc(), ManualOverrideReason.id.desc())
        .limit(15)
        .all()
    )
    recent_room_move_rows = (
        db.query(RoomMoveEvent.move_type, RoomMoveEvent.reason_code)
        .filter(RoomMoveEvent.hotel_id == hotel_id)
        .order_by(RoomMoveEvent.occurred_at.desc(), RoomMoveEvent.id.desc())
        .limit(15)
        .all()
    )

    occupancy_next_days = []
    for day_offset in range(min(horizon_days, 7)):
        day = today + timedelta(days=day_offset)
        occupied = sum(
            1
            for reservation in upcoming_reservations
            if reservation.check_in_date <= day < reservation.check_out_date
        )
        occupancy_next_days.append(
            {
                "date": day.isoformat(),
                "occupied": occupied,
                "total_rooms": total_rooms,
                "occupancy_rate": round((occupied / total_rooms) * 100, 1) if total_rooms else 0.0,
            }
        )

    return {
        "hotel": {
            "hotel_id": hotel_id,
            "hotel_name": hotel.hotel_name,
            "timezone": hotel.hotel_timezone,
            "default_currency": hotel.default_currency,
        },
        "intent_type": intent_type,
        "inventory": {
            "total_active_rooms": total_rooms,
            "room_status_counts": room_status_counts,
        },
        "allocation_policy": {
            "profile_code": policy.profile.code,
            "profile_name": policy.profile.name,
            "version_id": policy.version.id,
            "constraints": policy.constraints,
            "weights": policy.weights,
        },
        "reservation_summary": {
            "lookback_days": lookback_days,
            "horizon_days": horizon_days,
            "recent_reservation_count": len(recent_reservations),
            "upcoming_active_reservation_count": len(upcoming_reservations),
            "upcoming_unassigned_count": unassigned_count,
            "upcoming_manual_review_count": manual_review_count,
            "recent_source_mix": dict(sorted(recent_source_mix.items())),
            "upcoming_source_mix": dict(sorted(upcoming_source_mix.items())),
            "occupancy_next_days": occupancy_next_days,
        },
        "operations": {
            "pending_action_count": len(pending_actions),
            "pending_action_mix": dict(sorted(pending_action_counter.items())),
            "top_pending_actions": pending_actions[:5],
            "recent_override_signals": [
                {
                    "override_type": override_type,
                    "reason_code": reason_code,
                }
                for override_type, reason_code in recent_override_rows
            ],
            "recent_room_moves": [
                {
                    "move_type": _enum_value(move_type),
                    "reason_code": reason_code,
                }
                for move_type, reason_code in recent_room_move_rows
            ],
        },
    }


def _enum_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    if value is None:
        return "unknown"
    return str(value)
