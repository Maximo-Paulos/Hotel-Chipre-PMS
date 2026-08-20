from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, TypeVar

from sqlalchemy.orm import Session

from app.database import Base
from app.models.audit_log import AuditActionEnum, AuditLog
from app.services.audit_log_service import model_snapshot, payload_json
from app.services.audit_projection import project_audit_to_mongo

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _entity_to_dict(entity: Any) -> dict[str, Any]:
    return model_snapshot(entity) or {}


def _payload(table_name: str, state: dict[str, Any] | None) -> str | None:
    return payload_json(state, table_name=table_name)


def _audit_projection_doc(audit_log: AuditLog) -> dict[str, Any]:
    action = audit_log.action.value if isinstance(audit_log.action, AuditActionEnum) else str(audit_log.action)
    timestamp = audit_log.created_at.isoformat() if audit_log.created_at else None
    return {
        "hotel_id": audit_log.hotel_id,
        "table_name": audit_log.table_name,
        "record_id": audit_log.record_id,
        "action": action,
        "actor_user_id": audit_log.actor_user_id,
        "payload_before": audit_log.payload_before,
        "payload_after": audit_log.payload_after,
        "timestamp": timestamp,
    }


def _get_model_for_table(table_name: str) -> type[Any] | None:
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if getattr(model, "__tablename__", None) == table_name:
            return model
    return None


def _first_bound_value(bound: inspect.BoundArguments, names: tuple[str, ...]) -> Any:
    for name in names:
        if name in bound.arguments:
            return bound.arguments[name]
    return None


def _extract_entity_arg(bound: inspect.BoundArguments, table_name: str) -> Any | None:
    for value in bound.arguments.values():
        if hasattr(value, "__table__") and getattr(value, "__tablename__", None) == table_name:
            return value
    return None


def _extract_db(bound: inspect.BoundArguments) -> Session | None:
    value = _first_bound_value(bound, ("db", "session"))
    if isinstance(value, Session):
        return value

    for arg in bound.arguments.values():
        if isinstance(arg, Session):
            return arg
    return None


def _extract_actor_user_id(bound: inspect.BoundArguments) -> int | None:
    value = _first_bound_value(
        bound,
        (
            "actor_user_id",
            "user_id",
            "current_user_id",
            "override_user_id",
            "changed_by_user_id",
            "created_by_user_id",
            "moved_by_user_id",
        ),
    )
    return value if isinstance(value, int) else None


def _extract_record_id(bound: inspect.BoundArguments, table_name: str, result: Any = None) -> int | None:
    if result is not None and hasattr(result, "__table__") and getattr(result, "__tablename__", None) == table_name:
        result_id = getattr(result, "id", None)
        return result_id if isinstance(result_id, int) else None

    entity_arg = _extract_entity_arg(bound, table_name)
    if entity_arg is not None:
        entity_id = getattr(entity_arg, "id", None)
        return entity_id if isinstance(entity_id, int) else None

    last_table_token = table_name.split("_")[-1].rstrip("s")
    candidates = (
        "record_id",
        "entity_id",
        "id",
        f"{table_name.rstrip('s')}_id",
        f"{last_table_token}_id",
    )
    value = _first_bound_value(bound, candidates)
    return value if isinstance(value, int) else None


def _load_entity(
    db: Session | None,
    *,
    table_name: str,
    record_id: int | None,
    hotel_id: int | None,
) -> Any | None:
    if db is None or record_id is None:
        return None

    model = _get_model_for_table(table_name)
    if model is None:
        return None

    query = db.query(model).filter(model.id == record_id)
    if hotel_id is not None and hasattr(model, "hotel_id"):
        query = query.filter(model.hotel_id == hotel_id)
    return query.one_or_none()


def audited_change(table_name: str, action: AuditActionEnum | str) -> Callable[[F], F]:
    """Record an AuditLog row for a successful entity mutation."""

    audit_action = action if isinstance(action, AuditActionEnum) else AuditActionEnum(action)

    def decorator(func: F) -> F:
        signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            db = _extract_db(bound)
            hotel_id = _first_bound_value(bound, ("hotel_id",))
            hotel_id = hotel_id if isinstance(hotel_id, int) else None
            actor_user_id = _extract_actor_user_id(bound)
            entity_arg = _extract_entity_arg(bound, table_name)
            if hotel_id is None and entity_arg is not None:
                entity_hotel_id = getattr(entity_arg, "hotel_id", None)
                hotel_id = entity_hotel_id if isinstance(entity_hotel_id, int) else None
            record_id = _extract_record_id(bound, table_name)
            before_state = _entity_to_dict(
                entity_arg or _load_entity(db, table_name=table_name, record_id=record_id, hotel_id=hotel_id)
            )

            result = func(*args, **kwargs)

            try:
                final_record_id = record_id or _extract_record_id(bound, table_name, result)
                after_entity = (
                    result
                    if hasattr(result, "__table__") and getattr(result, "__tablename__", None) == table_name
                    else _extract_entity_arg(bound, table_name)
                    or _load_entity(
                        db,
                        table_name=table_name,
                        record_id=final_record_id,
                        hotel_id=hotel_id,
                    )
                )
                after_state = _entity_to_dict(after_entity)

                if db is None or hotel_id is None or final_record_id is None:
                    logger.warning(
                        "Skipping audit log for %s: missing db, hotel_id, or record_id",
                        func.__name__,
                    )
                    return result

                with db.begin_nested():
                    audit_log = AuditLog(
                        hotel_id=hotel_id,
                        table_name=table_name,
                        record_id=final_record_id,
                        action=audit_action,
                        actor_user_id=actor_user_id,
                        payload_before=_payload(table_name, before_state),
                        payload_after=_payload(table_name, after_state),
                    )
                    db.add(audit_log)
                    db.flush()
                    try:
                        project_audit_to_mongo(_audit_projection_doc(audit_log))
                    except Exception:
                        logger.debug(
                            "Audit Mongo projection failed for %s table=%s record_id=%s action=%s",
                            func.__name__,
                            table_name,
                            final_record_id,
                            audit_action.value,
                        )
            except Exception as exc:
                logger.error(
                    "Audit logging failed for %s table=%s record_id=%s action=%s",
                    func.__name__,
                    table_name,
                    record_id,
                    audit_action.value,
                    extra={"error_type": type(exc).__name__},
                )

            return result

        return wrapper  # type: ignore[return-value]

    return decorator
