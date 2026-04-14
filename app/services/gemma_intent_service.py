from __future__ import annotations

from dataclasses import dataclass, field
import unicodedata


@dataclass(slots=True)
class GemmaIntent:
    intent_type: str
    mode: str
    confidence: float
    keywords: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)


def classify_gemma_intent(message: str) -> GemmaIntent:
    normalized = _normalize(message)
    if len(normalized) < 6:
        return GemmaIntent(
            intent_type="clarify_request",
            mode="clarify",
            confidence=0.2,
            missing_information=["Explicame un poco mas que queres revisar o cambiar."],
        )

    keywords = _extract_keywords(normalized)
    is_question = any(token in normalized for token in ("?", "por que", "porque", "como ", "cual ", "que "))

    if any(token in normalized for token in ("booking", "expedia", "despegar", "canal")) and any(
        token in normalized for token in ("menos reservas", "cayo", "bajo", "rinde", "rendimiento", "ocupa", "ocupacion")
    ):
        return GemmaIntent("analyze_channel_drop", "analysis", 0.9, keywords)

    if any(token in normalized for token in ("rendimiento", "rindio", "ocupa", "ocupacion", "reservas", "restricciones", "hotel este mes")) and is_question:
        return GemmaIntent("analyze_performance", "analysis", 0.88, keywords)

    if any(token in normalized for token in ("solver", "asignacion", "habitacion", "por que se asigno", "motor")) and is_question:
        return GemmaIntent("explain_solver_behavior", "analysis", 0.8, keywords)

    if any(
        token in normalized
        for token in (
            "quiero",
            "cambiar",
            "ajustar",
            "configurar",
            "priorizar",
            "proteger",
            "dejar libres",
            "no quiero",
            "evitar",
        )
    ):
        if any(token in normalized for token in ("booking", "expedia", "despegar", "canal")):
            return GemmaIntent("configure_channel_rule", "proposal", 0.86, keywords)
        return GemmaIntent("configure_allocation_policy", "proposal", 0.84, keywords)

    if any(token in normalized for token in ("movi", "movi la reserva", "corrigi", "cambie manualmente", "override")):
        return GemmaIntent("capture_override_reason", "clarify", 0.7, keywords)

    if any(token in normalized for token in ("recomenda", "sugerime", "que me conviene", "mejorar")):
        return GemmaIntent("recommend_change", "analysis", 0.72, keywords)

    return GemmaIntent("unsupported_request", "unsupported", 0.35, keywords)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(ascii_text.lower().strip().split())


def _extract_keywords(normalized: str) -> list[str]:
    interesting = (
        "booking",
        "expedia",
        "despegar",
        "ocupacion",
        "restricciones",
        "huecos",
        "estadias largas",
        "habitacion",
        "asignacion",
        "solver",
    )
    return [token for token in interesting if token in normalized]
