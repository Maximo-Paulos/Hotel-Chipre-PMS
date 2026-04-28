from __future__ import annotations

import json
from pathlib import Path


FIXTURE_FILES = [
    "hotel_small_ars.json",
    "hotel_multichannel.json",
    "hotel_no_show.json",
    "hotel_room_events.json",
    "owner_multi_hotel.json",
]


def test_analytics_fixtures_exist_and_parse():
    base = Path(__file__).resolve().parent / "fixtures" / "analytics"
    assert base.exists()

    for filename in FIXTURE_FILES:
        path = base / filename
        assert path.exists(), filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "expected" in payload
        assert "hotel" in payload or "owner" in payload

        if filename != "owner_multi_hotel.json":
            assert "hotel" in payload
            assert "reservations" in payload or "room_state_events" in payload
