from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol

import httpx

from app.config import Settings, get_settings


LOGGER = logging.getLogger(__name__)

AnalyticsInsightCode = Literal["home", "anomalies", "pricing", "chat"]


@dataclass(frozen=True, slots=True)
class AnalyticsAIProviderConfig:
    enabled: bool
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float
    max_output_tokens: int
    temperature: float
    strict_json: bool
    quota_monthly: int


@dataclass(frozen=True, slots=True)
class AnalyticsAIProviderStatus:
    provider: str
    configured: bool
    runtime_healthy: bool
    effective_model: str | None
    runtime_status: str
    fallback_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AnalyticsAIRequest:
    hotel_id: int
    insight_code: AnalyticsInsightCode
    context: dict[str, Any]
    language: str = "es"


@dataclass(frozen=True, slots=True)
class AnalyticsAIResult:
    summary: str
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)


class AnalyticsAIProviderError(RuntimeError):
    pass


class AnalyticsAIProvider(Protocol):
    @property
    def name(self) -> str:
        ...

    def status(self) -> AnalyticsAIProviderStatus:
        ...

    def generate_insight(self, request: AnalyticsAIRequest) -> AnalyticsAIResult:
        ...

    def generate_chat_answer(self, request: AnalyticsAIRequest, *, message: str) -> AnalyticsAIResult:
        ...


class DisabledAnalyticsAIProvider:
    name = "disabled"

    def __init__(self, config: AnalyticsAIProviderConfig) -> None:
        self.config = config

    def status(self) -> AnalyticsAIProviderStatus:
        return AnalyticsAIProviderStatus(
            provider="disabled",
            configured=False,
            runtime_healthy=False,
            effective_model=None,
            runtime_status="disabled",
            fallback_reason="AI provider disabled",
        )

    def generate_insight(self, request: AnalyticsAIRequest) -> AnalyticsAIResult:
        raise AnalyticsAIProviderError("AI provider disabled")

    def generate_chat_answer(self, request: AnalyticsAIRequest, *, message: str) -> AnalyticsAIResult:
        raise AnalyticsAIProviderError("AI provider disabled")


class _OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, config: AnalyticsAIProviderConfig, *, http_client: httpx.Client | None = None) -> None:
        self.config = config
        self._http_client = http_client

    def status(self) -> AnalyticsAIProviderStatus:
        missing = self._missing_config()
        configured = not missing
        return AnalyticsAIProviderStatus(
            provider=self.name,
            configured=configured,
            runtime_healthy=bool(self.config.enabled and configured),
            effective_model=self.config.model or None,
            runtime_status="ready" if self.config.enabled and configured else "missing_config",
            fallback_reason=", ".join(missing) if missing else None,
        )

    def generate_insight(self, request: AnalyticsAIRequest) -> AnalyticsAIResult:
        status = self.status()
        if not status.runtime_healthy:
            raise AnalyticsAIProviderError(status.fallback_reason or "AI provider not configured")
        body = self._request_body(request)
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        if self._http_client is not None:
            payload = self._post_with_client(self._http_client, headers=headers, body=body)
        else:
            with httpx.Client(timeout=httpx.Timeout(self.config.timeout_seconds)) as client:
                payload = self._post_with_client(client, headers=headers, body=body)
        parsed = _parse_openai_json_payload(payload)
        return _normalize_provider_result(parsed)

    def generate_chat_answer(self, request: AnalyticsAIRequest, *, message: str) -> AnalyticsAIResult:
        status = self.status()
        if not status.runtime_healthy:
            raise AnalyticsAIProviderError(status.fallback_reason or "AI provider not configured")
        body = self._request_body(request, user_message=message)
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        if self._http_client is not None:
            payload = self._post_with_client(self._http_client, headers=headers, body=body)
        else:
            with httpx.Client(timeout=httpx.Timeout(self.config.timeout_seconds)) as client:
                payload = self._post_with_client(client, headers=headers, body=body)
        parsed = _parse_openai_json_payload(payload)
        return _normalize_provider_result(parsed, summary_key="answer")

    def _post_with_client(self, client: httpx.Client, *, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        response = client.post(self.config.base_url.rstrip("/"), headers=headers, json=body)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise AnalyticsAIProviderError("AI provider returned a non-object response")
        return payload

    def _missing_config(self) -> list[str]:
        missing: list[str] = []
        if not self.config.enabled:
            missing.append("AI_ENABLED=false")
        if not self.config.base_url:
            missing.append("AI_BASE_URL")
        if not self.config.model:
            missing.append("AI_MODEL")
        return missing

    def _request_body(self, request: AnalyticsAIRequest, *, user_message: str | None = None) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "messages": _build_analytics_messages(request, user_message=user_message),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_output_tokens,
            **({"response_format": {"type": "json_object"}} if self.config.strict_json else {}),
        }


class GemmaProvider(_OpenAICompatibleProvider):
    name = "gemma"


class OpenAIProvider(_OpenAICompatibleProvider):
    name = "openai"

    def _missing_config(self) -> list[str]:
        missing = super()._missing_config()
        if not self.config.api_key:
            missing.append("AI_API_KEY")
        return missing


def get_analytics_ai_provider(settings: Settings | None = None) -> AnalyticsAIProvider:
    config = build_analytics_ai_config(settings or get_settings())
    provider = config.provider
    if provider in {"disabled", ""}:
        return DisabledAnalyticsAIProvider(config)
    if provider in {"gemma", "openai_compatible"}:
        return GemmaProvider(config)
    if provider == "openai":
        return OpenAIProvider(config)
    return DisabledAnalyticsAIProvider(replace(config, enabled=False, provider="disabled"))


