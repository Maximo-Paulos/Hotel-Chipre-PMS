from __future__ import annotations

from types import SimpleNamespace

from app.scripts import run_notification_cycle
from app.tasks import notification_tasks


def test_notification_cycle_runs_task_bodies_and_logs_aggregate_counts(monkeypatch, caplog):
    calls: list[str] = []
    monkeypatch.setattr(
        notification_tasks,
        "generate_daily_reports",
        SimpleNamespace(
            run=lambda: calls.append("reports") or {"hotels_reported": 2, "results": [{"hotel_id": 1}]}
        ),
    )
    monkeypatch.setattr(
        notification_tasks,
        "process_outbox",
        SimpleNamespace(
            run=lambda: calls.append("outbox")
            or {"processed": 3, "sent": 2, "failed": 1, "expired": 0, "retried": 1, "deferred": 0}
        ),
    )

    assert run_notification_cycle.main() == 0
    assert calls == ["reports", "outbox"]
