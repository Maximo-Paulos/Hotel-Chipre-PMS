from datetime import date

from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationPolicyProfile,
    AllocationPolicyVersion,
    AllocationRun,
    AllocationRunStatusEnum,
    LLMFeedbackEvent,
    LLMPolicySuggestion,
    LLMPolicySuggestionStatusEnum,
    ManualOverrideReason,
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
from app.models.operations import (
    BillingAdjustment,
    BillingAdjustmentTypeEnum,
    ReservationAdjustment,
    ReservationAdjustmentKindEnum,
    ReservationAdjustmentStatusEnum,
    ReservationStatusHistory,
    RoomMoveEvent,
    RoomMoveTypeEnum,
)
from app.models.ota_core import (
    OTACommissionRule,
    OTAConnection,
    OTAConnectionStatusEnum,
    OTACurrencyRate,
    OTAPropertyMapping,
    OTAProvider,
    OTAPriceRule,
    OTARatePlanMapping,
    OTAReservationLink,
    OTAReservationLifecycleEnum,
    OTARoomMapping,
    OTASyncEvent,
    OTASyncJob,
    OTASyncJobStatusEnum,
)
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum


def test_commercial_foundation_links_into_reservations(db, hotel_config, sample_categories, sample_rooms, sample_guest):
    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="DBL_SHARED",
        name="Doble bano compartido",
        min_occupancy=1,
        max_occupancy=2,
        bathroom_type="shared",
    )
    db.add(product)
    db.flush()

    db.add(
        ProductRoomCompatibility(
            hotel_id=hotel_config.id,
            sellable_product_id=product.id,
            room_category_id=sample_categories[0].id,
            compatibility_kind="exact",
            priority=10,
        )
    )
    db.add(
        ProductRoomCompatibility(
            hotel_id=hotel_config.id,
            sellable_product_id=product.id,
            room_category_id=sample_categories[1].id,
            compatibility_kind="upgrade_fallback",
            priority=50,
            price_adjustment_type="percentage",
            price_adjustment_value=10.0,
        )
    )

    rate_plan = RatePlan(
        hotel_id=hotel_config.id,
        sellable_product_id=product.id,
        code="FLEX",
        name="Flexible",
        currency_code="ARS",
        min_nights_default=1,
        free_cancellation_hours=24,
        default_commission_pct=15.0,
    )
    db.add(rate_plan)
    db.flush()

    db.add(
        RatePlanPrice(
            hotel_id=hotel_config.id,
            rate_plan_id=rate_plan.id,
            sales_channel_code="booking",
            occupancy=2,
            currency_code="ARS",
            base_amount=50000.0,
        )
    )

    tax_policy = TaxPolicy(
        hotel_id=hotel_config.id,
        code="DEFAULT",
        name="Politica fiscal base",
        taxes_included=True,
        apply_vat_by_default=True,
        vat_rate=21.0,
        foreign_guest_tax_exempt=True,
    )
    db.add(tax_policy)
    db.flush()

    db.add(
        TaxRule(
            hotel_id=hotel_config.id,
            tax_policy_id=tax_policy.id,
            channel_code="booking",
            guest_scope="local",
            tax_code="IVA",
            tax_name="IVA",
            tax_type="percentage",
            amount=21.0,
        )
    )
    db.add(
        FxPolicy(
            hotel_id=hotel_config.id,
            code="OFFICIAL_SELL",
            name="Dolar oficial venta",
            base_currency="ARS",
            preferred_source="official",
            preferred_side="sell",
        )
    )

    reservation = Reservation(
        confirmation_code="RES-FOUND-001",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        rate_plan_id=rate_plan.id,
        tax_policy_id=tax_policy.id,
        check_in_date=date(2026, 5, 1),
        check_out_date=date(2026, 5, 3),
        total_amount=100000.0,
        subtotal_amount=82644.63,
        tax_amount=17355.37,
        net_amount=100000.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    assert reservation.sellable_product.code == "DBL_SHARED"
    assert reservation.rate_plan.code == "FLEX"
    assert reservation.tax_policy.code == "DEFAULT"
    assert {compat.room_category_id for compat in product.compatibilities} == {
        sample_categories[0].id,
        sample_categories[1].id,
    }


def test_ota_core_foundation_supports_channel_mappings_and_sync(db, hotel_config, sample_categories):
    provider = OTAProvider(
        code="booking",
        name="Booking.com",
        auth_type="connectivity_api",
        security_model="partner_credentials",
    )
    db.add(provider)
    db.flush()

    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="DBL_SHARED",
        name="Doble bano compartido",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    rate_plan = RatePlan(
        hotel_id=hotel_config.id,
        sellable_product_id=product.id,
        code="BOOKING_FLEX",
        name="Booking Flexible",
    )
    db.add(rate_plan)
    db.flush()

    connection = OTAConnection(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        environment="sandbox",
        status=OTAConnectionStatusEnum.HEALTHY,
        external_account_id="acct-001",
        external_property_id="property-001",
    )
    db.add(connection)
    db.flush()

    db.add(
        OTAPropertyMapping(
            hotel_id=hotel_config.id,
            provider_id=provider.id,
            connection_id=connection.id,
            external_property_id="property-001",
            external_property_name="Mi Hotel",
        )
    )
    db.add(
        OTARoomMapping(
            hotel_id=hotel_config.id,
            provider_id=provider.id,
            connection_id=connection.id,
            sellable_product_id=product.id,
            room_category_id=sample_categories[0].id,
            external_room_type_id="room-std-shared",
            external_room_type_name="Shared Double",
        )
    )
    db.add(
        OTARatePlanMapping(
            hotel_id=hotel_config.id,
            provider_id=provider.id,
            connection_id=connection.id,
            rate_plan_id=rate_plan.id,
            external_rate_plan_id="plan-flex",
            external_rate_plan_name="Flexible",
        )
    )
    db.add(
        OTAPriceRule(
            hotel_id=hotel_config.id,
            provider_id=provider.id,
            rate_plan_id=rate_plan.id,
            stay_date=date(2026, 5, 1),
            occupancy=2,
            currency_code="ARS",
            gross_amount=50000.0,
            commission_pct=15.0,
        )
    )
    db.add(
        OTACommissionRule(
            hotel_id=hotel_config.id,
            provider_id=provider.id,
            rate_plan_id=rate_plan.id,
            commission_pct=15.0,
            payout_model="agency",
        )
    )
    db.add(
        OTACurrencyRate(
            hotel_id=hotel_config.id,
            provider_id=provider.id,
            base_currency="USD",
            quote_currency="ARS",
            rate=950.0,
            source="official",
        )
    )
    db.flush()

    sync_job = OTASyncJob(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        connection_id=connection.id,
        job_type="push_rates",
        status=OTASyncJobStatusEnum.RUNNING,
    )
    db.add(sync_job)
    db.flush()

    ota_link = OTAReservationLink(
        hotel_id=hotel_config.id,
        provider_id=provider.id,
        connection_id=connection.id,
        rate_plan_id=rate_plan.id,
        external_reservation_id="BKG-5001",
        external_confirmation_code="CONF-5001",
        provider_state=OTAReservationLifecycleEnum.CONFIRMED,
        sync_status="synced",
        currency_code="USD",
        gross_total=120.0,
        commission_total=18.0,
    )
    db.add(ota_link)
    db.add(
        OTASyncEvent(
            job_id=sync_job.id,
            hotel_id=hotel_config.id,
            provider_id=provider.id,
            event_type="request",
            result="ok",
            http_status=200,
        )
    )
    db.commit()

    saved_link = db.query(OTAReservationLink).filter_by(external_reservation_id="BKG-5001").one()
    assert saved_link.provider.code == "booking"
    assert saved_link.connection.status == OTAConnectionStatusEnum.HEALTHY
    assert db.query(OTASyncEvent).filter_by(job_id=sync_job.id).count() == 1


def test_allocation_and_operations_foundation_capture_manual_resolution(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    reservation = Reservation(
        confirmation_code="RES-FOUND-002",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 4),
        total_amount=90000.0,
        subtotal_amount=90000.0,
        net_amount=90000.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.OTHER_OTA,
        source_provider_code="despegar",
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    profile = AllocationPolicyProfile(
        hotel_id=hotel_config.id,
        code="DEFAULT",
        name="Politica base",
    )
    db.add(profile)
    db.flush()

    version = AllocationPolicyVersion(
        hotel_id=hotel_config.id,
        profile_id=profile.id,
        version_number=1,
        source="questionnaire",
        constraints_json='{"exact_category_first": true}',
        weights_json='{"minimize_one_night_gaps": 5}',
        is_published=True,
    )
    db.add(version)
    db.flush()

    run = AllocationRun(
        hotel_id=hotel_config.id,
        policy_version_id=version.id,
        trigger_type="new_reservation",
        status=AllocationRunStatusEnum.SUCCEEDED,
        objective_score=12.5,
    )
    db.add(run)
    db.flush()

    db.add(
        AllocationAssignment(
            hotel_id=hotel_config.id,
            allocation_run_id=run.id,
            reservation_id=reservation.id,
            room_id=sample_rooms[0].id,
            status=AllocationAssignmentStatusEnum.APPLIED,
        )
    )
    override = ManualOverrideReason(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        override_type="upgrade",
        reason_code="guest_requested_private_bathroom",
        notes="Upgrade manual al check-in",
    )
    db.add(override)
    db.flush()

    adjustment = ReservationAdjustment(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        kind=ReservationAdjustmentKindEnum.OTA_CANCEL_AND_REBOOK,
        status=ReservationAdjustmentStatusEnum.APPLIED,
        reason_code="booking_upgrade_to_direct",
        amount_delta=15000.0,
        currency_code="ARS",
    )
    db.add(adjustment)
    db.flush()

    db.add(
        RoomMoveEvent(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            from_room_id=sample_rooms[0].id,
            to_room_id=sample_rooms[1].id,
            move_type=RoomMoveTypeEnum.UPGRADE,
            reason_code="guest_requested_private_bathroom",
        )
    )
    db.add(
        BillingAdjustment(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            reservation_adjustment_id=adjustment.id,
            adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
            amount=15000.0,
            currency_code="ARS",
            total_amount=15000.0,
        )
    )
    db.add(
        ReservationStatusHistory(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            from_status=ReservationStatusEnum.PENDING.value,
            to_status=ReservationStatusEnum.PENDING.value,
            reason_code="adjustment_recorded",
        )
    )
    db.add(
        LLMPolicySuggestion(
            hotel_id=hotel_config.id,
            profile_id=profile.id,
            suggestion_type="weight_update",
            status=LLMPolicySuggestionStatusEnum.DRAFT,
            source_model="gemma-4",
            suggested_policy_json='{"prefer_private_bathroom_upgrades": true}',
        )
    )
    db.add(
        LLMFeedbackEvent(
            hotel_id=hotel_config.id,
            reservation_id=reservation.id,
            allocation_run_id=run.id,
            manual_override_reason_id=override.id,
            event_type="manual_override_feedback",
            source_model="gemma-4",
        )
    )
    db.commit()

    assert db.query(ReservationAdjustment).count() == 1
    assert db.query(RoomMoveEvent).filter_by(move_type=RoomMoveTypeEnum.UPGRADE).count() == 1
    assert db.query(BillingAdjustment).filter_by(adjustment_type=BillingAdjustmentTypeEnum.CHARGE).count() == 1
    assert db.query(LLMFeedbackEvent).filter_by(manual_override_reason_id=override.id).count() == 1
