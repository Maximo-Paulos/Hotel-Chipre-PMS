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
from app.models.room import Room, RoomCategory
from app.services.room_service import active_rooms
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
from app.services.hotel_configuration_service import (
    set_deposit_policy as apply_deposit_policy,
    set_identity,
    set_ota_channels,
    set_payment_methods,
)
from app.services.staff_invitation_service import normalize_staff_role, provision_staff_invitation
from app.services.room_catalog_service import upsert_categories as upsert_catalog_categories, upsert_rooms as upsert_catalog_rooms


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


def _serialize_categories(db: Session, hotel_id: int) -> list[dict]:
    categories = (
        db.query(
            RoomCategory.name,
            RoomCategory.code,
            RoomCategory.description,
            RoomCategory.base_price_per_night,
            RoomCategory.max_occupancy,
            RoomCategory.amenities,
        )
        .filter(RoomCategory.hotel_id == hotel_id)
        .order_by(RoomCategory.id.asc())
        .all()
    )
    return [
        {
            "name": name,
            "code": code,
            "description": description,
            "base_price_per_night": base_price_per_night,
            "max_occupancy": max_occupancy,
            "amenities": amenities,
        }
        for name, code, description, base_price_per_night, max_occupancy, amenities in categories
    ]


def _serialize_rooms(db: Session, hotel_id: int) -> list[dict]:
    rooms = (
        active_rooms(db, hotel_id)
        .with_entities(Room.room_number, Room.floor, RoomCategory.code)
        .join(RoomCategory, Room.category_id == RoomCategory.id)
        .order_by(Room.id.asc())
        .all()
    )
    return [
        {
            "room_number": room_number,
            "floor": floor,
            "category_code": category_code,
        }
        for room_number, floor, category_code in rooms
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

    set_identity(
        config,
        name=payload.name,
        timezone=payload.timezone,
        currency=payload.currency,
        languages=payload.languages,
        jurisdiction_code=payload.jurisdiction_code,
    )
    db.flush()
    return _status_from_state(db, state)


def set_deposit_policy(db: Session, payload: DepositPolicyPayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    config = _get_or_create_config(db, hid)

    state.set_deposit_policy(payload.model_dump())
    state.policy_set = True

    apply_deposit_policy(
        config,
        deposit_percentage=payload.deposit_percentage,
        free_cancellation_hours=payload.free_cancellation_hours,
        cancellation_penalty_percentage=payload.cancellation_penalty_percentage,
    )
    db.flush()
    return _status_from_state(db, state)


def upsert_payment_methods(db: Session, payload: PaymentMethodsPayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    config = _get_or_create_config(db, hid)

    payment_payload = payload.model_dump()
    state.set_payment_methods(payment_payload)
    state.payments_set = True

    set_payment_methods(
        config,
        mercado_pago=payload.mercado_pago.enabled,
        paypal=payload.paypal.enabled,
        credit_card=payload.stripe.enabled,
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

    set_ota_channels(
        config,
        booking=payload.booking.enabled,
        expedia=payload.expedia.enabled,
        despegar=payload.despegar.enabled,
    )
    db.flush()
    return _status_from_state(db, state)


def set_subscription_choice(db: Session, payload: SubscriptionChoicePayload, hotel_id: Optional[int] = None) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)

    if payload.plan_code not in ALLOWED_SUBSCRIPTION_PLANS:
        raise OnboardingError("Plan de suscripción inválido")

    config = _get_or_create_config(db, hid)
    stripe_enabled = bool(config.enable_credit_card)
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

    created, updated = upsert_catalog_categories(db, hotel_id=hid, categories=categories)

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

    try:
        created, updated = upsert_catalog_rooms(db, hotel_id=hid, rooms=rooms)
    except ValueError as exc:
        raise OnboardingError(str(exc)) from exc
    status_payload = _status_from_state(db, state)
    status_payload["created"] = created
    status_payload["updated"] = updated
    return status_payload


def store_staff(
    db: Session,
    staff: Iterable[StaffMember],
    hotel_id: Optional[int] = None,
    actor_user_id: int | None = None,
    actor_email: str | None = None,
) -> dict:
    hid = resolve_hotel_id(db, hotel_id)
    state = get_or_create_state(db, hid)
    staff_members = list(staff)
    staff_list = [member.model_dump() for member in staff_members]
    state.set_staff(staff_list)
    inviter_email = actor_email or state.owner_email
    if inviter_email:
        for member in staff_members:
            if not member.email:
                continue
            try:
                normalized_role = normalize_staff_role(member.role)
                provision_staff_invitation(
                    db,
                    hotel_id=hid,
                    email=member.email,
                    role=normalized_role,
                    inviter_user_id=actor_user_id,
                    inviter_email=inviter_email,
                )
            except ValueError as exc:
                raise OnboardingError(str(exc)) from exc
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
