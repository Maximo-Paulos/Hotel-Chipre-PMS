"""Coalesce reservation reoptimization work by hotel."""
from __future__ import annotations

import logging
import threading
import time

from app.services.distributed_lock import DistributedLockBusy

logger = logging.getLogger(__name__)

_state_lock = threading.Lock()
_running_hotels: set[int] = set()
_pending_by_hotel: dict[int, tuple[str, str | None]] = {}


def _run_reoptimization_once(hotel_id: int, trigger_type: str, origin_key: str | None) -> None:
    """Run one SQL-backed pass, retrying only transient lock contention."""
    from app.database import get_session_factory
    from app.services.allocation_runtime_service import run_persisted_allocation
    from app.services.tenant_context import set_tenant_hotel_context

    max_attempts = 10
    for attempt in range(max_attempts):
        db = None
        try:
            session_factory = get_session_factory()
            db = session_factory()
            if origin_key:
                db.info["domain_event_origin_key"] = origin_key
            set_tenant_hotel_context(db, hotel_id)
            run_persisted_allocation(db, hotel_id=hotel_id, trigger_type=trigger_type)
            db.commit()
            return
        except DistributedLockBusy as exc:
            if db is not None:
                db.rollback()
            if attempt + 1 >= max_attempts:
                logger.error(
                    "Background reservation reoptimization lock remained busy for hotel_id=%s trigger_type=%s",
                    hotel_id,
                    trigger_type,
                    extra={"error_type": type(exc).__name__},
                )
                return
            # Retry outside a checked-out session; ordinary requests do not poll.
            time.sleep(min(0.1 * (2**attempt), 1.0))
        except Exception as exc:
            logger.error(
                "Background reservation reoptimization failed for hotel_id=%s trigger_type=%s",
                hotel_id,
                trigger_type,
                extra={"error_type": type(exc).__name__},
            )
            if db is not None:
                db.rollback()
            return
        finally:
            if db is not None:
                db.close()


def trigger_reoptimization_bg(
    hotel_id: int,
    trigger_type: str = "new_reservation",
    origin_key: str | None = None,
) -> None:
    """Reoptimize once per hotel and coalesce concurrent same-process triggers.

    The selected Render profile runs one API process. Triggers that arrive
    during a pass mark the hotel dirty; the active task performs one follow-up
    pass against the latest committed state instead of launching duplicate
    solvers or silently dropping the invalidation. PostgreSQL advisory locking
    remains the cross-process guard during service replacement.
    """
    with _state_lock:
        if hotel_id in _running_hotels:
            _pending_by_hotel[hotel_id] = (trigger_type, origin_key)
            return
        _running_hotels.add(hotel_id)
        trigger_type, origin_key = _pending_by_hotel.pop(
            hotel_id, (trigger_type, origin_key)
        )

    try:
        while True:
            _run_reoptimization_once(hotel_id, trigger_type, origin_key)
            with _state_lock:
                pending = _pending_by_hotel.pop(hotel_id, None)
                if pending is None:
                    _running_hotels.discard(hotel_id)
                    return
            trigger_type, origin_key = pending
    except BaseException:
        # Preserve a pending invalidation; the next trigger can claim and run it.
        with _state_lock:
            _running_hotels.discard(hotel_id)
        raise
