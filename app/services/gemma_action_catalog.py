from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class GemmaSuggestedAction:
    action_type: str
    label: str
    payload: dict
    requires_confirmation: bool = True


@dataclass(slots=True)
class GemmaProposalPreview:
    title: str
    impact_summary: str
    rationale: list[str] = field(default_factory=list)
    changed_weights: list[dict] = field(default_factory=list)
    changed_constraints: list[dict] = field(default_factory=list)


def build_controlled_proposal(
    *,
    intent_type: str,
    message: str,
    context: dict,
) -> tuple[list[dict], dict] | tuple[list, None]:
    if intent_type not in {"configure_allocation_policy", "configure_channel_rule"}:
        return [], None

    normalized = " ".join((message or "").lower().split())
    policy = context.get("allocation_policy") or {}
    weights = dict(policy.get("weights") or {})
    constraints = dict(policy.get("constraints") or {})

    changed_weights: list[dict] = []
    changed_constraints: list[dict] = []
    rationale: list[str] = []
    action_payload: dict = {"weights": {}, "constraints": {}}

    def update_weight(key: str, target: float, reason: str) -> None:
        current = float(weights.get(key, 0.0))
        target_value = max(current, float(target))
        if target_value <= current:
            return
        action_payload["weights"][key] = target_value
        changed_weights.append({"key": key, "from": current, "to": target_value})
        rationale.append(reason)

    def update_constraint(key: str, target: bool, reason: str) -> None:
        current = bool(constraints.get(key))
        if current == target:
            return
        action_payload["constraints"][key] = target
        changed_constraints.append({"key": key, "from": current, "to": target})
        rationale.append(reason)

    if any(token in normalized for token in ("huecos", "hueco", "noches sueltas", "fragment")):
        update_weight("room_usage_penalty", float(weights.get("room_usage_penalty", 50.0)) + 20.0, "Subir penalizacion de uso para reducir fragmentacion.")
    if any(token in normalized for token in ("estadias largas", "estadias largas.", "larga", "largas")):
        update_weight("fallback_priority_penalty", float(weights.get("fallback_priority_penalty", 25.0)) + 15.0, "Reservar mas flexibilidad futura para estadias de mayor valor.")
    if any(token in normalized for token in ("misma categoria", "exact match", "exacta", "exacto")):
        update_weight("prefer_exact_match", float(weights.get("prefer_exact_match", 500.0)) + 150.0, "Favorecer asignaciones en la misma categoria.")
    if any(token in normalized for token in ("no mover", "evitar mover", "mover huesped", "mover reservas")):
        update_weight("stability", float(weights.get("stability", 5.0)) + 2.0, "Reducir cambios manuales y movimientos de habitacion.")
    if any(token in normalized for token in ("sin fallback", "no fallback", "sin cambio de categoria", "misma categoria siempre")):
        update_constraint("allow_category_fallback", False, "Desactivar fallback para exigir match de categoria.")

    if intent_type == "configure_channel_rule":
        channel = _detect_channel(normalized)
        if channel:
            action = GemmaSuggestedAction(
                action_type="channel.rule.review",
                label=f"Revisar configuracion de {channel}",
                payload={
                    "channel_code": channel,
                    "requested_change": message.strip(),
                },
                requires_confirmation=True,
            )
            preview = GemmaProposalPreview(
                title=f"Revision controlada para {channel}",
                impact_summary=f"Se prepararia una revision de reglas del canal {channel} antes de ejecutar cambios.",
                rationale=["El pedido menciona un canal especifico y requiere validacion comercial."],
            )
            return [asdict(action)], asdict(preview)

    if not action_payload["weights"] and not action_payload["constraints"]:
        return [], None

    action = GemmaSuggestedAction(
        action_type="allocation_policy.update_preview",
        label="Preparar propuesta de politica de asignacion",
        payload=action_payload,
        requires_confirmation=True,
    )
    preview = GemmaProposalPreview(
        title="Preview de politica de asignacion",
        impact_summary="Se generaria un ajuste controlado sobre la politica activa para revisar antes de aplicar.",
        rationale=_dedupe_preserve_order(rationale),
        changed_weights=changed_weights,
        changed_constraints=changed_constraints,
    )
    return [asdict(action)], asdict(preview)


def _detect_channel(normalized_message: str) -> str | None:
    for channel in ("booking", "expedia", "despegar"):
        if channel in normalized_message:
            return channel
    return None


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
