"""Small durable heartbeat API for workers and schedulers."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.job_runtime import ServiceHeartbeat


def record_heartbeat(
    db: Session,
    *,
    service_name: str,
    instance_id: str,
    queue_name: str | None = None,
    metadata: dict | None = None,
) -> ServiceHeartbeat:
    environment = get_settings().APP_ENV
    row = (
        db.query(ServiceHeartbeat)
        .filter(
            ServiceHeartbeat.environment == environment,
            ServiceHeartbeat.service_name == service_name,
            ServiceHeartbeat.instance_id == instance_id,
        )
        .one_or_none()
    )
    if row is None:
        row = ServiceHeartbeat(environment=environment, service_name=service_name, instance_id=instance_id)
        db.add(row)
    row.queue_name = queue_name
    row.last_seen_at = datetime.now(timezone.utc)
    row.metadata_json = json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))
    db.flush()
    return row
