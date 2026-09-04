"""Safe, field-level collaboration primitives.

The collaboration layer is intentionally smaller than the transactional PMS
domain.  It can merge drafts for fields that are explicitly listed below, but
it never becomes an alternate path for money movement or lifecycle actions.
Postgres remains the authority: callers must lock/read the current resource,
apply the validated values, and commit through the normal SQLAlchemy session.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.models.cash_register import CashSession
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.laundry_vendor import LaundryVendor
from app.models.linen import LinenItem
from app.models.reservation import Reservation
from app.models.room import Room, RoomCategory
from app.models.stock import StockItem
from app.schemas.guest import GuestUpdate
from app.schemas.hotel_config import HotelConfigUpdate
from app.schemas.reservation import ReservationUpdate
from app.schemas.room import RoomUpdate
from app.services.permission_service import (
    PERMISSION_CASH_OPERATE,
    PERMISSION_CASH_VIEW,
    PERMISSION_GUEST_READ,
    PERMISSION_GUEST_UPDATE,
    PERMISSION_HOTEL_SETTINGS_READ,
    PERMISSION_HOTEL_SETTINGS_UPDATE,
    PERMISSION_LAUNDRY_READ,
    PERMISSION_LAUNDRY_VENDOR_MANAGE,
    PERMISSION_RESERVATION_READ,
    PERMISSION_RESERVATION_UPDATE,
    PERMISSION_ROOM_READ,
    PERMISSION_ROOM_STATUS_UPDATE,
    PERMISSION_STOCK_ADMIN,
    PERMISSION_STOCK_READ,
)


COLLABORATION_MAX_FIELDS = 20
COLLABORATION_MAX_TEXT_LENGTH = 4_000


class _StockDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    sku: str | None = Field(default=None, max_length=80)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    min_quantity: Decimal | None = Field(default=None, ge=0)
    active: bool | None = None
    unit_cost: Decimal | None = Field(default=None, ge=0)


class _LinenDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    min_quantity: Decimal | None = Field(default=None, ge=0)
    active: bool | None = None


class _LaundryVendorDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_email: str | None = Field(default=None, max_length=150)
    active: bool | None = None


class _CashSessionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=COLLABORATION_MAX_TEXT_LENGTH)


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    resource_type: str
    model: type[Any]
    read_permission: str
    write_permission: str
    editable_fields: frozenset[str]
    schema_model: type[BaseModel]


@dataclass(frozen=True, slots=True)
class MergeResult:
    values: dict[str, Any]
    conflicting_fields: tuple[str, ...]


_RESERVATION_FIELDS = frozenset(
    {
        "room_id",
        "check_in_date",
        "check_out_date",
        "num_adults",
        "num_children",
        "notes",
        "arrival_time_hint",
        "reservation_comment",
        "mobility_restriction",
    }
)
_GUEST_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "document_type",
        "document_number",
        "nationality",
        "date_of_birth",
        "gender",
        "email",
        "phone",
        "address_line1",
        "address_line2",
        "city",
        "state_province",
        "postal_code",
        "country",
        "birth_place",
        "birth_country",
        "marital_status",
        "occupation",
        "special_requests",
        "observations",
    }
)
_ROOM_FIELDS = frozenset(
    {
        "room_number",
        "floor",
        "category_id",
        "score",
        "is_accessible",
        "description",
        "notes",
    }
)
_SETTINGS_FIELDS = frozenset(
    {
        "deposit_percentage",
        "enable_full_payment",
        "enable_deposit_payment",
        "enable_cash",
        "enable_mercado_pago",
        "enable_paypal",
        "enable_credit_card",
        "enable_debit_card",
        "enable_bank_transfer",
        "free_cancellation_hours",
        "cancellation_penalty_percentage",
        "allow_cancellation_after_checkin",
        "enable_booking_sync",
        "enable_expedia_sync",
        "enable_despegar_sync",
        "require_document_for_checkin",
        "require_terms_acceptance",
        "hotel_name",
        "hotel_timezone",
        "default_currency",
        "languages",
        "jurisdiction_code",
        "allow_overbooking",
        "no_show_cutoff_hours",
    }
)


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    "reservation": ResourceSpec(
        "reservation",
        Reservation,
        PERMISSION_RESERVATION_READ,
        PERMISSION_RESERVATION_UPDATE,
        _RESERVATION_FIELDS,
        ReservationUpdate,
    ),
    "guest": ResourceSpec(
        "guest",
        Guest,
        PERMISSION_GUEST_READ,
        PERMISSION_GUEST_UPDATE,
        _GUEST_FIELDS,
        GuestUpdate,
    ),
    "room": ResourceSpec(
        "room",
        Room,
        PERMISSION_ROOM_READ,
        PERMISSION_ROOM_STATUS_UPDATE,
        _ROOM_FIELDS,
        RoomUpdate,
    ),
    "stock_item": ResourceSpec(
        "stock_item",
        StockItem,
        PERMISSION_STOCK_READ,
        PERMISSION_STOCK_ADMIN,
        frozenset({"name", "sku", "unit", "min_quantity", "active", "unit_cost"}),
        _StockDraft,
    ),
    "linen_item": ResourceSpec(
        "linen_item",
        LinenItem,
        PERMISSION_LAUNDRY_READ,
        PERMISSION_LAUNDRY_VENDOR_MANAGE,
        frozenset({"name", "unit", "min_quantity", "active"}),
        _LinenDraft,
    ),
    "laundry_vendor": ResourceSpec(
        "laundry_vendor",
        LaundryVendor,
        PERMISSION_LAUNDRY_READ,
        PERMISSION_LAUNDRY_VENDOR_MANAGE,
        frozenset({"name", "contact_phone", "contact_email", "active"}),
        _LaundryVendorDraft,
    ),
    "cash_session": ResourceSpec(
        "cash_session",
        CashSession,
        PERMISSION_CASH_VIEW,
        PERMISSION_CASH_OPERATE,
        frozenset({"notes"}),
        _CashSessionDraft,
    ),
    "settings": ResourceSpec(
        "settings",
        HotelConfiguration,
        PERMISSION_HOTEL_SETTINGS_READ,
        PERMISSION_HOTEL_SETTINGS_UPDATE,
        _SETTINGS_FIELDS,
        HotelConfigUpdate,
    ),
}

_RESOURCE_ALIASES = {
    "reservation": "reservation",
    "reservations": "reservation",
    "guest": "guest",
    "guests": "guest",
    "room": "room",
    "rooms": "room",
    "stock": "stock_item",
    "stock_item": "stock_item",
    "stock-items": "stock_item",
    "linen": "linen_item",
    "linen_item": "linen_item",
    "laundry_vendor": "laundry_vendor",
    "laundry-vendor": "laundry_vendor",
    "vendor": "laundry_vendor",
    "cash_session": "cash_session",
    "cash-session": "cash_session",
    "settings": "settings",
    "hotel_settings": "settings",
    "hotel-configuration": "settings",
}


def normalize_resource_type(resource_type: str) -> str:
    normalized = str(resource_type or "").strip().lower()
    canonical = _RESOURCE_ALIASES.get(normalized)
    if canonical is None:
        raise ValueError("Unsupported collaborative resource type")
    return canonical


def get_resource_spec(resource_type: str) -> ResourceSpec:
    return RESOURCE_SPECS[normalize_resource_type(resource_type)]


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"Unsupported collaboration value: {type(value).__name__}")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=_json_default, ensure_ascii=True, allow_nan=False))


def resource_revision(values: Mapping[str, Any]) -> str:
    """Return a deterministic opaque revision for editable field values."""

    canonical = json.dumps(
        dict(values),
        default=_json_default,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def merge_field_changes(
    server_values: Mapping[str, Any],
    base_values: Mapping[str, Any],
    changes: Mapping[str, Any],
) -> MergeResult:
    """Merge non-overlapping changes and report same-field conflicts.

    A field is safe to merge when the server still equals the client's base
    value.  If the client omitted the base value for a field that already
    exists on the server, the conservative result is a conflict rather than
    silently overwriting an operator's work.
    """

    sentinel = object()
    merged = dict(server_values)
    conflicts: list[str] = []
    for field, incoming in changes.items():
        current = server_values.get(field, sentinel)
        base = base_values.get(field, sentinel)
        if current != base and incoming != current:
            conflicts.append(field)
            continue
        merged[field] = incoming
    return MergeResult(merged, tuple(sorted(set(conflicts))))


def _model_dump_for_wire(model: BaseModel) -> dict[str, Any]:
    return _json_safe(model.model_dump(exclude_unset=True, mode="json"))


def _model_dump_for_database(resource_type: str, changes: Mapping[str, Any]) -> dict[str, Any]:
    spec = get_resource_spec(resource_type)
    model = spec.schema_model.model_validate(dict(changes))
    return model.model_dump(exclude_unset=True, mode="python")


def validate_draft_changes(
    resource_type: str,
    changes: Mapping[str, Any],
    *,
    max_fields: int = COLLABORATION_MAX_FIELDS,
) -> dict[str, Any]:
    """Validate and sanitize a draft/patch against its field allowlist."""

    spec = get_resource_spec(resource_type)
    if not isinstance(changes, Mapping):
        raise ValueError("changes must be an object")
    field_limit = max(1, min(int(max_fields), 100))
    if len(changes) > field_limit:
        raise ValueError(f"A collaboration patch cannot contain more than {field_limit} fields")
    unknown = set(changes) - spec.editable_fields
    if unknown:
        field = sorted(str(value) for value in unknown)[0]
        raise ValueError(f"Field '{field}' is not editable")
    if any(not isinstance(field, str) or not field.strip() for field in changes):
        raise ValueError("Collaboration field names must be non-empty strings")

    try:
        normalized = _model_dump_for_wire(spec.schema_model.model_validate(dict(changes)))
    except ValidationError as exc:
        # Do not expose Pydantic internals or submitted values in an API error.
        first_error = exc.errors()[0] if exc.errors() else {}
        location = first_error.get("loc", ("field",))
        raise ValueError(f"Invalid collaboration value for {location[0]}") from exc

    for field, value in normalized.items():
        if isinstance(value, str) and len(value) > COLLABORATION_MAX_TEXT_LENGTH:
            raise ValueError(f"Field '{field}' exceeds the collaboration text limit")
        if isinstance(value, list) and len(value) > COLLABORATION_MAX_FIELDS:
            raise ValueError(f"Field '{field}' contains too many values")
    return normalized


def editable_resource_values(resource_type: str, resource: Any) -> dict[str, Any]:
    spec = get_resource_spec(resource_type)
    return {
        field: _json_safe(getattr(resource, field, None))
        for field in sorted(spec.editable_fields)
    }


def serialize_resource(resource_type: str, resource: Any) -> dict[str, Any]:
    """Serialize only collaboration-editable fields, never model internals."""

    return editable_resource_values(resource_type, resource)


def resource_version(resource: Any) -> int | None:
    value = getattr(resource, "version", None)
    return int(value) if isinstance(value, int) else None


def get_resource(
    db: Session,
    resource_type: str,
    resource_id: int,
    hotel_id: int,
    *,
    lock_for_update: bool = False,
) -> Any | None:
    """Load one resource with an explicit tenant predicate."""

    spec = get_resource_spec(resource_type)
    if not isinstance(resource_id, int) or resource_id <= 0:
        return None
    if spec.resource_type == "settings":
        if resource_id != hotel_id:
            return None
        query = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id)
    else:
        query = db.query(spec.model).filter(spec.model.id == resource_id)
        hotel_column = getattr(spec.model, "hotel_id", None)
        if hotel_column is None:
            return None
        query = query.filter(hotel_column == hotel_id)
        deleted_column = getattr(spec.model, "deleted_at", None)
        if deleted_column is not None:
            query = query.filter(deleted_column.is_(None))
    if lock_for_update:
        query = query.with_for_update()
    return query.one_or_none()


def apply_resource_changes(
    db: Session,
    resource_type: str,
    resource: Any,
    changes: Mapping[str, Any],
    *,
    hotel_id: int,
    user_id: int | None = None,
    actor_role: str | None = None,
) -> Any:
    """Apply already-authorized collaboration fields using domain services."""

    spec = get_resource_spec(resource_type)
    normalized = validate_draft_changes(spec.resource_type, changes)
    if not normalized:
        return resource
    db_values = _model_dump_for_database(spec.resource_type, normalized)

    if spec.resource_type == "reservation":
        from app.services.reservation_service import update_reservation_fields

        update_reservation_fields(
            db,
            resource,
            ReservationUpdate.model_validate(db_values),
            hotel_id,
            changed_by_user_id=user_id,
            actor_role=actor_role,
            client_version=resource.version,
        )
        return resource

    if spec.resource_type == "room" and "category_id" in db_values:
        category = (
            db.query(RoomCategory)
            .filter(RoomCategory.id == db_values["category_id"], RoomCategory.hotel_id == hotel_id)
            .one_or_none()
        )
        if category is None:
            raise ValueError("Room category not found")

    if spec.resource_type == "stock_item":
        from app.services.stock_service import update_stock_item

        update_stock_item(db, hotel_id=hotel_id, item_id=resource.id, **db_values)
        return resource

    if spec.resource_type == "laundry_vendor":
        from app.services.laundry_vendor_service import update_vendor

        update_vendor(db, hotel_id=hotel_id, vendor_id=resource.id, **db_values)
        return resource

    if spec.resource_type == "settings":
        from app.services.hotel_configuration_service import apply_configuration_update

        apply_configuration_update(resource, db_values)
    else:
        for field, value in db_values.items():
            setattr(resource, field, value)
    db.flush()
    return resource