def build_analytics_ai_config(settings: Settings) -> AnalyticsAIProviderConfig:
    provider = _effective_provider(settings)
    base_url = _first_configured(settings.AI_BASE_URL, settings.GEMMA_ENDPOINT_URL)
    if provider == "openai" and not base_url:
        base_url = "https://api.openai.com/v1/chat/completions"
    return AnalyticsAIProviderConfig(
        enabled=_effective_enabled(settings),
        provider=provider,
        base_url=base_url,
        api_key=_first_configured(settings.AI_API_KEY, settings.GEMMA_API_KEY),
        model=_first_configured(settings.AI_MODEL, settings.GEMMA_MODEL),
        timeout_seconds=float(settings.AI_TIMEOUT_SECONDS or settings.GEMMA_TIMEOUT_SECONDS or 20.0),
        max_output_tokens=int(settings.AI_MAX_OUTPUT_TOKENS or settings.GEMMA_MAX_OUTPUT_TOKENS or 1024),
        temperature=float(settings.AI_TEMPERATURE if settings.AI_TEMPERATURE is not None else settings.GEMMA_TEMPERATURE),
        strict_json=bool(settings.AI_STRICT_JSON if settings.AI_STRICT_JSON is not None else settings.GEMMA_STRICT_JSON),
        quota_monthly=int(settings.AI_MONTHLY_QUOTA or settings.GEMMA_RATE_LIMIT_MAX_MESSAGES or 20),
    )


def _effective_enabled(settings: Settings) -> bool:
    if settings.AI_ENABLED is not None:
        return bool(settings.AI_ENABLED)
    return bool(settings.GEMMA_ENABLED)


def _effective_provider(settings: Settings) -> str:
    provider = _first_configured(settings.AI_PROVIDER, settings.GEMMA_PROVIDER).strip().lower()
    if provider == "auto":
        if _first_configured(settings.AI_BASE_URL, settings.GEMMA_ENDPOINT_URL):
            return "gemma"
        if _first_configured(settings.AI_API_KEY, settings.GEMMA_API_KEY) and _first_configured(settings.AI_MODEL, settings.GEMMA_MODEL):
            return "openai"
        return "disabled"
    if provider in {"openai_compatible", "google_gemini_api"}:
        return "gemma"
    if provider in {"gemma", "openai", "disabled"}:
        return provider
    return "disabled"


def _first_configured(*values: str | None) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _build_analytics_messages(request: AnalyticsAIRequest, *, user_message: str | None = None) -> list[dict[str, str]]:
    controlled_payload = {
        "kind": "analytics_insight",
        "allowed_tasks": ["home", "anomalies", "pricing"],
        "insight_code": request.insight_code,
        "hotel_id": request.hotel_id,
        "context": request.context,
        "message": user_message,
        "rules": {
            "domain": "hotel_analytics",
            "language": request.language,
            "json_only": True,
            "no_chat": True,
            "no_general_answers": True,
            "no_external_actions": True,
            "no_sql": True,
            "no_cross_hotel_data": True,
        },
    }
    if request.insight_code == "chat":
        controlled_payload["kind"] = "analytics_chat"
        controlled_payload["allowed_tasks"] = ["explain_metrics", "detect_anomalies", "pricing_advice", "summarize_hotel", "analyze_channels", "analyze_rooms", "analyze_categories"]
    return [
        {
            "role": "system",
            "content": (
                "You are an analytics assistant for a hotel PMS. "
                "Only analyze the supplied hotel analytics context. "
                "Reject general-purpose requests and do not produce free-form chat. "
                "Do not ask for SQL access, do not infer data outside the payload, and do not mix hotels. "
                "Return only JSON with answer, summary, warnings, recommendations, and data."
            ),
        },
        {"role": "user", "content": json.dumps(controlled_payload, ensure_ascii=True, sort_keys=True)},
    ]


def _parse_openai_json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices") or []
    raw_text = ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            raw_text = message["content"]
            break
        if isinstance(choice.get("text"), str):
            raw_text = choice["text"]
            break
    if not raw_text:
        raise AnalyticsAIProviderError("AI provider response did not contain text")
    text = _strip_code_fences(raw_text.strip())
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnalyticsAIProviderError("AI provider response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise AnalyticsAIProviderError("AI provider response JSON must be an object")
    return parsed


def _strip_code_fences(text: str) -> str:
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return text


def _normalize_provider_result(parsed: dict[str, Any], *, summary_key: str = "summary") -> AnalyticsAIResult:
    summary = _normalize_text(parsed.get(summary_key) or parsed.get("summary"), "Insight operativo generado por IA.")
    warnings = _normalize_string_list(parsed.get("warnings"))
    recommendations = _normalize_string_list(parsed.get("recommendations"))
    data = parsed.get("data") if isinstance(parsed.get("data"), dict) else {}
    if not recommendations and isinstance(data.get("recommendations"), list):
        recommendations = _normalize_string_list(data.get("recommendations"))
    return AnalyticsAIResult(
        summary=summary,
        warnings=warnings,
        recommendations=recommendations,
        data=data,
        raw_response=parsed,
    )


def _normalize_text(value: Any, fallback: str, limit: int = 240) -> str:
    if not isinstance(value, str):
        value = fallback
    return " ".join(value.split()).strip()[:limit]


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = " ".join(item.split()).strip()
            if text:
                result.append(text[:240])
    return result
