from __future__ import annotations

from datetime import date

from app.database import Base
from app.models.allocation import (
    AllocationAssignment,
    AllocationPolicyProfile,
    AllocationPolicyVersion,
    AllocationRun,
    LLMPolicySuggestion,
)
from app.models.commercial import (
    FxPolicy,
    ProductRoomCompatibility,
    RatePlan,
    RatePlanPrice,
    SellableProduct,
    TaxPolicy,
    TaxRule,
)
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.operations import (
    BillingAdjustment,
    ReservationAdjustment,
    ReservationAdjustmentKindEnum,
)
from app.models.ota_core import (
    OTAConnection,
    OTAInventoryRule,
    OTAPriceRule,
    OTAPropertyMapping,
    OTAProvider,
    OTARatePlanMapping,
    OTAReservationLink,
    OTASyncJob,
)
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.models.user import User


def test_foundation_tables_are_registered():
    required_tables = {
        "sellable_products",
        "product_room_compatibility",
        "rate_plans",
        "rate_plan_prices",
        "tax_policies",
        "tax_rules",
        "fx_policies",
        "ota_providers",
        "ota_connections",
        "ota_property_mappings",
        "ota_room_mappings",
        "ota_rate_plan_mappings",
        "ota_inventory_rules",
        "ota_price_rules",
        "ota_reservation_links",
        "ota_sync_jobs",
        "reservation_adjustments",
        "billing_adjustments",
        "allocation_policy_profiles",
        "allocation_policy_versions",
        "allocation_runs",
        "allocation_assignments",
        "llm_policy_suggestions",
    }
    assert required_tables.issubset(Base.metadata.tables.keys())


