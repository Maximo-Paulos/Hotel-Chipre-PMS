from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

from app.models.allocation import LLMFeedbackEvent
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.allocation import LLMPolicySuggestion
from app.services.allocation_learning_service import draft_policy_from_feedback, draft_policy_from_questionnaire
from app.services.allocation_policy_service import record_manual_override_feedback


def test_questionnaire_draft_persists_gemma_metadata(db, hotel_config):
    fake_policy = {
        "constraints": {
            "no_overlap": True,
            "respect_locked_assignments": True,
            "allow_category_fallback": False,
        },
        "weights": {
            "prefer_exact_match": 1000.0,
            "stability": 8.0,
            "room_usage_penalty": 40.0,
            "unassigned_penalty": 10000.0,
            "fallback_priority_penalty": 10.0,
        },
        "questionnaire_summary": {
            "business_summary": "Business hotel",
            "prioritize_exact_match": 5,
            "minimize_one_night_gaps": 4,
            "minimize_moves": 4,
            "preserve_future_availability": 5,
            "allow_category_fallback": False,
            "notes": "Keep room moves low",
        },
        "summary": "Business hotel",
        "policy_meta": {
            "source_kind": "gemma",
            "source_model": "gemma:fake-model",
            "confidence": 0.91,
            "warnings": [],
        },
    }

    class FakeGemmaService:
        def redact_text_for_llm(self, value, *, limit=2000):
            return str(value).replace("ana@hotel.test", "[redacted-email]")[:limit]

        def suggest_policy_from_questionnaire(self, **kwargs):
            return SimpleNamespace(
                source_kind="gemma",
                source_model="gemma:fake-model",
                suggested_policy=fake_policy,
                explanation="Structured gemma suggestion",
                warnings=[],
                confidence=0.91,
                raw_response={"constraints": fake_policy["constraints"]},
            )

    from app.services import allocation_learning_service as learning_module

    original = learning_module.GemmaService
    learning_module.GemmaService = FakeGemmaService
    try:
        draft = draft_policy_from_questionnaire(
            db,
            hotel_id=hotel_config.id,
            business_summary="Business hotel ana@hotel.test",
            prioritize_exact_match=5,
            minimize_one_night_gaps=4,
            minimize_moves=4,
            preserve_future_availability=5,
            allow_category_fallback=False,
            notes="Keep room moves low",
        )
        db.commit()
    finally:
        learning_module.GemmaService = original

    persisted = (
        db.query(LLMPolicySuggestion)
        .filter(
            LLMPolicySuggestion.hotel_id == hotel_config.id,
            LLMPolicySuggestion.id == draft.suggestion.id,
        )
        .one()
    )

    assert persisted.source_model == "gemma:fake-model"
    assert persisted.input_summary == "Business hotel [redacted-email]"
    stored_policy = json.loads(persisted.suggested_policy_json)
    assert stored_policy["policy_meta"]["source_kind"] == "gemma"
    assert stored_policy["policy_meta"]["source_model"] == "gemma:fake-model"
    assert draft.suggested_policy["weights"]["prefer_exact_match"] == 1000.0


def test_feedback_draft_uses_recent_feedback_events(db, hotel_config, sample_guest, sample_categories):
    reservation = Reservation(
        confirmation_code="LEARN-FEEDBACK-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        check_in_date=sample_guest.created_at.date(),
        check_out_date=sample_guest.created_at.date() + timedelta(days=1),
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
        override_type="room_move",
        reason_code="keep_group_together",
        notes="Se movio para acomodar una familia",
        created_by_user_id=None,
        allocation_run_id=None,
        source_model="manual",
    )
    db.flush()

    class FakeGemmaService:
        def suggest_policy_from_feedback(self, **kwargs):
            assert kwargs["feedback_events"]
            assert kwargs["feedback_events"][0]["event_type"] == "manual_override"
            return SimpleNamespace(
                source_kind="gemma",
                source_model="gemma:feedback-model",
                suggested_policy={
                    "constraints": {
                        "no_overlap": True,
                        "respect_locked_assignments": True,
                        "allow_category_fallback": True,
                    },
                    "weights": {
                        "prefer_exact_match": 700.0,
                        "stability": 9.0,
                        "room_usage_penalty": 50.0,
                        "unassigned_penalty": 10000.0,
                        "fallback_priority_penalty": 12.0,
                    },
                    "feedback_summary": {
                        "event_count": 1,
                        "recent_events": kwargs["feedback_events"],
                        "notes": kwargs["notes"],
                    },
                    "summary": "Draft from manual override feedback",
                    "policy_meta": {
                        "source_kind": "gemma",
                        "source_model": "gemma:feedback-model",
                        "confidence": 0.74,
                        "warnings": [],
                    },
                },
                explanation="Gemma learned from recent room moves",
                warnings=[],
                confidence=0.74,
                raw_response={"ok": True},
            )

    from app.services import allocation_learning_service as learning_module

    original = learning_module.GemmaService
    learning_module.GemmaService = FakeGemmaService
    try:
        draft = draft_policy_from_feedback(
            db,
            hotel_id=hotel_config.id,
            max_events=10,
            notes="Priorizar mantener grupos juntos",
        )
        db.commit()
    finally:
        learning_module.GemmaService = original

    persisted = (
        db.query(LLMPolicySuggestion)
        .filter(
            LLMPolicySuggestion.hotel_id == hotel_config.id,
            LLMPolicySuggestion.id == draft.suggestion.id,
        )
        .one()
    )

    assert override.id is not None
    assert feedback.id is not None
    assert persisted.source_model == "gemma:feedback-model"
    assert persisted.suggestion_type == "feedback_learning"
    stored_policy = json.loads(persisted.suggested_policy_json)
    assert stored_policy["feedback_summary"]["event_count"] == 1
    assert stored_policy["policy_meta"]["source_model"] == "gemma:feedback-model"
    assert db.query(LLMFeedbackEvent).filter_by(reservation_id=reservation.id).count() == 1
