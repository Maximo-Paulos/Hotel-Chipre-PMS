from __future__ import annotations

from app.adapters.job_dispatcher import TASK_SPECS, JobDispatcher, dispatch_once
from app.models.job_runtime import ServiceHeartbeat
from app.services.service_heartbeat import record_heartbeat


class _FakeDispatcher(JobDispatcher):
    def __init__(self):
        self.calls = []

    def dispatch(self, task_name, *, args=(), kwargs=None, spec=None, headers=None):
        self.calls.append((task_name, args, kwargs, spec, headers))
        return "fake-task-id"


def test_dispatch_once_is_postgres_dedupe_contract(db, hotel_config):
    dispatcher = _FakeDispatcher()
    row, created = dispatch_once(
        db,
        dispatcher,
        hotel_id=hotel_config.id,
        task_name="domain_events.publish_outbox",
        deduplication_key="outbox:1",
        kwargs={"hotel_id": hotel_config.id},
        correlation_id="corr-1",
    )
    db.commit()
    duplicate, duplicate_created = dispatch_once(
        db,
        dispatcher,
        hotel_id=hotel_config.id,
        task_name="domain_events.publish_outbox",
        deduplication_key="outbox:1",
    )
    assert created is True
    assert duplicate_created is False
    assert duplicate.id == row.id
    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0][3] == TASK_SPECS["domain_events.publish_outbox"]
    assert dispatcher.calls[0][4]["hotel_id"] == hotel_config.id


def test_record_heartbeat_updates_same_identity(db, monkeypatch):
    record = record_heartbeat(db, service_name="worker", instance_id="local-1", queue_name="critical")
    db.commit()
    updated = record_heartbeat(db, service_name="worker", instance_id="local-1", queue_name="heavy", metadata={"lag": 0})
    db.commit()
    assert updated.id == record.id
    assert updated.queue_name == "heavy"
    assert db.query(ServiceHeartbeat).count() == 1
