from __future__ import annotations

import logging
from typing import Any

from app.db.neo4j import get_neo4j_driver


logger = logging.getLogger(__name__)

ASSIGNMENT_CYPHER = """
MERGE (reservation:Reservation {hotel_id: $hotel_id, reservation_id: $reservation_id})
SET reservation.status = $status
MERGE (room:Room {hotel_id: $hotel_id, room_id: $room_id})
MERGE (guest:Guest {hotel_id: $hotel_id, guest_id: $guest_id})
WITH reservation, room, guest
OPTIONAL MATCH (reservation)-[old_assignment:ASSIGNED_TO]->(:Room)
DELETE old_assignment
MERGE (reservation)-[:ASSIGNED_TO]->(room)
MERGE (guest)-[:HAS_RESERVATION]->(reservation)
"""

ROOM_MOVEMENT_CYPHER = """
MERGE (reservation:Reservation {hotel_id: $hotel_id, reservation_id: $reservation_id})
MERGE (room:Room {hotel_id: $hotel_id, room_id: $to_room_id})
MERGE (reservation)-[movement:MOVED {group_id: $group_id}]->(room)
SET movement.from_room_id = $from_room_id,
    movement.to_room_id = $to_room_id
"""

COMPANY_LINK_CYPHER = """
MERGE (company:Company {hotel_id: $hotel_id, company_id: $company_id})
MERGE (reservation:Reservation {hotel_id: $hotel_id, reservation_id: $reservation_id})
MERGE (company)-[:BOOKED]->(reservation)
"""


def _run_write(driver: Any | None, cypher: str, parameters: dict[str, Any]) -> None:
    if driver is None:
        return
    with driver.session() as session:
        session.run(cypher, parameters)


def _enum_value(value: Any) -> str:
    return str(value.value if hasattr(value, "value") else value)


def project_reservation_assignment(
    hotel_id: int,
    reservation_id: int,
    room_id: int,
    guest_id: int,
    status: str,
) -> None:
    if room_id is None or guest_id is None:
        return
    try:
        driver = get_neo4j_driver()
        if driver is None:
            return
        _run_write(
            driver,
            ASSIGNMENT_CYPHER,
            {
                "hotel_id": int(hotel_id),
                "reservation_id": int(reservation_id),
                "room_id": int(room_id),
                "guest_id": int(guest_id),
                "status": _enum_value(status),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive datastore isolation
        logger.warning("neo4j.assignment_projection_failed", extra={"error": str(exc)})


def project_room_movement(
    hotel_id: int,
    reservation_id: int,
    from_room_id: int | None,
    to_room_id: int,
    group_id: int,
) -> None:
    if to_room_id is None or group_id is None:
        return
    try:
        driver = get_neo4j_driver()
        if driver is None:
            return
        _run_write(
            driver,
            ROOM_MOVEMENT_CYPHER,
            {
                "hotel_id": int(hotel_id),
                "reservation_id": int(reservation_id),
                "from_room_id": int(from_room_id) if from_room_id is not None else None,
                "to_room_id": int(to_room_id),
                "group_id": int(group_id),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive datastore isolation
        logger.warning("neo4j.room_movement_projection_failed", extra={"error": str(exc)})


def project_company_link(hotel_id: int, company_id: int, reservation_id: int) -> None:
    if company_id is None:
        return
    try:
        driver = get_neo4j_driver()
        if driver is None:
            return
        _run_write(
            driver,
            COMPANY_LINK_CYPHER,
            {
                "hotel_id": int(hotel_id),
                "company_id": int(company_id),
                "reservation_id": int(reservation_id),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive datastore isolation
        logger.warning("neo4j.company_link_projection_failed", extra={"error": str(exc)})
