"""
OTA Integration Service.
Handles incoming reservations from Booking.com and Expedia,
and outgoing inventory/availability updates.
Uses row-level locking to handle race conditions on simultaneous bookings.
"""
import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.reservation import Reservation, ReservationStatusEnum, ReservationSourceEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest
from app.models.ota import OTAReservationMapping, OTASyncStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.services.reservation_service import (
    create_reservation,
    find_available_rooms,
    generate_confirmation_code,
    ReservationError,
)
from app.schemas.reservation import ReservationCreate


class OTAError(Exception):
    """Custom exception for OTA integration errors."""
    pass


class OTAIntegrationService:
    """
    Handles bidirectional synchronization with OTAs (Booking.com, Expedia).
    
    Inbound: Receives reservation notifications via webhooks.
    Outbound: Pushes availability/inventory updates when internal state changes.
    """

    @staticmethod
    def process_booking_webhook(db: Session, payload: dict) -> OTAReservationMapping:
        """
        Process an incoming reservation from Booking.com.
        
        Expected payload structure (simplified from Booking.com OC API):
        {
            "reservation_id": "12345678",
            "guest_name": "John Doe",
            "guest_email": "john@email.com",
            "checkin": "2026-04-01",
            "checkout": "2026-04-05",
            "room_type": "STD_DBL",
            "num_adults": 2,
            "num_children": 0,
            "total_price": 500.00,
            "currency": "ARS"
        }
        
        Uses SELECT FOR UPDATE to prevent race conditions when the last room
        is being booked simultaneously from multiple sources.
        """
        ota_res_id = payload.get("reservation_id", "")
        if not ota_res_id:
            raise OTAError("Missing reservation_id in Booking.com payload")

        # Check for duplicate
        existing = db.query(OTAReservationMapping).filter(
            OTAReservationMapping.ota_name == "booking",
            OTAReservationMapping.ota_reservation_id == ota_res_id,
        ).first()
        if existing:
            return existing

        # Create mapping record first (for audit)
        mapping = OTAReservationMapping(
            ota_name="booking",
            ota_reservation_id=ota_res_id,
            ota_guest_name=payload.get("guest_name", ""),
            raw_payload=json.dumps(payload),
            sync_status=OTASyncStatusEnum.PENDING,
        )
        db.add(mapping)
        db.flush()

        try:
            # Parse payload
            guest_name = payload.get("guest_name", "OTA Guest")
            name_parts = guest_name.split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            checkin = date.fromisoformat(payload["checkin"])
            checkout = date.fromisoformat(payload["checkout"])
            room_type_code = payload.get("room_type", "")
            total_price = float(payload.get("total_price", 0))

            # Find category by code
            category = db.query(RoomCategory).filter(
                RoomCategory.code == room_type_code
            ).first()
            if not category:
                raise OTAError(f"Unknown room type code: {room_type_code}")

            # Check availability with lock
            available_rooms = find_available_rooms(db, category.id, checkin, checkout)
            if not available_rooms:
                mapping.sync_status = OTASyncStatusEnum.CONFLICT
                mapping.error_message = "No rooms available — overbooking detected"
                db.flush()
                raise OTAError(
                    f"OVERBOOKING: No rooms available for Booking.com reservation "
                    f"{ota_res_id} ({room_type_code}, {checkin} to {checkout})"
                )

            # Lock the first available room
            room = db.query(Room).filter(
                Room.id == available_rooms[0].id
            ).with_for_update().first()

            # Double-check availability after lock (prevents race condition)
            from app.services.reservation_service import check_room_availability
            if not check_room_availability(db, room.id, checkin, checkout):
                mapping.sync_status = OTASyncStatusEnum.CONFLICT
                mapping.error_message = "Room taken after lock — race condition handled"
                db.flush()
                raise OTAError(
                    f"RACE CONDITION: Room {room.room_number} was taken between "
                    f"availability check and lock acquisition"
                )

            # Create or find guest
            guest = Guest(
                first_name=first_name,
                last_name=last_name,
                email=payload.get("guest_email", ""),
            )
            db.add(guest)
            db.flush()

            # Create reservation
            reservation_data = ReservationCreate(
                guest_id=guest.id,
                category_id=category.id,
                room_id=room.id,
                check_in_date=checkin,
                check_out_date=checkout,
                num_adults=int(payload.get("num_adults", 1)),
                num_children=int(payload.get("num_children", 0)),
                source=ReservationSourceEnum.BOOKING,
                external_id=ota_res_id,
            )
            reservation = create_reservation(db, reservation_data)

            # Override total with OTA-provided price
            if total_price > 0:
                reservation.total_amount = total_price

            # OTA reservations are typically pre-paid
            reservation.amount_paid = total_price
            reservation.status = ReservationStatusEnum.FULLY_PAID

            # Update mapping
            mapping.reservation_id = reservation.id
            mapping.sync_status = OTASyncStatusEnum.SYNCED
            db.flush()

            return mapping

        except OTAError:
            raise
        except Exception as e:
            mapping.sync_status = OTASyncStatusEnum.FAILED
            mapping.error_message = str(e)
            db.flush()
            raise OTAError(f"Failed to process Booking.com reservation: {e}")

    @staticmethod
    def process_expedia_webhook(db: Session, payload: dict) -> OTAReservationMapping:
        """
        Process an incoming reservation from Expedia.
        
        Expected payload structure (simplified from Expedia EQC):
        {
            "booking_id": "EXP-987654",
            "guest": {"first_name": "Jane", "last_name": "Smith", "email": "jane@email.com"},
            "stay": {"checkin": "2026-04-10", "checkout": "2026-04-13"},
            "room_type_id": "SUP_DBL",
            "occupancy": {"adults": 2, "children": 1},
            "pricing": {"total": 750.00, "currency": "ARS"}
        }
        """
        ota_res_id = payload.get("booking_id", "")
        if not ota_res_id:
            raise OTAError("Missing booking_id in Expedia payload")

        # Check for duplicate
        existing = db.query(OTAReservationMapping).filter(
            OTAReservationMapping.ota_name == "expedia",
            OTAReservationMapping.ota_reservation_id == ota_res_id,
        ).first()
        if existing:
            return existing

        guest_data = payload.get("guest", {})
        guest_name = f"{guest_data.get('first_name', '')} {guest_data.get('last_name', '')}".strip()

        mapping = OTAReservationMapping(
            ota_name="expedia",
            ota_reservation_id=ota_res_id,
            ota_guest_name=guest_name,
            raw_payload=json.dumps(payload),
            sync_status=OTASyncStatusEnum.PENDING,
        )
        db.add(mapping)
        db.flush()

        try:
            stay = payload.get("stay", {})
            checkin = date.fromisoformat(stay["checkin"])
            checkout = date.fromisoformat(stay["checkout"])
            room_type_code = payload.get("room_type_id", "")
            pricing = payload.get("pricing", {})
            total_price = float(pricing.get("total", 0))
            occupancy = payload.get("occupancy", {})

            category = db.query(RoomCategory).filter(
                RoomCategory.code == room_type_code
            ).first()
            if not category:
                raise OTAError(f"Unknown Expedia room type: {room_type_code}")

            available_rooms = find_available_rooms(db, category.id, checkin, checkout)
            if not available_rooms:
                mapping.sync_status = OTASyncStatusEnum.CONFLICT
                mapping.error_message = "No rooms available — overbooking risk"
                db.flush()
                raise OTAError(
                    f"OVERBOOKING: No rooms for Expedia reservation {ota_res_id}"
                )

            room = db.query(Room).filter(
                Room.id == available_rooms[0].id
            ).with_for_update().first()

            from app.services.reservation_service import check_room_availability
            if not check_room_availability(db, room.id, checkin, checkout):
                mapping.sync_status = OTASyncStatusEnum.CONFLICT
                mapping.error_message = "Race condition on room assignment"
                db.flush()
                raise OTAError("Room taken during lock — race condition")

            guest = Guest(
                first_name=guest_data.get("first_name", "Expedia"),
                last_name=guest_data.get("last_name", "Guest"),
                email=guest_data.get("email", ""),
            )
            db.add(guest)
            db.flush()

            reservation_data = ReservationCreate(
                guest_id=guest.id,
                category_id=category.id,
                room_id=room.id,
                check_in_date=checkin,
                check_out_date=checkout,
                num_adults=int(occupancy.get("adults", 1)),
                num_children=int(occupancy.get("children", 0)),
                source=ReservationSourceEnum.EXPEDIA,
                external_id=ota_res_id,
            )
            reservation = create_reservation(db, reservation_data)

            if total_price > 0:
                reservation.total_amount = total_price
            reservation.amount_paid = total_price
            reservation.status = ReservationStatusEnum.FULLY_PAID

            mapping.reservation_id = reservation.id
            mapping.sync_status = OTASyncStatusEnum.SYNCED
            db.flush()

            return mapping

        except OTAError:
            raise
        except Exception as e:
            mapping.sync_status = OTASyncStatusEnum.FAILED
            mapping.error_message = str(e)
            db.flush()
            raise OTAError(f"Failed to process Expedia reservation: {e}")

    @staticmethod
    def build_availability_update(db: Session, category_id: int, start_date: date, end_date: date) -> list[dict]:
        """
        Build an availability update payload for a given category and date range.
        Returns a list of {date, available_rooms} entries for OTA sync.
        """
        from datetime import timedelta

        rooms = db.query(Room).filter(
            Room.category_id == category_id,
            Room.is_active == True,
            Room.status.in_([RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED]),
        ).all()

        total_rooms = len(rooms)
        availability = []

        current = start_date
        while current < end_date:
            next_day = current + timedelta(days=1)
            booked = 0
            for room in rooms:
                from app.services.reservation_service import check_room_availability
                if not check_room_availability(db, room.id, current, next_day):
                    booked += 1

            availability.append({
                "date": current.isoformat(),
                "total_rooms": total_rooms,
                "booked": booked,
                "available": total_rooms - booked,
            })
            current = next_day

        return availability
