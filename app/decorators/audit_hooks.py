from __future__ import annotations

import functools
import inspect
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, TypeVar

from sqlalchemy.orm import Session

from app.database import Base
from app.models.audit_log import AuditActionEnum, AuditLog

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _entity_to_dict(entity: Any) -> dict[str, Any]:
    if entity is None or not hasattr(entity, "__table__"):
        return {}

    return {
        column.name: getattr(entity, column.name, None)
        for column in entity.__table__.columns
        if not column.name.startswith("_")
    }


def _payload(state: dict[str, Any] | None) -> str | None:
    if not state:
        return None
    return json.dumps(state, sort_keys=True, default=_json_default)


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
        ("actor_user_id", "user_id", "current_user_id", "override_user_id"),
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
                    db.add(
                        AuditLog(
                            hotel_id=hotel_id,
                            table_name=table_name,
                            record_id=final_record_id,
                            action=audit_action,
                            actor_user_id=actor_user_id,
                            payload_before=_payload(before_state),
                            payload_after=_payload(after_state),
                        )
                    )
                    db.flush()
            except Exception:
                logger.exception(
                    "Audit logging failed for %s table=%s record_id=%s action=%s",
                    func.__name__,
                    table_name,
                    record_id,
                    audit_action.value,
                )

            return result

        return wrapper  # type: ignore[return-value]

    return decorator
