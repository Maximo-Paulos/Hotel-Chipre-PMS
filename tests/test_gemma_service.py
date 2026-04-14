from __future__ import annotations

import json

import httpx

from app.config import Settings
from app.services.gemma_service import GemmaService


def test_gemma_service_falls_back_when_disabled():
    service = GemmaService(
        settings=Settings(
            GEMMA_ENABLED=False,
            GEMMA_PROVIDER="disabled",
            GEMMA_MODEL="gemma-test",
        )
    )

    draft = service.suggest_policy_from_questionnaire(
        hotel_id=1,
        business_summary="Hotel familiar con foco en ocupacion continua",
        prioritize_exact_match=4,
        minimize_one_night_gaps=5,
        minimize_moves=4,
        preserve_future_availability=3,
        allow_category_fallback=True,
        notes="Preferimos no mover reservas si no hace falta",
    )

    assert draft.source_kind == "heuristic"
    assert draft.source_model == "questionnaire_heuristic_seed"
    assert draft.suggested_policy["policy_meta"]["source_kind"] == "heuristic"
    assert draft.suggested_policy["constraints"]["allow_category_fallback"] is True


def test_gemma_service_uses_remote_json_and_sanitizes_output():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "gemma-test"
        assert body["response_format"] == {"type": "json_object"}
        assert body["messages"][1]["role"] == "user"

        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "constraints": {
                                    "no_overlap": True,
                                    "allow_category_fallback": False,
                                    "unexpected_key": True,
                                },
                                "weights": {
                                    "prefer_exact_match": "900",
                                    "stability": -2,
                                    "room_usage_penalty": "not-a-number",
                                    "fallback_priority_penalty": 7,
                                },
                                "summary": "Gemma summary",
                                "explanation": "Keep exact matches as priority.",
                                "confidence": 0.82,
                                "source_model": "gemma-custom-model",
                            }
                        )
                    }
                }
            ]
        }
        return httpx.Response(200, json=response_payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = GemmaService(
        settings=Settings(
            GEMMA_ENABLED=True,
            GEMMA_PROVIDER="openai_compatible",
            GEMMA_ENDPOINT_URL="https://llm.example/v1/chat/completions",
            GEMMA_MODEL="gemma-test",
            GEMMA_API_KEY="secret",
            GEMMA_STRICT_JSON=True,
        ),
        http_client=client,
    )

    draft = service.suggest_policy_from_questionnaire(
        hotel_id=7,
        business_summary="Hotel corporativo con preferencia por exact match",
        prioritize_exact_match=5,
        minimize_one_night_gaps=4,
        minimize_moves=3,
        preserve_future_availability=4,
        allow_category_fallback=False,
        notes=None,
    )

    assert draft.source_kind == "gemma"
    assert draft.source_model == "gemma-custom-model"
    assert draft.confidence == 0.82
    assert draft.suggested_policy["constraints"] == {
        "no_overlap": True,
        "respect_locked_assignments": True,
        "allow_category_fallback": False,
    }
    assert draft.suggested_policy["weights"]["prefer_exact_match"] == 900.0
    assert draft.suggested_policy["weights"]["stability"] == 0.0
    assert draft.suggested_policy["weights"]["room_usage_penalty"] == 50.0
    assert draft.suggested_policy["weights"]["fallback_priority_penalty"] == 7.0
    assert draft.suggested_policy["policy_meta"]["source_kind"] == "gemma"
    assert draft.warnings


def test_gemma_service_falls_back_on_invalid_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "not-json at all",
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = GemmaService(
        settings=Settings(
            GEMMA_ENABLED=True,
            GEMMA_PROVIDER="openai_compatible",
            GEMMA_ENDPOINT_URL="https://llm.example/v1/chat/completions",
            GEMMA_MODEL="gemma-test",
            GEMMA_API_KEY="secret",
        ),
        http_client=client,
    )

    draft = service.suggest_policy_from_questionnaire(
        hotel_id=3,
        business_summary="Hotel boutique",
        prioritize_exact_match=3,
        minimize_one_night_gaps=3,
        minimize_moves=3,
        preserve_future_availability=3,
        allow_category_fallback=True,
        notes=None,
    )

    assert draft.source_kind == "fallback"
    assert draft.source_model.startswith("gemma-fallback:")
    assert draft.suggested_policy["policy_meta"]["source_kind"] == "fallback"
    assert draft.warnings


def test_gemma_service_feedback_seed_falls_back_when_disabled():
    service = GemmaService(
        settings=Settings(
            GEMMA_ENABLED=False,
            GEMMA_PROVIDER="disabled",
            GEMMA_MODEL="gemma-test",
        )
    )

    draft = service.suggest_policy_from_feedback(
        hotel_id=5,
        current_constraints={
            "no_overlap": True,
            "respect_locked_assignments": True,
            "allow_category_fallback": False,
        },
        current_weights={
            "prefer_exact_match": 700,
            "stability": 8,
            "room_usage_penalty": 50,
            "unassigned_penalty": 10000,
            "fallback_priority_penalty": 10,
        },
        feedback_events=[{"event_type": "manual_override", "payload": {"reason_code": "keep_group_together"}}],
        notes="Aprender de room moves",
    )

    assert draft.source_kind == "heuristic"
    assert draft.source_model == "feedback_heuristic_seed"
    assert draft.suggested_policy["feedback_summary"]["event_count"] == 1
    assert draft.suggested_policy["constraints"]["allow_category_fallback"] is False


def test_gemma_service_feedback_remote_json_is_sanitized():
    def handler(request: httpx.Request) -> httpx.Response:
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "constraints": {
                                    "no_overlap": True,
                                    "respect_locked_assignments": True,
                                    "allow_category_fallback": False,
                                },
                                "weights": {
                                    "prefer_exact_match": 850,
                                    "stability": 6,
                                    "room_usage_penalty": 45,
                                    "unassigned_penalty": 12000,
                                    "fallback_priority_penalty": 5,
                                },
                                "summary": "Refine fallback after room move feedback",
                                "explanation": "Recent overrides suggest exact-match preference should increase.",
                                "confidence": 0.77,
                                "source_model": "gemma-feedback-model",
                            }
                        )
                    }
                }
            ]
        }
        return httpx.Response(200, json=response_payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = GemmaService(
        settings=Settings(
            GEMMA_ENABLED=True,
            GEMMA_PROVIDER="openai_compatible",
            GEMMA_ENDPOINT_URL="https://llm.example/v1/chat/completions",
            GEMMA_MODEL="gemma-test",
            GEMMA_API_KEY="secret",
            GEMMA_STRICT_JSON=True,
        ),
        http_client=client,
    )

    draft = service.suggest_policy_from_feedback(
        hotel_id=11,
        current_constraints={
            "no_overlap": True,
            "respect_locked_assignments": True,
            "allow_category_fallback": True,
        },
        current_weights={
            "prefer_exact_match": 500,
            "stability": 5,
            "room_usage_penalty": 50,
            "unassigned_penalty": 10000,
            "fallback_priority_penalty": 25,
        },
        feedback_events=[{"event_type": "manual_override", "payload": {"reason_code": "keep_group_together"}}],
        notes=None,
    )

    assert draft.source_kind == "gemma"
    assert draft.source_model == "gemma-feedback-model"
    assert draft.confidence == 0.77
    assert draft.suggested_policy["feedback_summary"]["event_count"] == 1
    assert draft.suggested_policy["weights"]["prefer_exact_match"] == 850.0
    assert draft.suggested_policy["constraints"]["allow_category_fallback"] is False


def test_gemma_service_redacts_sensitive_prompt_content_before_remote_call():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        prompt = body["messages"][1]["content"]
        assert "ana.perez@hotel.test" not in prompt
        assert "+54 11 5555 7788" not in prompt
        assert "DNI 30111222" not in prompt
        assert "Juan Perez" not in prompt
        assert "[redacted-email]" in prompt
        assert "[redacted-phone]" in prompt
        assert "[redacted-document]" in prompt
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "constraints": {
                                        "no_overlap": True,
                                        "respect_locked_assignments": True,
                                        "allow_category_fallback": False,
                                    },
                                    "weights": {
                                        "prefer_exact_match": 700,
                                        "stability": 6,
                                        "room_usage_penalty": 40,
                                        "unassigned_penalty": 10000,
                                        "fallback_priority_penalty": 10,
                                    },
                                    "summary": "Prompt redacted correctly",
                                    "explanation": "No PII should reach the remote model.",
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = GemmaService(
        settings=Settings(
            GEMMA_ENABLED=True,
            GEMMA_PROVIDER="openai_compatible",
            GEMMA_ENDPOINT_URL="https://llm.example/v1/chat/completions",
            GEMMA_MODEL="gemma-test",
            GEMMA_API_KEY="secret",
            GEMMA_STRICT_JSON=True,
        ),
        http_client=client,
    )

    draft = service.suggest_policy_from_feedback(
        hotel_id=21,
        current_constraints={
            "no_overlap": True,
            "respect_locked_assignments": True,
            "allow_category_fallback": True,
        },
        current_weights={
            "prefer_exact_match": 500,
            "stability": 5,
            "room_usage_penalty": 50,
            "unassigned_penalty": 10000,
            "fallback_priority_penalty": 25,
        },
        feedback_events=[
            {
                "event_type": "manual_override",
                "payload": {
                    "guest_name": "Juan Perez",
                    "guest_email": "ana.perez@hotel.test",
                    "phone": "+54 11 5555 7788",
                    "notes": "DNI 30111222 pidio cambiar a una habitacion mejor",
                },
            }
        ],
        notes="Contactar a Juan Perez en ana.perez@hotel.test antes del check-in",
    )

    assert draft.source_kind == "gemma"
    assert draft.suggested_policy["feedback_summary"]["recent_events"][0]["payload"]["guest_email"] == "[redacted-email]"
