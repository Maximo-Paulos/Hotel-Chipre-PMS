"""PostgreSQL regression for atomic audit persistence on legacy booking delete."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from app.dependencies.auth import AuthContext
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomHousekeepingStatusEnum, RoomStatusEnum
from app.models.user import User
from app.services.tenant_context import set_tenant_hotel_context
from app.api.bookings import delete_booking


def test_legacy_booking_soft_delete_and_audit_commit_together_on_postgres(pg_engine):
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 240_000_000 + uuid4().int % 10_000_000
    user_id = 250_000_000 + uuid4().int % 10_000_000
    check_in = date.today() + timedelta(days=45)
    check_out = check_in + timedelta(days=1)

    with session_factory.begin() as seed:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic delete audit {suffix}", subscription_active=True))
        seed.add(User(id=user_id, email=f"delete-audit-{suffix.lower()}@example.test", password_hash="synthetic", is_active=True, is_verified=True))
        seed.flush()

        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic delete category {suffix}",
            code=f"SD{suffix}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        seed.add_all([category, guest])
        seed.flush()

        room = Room(
            hotel_id=hotel_id,
            room_number=f"D{suffix[:8]}",
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
        )
        seed.add(room)
        seed.flush()

        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"SD-{suffix}",
            guest_id=guest.id,
            room_id=room.id,
            category_id=category.id,
            check_in_date=check_in,
            check_out_date=check_out,
            total_amount=Decimal("100.00"),
            subtotal_amount=Decimal("100.00"),
            net_amount=Decimal("100.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
        )
        seed.add(reservation)
        seed.flush()
        reservation_id = reservation.id

    context = AuthContext(
        hotel_id=hotel_id,
        user_id=user_id,
        user_email=f"delete-audit-{suffix.lower()}@example.test",
        user_role="owner",
        base_role="owner",
        is_verified=True,
        permissions=set(),
    )
    with session_factory() as request_session:
        set_tenant_hotel_context(request_session, hotel_id)
        result = delete_booking(reservation_id, db=request_session, context=context)
        assert result == {"deleted": True, "id": reservation_id}

    with session_factory() as verify:
        set_tenant_hotel_context(verify, hotel_id)
        persisted = verify.get(Reservation, reservation_id)
        assert persisted is not None
        assert persisted.deleted_at is not None
        audit = (
            verify.query(AuditLog)
            .filter_by(
                hotel_id=hotel_id,
                table_name="reservations",
                record_id=reservation_id,
                action=AuditActionEnum.DELETE,
            )
            .one()
        )
        assert audit.actor_user_id == user_id
        assert audit.payload_before is not None
        assert audit.payload_after is not None
