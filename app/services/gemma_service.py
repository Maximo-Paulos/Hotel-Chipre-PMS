"""
Gemma-aware policy suggestion service.

This module keeps the PMS safe by treating Gemma as a structured suggestion
layer, never as the source of truth. The solver and commercial policies remain
deterministic and validated.
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.services.allocation_policy_service import (
    DEFAULT_ALLOCATION_CONSTRAINTS,
    DEFAULT_ALLOCATION_WEIGHTS,
)


LOGGER = logging.getLogger(__name__)

_ALLOWED_CONSTRAINT_KEYS = tuple(DEFAULT_ALLOCATION_CONSTRAINTS.keys())
_ALLOWED_WEIGHT_KEYS = tuple(DEFAULT_ALLOCATION_WEIGHTS.keys())
_REDACTED_EMAIL = "[redacted-email]"
_REDACTED_PHONE = "[redacted-phone]"
_REDACTED_DOCUMENT = "[redacted-document]"
_REDACTED_NAME = "[redacted-name]"
_REDACTED_VALUE = "[redacted]"
_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)")
_DOCUMENT_RE = re.compile(r"(?i)\b(?:dni|documento|document|passport|pasaporte|doc)\s*[:=#-]?\s*[a-z0-9-]{5,}\b")
_NAME_FIELD_RE = re.compile(
    r"(?i)\b(?:guest|huesped|huésped|name|nombre|first_name|last_name|apellido)\s*[:=]\s*([^\n,;]+)"
)
_ACTION_NAME_RE = re.compile(
    r"(?i)\b(?:contactar a|llamar a|hablar con|guest|huesped|huésped)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,2})"
)
_SENSITIVE_KEY_TOKENS = (
    "email",
    "mail",
    "phone",
    "telefono",
    "tel",
    "whatsapp",
    "document",
    "doc",
    "dni",
    "passport",
    "pasaporte",
    "guest_name",
    "first_name",
    "last_name",
    "full_name",
    "nombre",
    "apellido",
)


@dataclass(slots=True)
class GemmaPolicyDraft:
    source_kind: str
    source_model: str
    suggested_policy: dict[str, Any]
    explanation: str
    warnings: list[str] = field(default_factory=list)
    confidence: float | None = None
    raw_response: dict[str, Any] | None = None


class GemmaServiceError(RuntimeError):
    """Raised when a Gemma request cannot be completed safely."""


class GemmaService:
    """
    Adapter for Gemma-backed policy suggestions.

    The service can talk to either:
    - the Google Gemini API using Gemma-compatible models, or
    - an OpenAI-compatible endpoint that serves Gemma.

    If the provider is not configured, the service falls back to a deterministic
    questionnaire seed.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._http_client = http_client

    def redact_text_for_llm(self, value: str | None, *, limit: int = 2000) -> str:
        return self._clean_text(self._sanitize_for_prompt(value, limit=limit), fallback="", limit=limit)

    def sanitize_feedback_events_for_llm(
        self,
        feedback_events: list[dict[str, Any]],
        *,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        trimmed_events = feedback_events[:limit]
        return [self._sanitize_for_prompt(event, limit=8000) for event in trimmed_events]

    def suggest_policy_from_questionnaire(
        self,
        *,
        hotel_id: int,
        business_summary: str,
        prioritize_exact_match: int,
        minimize_one_night_gaps: int,
        minimize_moves: int,
        preserve_future_availability: int,
        allow_category_fallback: bool,
        notes: str | None = None,
    ) -> GemmaPolicyDraft:
        sanitized_business_summary = self.redact_text_for_llm(business_summary, limit=1200)
        sanitized_notes = self.redact_text_for_llm(notes, limit=1200)
        seed = self._build_seed_policy(
            business_summary=sanitized_business_summary,
            prioritize_exact_match=prioritize_exact_match,
            minimize_one_night_gaps=minimize_one_night_gaps,
            minimize_moves=minimize_moves,
            preserve_future_availability=preserve_future_availability,
            allow_category_fallback=allow_category_fallback,
            notes=sanitized_notes,
        )

        provider = self._effective_provider()
        if provider is None:
            return self._build_fallback_draft(
                seed,
                source_kind="heuristic",
                source_model="questionnaire_heuristic_seed",
                explanation="Gemma is disabled or not configured, so the questionnaire seed was used.",
            )

        prompt = self._build_prompt(
            hotel_id=hotel_id,
            business_summary=sanitized_business_summary,
            seed=seed,
            notes=sanitized_notes,
        )
        try:
            payload = self._call_remote_model(provider, prompt)
            parsed = self._extract_policy_payload(payload)
            return self._sanitize_remote_policy(parsed, seed=seed, provider=provider)
        except Exception as exc:
            LOGGER.warning("Gemma suggestion fallback triggered: %s", exc)
            return self._build_fallback_draft(
                seed,
                source_kind="fallback",
                source_model=self._source_model_label(provider, fallback=True),
                explanation=f"Gemma suggestion unavailable, using questionnaire seed. Reason: {exc}",
                warnings=[str(exc)],
            )

    def suggest_policy_from_feedback(
        self,
        *,
        hotel_id: int,
        current_constraints: dict[str, Any],
        current_weights: dict[str, Any],
        feedback_events: list[dict[str, Any]],
        notes: str | None = None,
    ) -> GemmaPolicyDraft:
        sanitized_feedback_events = self.sanitize_feedback_events_for_llm(feedback_events)
        sanitized_notes = self.redact_text_for_llm(notes, limit=1200)
        seed = self._build_feedback_seed_policy(
            current_constraints=current_constraints,
            current_weights=current_weights,
            feedback_events=sanitized_feedback_events,
            notes=sanitized_notes,
        )

        provider = self._effective_provider()
        if provider is None:
            return self._build_fallback_draft(
                seed,
                source_kind="heuristic",
                source_model="feedback_heuristic_seed",
                explanation="Gemma is disabled or not configured, so the feedback-based seed was used.",
            )

        prompt = self._build_feedback_prompt(
            hotel_id=hotel_id,
            current_constraints=current_constraints,
            current_weights=current_weights,
            feedback_events=sanitized_feedback_events,
            notes=sanitized_notes,
        )
        try:
            payload = self._call_remote_model(provider, prompt)
            parsed = self._extract_policy_payload(payload)
            return self._sanitize_remote_policy(parsed, seed=seed, provider=provider)
        except Exception as exc:
            LOGGER.warning("Gemma feedback suggestion fallback triggered: %s", exc)
            return self._build_fallback_draft(
                seed,
                source_kind="fallback",
                source_model=self._source_model_label(provider, fallback=True),
                explanation=f"Gemma feedback suggestion unavailable, using active policy seed. Reason: {exc}",
                warnings=[str(exc)],
            )

    def _effective_provider(self) -> str | None:
        provider = (self.settings.GEMMA_PROVIDER or "disabled").strip().lower()
        enabled = bool(self.settings.GEMMA_ENABLED)
        if provider == "auto":
            if self.settings.GEMMA_ENDPOINT_URL:
                provider = "openai_compatible"
            elif self.settings.GEMMA_API_KEY and self.settings.GEMMA_MODEL:
                provider = "google_gemini_api"
            else:
                provider = "disabled"
        if not enabled or provider == "disabled":
            return None
        if provider not in {"openai_compatible", "google_gemini_api"}:
            return None
        if not self.settings.GEMMA_MODEL:
            return None
        if provider == "openai_compatible" and not self.settings.GEMMA_ENDPOINT_URL:
            return None
        if provider == "google_gemini_api" and not self.settings.GEMMA_API_KEY:
            return None
        return provider

    def _build_prompt(self, *, hotel_id: int, business_summary: str, seed: dict[str, Any], notes: str | None) -> str:
        return (
            "You are configuring the allocation policy of a hotel PMS.\n"
            "Return only valid JSON. Do not use markdown or code fences.\n"
            "The JSON must contain: constraints, weights, explanation, confidence, warnings, summary.\n"
            "Use only these constraint keys: "
            + ", ".join(_ALLOWED_CONSTRAINT_KEYS)
            + "\n"
            + "Use only these weight keys: "
            + ", ".join(_ALLOWED_WEIGHT_KEYS)
            + "\n"
            "Constraints must be booleans. Weights must be numeric and non-negative.\n"
            "Do not invent new keys inside constraints or weights.\n\n"
            f"Hotel id: {hotel_id}\n"
            f"Business summary: {business_summary}\n"
            f"Notes: {notes or ''}\n"
            f"Seed policy JSON: {json.dumps(seed, ensure_ascii=True, sort_keys=True)}\n"
        )

    def _build_feedback_prompt(
        self,
        *,
        hotel_id: int,
        current_constraints: dict[str, Any],
        current_weights: dict[str, Any],
        feedback_events: list[dict[str, Any]],
        notes: str | None,
    ) -> str:
        return (
            "You are refining the allocation policy of a hotel PMS from real operational feedback.\n"
            "Return only valid JSON. Do not use markdown or code fences.\n"
            "The JSON must contain: constraints, weights, explanation, confidence, warnings, summary.\n"
            "Use only these constraint keys: "
            + ", ".join(_ALLOWED_CONSTRAINT_KEYS)
            + "\n"
            + "Use only these weight keys: "
            + ", ".join(_ALLOWED_WEIGHT_KEYS)
            + "\n"
            "Constraints must be booleans. Weights must be numeric and non-negative.\n"
            "Do not invent new keys inside constraints or weights.\n"
            "Be conservative: only change values when the feedback clearly supports it.\n\n"
            f"Hotel id: {hotel_id}\n"
            f"Current constraints JSON: {json.dumps(current_constraints, ensure_ascii=True, sort_keys=True)}\n"
            f"Current weights JSON: {json.dumps(current_weights, ensure_ascii=True, sort_keys=True)}\n"
            f"Feedback events JSON: {json.dumps(feedback_events, ensure_ascii=True, sort_keys=True)}\n"
            f"Notes: {notes or ''}\n"
        )

    def _call_remote_model(self, provider: str, prompt: str) -> dict[str, Any]:
        timeout = httpx.Timeout(float(self.settings.GEMMA_TIMEOUT_SECONDS or 20.0))
        if self._http_client is not None:
            return self._call_remote_model_with_client(provider, prompt, self._http_client)

        with httpx.Client(timeout=timeout) as client:
            return self._call_remote_model_with_client(provider, prompt, client)

    def _call_remote_model_with_client(
        self,
        provider: str,
        prompt: str,
        client: httpx.Client,
    ) -> dict[str, Any]:
        if provider == "google_gemini_api":
            return self._call_google_gemini_api(prompt, client)
        return self._call_openai_compatible(prompt, client)

    def _call_google_gemini_api(self, prompt: str, client: httpx.Client) -> dict[str, Any]:
        base_url = (self.settings.GEMMA_ENDPOINT_URL or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        url = f"{base_url}/models/{self.settings.GEMMA_MODEL}:generateContent"
        params = {"key": self.settings.GEMMA_API_KEY}
        body = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are a hotel allocation policy assistant. "
                            "Return only JSON with the requested structure."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": float(self.settings.GEMMA_TEMPERATURE or 0.2),
                "maxOutputTokens": int(self.settings.GEMMA_MAX_OUTPUT_TOKENS or 1024),
                "responseMimeType": "application/json",
            },
        }
        response = client.post(url, params=params, json=body)
        response.raise_for_status()
        data = response.json()
        text = self._extract_gemini_text(data)
        return self._decode_json_payload(text)

    def _call_openai_compatible(self, prompt: str, client: httpx.Client) -> dict[str, Any]:
        url = self.settings.GEMMA_ENDPOINT_URL.rstrip("/")
        if not url:
            raise GemmaServiceError("Gemma endpoint is missing")
        headers = {"Content-Type": "application/json"}
        if self.settings.GEMMA_API_KEY:
            headers["Authorization"] = f"Bearer {self.settings.GEMMA_API_KEY}"
        body = {
            "model": self.settings.GEMMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a hotel allocation policy assistant. "
                        "Return only JSON with the requested structure."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": float(self.settings.GEMMA_TEMPERATURE or 0.2),
            "max_tokens": int(self.settings.GEMMA_MAX_OUTPUT_TOKENS or 1024),
        }
        if self.settings.GEMMA_STRICT_JSON:
            body["response_format"] = {"type": "json_object"}

        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
        text = self._extract_openai_text(data)
        return self._decode_json_payload(text)

    def _extract_gemini_text(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates") or []
        for candidate in candidates:
            content = candidate.get("content") if isinstance(candidate, dict) else None
            if not isinstance(content, dict):
                continue
            parts = content.get("parts") or []
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    return part["text"]
        raise GemmaServiceError("Gemma API response did not contain text")

    def _extract_openai_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        for choice in choices:
            message = choice.get("message") if isinstance(choice, dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(choice, dict) and isinstance(choice.get("text"), str):
                return choice["text"]
        raise GemmaServiceError("OpenAI-compatible response did not contain text")

    def _decode_json_payload(self, raw_text: str) -> dict[str, Any]:
        text = (raw_text or "").strip()
        if not text:
            raise GemmaServiceError("Gemma response was empty")
        text = self._strip_code_fences(text)
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise GemmaServiceError("Gemma response was not valid JSON")
            loaded = json.loads(match.group(0))
        if not isinstance(loaded, dict):
            raise GemmaServiceError("Gemma response JSON must be an object")
        return loaded

    def _strip_code_fences(self, text: str) -> str:
        if text.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", text)
            stripped = re.sub(r"\s*```$", "", stripped)
            return stripped.strip()
        return text

    def _extract_policy_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise GemmaServiceError("Gemma payload must be an object")
        if "constraints" in payload or "weights" in payload:
            return payload
        nested = payload.get("suggested_policy") or payload.get("policy") or payload.get("result")
        if isinstance(nested, dict):
            return nested
        raise GemmaServiceError("Gemma payload did not contain a policy object")

    def _sanitize_remote_policy(
        self,
        payload: dict[str, Any],
        *,
        seed: dict[str, Any],
        provider: str,
    ) -> GemmaPolicyDraft:
        warnings: list[str] = []
        constraints = self._sanitize_constraints(payload.get("constraints"), warnings)
        weights = self._sanitize_weights(payload.get("weights"), warnings)
        summary = self._clean_text(
            self._sanitize_for_prompt(payload.get("summary"), limit=500),
            fallback=self._seed_summary(seed),
            limit=500,
        )
        explanation = self._clean_text(
            self._sanitize_for_prompt(payload.get("explanation"), limit=4000),
            fallback=seed["explanation"],
            limit=4000,
        )
        confidence = self._coerce_confidence(payload.get("confidence"), warnings)
        source_model = self._clean_text(
            payload.get("source_model"),
            fallback=self._source_model_label(provider, fallback=False),
            limit=100,
        )
        source_kind = self._clean_text(
            payload.get("source_kind"),
            fallback="gemma",
            limit=40,
        )
        policy = {
            "constraints": constraints,
            "weights": weights,
            "summary": summary,
            "policy_meta": {
                "source_kind": source_kind,
                "source_model": source_model,
                "confidence": confidence,
                "warnings": warnings,
            },
        }
        if "questionnaire_summary" in seed:
            policy["questionnaire_summary"] = seed["questionnaire_summary"]
        if "feedback_summary" in seed:
            policy["feedback_summary"] = seed["feedback_summary"]
        if payload.get("notes"):
            policy["notes"] = self._clean_text(
                self._sanitize_for_prompt(payload.get("notes"), limit=2000),
                fallback="",
                limit=2000,
            )
        explanation = self._merge_explanation(explanation, warnings)
        return GemmaPolicyDraft(
            source_kind=source_kind,
            source_model=source_model,
            suggested_policy=policy,
            explanation=explanation,
            warnings=warnings,
            confidence=confidence,
            raw_response=payload,
        )

    def _build_fallback_draft(
        self,
        seed: dict[str, Any],
        *,
        source_kind: str,
        source_model: str,
        explanation: str,
        warnings: list[str] | None = None,
    ) -> GemmaPolicyDraft:
        policy = {
            "constraints": dict(seed["constraints"]),
            "weights": dict(seed["weights"]),
            "summary": self._seed_summary(seed),
            "policy_meta": {
                "source_kind": source_kind,
                "source_model": source_model,
                "confidence": None,
                "warnings": warnings or [],
            },
        }
        if "questionnaire_summary" in seed:
            policy["questionnaire_summary"] = seed["questionnaire_summary"]
        if "feedback_summary" in seed:
            policy["feedback_summary"] = seed["feedback_summary"]
        return GemmaPolicyDraft(
            source_kind=source_kind,
            source_model=source_model,
            suggested_policy=policy,
            explanation=self._merge_explanation(explanation, warnings or []),
            warnings=warnings or [],
            confidence=None,
            raw_response=None,
        )

    def _build_seed_policy(
        self,
        *,
        business_summary: str,
        prioritize_exact_match: int,
        minimize_one_night_gaps: int,
        minimize_moves: int,
        preserve_future_availability: int,
        allow_category_fallback: bool,
        notes: str | None,
    ) -> dict[str, Any]:
        weights = dict(DEFAULT_ALLOCATION_WEIGHTS)
        constraints = dict(DEFAULT_ALLOCATION_CONSTRAINTS)
        weights["prefer_exact_match"] = float(200 + (prioritize_exact_match * 150))
        weights["room_usage_penalty"] = float(20 + (minimize_one_night_gaps * 15))
        weights["stability"] = float(1 + (minimize_moves * 2))
        weights["fallback_priority_penalty"] = float(10 + (preserve_future_availability * 8))
        constraints["allow_category_fallback"] = bool(allow_category_fallback)

        summary_lower = business_summary.lower()
        if "maximiz" in summary_lower and "factur" in summary_lower:
            weights["fallback_priority_penalty"] = max(5.0, weights["fallback_priority_penalty"] - 10.0)
        if "hueco" in summary_lower or "fragment" in summary_lower:
            weights["room_usage_penalty"] += 15.0
        if "no mover" in summary_lower or "evitar mover" in summary_lower:
            weights["stability"] += 3.0
        if "exact" in summary_lower or "misma categoria" in summary_lower:
            weights["prefer_exact_match"] += 75.0

        questionnaire_summary = {
            "business_summary": business_summary,
            "prioritize_exact_match": prioritize_exact_match,
            "minimize_one_night_gaps": minimize_one_night_gaps,
            "minimize_moves": minimize_moves,
            "preserve_future_availability": preserve_future_availability,
            "allow_category_fallback": allow_category_fallback,
            "notes": notes,
        }
        return {
            "constraints": constraints,
            "weights": weights,
            "questionnaire_summary": questionnaire_summary,
            "explanation": (
                "Borrador estructurado desde cuestionario del hotel. "
                "Pensado para que Gemma lo refine sin tocar la politica publicada automaticamente."
            ),
        }

    def _build_feedback_seed_policy(
        self,
        *,
        current_constraints: dict[str, Any],
        current_weights: dict[str, Any],
        feedback_events: list[dict[str, Any]],
        notes: str | None,
    ) -> dict[str, Any]:
        constraints = self._sanitize_constraints(current_constraints, [])
        weights = self._sanitize_weights(current_weights, [])
        feedback_summary = {
            "event_count": len(feedback_events),
            "recent_events": feedback_events[:10],
            "notes": notes,
        }
        return {
            "constraints": constraints,
            "weights": weights,
            "feedback_summary": feedback_summary,
            "explanation": (
                "Borrador estructurado desde feedback operativo real. "
                "Pensado para que Gemma refine la politica sin tocar la version publicada automaticamente."
            ),
        }

    def _sanitize_constraints(self, raw_value: Any, warnings: list[str]) -> dict[str, bool]:
        sanitized = dict(DEFAULT_ALLOCATION_CONSTRAINTS)
        if not isinstance(raw_value, dict):
            warnings.append("constraints_missing_or_invalid")
            return sanitized

        for key in _ALLOWED_CONSTRAINT_KEYS:
            if key not in raw_value:
                continue
            value = raw_value.get(key)
            if isinstance(value, bool):
                sanitized[key] = value
            elif value in (0, 1, "0", "1", "true", "false", "True", "False"):
                sanitized[key] = str(value).lower() in {"1", "true"}
            else:
                warnings.append(f"constraint_{key}_invalid")
        return sanitized

    def _sanitize_weights(self, raw_value: Any, warnings: list[str]) -> dict[str, float]:
        sanitized = dict(DEFAULT_ALLOCATION_WEIGHTS)
        if not isinstance(raw_value, dict):
            warnings.append("weights_missing_or_invalid")
            return sanitized

        for key in _ALLOWED_WEIGHT_KEYS:
            if key not in raw_value:
                continue
            numeric = self._coerce_float(raw_value.get(key))
            if numeric is None:
                warnings.append(f"weight_{key}_invalid")
                continue
            sanitized[key] = max(0.0, numeric)
        return sanitized

    def _coerce_confidence(self, value: Any, warnings: list[str]) -> float | None:
        numeric = self._coerce_float(value)
        if numeric is None:
            if value is not None:
                warnings.append("confidence_invalid")
            return None
        return min(max(numeric, 0.0), 1.0)

    def _coerce_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric

    def _sanitize_for_prompt(self, value: Any, *, key_hint: str | None = None, limit: int = 4000) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, nested in value.items():
                hint = str(key)
                if self._is_sensitive_key(hint):
                    sanitized[hint] = self._redacted_placeholder_for_key(hint)
                    continue
                sanitized[hint] = self._sanitize_for_prompt(nested, key_hint=hint, limit=limit)
            return sanitized

        if isinstance(value, list):
            return [self._sanitize_for_prompt(item, key_hint=key_hint, limit=limit) for item in value[:25]]

        if isinstance(value, str):
            return self._redact_free_text(value, key_hint=key_hint, limit=limit)

        return value

    def _redact_free_text(self, value: str, *, key_hint: str | None, limit: int) -> str:
        text = value.strip()
        if not text:
            return ""

        lowered_hint = (key_hint or "").strip().lower()
        if lowered_hint and self._is_sensitive_key(lowered_hint):
            if any(token in lowered_hint for token in ("name", "nombre", "apellido")):
                return _REDACTED_NAME
            if any(token in lowered_hint for token in ("email", "mail")):
                return _REDACTED_EMAIL
            if any(token in lowered_hint for token in ("phone", "telefono", "tel", "whatsapp")):
                return _REDACTED_PHONE
            if any(token in lowered_hint for token in ("document", "doc", "dni", "passport", "pasaporte")):
                return _REDACTED_DOCUMENT
            return _REDACTED_VALUE

        text = _EMAIL_RE.sub(_REDACTED_EMAIL, text)
        text = _DOCUMENT_RE.sub(_REDACTED_DOCUMENT, text)
        text = _NAME_FIELD_RE.sub(lambda match: match.group(0).replace(match.group(1), _REDACTED_NAME), text)
        text = _ACTION_NAME_RE.sub(lambda match: match.group(0).replace(match.group(1), _REDACTED_NAME), text)
        text = _PHONE_RE.sub(_REDACTED_PHONE, text)
        text = re.sub(r"\b\d{7,}\b", _REDACTED_DOCUMENT, text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:limit]

    def _is_sensitive_key(self, key: str) -> bool:
        lowered = key.lower()
        return any(token in lowered for token in _SENSITIVE_KEY_TOKENS)

    def _redacted_placeholder_for_key(self, key: str) -> str:
        lowered = key.lower()
        if any(token in lowered for token in ("name", "nombre", "apellido")):
            return _REDACTED_NAME
        if any(token in lowered for token in ("email", "mail")):
            return _REDACTED_EMAIL
        if any(token in lowered for token in ("phone", "telefono", "tel", "whatsapp")):
            return _REDACTED_PHONE
        if any(token in lowered for token in ("document", "doc", "dni", "passport", "pasaporte")):
            return _REDACTED_DOCUMENT
        return _REDACTED_VALUE

    def _clean_text(self, value: Any, *, fallback: str, limit: int) -> str:
        if not isinstance(value, str):
            value = fallback
        text = value.strip() if value else fallback
        return text[:limit]

    def _seed_summary(self, seed: dict[str, Any]) -> str:
        questionnaire_summary = seed.get("questionnaire_summary")
        if isinstance(questionnaire_summary, dict):
            business_summary = questionnaire_summary.get("business_summary")
            if isinstance(business_summary, str) and business_summary.strip():
                return business_summary.strip()
        feedback_summary = seed.get("feedback_summary")
        if isinstance(feedback_summary, dict):
            event_count = feedback_summary.get("event_count")
            if isinstance(event_count, int):
                return f"Policy feedback draft based on {event_count} feedback event(s)."
        return "Allocation policy draft"

    def _merge_explanation(self, explanation: str, warnings: list[str]) -> str:
        merged = explanation.strip()
        if warnings:
            warning_text = ", ".join(sorted(set(warnings)))
            merged = f"{merged} Warnings: {warning_text}." if merged else f"Warnings: {warning_text}."
        return merged

    def _source_model_label(self, provider: str, *, fallback: bool) -> str:
        prefix = "gemma-fallback" if fallback else "gemma"
        label = f"{prefix}:{provider}:{self.settings.GEMMA_MODEL}"
        return label[:100]