def test_foundation_models_support_hotel_scoped_commercial_and_ota_flow(db):
    hotel = HotelConfiguration(id=11, hotel_name="Hotel OTA", subscription_active=True)
    user = User(email="owner11@test.com", password_hash="hash", role="owner", is_verified=True)
    category = RoomCategory(
        hotel_id=11,
        name="Doble Bano Compartido",
        code="DBL_COMP",
        base_price_per_night=50_000.0,
        max_occupancy=2,
    )
    room = Room(
        hotel_id=11,
        room_number="201",
        floor=2,
        category=category,
        status=RoomStatusEnum.AVAILABLE,
    )
    guest = Guest(
        hotel_id=11,
        first_name="Lucia",
        last_name="Test",
        email="lucia@test.com",
        terms_accepted=True,
        nationality="Argentina",
    )
    provider = OTAProvider(code="booking", name="Booking.com", auth_type="connectivity_api", security_model="partner")
    db.add(hotel)
    db.flush()
    db.add_all([user, category, room, guest, provider])
    db.flush()

    product = SellableProduct(
        hotel_id=11,
        primary_room_category_id=category.id,
        code="doble_bano_compartido",
        name="Doble Bano Compartido",
        min_occupancy=1,
        max_occupancy=2,
        bathroom_type="shared",
    )
    db.add(product)
    db.flush()

    compatibility = ProductRoomCompatibility(
        hotel_id=11,
        sellable_product_id=product.id,
        room_category_id=category.id,
        compatibility_kind="exact",
        priority=1,
    )
    rate_plan = RatePlan(
        hotel_id=11,
        sellable_product_id=product.id,
        code="flex_booking",
        name="Flexible Booking",
        currency_code="ARS",
        min_nights_default=1,
        free_cancellation_hours=48,
        default_commission_pct=15.0,
    )
    rate_price = RatePlanPrice(
        hotel_id=11,
        rate_plan=rate_plan,
        sales_channel_code="booking",
        occupancy=2,
        currency_code="ARS",
        base_amount=50_000.0,
    )
    tax_policy = TaxPolicy(
        hotel_id=11,
        code="argentina_base",
        name="Argentina Base",
        taxes_included=False,
        apply_vat_by_default=True,
        vat_rate=21.0,
        foreign_guest_tax_exempt=True,
    )
    tax_rule = TaxRule(
        hotel_id=11,
        tax_policy=tax_policy,
        tax_code="VAT",
        tax_name="IVA",
        tax_type="percentage",
        amount=21.0,
    )
    fx_policy = FxPolicy(
        hotel_id=11,
        code="official_sell",
        name="Official Sell",
        base_currency="ARS",
        preferred_source="official",
        preferred_side="sell",
    )
    db.add_all([compatibility, rate_plan, rate_price, tax_policy, tax_rule, fx_policy])
    db.flush()

    reservation = Reservation(
        confirmation_code="BK-0001",
        hotel_id=11,
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        sellable_product_id=product.id,
        rate_plan_id=rate_plan.id,
        tax_policy_id=tax_policy.id,
        check_in_date=date(2026, 5, 1),
        check_out_date=date(2026, 5, 3),
        total_amount=60_500.0,
        subtotal_amount=50_000.0,
        tax_amount=10_500.0,
        net_amount=50_000.0,
        amount_paid=0.0,
        deposit_amount=15_000.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        external_id="booking-ext-1",
        external_confirmation_code="BKG-CNF-1",
        arrival_time_hint="18:00",
    )
    db.add(reservation)
    db.flush()

    connection = OTAConnection(
        hotel_id=11,
        provider_id=provider.id,
        environment="sandbox",
        status="healthy",
        is_enabled=True,
        external_property_id="property-11",
    )
    db.add(connection)
    db.flush()

    ota_property = OTAPropertyMapping(
        hotel_id=11,
        provider_id=provider.id,
        connection_id=connection.id,
        external_property_id="property-11",
        external_property_name="Hotel OTA",
    )
    ota_rate_plan = OTARatePlanMapping(
        hotel_id=11,
        provider_id=provider.id,
        connection_id=connection.id,
        rate_plan_id=rate_plan.id,
        external_rate_plan_id="rate-11",
        external_rate_plan_name="Flexible",
    )
    inventory_rule = OTAInventoryRule(
        hotel_id=11,
        provider_id=provider.id,
        rate_plan_id=rate_plan.id,
        stay_date=date(2026, 5, 1),
        allotment=3,
        min_stay=1,
    )
    price_rule = OTAPriceRule(
        hotel_id=11,
        provider_id=provider.id,
        rate_plan_id=rate_plan.id,
        stay_date=date(2026, 5, 1),
        occupancy=2,
        currency_code="ARS",
        gross_amount=60_500.0,
        tax_amount=10_500.0,
        commission_pct=15.0,
    )
    ota_link = OTAReservationLink(
        hotel_id=11,
        provider_id=provider.id,
        connection_id=connection.id,
        reservation_id=reservation.id,
        rate_plan_id=rate_plan.id,
        external_reservation_id="booking-ext-1",
        external_confirmation_code="BKG-CNF-1",
        sync_status="synced",
        currency_code="ARS",
        gross_total=60_500.0,
    )
    ota_job = OTASyncJob(
        hotel_id=11,
        provider_id=provider.id,
        connection_id=connection.id,
        job_type="pull_reservations",
    )
    db.add_all([ota_property, ota_rate_plan, inventory_rule, price_rule, ota_link, ota_job])
    db.flush()

    adjustment = ReservationAdjustment(
        hotel_id=11,
        reservation_id=reservation.id,
        ota_reservation_link_id=ota_link.id,
        kind=ReservationAdjustmentKindEnum.UPGRADE,
        status="draft",
        amount_delta=12_000.0,
        currency_code="ARS",
    )
    transaction = Transaction(
        hotel_id=11,
        reservation_id=reservation.id,
        amount=12_000.0,
        gross_amount=12_000.0,
        net_amount=12_000.0,
        currency="ARS",
        provider_code="mercado_pago",
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        payment_method=PaymentMethodEnum.MERCADO_PAGO,
        status=TransactionStatusEnum.PENDING,
    )
    db.add_all([adjustment, transaction])
    db.flush()

    billing_adjustment = BillingAdjustment(
        hotel_id=11,
        reservation_id=reservation.id,
        reservation_adjustment_id=adjustment.id,
        adjustment_type="charge",
        amount=12_000.0,
        currency_code="ARS",
        total_amount=12_000.0,
    )
    policy_profile = AllocationPolicyProfile(hotel_id=11, code="default", name="Default")
    db.add_all([billing_adjustment, policy_profile])
    db.flush()

    llm_suggestion = LLMPolicySuggestion(
        hotel_id=11,
        profile_id=policy_profile.id,
        suggestion_type="weights",
        status="draft",
        source_model="gemma",
        suggested_policy_json='{"prefer_exact_match": 1.0}',
    )
    db.add(llm_suggestion)
    db.flush()

    policy_version = AllocationPolicyVersion(
        hotel_id=11,
        profile_id=policy_profile.id,
        version_number=1,
        source="manual",
        weights_json='{"prefer_exact_match": 1.0}',
        created_by_user_id=user.id,
    )
    allocation_run = AllocationRun(
        hotel_id=11,
        policy_version_id=policy_version.id,
        trigger_type="new_reservation",
        status="pending",
    )
    db.add_all([policy_version, allocation_run])
    db.flush()

    assignment = AllocationAssignment(
        hotel_id=11,
        allocation_run_id=allocation_run.id,
        reservation_id=reservation.id,
        room_id=room.id,
        sellable_product_id=product.id,
        status="proposed",
    )
    db.add(assignment)
    db.commit()

    saved = db.get(Reservation, reservation.id)
    assert saved.sellable_product_id == product.id
    assert saved.rate_plan_id == rate_plan.id
    assert saved.source_provider_code == "booking"
    assert db.query(OTAReservationLink).filter_by(reservation_id=reservation.id).one().external_reservation_id == "booking-ext-1"
    assert db.query(ReservationAdjustment).filter_by(reservation_id=reservation.id).one().amount_delta == 12_000.0
    assert db.query(AllocationAssignment).filter_by(reservation_id=reservation.id).one().room_id == room.id


def test_other_ota_source_can_keep_exact_provider_code(db):
    hotel = HotelConfiguration(id=21, hotel_name="Hotel Source", subscription_active=True)
    guest = Guest(hotel_id=21, first_name="Ana", last_name="OTA", terms_accepted=True)
    category = RoomCategory(hotel_id=21, name="Base", code="BASE", base_price_per_night=100.0, max_occupancy=2)
    db.add(hotel)
    db.flush()
    db.add_all([guest, category])
    db.flush()

    reservation = Reservation(
        confirmation_code="DSP-1",
        hotel_id=21,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 2),
        total_amount=100.0,
        amount_paid=0.0,
        deposit_amount=0.0,
        source=ReservationSourceEnum.OTHER_OTA,
        source_provider_code="despegar",
    )
    db.add(reservation)
    db.commit()

    saved = db.get(Reservation, reservation.id)
    assert saved.source == ReservationSourceEnum.OTHER_OTA
    assert saved.source_provider_code == "despegar"
