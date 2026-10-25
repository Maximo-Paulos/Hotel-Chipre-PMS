"""Shared, fixed post-checkout checklist definition and state guards."""
from sqlalchemy.orm import Session

from app.models.housekeeping_checklist import (
    HousekeepingChecklist,
    HousekeepingChecklistItemCodeEnum,
    HousekeepingChecklistStatusEnum,
)

# Item codes are stable API values. Labels are immutable snapshots copied to
# each checklist at checkout so an old task keeps the wording it was created with.
REQUIRED_HOUSEKEEPING_CHECKLIST_ITEMS = (
    (HousekeepingChecklistItemCodeEnum.CHANGE_SHEETS, "Cambiar sábanas"),
    (HousekeepingChecklistItemCodeEnum.CLEAN_BATHROOM, "Limpiar baño"),
    (HousekeepingChecklistItemCodeEnum.REPLENISH_TOWELS, "Reponer toallas"),
    (HousekeepingChecklistItemCodeEnum.EMPTY_WASTE, "Vaciar residuos"),
    (HousekeepingChecklistItemCodeEnum.CHECK_AMENITIES, "Revisar amenities"),
)
REQUIRED_HOUSEKEEPING_CHECKLIST_CODES = frozenset(code.value for code, _label in REQUIRED_HOUSEKEEPING_CHECKLIST_ITEMS)


def open_housekeeping_checklist_exists(db: Session, *, hotel_id: int, room_id: int) -> bool:
    return (
        db.query(HousekeepingChecklist.id)
        .filter(
            HousekeepingChecklist.hotel_id == hotel_id,
            HousekeepingChecklist.room_id == room_id,
            HousekeepingChecklist.status == HousekeepingChecklistStatusEnum.OPEN.value,
        )
        .first()
        is not None
    )
