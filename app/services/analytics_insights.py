from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.analytics_insights import AnalyticsAIChatRead, AnalyticsAIChatRequest, AnalyticsInsightRead, AnalyticsInsightRequest, AnalyticsInsightStatusRead
from app.services.analytics_ai_providers import AnalyticsAIRequest, get_analytics_ai_provider
from app.services.analytics_service import (
    AI_MONTHLY_QUOTA_FALLBACK,
    build_channels_payload,
    build_home_payload,
    build_operations_payload,
    build_rooms_overview_payload,
    build_segments_payload,
    build_category_detail_payload,
    get_ai_config,
    increment_ai_usage,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _runtime_status() -> dict[str, Any]:
    status_payload = get_analytics_ai_provider().status()
    return {
        "provider": status_payload.provider,
        "configured": status_payload.configured,
        "model": status_payload.effective_model,
        "reachable": status_payload.runtime_healthy,
        "status": status_payload.runtime_status,
        "fallback_reason": status_payload.fallback_reason,
    }


def get_analytics_ai_status(db: Session, *, hotel_id: int) -> AnalyticsInsightStatusRead:
    config = get_ai_config(db, hotel_id)
    runtime = _runtime_status()
    return AnalyticsInsightStatusRead(
        hotel_id=hotel_id,
        analytics_ai_enabled=config.analytics_ai_enabled,
        provider=config.provider,
        runtime_healthy=bool(runtime.get("status") == "ready" or runtime.get("reachable")),
        effective_model=config.effective_model,
        quota_monthly=int(config.quota_monthly or AI_MONTHLY_QUOTA_FALLBACK),
        quota_used=int(config.quota_used or 0),
        quota_remaining=int(config.quota_remaining or 0),
        runtime_status=str(runtime.get("status") or "disabled"),
        fallback_reason=runtime.get("fallback_reason"),
    )


def _request_payload(db: Session, *, hotel_id: int, code: Literal["home", "anomalies", "pricing"], payload: AnalyticsInsightRequest) -> dict[str, Any]:
    if code == "home":
        return build_home_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        )
    if code == "anomalies":
        home_payload = build_home_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        )
        operations_payload = build_operations_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        )
        channels_payload = build_channels_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        )
        segments_payload = build_segments_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        )
        return {
            "home": home_payload.get("data", {}),
            "operations": operations_payload.get("data", {}),
            "channels": channels_payload.get("data", {}),
            "segments": segments_payload.get("data", {}),
        }
    if code == "pricing":
        if payload.category_id is not None:
            category_payload = build_category_detail_payload(
                db,
                hotel_id=hotel_id,
                category_id=payload.category_id,
                date_from=payload.date_from,
                date_to=payload.date_to,
                compare_previous=payload.compare_previous,
                compare_yoy=payload.compare_yoy,
                currency_display=payload.currency_display,
            )
            return {"category": category_payload.get("data", {})}
        rooms_payload = build_rooms_overview_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        )
        return {"rooms": rooms_payload.get("data", {})}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insight code inválido")


_CHAT_DOMAIN_TERMS = {
    "hotel",
    "habitacion",
    "habitaciones",
    "ocupacion",
    "ocupación",
    "reserva",
    "reservas",
    "canal",
    "canales",
    "margen",
    "tarifa",
    "tarifas",
    "pricing",
    "categoria",
    "categorias",
    "categoría",
    "categorías",
    "facturacion",
    "facturación",
    "revenue",
    "ingresos",
    "no-show",
    "noshow",
    "anomalia",
    "anomalía",
    "anomalias",
    "anomalías",
    "operacion",
    "operación",
    "segmento",
    "segmentos",
    "pickup",
    "room",
    "rooms",
    "occupancy",
}

_CHAT_BLOCKED_TERMS = {
    "novela",
    "cuento",
    "poema",
    "programa",
    "programar",
    "codigo",
    "código",
    "web",
    "javascript",
    "python",
    "receta",
    "historia",
    "politica",
    "política",
    "sql",
    "base de datos",
    "otro hotel",
    "otros hoteles",
}


