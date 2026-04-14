from __future__ import annotations

import json
from datetime import date

from app.models.allocation import AllocationExplanation
from app.models.commercial import ProductRoomCompatibility, SellableProduct
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.services.allocation_policy_service import (
    apply_policy_suggestion,
    create_policy_suggestion_draft,
    create_policy_version,
    ensure_default_policy_profile,
    ensure_default_policy_version,
    get_active_policy_settings,
    publish_policy_version,
    record_manual_override_feedback,
    review_policy_suggestion,
)
from app.services.allocation_learning_service import draft_policy_from_questionnaire
from app.services.allocation_runtime_service import get_allocation_run_details, run_persisted_allocation


def test_policy_service_seeds_default_profile_and_version(db):
    db.add(HotelConfiguration(id=61, hotel_name="Policy Hotel", subscription_active=True))
    db.flush()

    profile = ensure_default_policy_profile(db, 61)
    version = ensure_default_policy_version(db, 61)
    settings = get_active_policy_settings(db, 61)

    assert profile.code == "default"
    assert version.profile_id == profile.id
    assert settings.version.id == version.id
    assert settings.weights["prefer_exact_match"] == 500.0
    assert settings.constraints["respect_locked_assignments"] is True


def test_policy_version_publish_switches_active_version(db):
    db.add(HotelConfiguration(id=62, hotel_name="Publish Hotel", subscription_active=True))
    db.flush()

    profile = ensure_default_policy_profile(db, 62)
    default_version = ensure_default_policy_version(db, 62)
    custom_version = create_policy_version(
        db,
        hotel_id=62,
        profile_id=profile.id,
        constraints={"no_overlap": True, "allow_category_fallback": False},
        weights={"prefer_exact_match": 900, "stability": 2, "room_usage_penalty": 30, "unassigned_penalty": 20000},
        prompt_summary="Hotel wants stronger exact-match priority",
        source="manual",
        publish=False,
    )

    publish_policy_version(db, hotel_id=62, profile_id=profile.id, version_id=custom_version.id)
    settings = get_active_policy_settings(db, 62)

    assert default_version.is_published is False
    assert settings.version.id == custom_version.id
    assert settings.weights["prefer_exact_match"] == 900.0
    assert settings.constraints["allow_category_fallback"] is False


