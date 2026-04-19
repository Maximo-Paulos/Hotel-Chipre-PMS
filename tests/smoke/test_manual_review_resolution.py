from __future__ import annotations

from tests.smoke.helpers import register_owner, seed_operational_reservation


def test_manual_review_resolution_smoke(client, engine):
    headers, hotel_id = register_owner(client, "manual-review-owner@example.com")
    seeded = seed_operational_reservation(
        engine,
        hotel_id,
        requires_manual_review=True,
        allocation_status="manual_review",
    )

    summary_before = client.get(
        f"/api/reservations/{seeded['reservation_id']}/operations-summary",
        headers=headers,
    )
    assert summary_before.status_code == 200, summary_before.text
    assert summary_before.json()["requires_manual_review"] is True

    clear_response = client.post(
        f"/api/reservations/{seeded['reservation_id']}/operations/clear-manual-review",
        json={"notes": "Revisado por smoke test"},
        headers=headers,
    )
    assert clear_response.status_code == 200, clear_response.text
    cleared = clear_response.json()
    assert cleared["requires_manual_review"] is False
    assert cleared["allocation_status"] == "assigned"

    summary_after = client.get(
        f"/api/reservations/{seeded['reservation_id']}/operations-summary",
        headers=headers,
    )
    assert summary_after.status_code == 200, summary_after.text
    assert summary_after.json()["requires_manual_review"] is False
