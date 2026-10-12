"""Neutral operational follow-up for declared laundry remito shortages.

This service records what the hotel documented with its supplier. It does not
decide responsibility, value missing linen, or create financial movements.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.laundry_vendor import LaundryRemito, LaundryRemitoLine, LaundryVendor
from app.models.linen import LinenItem
from app.models.security_audit_log import SecurityAuditLog
from app.services.row_locks import lock_query


FOLLOW_UP_STATUSES = {"open", "contacted", "response_recorded", "closed"}
EDITABLE_FIELDS = {
    "follow_up_status",
    "follow_up_note",
    "supplier_reference",
    "supplier_contacted_on",
    "supplier_contact_note",
    "supplier_response_on",
    "supplier_response_note",
}


class LaundryMissingFollowUpError(ValueError):
    """Raised when an operational follow-up cannot be read or updated."""


class LaundryMissingFollowUpNotFound(LaundryMissingFollowUpError):
    """Raised when a shortage line is outside the hotel or does not exist."""


def list_missing_follow_ups(*, db: Session, hotel_id: int) -> list[dict]:
    rows = (
        db.query(LaundryRemitoLine, LaundryRemito, LaundryVendor, LinenItem)
        .join(
            LaundryRemito,
            (LaundryRemito.id == LaundryRemitoLine.remito_id)
            & (LaundryRemito.hotel_id == LaundryRemitoLine.hotel_id),
        )
        .join(
            LaundryVendor,
            (LaundryVendor.id == LaundryRemito.vendor_id)
            & (LaundryVendor.hotel_id == LaundryRemito.hotel_id),
        )
        .join(
            LinenItem,
            (LinenItem.id == LaundryRemitoLine.linen_item_id)
            & (LinenItem.hotel_id == LaundryRemitoLine.hotel_id),
        )
        .filter(
            LaundryRemitoLine.hotel_id == hotel_id,
            LaundryRemitoLine.missing_quantity > 0,
        )
        .order_by(LaundryRemito.remito_date.desc(), LaundryRemitoLine.id.desc())
        .all()
    )
    return [
        _serialize_follow_up(line=line, remito=remito, vendor=vendor, item=item)
        for line, remito, vendor, item in rows
    ]


def update_missing_follow_up(
    *,
    db: Session,
    hotel_id: int,
    remito_line_id: int,
    changes: dict,
    actor_user_id: int | None,
) -> dict:
    unknown_fields = set(changes) - EDITABLE_FIELDS
    if unknown_fields:
        raise LaundryMissingFollowUpError("El seguimiento contiene campos no permitidos.")
    if not changes:
        raise LaundryMissingFollowUpError("Indicá al menos un dato para actualizar.")

    line_query = db.query(LaundryRemitoLine).filter(
        LaundryRemitoLine.id == remito_line_id,
        LaundryRemitoLine.hotel_id == hotel_id,
        LaundryRemitoLine.missing_quantity > 0,
    )
    line = lock_query(line_query, LaundryRemitoLine).first()
    if line is None:
        raise LaundryMissingFollowUpNotFound("No se encontró el seguimiento de faltante.")

    before_status = line.follow_up_status
    normalized_changes = {}
    for field, value in changes.items():
        if field in {"follow_up_note", "supplier_reference", "supplier_contact_note", "supplier_response_note"}:
            value = value.strip() or None if value is not None else None
        if getattr(line, field) != value:
            normalized_changes[field] = value

    candidate_status = normalized_changes.get("follow_up_status", line.follow_up_status)
    candidate_contacted_on = normalized_changes.get("supplier_contacted_on", line.supplier_contacted_on)
    candidate_response_on = normalized_changes.get("supplier_response_on", line.supplier_response_on)
    candidate_response_note = normalized_changes.get("supplier_response_note", line.supplier_response_note)
    if candidate_status not in FOLLOW_UP_STATUSES:
        raise LaundryMissingFollowUpError("El estado del seguimiento no es válido.")
    if candidate_status == "contacted" and candidate_contacted_on is None:
        raise LaundryMissingFollowUpError("Registrá la fecha de contacto antes de marcar el seguimiento como contactado.")
    if candidate_status == "response_recorded" and (
        candidate_contacted_on is None or candidate_response_on is None or not candidate_response_note
    ):
        raise LaundryMissingFollowUpError(
            "Para registrar una respuesta, completá la fecha de contacto, la fecha de respuesta y el detalle recibido."
        )

    if normalized_changes:
        for field, value in normalized_changes.items():
            setattr(line, field, value)
        line.follow_up_updated_by_user_id = actor_user_id
        line.follow_up_updated_at = datetime.now(timezone.utc)
        db.flush()
        db.add(
            SecurityAuditLog(
                hotel_id=hotel_id,
                user_id=actor_user_id,
                action="laundry.missing_follow_up.updated",
                resource_type="laundry_remito_line",
                resource_id=str(line.id),
                details=json.dumps(
                    {
                        "changed_fields": sorted(normalized_changes),
                        "status_before": before_status,
                        "status_after": line.follow_up_status,
                    },
                    sort_keys=True,
                ),
            )
        )

    joined = (
        db.query(LaundryRemito, LaundryVendor, LinenItem)
        .join(LaundryVendor, (LaundryVendor.id == LaundryRemito.vendor_id) & (LaundryVendor.hotel_id == LaundryRemito.hotel_id))
        .join(LinenItem, (LinenItem.id == line.linen_item_id) & (LinenItem.hotel_id == line.hotel_id))
        .filter(LaundryRemito.id == line.remito_id, LaundryRemito.hotel_id == hotel_id)
        .first()
    )
    if joined is None:
        raise LaundryMissingFollowUpNotFound("No se encontró el remito asociado al seguimiento.")
    remito, vendor, item = joined
    return _serialize_follow_up(line=line, remito=remito, vendor=vendor, item=item)


def _serialize_follow_up(*, line: LaundryRemitoLine, remito: LaundryRemito, vendor: LaundryVendor, item: LinenItem) -> dict:
    """Return operational details only; deliberately omit all price fields."""

    return {
        "id": line.id,
        "remito_id": remito.id,
        "remito_number": remito.remito_number,
        "remito_date": remito.remito_date,
        "vendor_id": vendor.id,
        "vendor_name": vendor.name,
        "linen_item_id": item.id,
        "linen_item_name": item.name,
        "quantity": line.quantity,
        "missing_quantity": line.missing_quantity,
        "follow_up_status": line.follow_up_status,
        "follow_up_note": line.follow_up_note,
        "supplier_reference": line.supplier_reference,
        "supplier_contacted_on": line.supplier_contacted_on,
        "supplier_contact_note": line.supplier_contact_note,
        "supplier_response_on": line.supplier_response_on,
        "supplier_response_note": line.supplier_response_note,
        "follow_up_updated_at": line.follow_up_updated_at,
    }