def test_record_manual_override_feedback_creates_reason_and_feedback(db, hotel_config, sample_guest, sample_categories):
    reservation = Reservation(
        confirmation_code="OVERRIDE-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 3),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=100.0,
        amount_paid=0.0,
        deposit_amount=30.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    override, feedback = record_manual_override_feedback(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        override_type="room_change",
        reason_code="vip_preference",
        notes="Mover a la mejor habitacion disponible",
        created_by_user_id=None,
        source_model="gemma-draft",
    )

    assert override.reservation_id == reservation.id
    assert override.reason_code == "vip_preference"
    assert feedback.manual_override_reason_id == override.id
    assert feedback.event_type == "manual_override"
    assert json.loads(feedback.payload_json)["override_type"] == "room_change"


def test_run_persisted_allocation_uses_published_policy_version(db, hotel_config, sample_categories, sample_rooms, sample_guest):
    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="STD_BASE_POLICY",
        name="Standard base policy",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()
    db.add(
        ProductRoomCompatibility(
            hotel_id=hotel_config.id,
            sellable_product_id=product.id,
            room_category_id=sample_categories[0].id,
            compatibility_kind="exact",
            priority=1,
        )
    )
    db.flush()

    reservation = Reservation(
        confirmation_code="ALLOC-POLICY-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 10, 1),
        check_out_date=date(2026, 10, 3),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=100.0,
        amount_paid=0.0,
        deposit_amount=30.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    profile = ensure_default_policy_profile(db, hotel_config.id)
    custom_version = create_policy_version(
        db,
        hotel_id=hotel_config.id,
        profile_id=profile.id,
        constraints={"no_overlap": True, "respect_locked_assignments": True},
        weights={"prefer_exact_match": 777, "stability": 9, "room_usage_penalty": 45, "unassigned_penalty": 20000},
        prompt_summary="Custom hotel policy",
        publish=True,
    )

    persisted = run_persisted_allocation(
        db,
        hotel_id=hotel_config.id,
        trigger_type="policy_test",
        apply=True,
        horizon_start=date(2026, 10, 1),
        horizon_end=date(2026, 10, 5),
    )
    db.commit()

    explanation = (
        db.query(AllocationExplanation)
        .filter_by(allocation_run_id=persisted.run.id, explanation_type="summary")
        .one()
    )
    assert persisted.run.policy_version_id == custom_version.id
    assert '"prefer_exact_match": 777' in explanation.details_json


def test_create_policy_suggestion_draft_stores_structured_payload(db):
    db.add(HotelConfiguration(id=63, hotel_name="Suggestion Hotel", subscription_active=True))
    db.flush()
    profile = ensure_default_policy_profile(db, 63)

    suggestion = create_policy_suggestion_draft(
        db,
        hotel_id=63,
        profile_id=profile.id,
        suggestion_type="questionnaire_ingest",
        input_summary="Hotel prioriza evitar huecos de una noche",
        suggested_policy={"weights": {"stability": 12, "prefer_exact_match": 650}},
        explanation="Borrador inicial a revisar por el hotel",
        source_model="gemma-4-draft",
    )

    assert suggestion.profile_id == profile.id
    assert suggestion.source_model == "gemma-4-draft"
    assert json.loads(suggestion.suggested_policy_json)["weights"]["stability"] == 12


def test_questionnaire_draft_creates_heuristic_policy_suggestion(db):
    db.add(HotelConfiguration(id=64, hotel_name="Questionnaire Hotel", subscription_active=True))
    db.flush()

    draft = draft_policy_from_questionnaire(
        db,
        hotel_id=64,
        business_summary="Queremos minimizar huecos y evitar mover reservas salvo necesidad.",
        prioritize_exact_match=4,
        minimize_one_night_gaps=5,
        minimize_moves=5,
        preserve_future_availability=3,
        allow_category_fallback=True,
        notes="Hotel urbano con estadias cortas",
    )

    payload = json.loads(draft.suggestion.suggested_policy_json)
    assert draft.suggestion.source_model == "questionnaire_heuristic_seed"
    assert payload["weights"]["room_usage_penalty"] > 50
    assert payload["weights"]["stability"] > 5
    assert payload["questionnaire_summary"]["notes"] == "Hotel urbano con estadias cortas"


def test_review_and_apply_policy_suggestion_creates_version_and_supersedes_previous_acceptance(db):
    db.add(HotelConfiguration(id=65, hotel_name="Review Hotel", subscription_active=True))
    db.flush()
    profile = ensure_default_policy_profile(db, 65)

    first = create_policy_suggestion_draft(
        db,
        hotel_id=65,
        profile_id=profile.id,
        suggestion_type="feedback_learning",
        input_summary="First accepted suggestion",
        suggested_policy={
            "constraints": {"no_overlap": True, "respect_locked_assignments": True, "allow_category_fallback": True},
            "weights": {"prefer_exact_match": 600, "stability": 6, "room_usage_penalty": 45, "unassigned_penalty": 10000, "fallback_priority_penalty": 20},
        },
        source_model="gemma-a",
    )
    second = create_policy_suggestion_draft(
        db,
        hotel_id=65,
        profile_id=profile.id,
        suggestion_type="feedback_learning",
        input_summary="Second accepted suggestion",
        suggested_policy={
            "constraints": {"no_overlap": True, "respect_locked_assignments": True, "allow_category_fallback": False},
            "weights": {"prefer_exact_match": 900, "stability": 7, "room_usage_penalty": 35, "unassigned_penalty": 12000, "fallback_priority_penalty": 10},
        },
        source_model="gemma-b",
    )
    db.flush()

    reviewed = review_policy_suggestion(
        db,
        hotel_id=65,
        suggestion_id=first.id,
        action="review",
        reviewed_by_user_id=None,
    )
    assert reviewed.status.value == "reviewed"

    accepted_first, first_version = apply_policy_suggestion(
        db,
        hotel_id=65,
        suggestion_id=first.id,
        created_by_user_id=None,
        publish=False,
    )
    accepted_second, second_version = apply_policy_suggestion(
        db,
        hotel_id=65,
        suggestion_id=second.id,
        created_by_user_id=None,
        publish=True,
        prompt_summary="Promote second suggestion",
    )
    db.flush()

    assert accepted_first.status.value == "superseded"
    assert accepted_second.status.value == "accepted"
    assert second_version.is_published is True
    settings = get_active_policy_settings(db, 65)
    assert settings.version.id == second_version.id
    assert settings.constraints["allow_category_fallback"] is False
    assert first_version.version_number < second_version.version_number


def test_get_allocation_run_details_returns_assignment_explanations(db, hotel_config, sample_categories, sample_rooms, sample_guest):
    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="DETAILS_POLICY",
        name="Details policy",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()
    db.add(
        ProductRoomCompatibility(
            hotel_id=hotel_config.id,
            sellable_product_id=product.id,
            room_category_id=sample_categories[0].id,
            compatibility_kind="exact",
            priority=1,
        )
    )
    reservation = Reservation(
        confirmation_code="ALLOC-DETAIL-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 12, 1),
        check_out_date=date(2026, 12, 3),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=100.0,
        amount_paid=0.0,
        deposit_amount=30.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    persisted = run_persisted_allocation(
        db,
        hotel_id=hotel_config.id,
        trigger_type="detail_test",
        apply=True,
        horizon_start=date(2026, 12, 1),
        horizon_end=date(2026, 12, 5),
    )
    db.commit()

    details = get_allocation_run_details(db, hotel_id=hotel_config.id, run_id=persisted.run.id)
    assert details is not None
    explanation_types = {item.explanation_type for item in details.explanations}
    assert "summary" in explanation_types
    assert "assignment" in explanation_types
    assert any(metric.metric_key == "assigned_reservations" for metric in details.metrics)