def _assert_analytics_chat_domain(message: str) -> None:
    normalized = " ".join((message or "").lower().split())
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El mensaje no puede estar vacio")
    if any(term in normalized for term in _CHAT_BLOCKED_TERMS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El chat IA Analytics solo responde preguntas del dominio hotelero del hotel actual.")
    if not any(term in normalized for term in _CHAT_DOMAIN_TERMS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El chat IA Analytics solo responde preguntas del dominio hotelero del hotel actual.")


def _chat_context(db: Session, *, hotel_id: int, payload: AnalyticsAIChatRequest) -> dict[str, Any]:
    insight_payload = AnalyticsInsightRequest(
        date_from=payload.date_from,
        date_to=payload.date_to,
        currency_display=payload.currency_display,
        compare_previous=payload.compare_previous,
        compare_yoy=payload.compare_yoy,
    )
    return {
        "home": _request_payload(db, hotel_id=hotel_id, code="home", payload=insight_payload).get("data", {}),
        "operations": build_operations_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        ).get("data", {}),
        "channels": build_channels_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        ).get("data", {}),
        "segments": build_segments_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        ).get("data", {}),
        "rooms": build_rooms_overview_payload(
            db,
            hotel_id=hotel_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            compare_previous=payload.compare_previous,
            compare_yoy=payload.compare_yoy,
            currency_display=payload.currency_display,
        ).get("data", {}),
    }


