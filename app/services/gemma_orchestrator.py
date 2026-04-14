from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.ai_assistant import AIAssistantInsight, AIAssistantMessage, AIAssistantSession
from app.models.user import User
from app.services.gemma_action_catalog import build_controlled_proposal
from app.services.gemma_action_run_service import create_action_runs_for_response
from app.services.gemma_context_service import build_gemma_hotel_context
from app.services.gemma_intent_service import GemmaIntent, classify_gemma_intent
from app.services.gemma_service import GemmaService

LOGGER = logging.getLogger(__name__)

ALLOWED_RUNTIME_MODES = {"analysis", "proposal", "clarify", "unsupported"}


class GemmaChatError(RuntimeError):
    """Raised when the assistant flow cannot be completed safely."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class GemmaChatResult:
    session: AIAssistantSession
    user_message: AIAssistantMessage
    assistant_message: AIAssistantMessage
    response_payload: dict[str, Any]


class GemmaOrchestrator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._gemma = GemmaService(self.settings)

    def send_message(
        self,
        db: Session,
        *,
        hotel_id: int,
        user_id: int | None,
        user_role: str | None,
        message: str,
        session_id: int | None = None,
    ) -> GemmaChatResult:
        cleaned_message = (message or "").strip()
        if not cleaned_message:
            raise GemmaChatError("El mensaje no puede estar vacio")
        self._assert_message_rate_limit(db, hotel_id=hotel_id, user_id=user_id)

        session = self._get_or_create_session(
            db,
            hotel_id=hotel_id,
            user_id=user_id,
            session_id=session_id,
            seed_title=_build_session_title(cleaned_message),
        )
        intent = classify_gemma_intent(cleaned_message)
        redacted_message = self._gemma.redact_text_for_llm(cleaned_message, limit=4000)
        user_message = AIAssistantMessage(
            session=session,
            hotel_id=hotel_id,
            role="user",
            raw_text=cleaned_message,
            redacted_text=redacted_message,
            intent_type=intent.intent_type,
            payload_json=json.dumps(
                {
                    "mode": intent.mode,
                    "confidence": intent.confidence,
                    "keywords": intent.keywords,
                    "missing_information": intent.missing_information,
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
        )
        db.add(user_message)
        db.flush()

        context = build_gemma_hotel_context(db, hotel_id=hotel_id, intent_type=intent.intent_type)
        response_payload = self._build_response_payload(
            session=session,
            db=db,
            hotel_id=hotel_id,
            user_id=user_id,
            user_role=user_role,
            intent=intent,
            message=cleaned_message,
            context=context,
        )
        assistant_message = AIAssistantMessage(
            session=session,
            hotel_id=hotel_id,
            role="assistant",
            raw_text=response_payload["answer"],
            redacted_text=response_payload["answer"],
            intent_type=intent.intent_type,
            payload_json=json.dumps(response_payload, ensure_ascii=True, sort_keys=True),
        )
        db.add(assistant_message)
        session.updated_at = datetime.now(timezone.utc)
        self._persist_insight(
            db,
            session=session,
            hotel_id=hotel_id,
            intent=intent,
            payload=response_payload,
        )
        db.flush()

        return GemmaChatResult(
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
            response_payload=response_payload,
        )

    def list_sessions(
        self,
        db: Session,
        *,
        hotel_id: int,
        user_id: int | None,
        limit: int = 20,
        include_archived: bool = False,
    ) -> list[AIAssistantSession]:
        query = (
            db.query(AIAssistantSession)
            .filter(AIAssistantSession.hotel_id == hotel_id)
            .order_by(AIAssistantSession.updated_at.desc(), AIAssistantSession.id.desc())
        )
        if user_id is not None:
            query = query.filter(AIAssistantSession.user_id == user_id)
        if not include_archived:
            query = query.filter(AIAssistantSession.status != "archived")
        return query.limit(limit).all()

    def get_session(
        self,
        db: Session,
        *,
        hotel_id: int,
        user_id: int | None,
        session_id: int,
    ) -> AIAssistantSession:
        query = db.query(AIAssistantSession).filter(
            AIAssistantSession.id == session_id,
            AIAssistantSession.hotel_id == hotel_id,
        )
        if user_id is not None:
            query = query.filter(AIAssistantSession.user_id == user_id)
        session = query.first()
        if session is None:
            raise GemmaChatError("Sesion no encontrada")
        return session

    def archive_session(
        self,
        db: Session,
        *,
        hotel_id: int,
        user_id: int | None,
        session_id: int,
    ) -> AIAssistantSession:
        session = self.get_session(db, hotel_id=hotel_id, user_id=user_id, session_id=session_id)
        session.status = "archived"
        session.updated_at = datetime.now(timezone.utc)
        db.flush()
        return session

    def list_insights(
        self,
        db: Session,
        *,
        hotel_id: int,
        user_id: int | None,
        limit: int = 20,
    ) -> list[AIAssistantInsight]:
        query = (
            db.query(AIAssistantInsight)
            .join(AIAssistantSession, AIAssistantSession.id == AIAssistantInsight.session_id)
            .filter(AIAssistantInsight.hotel_id == hotel_id)
            .order_by(AIAssistantInsight.created_at.desc(), AIAssistantInsight.id.desc())
        )
        if user_id is not None:
            query = query.filter(AIAssistantSession.user_id == user_id)
        return query.limit(limit).all()

    def get_runtime_status(self) -> dict[str, Any]:
        provider = (self.settings.GEMMA_PROVIDER or "disabled").strip().lower()
        enabled = bool(self.settings.GEMMA_ENABLED)
        configured = self._local_runtime_enabled()
        base_status = {
            "enabled": enabled,
            "configured": configured,
            "provider": provider or "disabled",
            "model": self.settings.GEMMA_MODEL or None,
            "endpoint_url": self.settings.GEMMA_ENDPOINT_URL or None,
            "strict_json": bool(self.settings.GEMMA_STRICT_JSON),
            "timeout_seconds": float(self.settings.GEMMA_TIMEOUT_SECONDS or 0.0) or None,
            "max_conversation_messages": int(self.settings.GEMMA_MAX_CONVERSATION_MESSAGES or 0) or None,
            "max_input_chars": int(self.settings.GEMMA_MAX_INPUT_CHARS or 0) or None,
            "reachable": False,
            "fallback_reason": None,
            "probe_error": None,
        }
        if not enabled:
            return base_status | {"status": "disabled", "fallback_reason": "GEMMA_ENABLED=false"}
        if provider != "openai_compatible":
            return base_status | {
                "status": "unsupported_provider",
                "fallback_reason": "Solo openai_compatible esta habilitado para el chat local en esta fase.",
            }
        if not configured:
            return base_status | {
                "status": "unconfigured",
                "fallback_reason": "Faltan endpoint o modelo para el runtime local.",
            }

        models_url = _derive_models_endpoint(self.settings.GEMMA_ENDPOINT_URL)
        headers = {}
        if self.settings.GEMMA_API_KEY:
            headers["Authorization"] = f"Bearer {self.settings.GEMMA_API_KEY}"
        timeout_seconds = min(float(self.settings.GEMMA_TIMEOUT_SECONDS or 20.0), 5.0)
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout_seconds)) as client:
                response = client.get(models_url, headers=headers)
                response.raise_for_status()
            return base_status | {"status": "ready", "reachable": True}
        except httpx.TimeoutException:
            return base_status | {
                "status": "timeout",
                "fallback_reason": "El runtime local no respondio a tiempo.",
                "probe_error": "timeout",
            }
        except httpx.HTTPStatusError as exc:
            return base_status | {
                "status": "http_error",
                "fallback_reason": "El runtime local devolvio un estado HTTP invalido.",
                "probe_error": f"http_{exc.response.status_code}" if exc.response is not None else "http_error",
            }
        except Exception as exc:
            return base_status | {
                "status": "unreachable",
                "fallback_reason": "No se pudo alcanzar el runtime local.",
                "probe_error": str(exc),
            }

    def _get_or_create_session(
        self,
        db: Session,
        *,
        hotel_id: int,
        user_id: int | None,
        session_id: int | None,
        seed_title: str,
    ) -> AIAssistantSession:
        if session_id is not None:
            return self.get_session(db, hotel_id=hotel_id, user_id=user_id, session_id=session_id)

        session = AIAssistantSession(
            hotel_id=hotel_id,
            user_id=_resolve_existing_user_id(db, user_id),
            mode="owner_copilot",
            status="active",
            title=seed_title,
        )
        db.add(session)
        db.flush()
        return session

    def _assert_message_rate_limit(self, db: Session, *, hotel_id: int, user_id: int | None) -> None:
        if user_id is None:
            return
        max_messages = int(self.settings.GEMMA_RATE_LIMIT_MAX_MESSAGES or 0)
        window_seconds = int(self.settings.GEMMA_RATE_LIMIT_WINDOW_SECONDS or 0)
        if max_messages <= 0 or window_seconds <= 0:
            return
        window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        recent_count = (
            db.query(AIAssistantMessage)
            .join(AIAssistantSession, AIAssistantSession.id == AIAssistantMessage.session_id)
            .filter(
                AIAssistantMessage.hotel_id == hotel_id,
                AIAssistantMessage.role == "user",
                AIAssistantMessage.created_at >= window_start,
                AIAssistantSession.user_id == user_id,
            )
            .count()
        )
        if recent_count >= max_messages:
            raise GemmaChatError(
                "Superaste el limite temporal de mensajes para Gemma. Espera un momento y vuelve a intentar.",
                status_code=429,
            )

    def _build_response_payload(
        self,
        *,
        session: AIAssistantSession,
        db: Session,
        hotel_id: int,
        user_id: int | None,
        user_role: str | None,
        intent: GemmaIntent,
        message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if intent.mode in {"clarify", "unsupported"}:
            payload = self._fallback_response(intent=intent, message=message, context=context, model_used=False)
            return self._attach_action_runs(db=db, session=session, hotel_id=hotel_id, user_id=user_id, payload=payload)

        if not self._local_runtime_enabled():
            payload = self._fallback_response(intent=intent, message=message, context=context, model_used=False)
            payload["warnings"].append("Gemma local no esta configurado; respondo con fallback deterministico.")
            payload["metadata"].update(
                {
                    "fallback_used": True,
                    "runtime_status": "disabled",
                    "runtime_provider": self.settings.GEMMA_PROVIDER,
                }
            )
            return self._attach_action_runs(db=db, session=session, hotel_id=hotel_id, user_id=user_id, payload=payload)

        try:
            conversation = self._build_conversation_messages(session=session)
            payload = self._call_local_runtime(
                message=message,
                intent=intent,
                context=context,
                user_role=user_role,
                conversation=conversation,
            )
        except httpx.TimeoutException:
            LOGGER.warning("Gemma local timeout for hotel_id=%s intent=%s", hotel_id, intent.intent_type)
            payload = self._fallback_with_runtime_issue(
                intent=intent,
                message=message,
                context=context,
                warning="Gemma local excedio el tiempo limite; respondo con fallback deterministico.",
                runtime_status="timeout",
                error_code="timeout",
            )
            return self._attach_action_runs(db=db, session=session, hotel_id=hotel_id, user_id=user_id, payload=payload)
        except httpx.HTTPStatusError as exc:
            LOGGER.warning(
                "Gemma local http error for hotel_id=%s intent=%s status=%s",
                hotel_id,
                intent.intent_type,
                exc.response.status_code if exc.response is not None else "unknown",
            )
            payload = self._fallback_with_runtime_issue(
                intent=intent,
                message=message,
                context=context,
                warning="Gemma local devolvio un error HTTP; respondo con fallback deterministico.",
                runtime_status="http_error",
                error_code=f"http_{exc.response.status_code}" if exc.response is not None else "http_error",
            )
            return self._attach_action_runs(db=db, session=session, hotel_id=hotel_id, user_id=user_id, payload=payload)
        except GemmaChatError as exc:
            LOGGER.warning("Gemma local payload error for hotel_id=%s intent=%s: %s", hotel_id, intent.intent_type, exc)
            payload = self._fallback_with_runtime_issue(
                intent=intent,
                message=message,
                context=context,
                warning="Gemma local respondio en un formato invalido; uso fallback deterministico.",
                runtime_status="invalid_payload",
                error_code="invalid_payload",
            )
            return self._attach_action_runs(db=db, session=session, hotel_id=hotel_id, user_id=user_id, payload=payload)
        except Exception as exc:
            LOGGER.exception("Gemma local unexpected failure for hotel_id=%s intent=%s", hotel_id, intent.intent_type)
            payload = self._fallback_with_runtime_issue(
                intent=intent,
                message=message,
                context=context,
                warning="Gemma local fallo de forma inesperada; respondo con fallback deterministico.",
                runtime_status="unexpected_error",
                error_code="unexpected_error",
            )
            return self._attach_action_runs(db=db, session=session, hotel_id=hotel_id, user_id=user_id, payload=payload)

        sanitized = self._sanitize_runtime_payload(payload, intent=intent, message=message, context=context)
        return self._attach_action_runs(db=db, session=session, hotel_id=hotel_id, user_id=user_id, payload=sanitized)

    def _local_runtime_enabled(self) -> bool:
        provider = (self.settings.GEMMA_PROVIDER or "").strip().lower()
        return bool(
            self.settings.GEMMA_ENABLED
            and provider == "openai_compatible"
            and self.settings.GEMMA_ENDPOINT_URL
            and self.settings.GEMMA_MODEL
        )

    def _build_conversation_messages(self, *, session: AIAssistantSession, max_messages: int = 6) -> list[dict[str, str]]:
        conversation = []
        for item in session.messages[-int(self.settings.GEMMA_MAX_CONVERSATION_MESSAGES or max_messages) :]:
            content = item.redacted_text if item.role == "user" else item.raw_text
            conversation.append({"role": item.role, "content": content or ""})
        return conversation

    def _call_local_runtime(
        self,
        *,
        message: str,
        intent: GemmaIntent,
        context: dict[str, Any],
        user_role: str | None,
        conversation: list[dict[str, str]],
    ) -> dict[str, Any]:
        endpoint = self.settings.GEMMA_ENDPOINT_URL.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if self.settings.GEMMA_API_KEY:
            headers["Authorization"] = f"Bearer {self.settings.GEMMA_API_KEY}"

        system_prompt = (
            "Sos Gemma 4 integrada a un PMS hotelero. "
            "Responde siempre en espanol simple. "
            "No inventes funcionalidades ni afirmes cambios ejecutados. "
            "En esta fase solo podes analizar y proponer. "
            "Usa unicamente el contexto provisto del hotel activo. "
            "Devolve solo JSON con las claves: mode, summary, answer, warnings, missing_information, confidence, suggested_follow_up, requires_confirmation, actions, preview."
        )
        user_prompt = {
            "intent_type": intent.intent_type,
            "intent_mode": intent.mode,
            "user_role": user_role,
            "latest_user_message": self._gemma.redact_text_for_llm(message, limit=int(self.settings.GEMMA_MAX_INPUT_CHARS or 4000)),
            "recent_conversation": conversation,
            "hotel_context": context,
            "product_limits": {
                "execution_enabled": False,
                "allowed_modes": ["analysis", "proposal", "clarify", "unsupported"],
            },
        }
        body: dict[str, Any] = {
            "model": self.settings.GEMMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=True, sort_keys=True)},
            ],
            "temperature": float(self.settings.GEMMA_TEMPERATURE or 0.2),
            "max_tokens": int(self.settings.GEMMA_MAX_OUTPUT_TOKENS or 1024),
        }
        if self.settings.GEMMA_STRICT_JSON:
            body["response_format"] = {"type": "json_object"}

        timeout = httpx.Timeout(float(self.settings.GEMMA_TIMEOUT_SECONDS or 20.0))
        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        raw_text = self._extract_openai_text(payload)
        return self._decode_json_payload(raw_text)

    def _extract_openai_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        for choice in choices:
            message = choice.get("message") if isinstance(choice, dict) else None
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(choice, dict) and isinstance(choice.get("text"), str):
                return choice["text"]
        raise GemmaChatError("La respuesta del runtime local no contiene texto")

    def _decode_json_payload(self, raw_text: str) -> dict[str, Any]:
        text = (raw_text or "").strip()
        if not text:
            raise GemmaChatError("La respuesta del runtime local vino vacia")
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GemmaChatError("La respuesta del runtime local no es JSON valido") from exc
        if not isinstance(data, dict):
            raise GemmaChatError("La respuesta del runtime local debe ser un objeto")
        return data

    def _sanitize_runtime_payload(
        self,
        payload: dict[str, Any],
        *,
        intent: GemmaIntent,
        message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = self._fallback_response(intent=intent, message=message, context=context, model_used=False)
        mode = str(payload.get("mode") or fallback["mode"]).strip().lower()
        if mode not in ALLOWED_RUNTIME_MODES:
            mode = fallback["mode"]
        summary = _safe_text(payload.get("summary"), fallback["summary"], 240)
        answer = _safe_text(payload.get("answer"), fallback["answer"], 4000)
        warnings = _coerce_string_list(payload.get("warnings")) or []
        missing_information = _coerce_string_list(payload.get("missing_information")) or []
        confidence = _coerce_float(payload.get("confidence"), fallback["confidence"])
        suggested_follow_up = _coerce_string_list(payload.get("suggested_follow_up")) or fallback["metadata"].get("suggested_follow_up", [])
        actions = _coerce_action_list(payload.get("actions"))
        preview = payload.get("preview") if isinstance(payload.get("preview"), dict) else None
        if mode == "proposal" and not actions:
            actions = list(fallback.get("actions") or [])
        if mode == "proposal" and preview is None:
            preview = fallback.get("preview")
        return {
            "mode": mode,
            "summary": summary,
            "answer": answer,
            "requires_confirmation": bool(payload.get("requires_confirmation") if isinstance(payload.get("requires_confirmation"), bool) else fallback.get("requires_confirmation", False)),
            "actions": actions,
            "preview": preview,
            "warnings": warnings,
            "missing_information": missing_information,
            "confidence": confidence,
            "metadata": {
                "intent_type": intent.intent_type,
                "used_model": self.settings.GEMMA_MODEL,
                "fallback_used": False,
                "runtime_status": "ok",
                "runtime_provider": self.settings.GEMMA_PROVIDER,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "suggested_follow_up": suggested_follow_up,
            },
        }

    def _fallback_response(
        self,
        *,
        intent: GemmaIntent,
        message: str,
        context: dict[str, Any],
        model_used: bool,
    ) -> dict[str, Any]:
        reservation_summary = context["reservation_summary"]
        operations = context["operations"]
        policy = context["allocation_policy"]
        hotel = context["hotel"]

        if intent.mode == "clarify":
            return {
                "mode": "clarify",
                "summary": "Necesito una aclaracion para ayudarte bien.",
                "answer": "Necesito un poco mas de detalle para responder con precision. Decime si queres analizar rendimiento, revisar una configuracion o entender una asignacion.",
                "requires_confirmation": False,
                "actions": [],
                "preview": None,
                "warnings": [],
                "missing_information": intent.missing_information or ["Aclara el objetivo puntual."],
                "confidence": 0.35,
                "metadata": {"intent_type": intent.intent_type, "used_model": self.settings.GEMMA_MODEL if model_used else None, "suggested_follow_up": []},
            }

        if intent.mode == "unsupported":
            return {
                "mode": "unsupported",
                "summary": "Ese pedido todavia no esta soportado por Gemma en esta fase.",
                "answer": "Hoy puedo analizar el hotel, explicar senales operativas y preparar propuestas de configuracion. No puedo ejecutar acciones fuera de ese catalogo.",
                "requires_confirmation": False,
                "actions": [],
                "preview": None,
                "warnings": ["Pedido fuera del alcance de Fase 1."],
                "missing_information": [],
                "confidence": 0.3,
                "metadata": {"intent_type": intent.intent_type, "used_model": self.settings.GEMMA_MODEL if model_used else None, "suggested_follow_up": ["Preguntame por ocupacion, canales o politica de asignacion."]},
            }

        if intent.intent_type in {"analyze_performance", "analyze_channel_drop", "recommend_change"}:
            recent_mix = reservation_summary["recent_source_mix"]
            top_source = next(iter(recent_mix.items()), ("sin datos", 0))
            answer = (
                f"Hotel activo: {hotel['hotel_name']}. "
                f"En la ventana reciente hay {reservation_summary['recent_reservation_count']} reservas y "
                f"{reservation_summary['upcoming_active_reservation_count']} activas hacia adelante. "
                f"El canal con mas peso reciente es {top_source[0]} ({top_source[1]} reservas). "
                f"Hoy hay {operations['pending_action_count']} acciones pendientes y "
                f"{reservation_summary['upcoming_unassigned_count']} reservas futuras sin habitacion asignada."
            )
            warnings = []
            if reservation_summary["upcoming_manual_review_count"] > 0:
                warnings.append("Hay reservas en revision manual que pueden afectar la conversion operativa.")
            return {
                "mode": "analysis",
                "summary": "Snapshot operativo del hotel.",
                "answer": answer,
                "requires_confirmation": False,
                "actions": [],
                "preview": None,
                "warnings": warnings,
                "missing_information": [],
                "confidence": 0.66,
                "metadata": {
                    "intent_type": intent.intent_type,
                    "used_model": self.settings.GEMMA_MODEL if model_used else None,
                    "suggested_follow_up": [
                        "Preguntame por Booking, Expedia o Despegar en particular.",
                        "Puedo preparar una propuesta para ajustar la politica de asignacion.",
                    ],
                },
            }

        if intent.intent_type == "explain_solver_behavior":
            top_weights = sorted(policy["weights"].items(), key=lambda item: item[1], reverse=True)[:3]
            answer = (
                "La asignacion actual se guia por la politica publicada del hotel. "
                f"Las restricciones activas son {', '.join(key for key, value in policy['constraints'].items() if value)}. "
                f"Los pesos mas fuertes hoy son {', '.join(f'{key}={value}' for key, value in top_weights)}."
            )
            return {
                "mode": "analysis",
                "summary": "Explicacion de la politica activa.",
                "answer": answer,
                "requires_confirmation": False,
                "actions": [],
                "preview": None,
                "warnings": [],
                "missing_information": [],
                "confidence": 0.7,
                "metadata": {
                    "intent_type": intent.intent_type,
                    "used_model": self.settings.GEMMA_MODEL if model_used else None,
                    "suggested_follow_up": ["Si queres, te preparo una propuesta para cambiar pesos o restricciones."],
                },
            }

        actions, preview = build_controlled_proposal(intent_type=intent.intent_type, message=message, context=context)
        return {
            "mode": "proposal",
            "summary": "Puedo convertir este pedido en una propuesta controlada.",
            "answer": (
                "Entendi que queres cambiar el comportamiento del sistema. "
                "En Fase 1 no aplico cambios automaticamente, pero ya puedo preparar una propuesta basada en la politica activa, "
                f"que hoy usa el perfil {policy['profile_code']} y {reservation_summary['upcoming_active_reservation_count']} reservas activas en horizonte."
            ),
            "requires_confirmation": True,
            "actions": actions,
            "preview": preview,
            "warnings": ["Fase 1 solo responde y prepara propuestas; no ejecuta cambios."],
            "missing_information": [],
            "confidence": 0.62,
            "metadata": {
                "intent_type": intent.intent_type,
                "used_model": self.settings.GEMMA_MODEL if model_used else None,
                "fallback_used": not model_used,
                "runtime_status": "fallback_only",
                "runtime_provider": self.settings.GEMMA_PROVIDER,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "suggested_follow_up": [
                    "Decime que queres priorizar: exact match, menos huecos o proteger estadias largas.",
                ],
            },
        }

    def _fallback_with_runtime_issue(
        self,
        *,
        intent: GemmaIntent,
        message: str,
        context: dict[str, Any],
        warning: str,
        runtime_status: str,
        error_code: str,
    ) -> dict[str, Any]:
        payload = self._fallback_response(intent=intent, message=message, context=context, model_used=False)
        payload["warnings"].append(warning)
        payload["metadata"].update(
            {
                "fallback_used": True,
                "runtime_status": runtime_status,
                "runtime_provider": self.settings.GEMMA_PROVIDER,
                "runtime_error_code": error_code,
            }
        )
        return payload

    def _attach_action_runs(
        self,
        *,
        db: Session,
        session: AIAssistantSession,
        hotel_id: int,
        user_id: int | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if str(payload.get("mode")) != "proposal":
            return payload
        actions = payload.get("actions")
        if not isinstance(actions, list) or not actions:
            return payload
        persisted_actions = create_action_runs_for_response(
            db,
            session=session,
            hotel_id=hotel_id,
            user_id=user_id,
            actions=actions,
            preview=payload.get("preview") if isinstance(payload.get("preview"), dict) else None,
        )
        payload["actions"] = persisted_actions
        return payload

    def _persist_insight(
        self,
        db: Session,
        *,
        session: AIAssistantSession,
        hotel_id: int,
        intent: GemmaIntent,
        payload: dict[str, Any],
    ) -> None:
        mode = str(payload.get("mode") or "").strip().lower()
        if mode not in {"analysis", "proposal", "execution", "learning"}:
            return
        summary = _safe_text(payload.get("summary"), "", 240)
        if not summary:
            return
        insight = AIAssistantInsight(
            session_id=session.id,
            hotel_id=hotel_id,
            insight_type=mode,
            summary=summary,
            details_json=json.dumps(
                {
                    "intent_type": intent.intent_type,
                    "mode": mode,
                    "confidence": payload.get("confidence"),
                    "warnings": list(payload.get("warnings") or []),
                    "missing_information": list(payload.get("missing_information") or []),
                    "metadata": dict(payload.get("metadata") or {}),
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
        )
        db.add(insight)


def _build_session_title(message: str) -> str:
    text = " ".join((message or "").strip().split())
    if len(text) <= 80:
        return text
    return text[:77].rstrip() + "..."


def _safe_text(value: Any, fallback: str | None, max_length: int) -> str:
    if not isinstance(value, str):
        value = fallback or ""
    return value.strip()[:max_length]


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                result.append(cleaned[:200])
    return result


def _coerce_float(value: Any, fallback: float | None) -> float | None:
    if value in (None, ""):
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_action_list(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    result: list[dict] = []
    for item in value:
        if isinstance(item, dict):
            result.append(item)
    return result


def _resolve_existing_user_id(db: Session, user_id: int | None) -> int | None:
    if user_id is None:
        return None
    exists = db.query(User.id).filter(User.id == user_id).first()
    return user_id if exists else None


def _derive_models_endpoint(endpoint_url: str | None) -> str:
    raw = (endpoint_url or "").rstrip("/")
    if raw.endswith("/chat/completions"):
        return raw[: -len("/chat/completions")] + "/models"
    return raw + "/models"
