from __future__ import annotations

import json

from app.config import Settings
from app.services.analytics_ai_providers import (
    AnalyticsAIRequest,
    GemmaProvider,
    OpenAIProvider,
    build_analytics_ai_config,
    get_analytics_ai_provider,
)


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "Resumen hotelero",
                                "warnings": ["Alerta de ocupacion"],
                                "recommendations": ["Revisar tarifa"],
                                "data": {"signal": "occupancy"},
                            }
                        )
                    }
                }
            ]
        }


class _Client:
    def __init__(self) -> None:
        self.last_request: dict | None = None

    def post(self, url: str, *, headers: dict, json: dict):
        self.last_request = {"url": url, "headers": headers, "json": json}
        return _Response()


def test_ai_env_provider_selects_gemma_over_legacy_names():
    settings = Settings(
        _env_file=None,
        AI_ENABLED=True,
        AI_PROVIDER="gemma",
        AI_BASE_URL="http://rig.local/v1/chat/completions",
        AI_MODEL="gemma-local",
        GEMMA_ENABLED=False,
        GEMMA_PROVIDER="disabled",
    )

    config = build_analytics_ai_config(settings)
    provider = get_analytics_ai_provider(settings)

    assert config.enabled is True
    assert config.provider == "gemma"
    assert config.base_url == "http://rig.local/v1/chat/completions"
    assert isinstance(provider, GemmaProvider)
    assert provider.status().runtime_healthy is True


def test_ai_env_provider_selects_openai_with_api_key():
    settings = Settings(
        _env_file=None,
        AI_ENABLED=True,
        AI_PROVIDER="openai",
        AI_BASE_URL="",
        AI_API_KEY="sk-test",
        AI_MODEL="gpt-test",
    )

    config = build_analytics_ai_config(settings)
    provider = get_analytics_ai_provider(settings)

    assert config.provider == "openai"
    assert config.base_url == "https://api.openai.com/v1/chat/completions"
    assert isinstance(provider, OpenAIProvider)
    assert provider.status().runtime_healthy is True


def test_provider_receives_only_curated_hotel_analytics_payload():
    client = _Client()
    provider = GemmaProvider(
        build_analytics_ai_config(
            Settings(
                _env_file=None,
                AI_ENABLED=True,
                AI_PROVIDER="gemma",
                AI_BASE_URL="http://rig.local/v1/chat/completions",
                AI_MODEL="gemma-local",
            )
        ),
        http_client=client,
    )

    result = provider.generate_insight(
        AnalyticsAIRequest(
            hotel_id=7,
            insight_code="pricing",
            context={"cards": [{"card_code": "margin", "value": "100.00"}]},
        )
    )

    assert result.summary == "Resumen hotelero"
    assert client.last_request is not None
    messages = client.last_request["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert "Do not ask for SQL access" in messages[0]["content"]
    user_payload = json.loads(messages[1]["content"])
    assert user_payload["hotel_id"] == 7
    assert user_payload["insight_code"] == "pricing"
    assert user_payload["rules"]["no_chat"] is True
    assert user_payload["rules"]["no_sql"] is True
    assert user_payload["rules"]["no_cross_hotel_data"] is True
    assert "prompt" not in user_payload


def test_provider_chat_uses_curated_hotel_context_and_controlled_message():
    client = _Client()
    provider = GemmaProvider(
        build_analytics_ai_config(
            Settings(
                _env_file=None,
                AI_ENABLED=True,
                AI_PROVIDER="gemma",
                AI_BASE_URL="http://rig.local/v1/chat/completions",
                AI_MODEL="gemma-local",
            )
        ),
        http_client=client,
    )

    result = provider.generate_chat_answer(
        AnalyticsAIRequest(
            hotel_id=9,
            insight_code="chat",
            context={"home": {"cards": [{"card_code": "occupancy", "value_pct": 62.5}]}},
        ),
        message="Resumime el estado del hotel este mes",
    )

    assert result.summary == "Resumen hotelero"
    assert client.last_request is not None
    messages = client.last_request["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert "Only analyze the supplied hotel analytics context" in messages[0]["content"]
    user_payload = json.loads(messages[1]["content"])
    assert user_payload["kind"] == "analytics_chat"
    assert user_payload["hotel_id"] == 9
    assert user_payload["insight_code"] == "chat"
    assert user_payload["message"] == "Resumime el estado del hotel este mes"
    assert user_payload["context"] == {"home": {"cards": [{"card_code": "occupancy", "value_pct": 62.5}]}}
    assert user_payload["rules"]["domain"] == "hotel_analytics"
    assert user_payload["rules"]["no_sql"] is True
    assert user_payload["rules"]["no_cross_hotel_data"] is True
    assert "prompt" not in user_payload