def _fallback_insight_summary(code: str, context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    recommendations: list[str] = []

    if code == "home":
        cards = context.get("cards") if isinstance(context, dict) else None
        occupancy = None
        no_shows = None
        if isinstance(cards, list):
            for card in cards:
                if not isinstance(card, dict):
                    continue
                if card.get("card_code") == "home_occupancy":
                    occupancy = card.get("value_pct")
                if card.get("card_code") == "home_no_shows":
                    no_shows = card.get("value_count")
        summary = "Insight operativo general del hotel."
        if occupancy is not None:
            summary = f"Ocupación observada en la ventana: {occupancy}%."
            if isinstance(occupancy, (int, float)) and occupancy < 60:
                recommendations.append("Revisar disponibilidad y ritmo de pickups para mejorar ocupación.")
        else:
            recommendations.append("Falta volumen de datos suficiente para concluir sobre ocupación.")
        if isinstance(no_shows, (int, float)) and no_shows > 0:
            warnings.append("Hay no-shows en la ventana analizada.")
        return summary, warnings, recommendations

    if code == "anomalies":
        operations = context.get("operations") if isinstance(context, dict) else None
        room_events = []
        if isinstance(operations, dict):
            room_events = operations.get("room_events") or []
        summary = f"Se encontraron {len(room_events)} señales operativas para revisar."
        if room_events:
            warnings.append("Hay eventos de habitación que merecen seguimiento operativo.")
            recommendations.append("Revisar eventos abiertos o recientes de habitaciones y su impacto sobre disponibilidad.")
        else:
            recommendations.append("No aparecen anomalías operativas relevantes en la ventana.")
        return summary, warnings, recommendations

    if code == "pricing":
        category_data = context.get("category") if isinstance(context, dict) else None
        rooms_data = context.get("rooms") if isinstance(context, dict) else None
        summary = "Propuesta de pricing calculada a partir del comportamiento reciente."
        if isinstance(category_data, dict):
            recommendations.append("Comparar la tarifa actual con la ocupación y el costo variable de la categoría.")
        elif isinstance(rooms_data, dict):
            recommendations.append("Segmentar el pricing por categoría según ocupación y margen operativo.")
        else:
            recommendations.append("No hay suficiente granularidad para una recomendación de pricing fina.")
        return summary, warnings, recommendations

    return "Insight no disponible.", warnings, recommendations


def _build_insight(
    db: Session,
    *,
    hotel_id: int,
    insight_code: Literal["home", "anomalies", "pricing"],
    payload: AnalyticsInsightRequest,
) -> AnalyticsInsightRead:
    config = get_ai_config(db, hotel_id)
    runtime = _runtime_status()
    context = _request_payload(db, hotel_id=hotel_id, code=insight_code, payload=payload)
    runtime_healthy = bool(runtime.get("status") == "ready" or runtime.get("reachable"))

    if not config.analytics_ai_enabled or not runtime_healthy:
        summary, warnings, recommendations = _fallback_insight_summary(insight_code, context)
        return AnalyticsInsightRead(
            hotel_id=hotel_id,
            insight_code=insight_code,
            date_from=payload.date_from,
            date_to=payload.date_to,
            analytics_ai_enabled=config.analytics_ai_enabled,
            provider=str(config.provider),
            runtime_healthy=runtime_healthy,
            effective_model=config.effective_model,
            quota_monthly=config.quota_monthly or AI_MONTHLY_QUOTA_FALLBACK,
            quota_used=config.quota_used or 0,
            quota_remaining=config.quota_remaining or 0,
            generated_at=_now(),
            summary=summary,
            warnings=warnings,
            recommendations=recommendations,
            data={"context": context, "runtime": runtime, "fallback": True},
        )

    usage_row = increment_ai_usage(db, hotel_id)
    try:
        provider = get_analytics_ai_provider()
        ai_result = provider.generate_insight(
            AnalyticsAIRequest(
                hotel_id=hotel_id,
                insight_code=insight_code,
                context=context,
            )
        )
        return AnalyticsInsightRead(
            hotel_id=hotel_id,
            insight_code=insight_code,
            date_from=payload.date_from,
            date_to=payload.date_to,
            analytics_ai_enabled=config.analytics_ai_enabled,
            provider=str(config.provider),
            runtime_healthy=True,
            effective_model=config.effective_model,
            quota_monthly=config.quota_monthly or AI_MONTHLY_QUOTA_FALLBACK,
            quota_used=usage_row.calls_used,
            quota_remaining=max((config.quota_remaining or 0) - 1, 0),
            generated_at=_now(),
            summary=ai_result.summary,
            warnings=ai_result.warnings,
            recommendations=ai_result.recommendations,
            data={"context": context, "runtime": runtime, "model_output": ai_result.raw_response},
        )
    except Exception as exc:
        summary, warnings, recommendations = _fallback_insight_summary(insight_code, context)
        warnings = warnings + [f"AI fallback: {exc.__class__.__name__}"]
        return AnalyticsInsightRead(
            hotel_id=hotel_id,
            insight_code=insight_code,
            date_from=payload.date_from,
            date_to=payload.date_to,
            analytics_ai_enabled=config.analytics_ai_enabled,
            provider=str(config.provider),
            runtime_healthy=True,
            effective_model=config.effective_model,
            quota_monthly=config.quota_monthly or AI_MONTHLY_QUOTA_FALLBACK,
            quota_used=usage_row.calls_used,
            quota_remaining=max((config.quota_remaining or 0) - 1, 0),
            generated_at=_now(),
            summary=summary,
            warnings=warnings,
            recommendations=recommendations,
            data={"context": context, "runtime": runtime, "fallback": True, "error": exc.__class__.__name__},
        )


def build_home_insight(db: Session, *, hotel_id: int, payload: AnalyticsInsightRequest) -> AnalyticsInsightRead:
    return _build_insight(db, hotel_id=hotel_id, insight_code="home", payload=payload)


def build_anomalies_insight(db: Session, *, hotel_id: int, payload: AnalyticsInsightRequest) -> AnalyticsInsightRead:
    return _build_insight(db, hotel_id=hotel_id, insight_code="anomalies", payload=payload)


def build_pricing_insight(db: Session, *, hotel_id: int, payload: AnalyticsInsightRequest) -> AnalyticsInsightRead:
    return _build_insight(db, hotel_id=hotel_id, insight_code="pricing", payload=payload)


def build_analytics_chat_answer(db: Session, *, hotel_id: int, payload: AnalyticsAIChatRequest) -> AnalyticsAIChatRead:
    _assert_analytics_chat_domain(payload.message)
    config = get_ai_config(db, hotel_id)
    runtime = _runtime_status()
    runtime_healthy = bool(runtime.get("status") == "ready" or runtime.get("reachable"))
    if not config.analytics_ai_enabled or not runtime_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La IA todavía no está conectada. Configurá el proveedor de IA para usar el asistente.",
        )

    context = _chat_context(db, hotel_id=hotel_id, payload=payload)
    usage_row = increment_ai_usage(db, hotel_id)
    try:
        provider = get_analytics_ai_provider()
        ai_result = provider.generate_chat_answer(
            AnalyticsAIRequest(hotel_id=hotel_id, insight_code="chat", context=context),
            message=payload.message,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La IA todavía no está conectada. Configurá el proveedor de IA para usar el asistente.",
        ) from exc
    db.flush()
    return AnalyticsAIChatRead(
        hotel_id=hotel_id,
        answer=ai_result.summary,
        warnings=ai_result.warnings,
        recommendations=ai_result.recommendations,
        generated_at=_now(),
    )
