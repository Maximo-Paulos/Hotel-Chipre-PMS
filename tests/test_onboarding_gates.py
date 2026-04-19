from app.schemas.onboarding import (
    DepositPolicyPayload,
    HotelIdentityPayload,
    OwnerPayload,
    PaymentMethodsPayload,
    ProviderSetupPayload,
    StaffMember,
    SubscriptionChoicePayload,
    OTAChannelsPayload,
)
from app.schemas.room import RoomCategoryCreate
from app.schemas.onboarding import RoomInput
from app.services.onboarding_service import (
    can_finish_onboarding,
    finish_onboarding,
    get_status,
    set_deposit_policy,
    set_hotel_identity,
    set_owner,
    set_subscription_choice,
    store_staff,
    upsert_categories,
    upsert_ota_channels,
    upsert_payment_methods,
    upsert_rooms,
)
from app.services.subscription_entitlements import suspend_subscription


def _complete_setup(db):
    set_owner(db, OwnerPayload(name="Ana Manager", email="owner@test.com", phone="+54 11 5555 1111", role="Owner"), hotel_id=1)
    set_hotel_identity(
        db,
        HotelIdentityPayload(
            name="Hotel Chipre Centro",
            timezone="America/Argentina/Buenos_Aires",
            currency="ARS",
            languages=["es", "en"],
            jurisdiction_code="AR",
        ),
        hotel_id=1,
    )
    upsert_categories(
        db,
        [
            RoomCategoryCreate(
                name="Standard Doble",
                code="STD",
                description="Base double room",
                base_price_per_night=100.0,
                max_occupancy=2,
                amenities="wifi",
            )
        ],
        hotel_id=1,
    )
    upsert_rooms(db, [RoomInput(room_number="101", floor=1, category_code="STD")], hotel_id=1)
    set_deposit_policy(
        db,
        DepositPolicyPayload(
            deposit_percentage=30,
            free_cancellation_hours=48,
            cancellation_penalty_percentage=0,
        ),
        hotel_id=1,
    )
    upsert_payment_methods(
        db,
        PaymentMethodsPayload(
            mercado_pago=ProviderSetupPayload(enabled=True, credentials={"account_id": "mp-user"}),
            paypal=ProviderSetupPayload(enabled=False, credentials={}),
            stripe=ProviderSetupPayload(enabled=False, credentials={}),
        ),
        hotel_id=1,
    )
    upsert_ota_channels(
        db,
        OTAChannelsPayload(
            booking=ProviderSetupPayload(enabled=True, credentials={"account_id": "booking-user"}),
            expedia=ProviderSetupPayload(enabled=False, credentials={}),
            despegar=ProviderSetupPayload(enabled=False, credentials={}),
        ),
        hotel_id=1,
    )
    set_subscription_choice(db, SubscriptionChoicePayload(plan_code="pro", start_trial=True), hotel_id=1)
    store_staff(db, [StaffMember(name="Lucia", role="Front desk", email="lucia@example.com")], hotel_id=1)
    db.flush()


def test_can_finish_blocks_on_each_missing_gate(db, hotel_config):
    empty_gates = can_finish_onboarding(db, hotel_id=1, actor_role="co_owner")
    assert empty_gates["can_finish"] is False
    assert "owner_role" in empty_gates["missing"]
    assert "hotel_identity" in empty_gates["missing"]
    assert "categories" in empty_gates["missing"]
    assert "rooms" in empty_gates["missing"]
    assert "staff" in empty_gates["missing"]

    _complete_setup(db)
    suspend_subscription(db, hotel_id=1, reason="manual-test")
    db.flush()

    suspended_gates = can_finish_onboarding(db, hotel_id=1, actor_role="owner")
    assert suspended_gates["can_finish"] is False
    assert "subscription_status" in suspended_gates["missing"]


def test_can_finish_unlocks_when_required_gates_close(db, hotel_config):
    _complete_setup(db)

    status_payload = get_status(db, hotel_id=1, actor_role="owner")

    assert "gates" in status_payload
    assert status_payload["gates"]["can_finish"] is True
    assert status_payload["gates"]["missing"] == []


def test_finish_onboarding_succeeds_when_all_gates_are_closed(db, hotel_config):
    _complete_setup(db)

    result = finish_onboarding(db, hotel_id=1, actor_role="owner")

    assert result["completed"] is True
    assert result["steps"]["finish"] is True
    assert result["gates"]["can_finish"] is True
