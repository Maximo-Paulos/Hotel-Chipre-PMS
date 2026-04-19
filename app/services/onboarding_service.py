"""
Onboarding service layer.

Tracks completion of required setup steps and produces a status structure that
the API and dashboard gating can use.
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.models.onboarding import OnboardingState
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.schemas.onboarding import (
    DepositPolicyPayload,
    HotelIdentityPayload,
    OTAChannelsPayload,
    OwnerPayload,
    PaymentMethodsPayload,
    RoomInput,
    StaffMember,
    SubscriptionChoicePayload,
)
from app.schemas.room import RoomCategoryCreate
from app.services.subscription_entitlements import (
    change_subscription_plan,
    get_subscription_snapshot,
    start_trial,
)


class OnboardingError(Exception):
    """Raised when onboarding preconditions are not met."""


ALLOWED_SUBSCRIPTION_PLANS = {"starter", "pro", "ultra"}
WRITE_ENABLED_SUBSCRIPTION_STATUSES = {"active", "trialing", "demo", "comped"}


def resolve_hotel_id(db: Session, provided: Optional[int] = None) -> int:
    """Return the current hotel id; requires explicit selection."""
    if provided is None:
        raise OnboardingError("hotel_id is required")
    config = db.get(HotelConfiguration, provided)
    if not config:
        config = HotelConfiguration(id=provided)
        db.add(config)
        db.flush()
    return provided


def get_or_create_state(db: Session, hotel_id: int) -> OnboardingState:
    state = db.query(OnboardingState).filter(OnboardingState.hotel_id == hotel_id).first()
    if not state:
        state = OnboardingState(hotel_id=hotel_id)
        db.add(state)
        db.flush()
    return state


def _get_or_create_config(db: Session, hotel_id: int) -> HotelConfiguration:
    config = db.get(HotelConfiguration, hotel_id)
    if config:
        return config
    config = HotelConfiguration(id=hotel_id)
    db.add(config)
    db.flush()
    return config


def _merge_extra_policies(config: HotelConfiguration, **updates) -> None:
    current = config.get_extra_policies()
    current.update(updates)
    config.set_extra_policies(current)


def _serialize_categories(db: Session, hotel_id: int) -> list[dict]:
    categories = db.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).order_by(RoomCategory.id.asc()).all()
    return [
        {
            "name": category.name,
            "code": category.code,
            "description": category.description,
            "base_price_per_night": category.base_price_per_night,
            "max_occupancy": category.max_occupancy,
            "amenities": category.amenities,
        }
        for category in categories
    ]


def _serialize_rooms(db: Session, hotel_id: int) -> list[dict]:
    rooms = db.query(Room).filter(Room.hotel_id == hotel_id).order_by(Room.id.asc()).all()
    return [
        {
            "room_number": room.room_number,
            "floor": room.floor,
            "category_code": room.category.code if room.category else None,
        }
        for room in rooms
    ]


def _summarize_provider_payload(payload: dict | None, provider_names: tuple[str, ...]) -> dict:
    raw = payload or {}
    summary: dict[str, dict] = {}
    for provider_name in provider_names:
        provider = raw.get(provider_name) or {}
        credentials = provider.get("credentials") or {}
        non_empty_credential_fields = sorted(
            [key for key, value in credentials.items() if isinstance(value, str) and value.strip()]
        )
        summary[provider_name] = {
            "enabled": bool(provider.get("enabled")),
            "has_credentials": bool(non_empty_credential_fields),
            "credential_fields": non_empty_credential_fields,
        }
    return summary


def _current_subscription_context(db: Session, hotel_id: int) -> dict:
    snapshot = get_subscription_snapshot(db, hotel_id)
    if snapshot.get("dirty"):
        db.flush()
    return {
        "plan": snapshot["plan"],
        "status": snapshot["status"],
        "room_limit": snapshot["room_limit"],
        "staff_limit": snapshot["staff_limit"],
        "can_write": snapshot["can_write"],
    }


def _build_finish_gates(status_payload: dict, actor_role: str | None = None) -> dict:
    missing: list[str] = []

    if actor_role != "owner":
        missing.append("owner_role")
    if not status_payload["steps"].get("identity"):
        missing.append("hotel_identity")
    if status_payload["counts"]["categories"] < 1:
        missing.append("categories")
    if status_payload["counts"]["rooms"] < 1:
        missing.append("rooms")
    if status_payload["counts"]["staff"] < 1:
        missing.append("staff")

    current_subscription = status_payload.get("current_subscription") or {}
    if current_subscription.get("status") not in WRITE_ENABLED_SUBSCRIPTION_STATUSES:
        missing.append("subscription_status")

    for step_name, blocker_name in {
        "policy": "policy",
        "payments": "payments",
        "ota": "ota",
        "subscription": "subscription_choice",
    }.items():
        if not status_payload["steps"].get(step_name):
            missing.append(blocker_name)

    return {"can_finish": len(missing) == 0, "missing": missing}


def _status_from_state(db: Session, state: OnboardingState, actor_role: str | None = None) -> dict:
    staff_list = state.get_staff()
    categories = _serialize_categories(db, state.hotel_id)
    rooms = _serialize_rooms(db, state.hotel_id)
    current_subscription = _current_subscription_context(db, state.hotel_id)

    owner_done = bool(state.owner_name and state.owner_email)
    categories_done = len(categories) > 0
    rooms_done = len(rooms) > 0
    staff_done = len(staff_list) > 0
    identity_done = state.identity_set and bool(state.get_hotel_identity())
    policy_done = state.policy_set and bool(state.get_deposit_policy())
    payments_done = state.payments_set and bool(state.get_payment_methods())
    ota_done = state.ota_set and bool(state.get_ota_channels())
    subscription_done = state.subscription_set and bool(state.get_subscription_choice())

    steps = {
        "owner": owner_done,
        "identity": identity_done,
        "categories": categories_done,
        "rooms": rooms_done,
        "policy": policy_done,
        "payments": payments_done,
        "ota": ota_done,
        "subscription": subscription_done,
        "staff": staff_done,
        "finish": state.finished,
    }
    completed = all(
        [
            owner_done,
            identity_done,
            categories_done,
            rooms_done,
            policy_done,
            payments_done,
            ota_done,
            subscription_done,
            staff_done,
            state.finished,
        ]
    )

    missing_steps = [name for name, done in steps.items() if not done]

    status_payload = {
        "hotel_id": state.hotel_id,
        "completed": completed,
        "steps": steps,
        "missing_steps": missing_steps,
        "counts": {
            "categories": len(categories),
            "rooms": len(rooms),
            "staff": len(staff_list),
        },
        "owner": None,
        "hotel_identity": state.get_hotel_identity() or None,
        "deposit_policy": state.get_deposit_policy() or None,
        "payment_methods": _summarize_provider_payload(
            state.get_payment_methods(),
            ("mercado_pago", "paypal", "stripe"),
        ),
        "ota_channels": _summarize_provider_payload(
            state.get_ota_channels(),
            ("booking", "expedia", "despegar"),
        ),
        "subscription_choice": state.get_subscription_choice() or None,
        "current_subscription": current_subscription,
        "categories": categories,
        "rooms": rooms,
        "staff": staff_list,
    }
    if owner_done:
        status_payload["owner"] = {
            "name": state.owner_name,
            "email": state.owner_email,
            "phone": state.owner_phone,
            "role": state.owner_role,
        }
    if actor_role is not None:
        status_payload["gates"] = _build_finish_gates(status_payload, actor_role)
    return status_payload


def get_status(db: Session, hotel_id: Optional[int] = None, actor_role: str | None = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    return _status_from_state(db, state, actor_role=actor_role)


def can_finish_onboarding(db: Session, hotel_id: Optional[int] = None, actor_role: str | None = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    status_payload = _status_from_state(db, state, actor_role=actor_role)
    return status_payload["gates"]


def set_owner(db: Session, payload: OwnerPayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    config = _get_or_create_config(db, hid)
    state.owner_name = payload.name
    state.owner_email = payload.email
    state.owner_phone = payload.phone
    state.owner_role = payload.role
    config.owner_email = payload.email
    db.flush()
    return _status_from_state(db, state)


def set_hotel_identity(db: Session, payload: HotelIdentityPayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    config = _get_or_create_config(db, hid)

    identity_payload = payload.model_dump()
    state.set_hotel_identity(identity_payload)
    state.identity_set = True

    config.hotel_name = payload.name
    config.hotel_timezone = payload.timezone
    config.default_currency = payload.currency
    _merge_extra_policies(
        config,
        languages=payload.languages,
        jurisdiction_code=payload.jurisdiction_code,
    )
    db.flush()
    return _status_from_state(db, state)


def set_deposit_policy(db: Session, payload: DepositPolicyPayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    config = _get_or_create_config(db, hid)

    policy_payload = payload.model_dump()
    policy_payload["allow_cancellation_after_checkin"] = False
    state.set_deposit_policy(policy_payload)
    state.policy_set = True

    config.deposit_percentage = payload.deposit_percentage
    config.free_cancellation_hours = payload.free_cancellation_hours
    config.cancellation_penalty_percentage = payload.cancellation_penalty_percentage
    config.allow_cancellation_after_checkin = False
    config.enable_full_payment = True
    config.enable_deposit_payment = True
    db.flush()
    return _status_from_state(db, state)


def upsert_payment_methods(db: Session, payload: PaymentMethodsPayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    config = _get_or_create_config(db, hid)

    payment_payload = payload.model_dump()
    state.set_payment_methods(payment_payload)
    state.payments_set = True

    config.enable_mercado_pago = payload.mercado_pago.enabled
    config.enable_paypal = payload.paypal.enabled
    config.enable_credit_card = payload.stripe.enabled
    _merge_extra_policies(
        config,
        payment_methods={
            "mercado_pago": {"enabled": payload.mercado_pago.enabled},
            "paypal": {"enabled": payload.paypal.enabled},
            "stripe": {"enabled": payload.stripe.enabled},
        },
    )
    db.flush()
    return _status_from_state(db, state)


def upsert_ota_channels(db: Session, payload: OTAChannelsPayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    config = _get_or_create_config(db, hid)

    ota_payload = payload.model_dump()
    state.set_ota_channels(ota_payload)
    state.ota_set = True

    config.enable_booking_sync = payload.booking.enabled
    config.enable_expedia_sync = payload.expedia.enabled
    _merge_extra_policies(
        config,
        ota_channels={
            "booking": {"enabled": payload.booking.enabled},
            "expedia": {"enabled": payload.expedia.enabled},
            "despegar": {"enabled": payload.despegar.enabled},
        },
    )
    db.flush()
    return _status_from_state(db, state)


def set_subscription_choice(db: Session, payload: SubscriptionChoicePayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)

    if payload.plan_code not in ALLOWED_SUBSCRIPTION_PLANS:
        raise OnboardingError("Plan de suscripción inválido")

    payment_methods = state.get_payment_methods()
    stripe_enabled = bool((payment_methods.get("stripe") or {}).get("enabled"))
    if stripe_enabled and payload.plan_code not in {"pro", "ultra"}:
        raise OnboardingError("Stripe solo está disponible para planes Pro o Ultra")

    if payload.start_trial:
        if payload.plan_code == "starter":
            raise OnboardingError("La prueba gratis solo está disponible para planes pagos")
        start_trial(db, hid, plan_code=payload.plan_code, actor={"source": "onboarding"})
    else:
        change_subscription_plan(db, hid, payload.plan_code)

    choice_payload = payload.model_dump()
    state.set_subscription_choice(choice_payload)
    state.subscription_set = True
    db.flush()
    return _status_from_state(db, state)


def upsert_categories(
    db: Session,
    categories: Iterable[RoomCategoryCreate],
    hotel_id: Optional[int] = None,
) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)

    existing = {c.code.lower(): c for c in db.query(RoomCategory).filter(RoomCategory.hotel_id == hid).all()}
    created = 0
    updated = 0
    for cat in categories:
        data = cat.model_dump()
        code_key = data["code"].lower()
        if code_key in existing:
            obj = existing[code_key]
            for field, value in data.items():
                setattr(obj, field, value)
            updated += 1
        else:
            obj = RoomCategory(hotel_id=hid, **data)
            db.add(obj)
            created += 1
    db.flush()

    status_payload = _status_from_state(db, state)
    status_payload["created"] = created
    status_payload["updated"] = updated
    return status_payload


def upsert_rooms(
    db: Session,
    rooms: Iterable[RoomInput],
    hotel_id: Optional[int] = None,
) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)

    categories = {c.code.lower(): c for c in db.query(RoomCategory).filter(RoomCategory.hotel_id == hid).all()}
    missing_codes = sorted({r.category_code.lower() for r in rooms if r.category_code.lower() not in categories})
    if missing_codes:
        raise OnboardingError(f"Missing categories for codes: {', '.join(missing_codes)}")

    existing_rooms = {r.room_number: r for r in db.query(Room).filter(Room.hotel_id == hid).all()}
    created = 0
    updated = 0

    for room_payload in rooms:
        code_key = room_payload.category_code.lower()
        category_id = categories[code_key].id
        if room_payload.room_number in existing_rooms:
            room = existing_rooms[room_payload.room_number]
            room.floor = room_payload.floor
            room.category_id = category_id
            room.is_active = True
            if room.status is None:
                room.status = RoomStatusEnum.AVAILABLE.value
            updated += 1
        else:
            room = Room(
                hotel_id=hid,
                room_number=room_payload.room_number,
                floor=room_payload.floor,
                category_id=category_id,
                status=RoomStatusEnum.AVAILABLE.value,
            )
            db.add(room)
            created += 1

    db.flush()
    status_payload = _status_from_state(db, state)
    status_payload["created"] = created
    status_payload["updated"] = updated
    return status_payload


def store_staff(
    db: Session,
    staff: Iterable[StaffMember],
    hotel_id: Optional[int] = None,
) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    staff_list = [member.model_dump() for member in staff]
    state.set_staff(staff_list)
    db.flush()
    return _status_from_state(db, state)


def finish_onboarding(db: Session, hotel_id: Optional[int] = None, actor_role: str | None = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    status_payload = _status_from_state(db, state, actor_role=actor_role)
    gates = status_payload["gates"]
    if not gates["can_finish"]:
        raise OnboardingError(f"Missing required onboarding gates: {', '.join(gates['missing'])}")

    state.finished = True
    db.flush()
    return _status_from_state(db, state, actor_role=actor_role)
