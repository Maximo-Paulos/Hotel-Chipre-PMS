from datetime import date

from app.schemas.reservation_operations import OccupancyGridResponse


def test_occupancy_grid_response_keeps_reservation_version_for_room_moves():
    response = OccupancyGridResponse.model_validate(
        {
            "rooms": [],
            "reservations": [
                {
                    "id": 41,
                    "version": 7,
                    "room_id": 12,
                    "confirmation_code": "SYNTHETIC-ROOM-MOVE",
                    "check_in_date": date(2026, 11, 10),
                    "check_out_date": date(2026, 11, 12),
                    "status": "pending",
                    "guest_name": "Synthetic Guest",
                    "num_adults": 1,
                    "num_children": 0,
                    "operational_balance_due": 100.0,
                }
            ],
            "unassigned": [],
            "blocks": [],
        }
    )

    assert response.reservations[0].version == 7
    assert response.model_dump(mode="json")["reservations"][0]["version"] == 7
