from types import SimpleNamespace

from app.api.rooms import update_room
from app.dependencies.auth import AuthContext
from app.models.hotel_membership import HotelMembership
from app.models.invitation import StaffInvitation
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.schemas.onboarding import (
    DepositPolicyPayload,
    HotelIdentityPayload,
    OTAChannelsPayload,
    PaymentMethodsPayload,
    ProviderSetupPayload,
    StaffMember,
)
from app.schemas.room import RoomCategoryCreate, RoomUpdate
from app.services import onboarding_service, room_state_service
from app.services.room_catalog_service import create_category as settings_create_category


def _context() -> AuthContext:
    return AuthContext(
        hotel_id=1,
        user_id=101,
        user_email="owner@example.com",
        user_role="manager",
        is_verified=True,
        permissions=set(),
    )


def test_generic_room_status_patch_projects_event_and_reallocates(db, hotel_config, monkeypatch):
    category = RoomCategory(hotel_id=1, name="Standard", code="STD", base_price_per_night=100, max_occupancy=2)
    db.add(category)
    db.flush()
    room = Room(hotel_id=1, room_number="101", floor=1, category_id=category.id, status=RoomStatusEnum.AVAILABLE)
    db.add(room)
    db.flush()
    events = []
    allocations = []

    monkeypatch.setattr(room_state_service, "project_room_state_event", lambda *args: events.append(args))
    monkeypatch.setattr(
        room_state_service,
        "run_persisted_allocation",
        lambda *args, **kwargs: allocations.append(kwargs) or SimpleNamespace(
            run=SimpleNamespace(id=1, status="completed"),
            solver_result=SimpleNamespace(assignments=[], unassigned_reservations=[], moved_reservations=[], objective_value=0, error=None),
        ),
    )

    result = update_room(
        room.id,
        RoomUpdate(status=RoomStatusEnum.BLOCKED, notes="mantenimiento"),
        db=db,
        context=_context(),
    )

    assert result.status == RoomStatusEnum.BLOCKED
    assert events and events[0][1:3] == (room.id, "blocked")
    assert allocations and allocations[0]["hotel_id"] == 1


def test_onboarding_staff_creates_real_invitation_without_email(db, hotel_config):
    owner = User(id=101, email="owner@example.com", password_hash="test", role="owner", is_verified=True)
    db.add(owner)
    db.flush()
    onboarding_service.set_owner(
        db,
        onboarding_service.OwnerPayload(name="Owner", email=owner.email, role="Owner"),
        hotel_id=1,
    )

    onboarding_service.store_staff(
        db,
        [StaffMember(name="Lucía", role="Front desk", email="lucia@example.com")],
        hotel_id=1,
        actor_user_id=owner.id,
        actor_email=owner.email,
    )

    invited = db.query(User).filter(User.email == "lucia@example.com").one()
    membership = db.query(HotelMembership).filter_by(hotel_id=1, user_id=invited.id).one()
    invitation = db.query(StaffInvitation).filter_by(hotel_id=1, email="lucia@example.com").one()
    assert membership.role == "receptionist"
    assert membership.status == "invited"
    assert invitation.status == "pending"


def test_onboarding_and_settings_categories_use_same_domain_shape(db, hotel_config):
    payload = RoomCategoryCreate(
        name="Suite", code="STE", description="Balcony", base_price_per_night=250, max_occupancy=4, amenities="wifi",
    )
    settings_category = settings_create_category(db, hotel_id=1, data=payload)
    db.commit()

    onboarding_service.upsert_categories(db, [payload], hotel_id=2)
    onboarding_category = db.query(RoomCategory).filter_by(hotel_id=2, code="STE").one()

    assert {
        "name": settings_category.name,
        "code": settings_category.code,
        "base_price_per_night": float(settings_category.base_price_per_night),
        "max_occupancy": settings_category.max_occupancy,
        "amenities": settings_category.amenities,
    } == {
        "name": onboarding_category.name,
        "code": onboarding_category.code,
        "base_price_per_night": float(onboarding_category.base_price_per_night),
        "max_occupancy": onboarding_category.max_occupancy,
        "amenities": onboarding_category.amenities,
    }


def test_onboarding_configuration_steps_update_authority_columns_only(db, hotel_config):
    hotel_config.enable_full_payment = False
    hotel_config.enable_deposit_payment = False

    onboarding_service.set_hotel_identity(
        db,
        HotelIdentityPayload(
            name="Hotel Authority",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            languages=["es", "en"],
            jurisdiction_code="UY",
        ),
        hotel_id=1,
    )
    onboarding_service.set_deposit_policy(
        db,
        DepositPolicyPayload(
            deposit_percentage=25,
            free_cancellation_hours=36,
            cancellation_penalty_percentage=15,
        ),
        hotel_id=1,
    )
    onboarding_service.upsert_payment_methods(
        db,
        PaymentMethodsPayload(
            mercado_pago=ProviderSetupPayload(enabled=True),
            paypal=ProviderSetupPayload(enabled=False),
            stripe=ProviderSetupPayload(enabled=False),
        ),
        hotel_id=1,
    )
    onboarding_service.upsert_ota_channels(
        db,
        OTAChannelsPayload(
            booking=ProviderSetupPayload(enabled=False),
            expedia=ProviderSetupPayload(enabled=True),
            despegar=ProviderSetupPayload(enabled=True),
        ),
        hotel_id=1,
    )
    db.refresh(hotel_config)

    assert hotel_config.hotel_name == "Hotel Authority"
    assert hotel_config.languages == ["es", "en"]
    assert hotel_config.jurisdiction_code == "UY"
    assert hotel_config.deposit_percentage == 25
    assert hotel_config.free_cancellation_hours == 36
    assert hotel_config.cancellation_penalty_percentage == 15
    assert hotel_config.enable_mercado_pago is True
    assert hotel_config.enable_paypal is False
    assert hotel_config.enable_credit_card is False
    assert hotel_config.enable_expedia_sync is True
    assert hotel_config.enable_despegar_sync is True
    assert hotel_config.enable_full_payment is False
    assert hotel_config.enable_deposit_payment is False
