"""
Tests for Reservation Service — booking creation, availability checks, state transitions.
"""
import pytest
from datetime import date

from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import (
    create_reservation,
    check_room_availability,
    find_available_rooms,
    transition_reservation_status,
    ReservationError,
    generate_confirmation_code,
)


class TestConfirmationCode:
    """Tests for confirmation code generation."""

    def test_code_format(self):
        code = generate_confirmation_code()
        assert code.startswith("RES-")
        assert len(code) == 12  # "RES-" + 8 chars

    def test_codes_are_unique(self):
        codes = {generate_confirmation_code() for _ in range(100)}
        assert len(codes) == 100  # All unique


class TestAvailability:
    """Tests for room availability checking."""

    def test_empty_room_is_available(self, db, sample_rooms, sample_categories, hotel_config):
        """A room with no reservations should be available."""
        room = sample_rooms[0]
        assert check_room_availability(
            db, room.id, date(2026, 4, 1), date(2026, 4, 5)
        ) is True

    def test_booked_room_is_unavailable(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """A room with an overlapping reservation should not be available."""
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),
        )
        create_reservation(db, data)
        db.flush()

        # Overlapping dates
        assert check_room_availability(
            db, sample_rooms[0].id, date(2026, 4, 3), date(2026, 4, 7)
        ) is False

    def test_adjacent_reservations_allowed(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Check-out day == next check-in day should be allowed (no overlap)."""
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),
        )
        create_reservation(db, data)
        db.flush()

        # Check-in exactly on checkout day: NO overlap
        assert check_room_availability(
            db, sample_rooms[0].id, date(2026, 4, 5), date(2026, 4, 8)
        ) is True

    def test_find_available_rooms(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Find available rooms after booking some."""
        cat_std = sample_categories[0]
        total_std_rooms = len([r for r in sample_rooms if r.category_id == cat_std.id])
        assert total_std_rooms == 20

        # Book one room
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=cat_std.id,
            room_id=sample_rooms[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),
        )
        create_reservation(db, data)
        db.flush()

        available = find_available_rooms(
            db, cat_std.id, date(2026, 4, 1), date(2026, 4, 5)
        )
        assert len(available) == total_std_rooms - 1


class TestReservationCreation:
    """Tests for reservation creation logic."""

    def test_create_basic_reservation(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Create a standard reservation and verify computed fields."""
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,  # $100/night
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),  # 4 nights
        )
        res = create_reservation(db, data)
        db.flush()

        assert res.id is not None
        assert res.confirmation_code.startswith("RES-")
        assert res.total_amount == 400.0  # 4 nights × $100
        assert res.deposit_amount == 120.0  # 30% of $400
        assert res.amount_paid == 0.0
        assert res.balance_due == 400.0
        assert res.status == ReservationStatusEnum.PENDING
        assert res.room_id is not None  # Auto-assigned

    def test_create_reservation_specific_room(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Reserve a specific room."""
        room = sample_rooms[5]  # Room 106
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=room.id,
            check_in_date=date(2026, 5, 10),
            check_out_date=date(2026, 5, 12),
        )
        res = create_reservation(db, data)
        assert res.room_id == room.id

    def test_create_reservation_invalid_guest(self, db, sample_rooms, sample_categories, hotel_config):
        """Should fail for non-existent guest."""
        data = ReservationCreate(
            guest_id=999999,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),
        )
        with pytest.raises(ReservationError, match="Guest.*not found"):
            create_reservation(db, data)

    def test_create_reservation_invalid_dates(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Should fail when check-out is before check-in."""
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 5),
            check_out_date=date(2026, 4, 1),  # Before check-in!
        )
        with pytest.raises(ReservationError, match="Check-out date must be after"):
            create_reservation(db, data)

    def test_create_reservation_wrong_category_room(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Should fail when room doesn't match the requested category."""
        # Room 301 is category SUP_DBL, trying to book as STD_DBL
        sup_room = [r for r in sample_rooms if r.room_number == "301"][0]
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,  # STD_DBL
            room_id=sup_room.id,  # This is SUP_DBL
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),
        )
        with pytest.raises(ReservationError, match="belongs to category"):
            create_reservation(db, data)

    def test_double_booking_prevented(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Cannot book the same room for overlapping dates."""
        room = sample_rooms[0]
        data1 = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=room.id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),
        )
        create_reservation(db, data1)
        db.flush()

        data2 = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=room.id,
            check_in_date=date(2026, 4, 3),
            check_out_date=date(2026, 4, 7),
        )
        with pytest.raises(ReservationError, match="not available"):
            create_reservation(db, data2)


def test_create_reservation_uses_rate_plan_quote_when_commercial_context_is_provided(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    from app.models.commercial import RatePlan, RatePlanPrice, SellableProduct, TaxPolicy, TaxRule

    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=sample_categories[0].id,
        code="STD_DIRECT",
        name="Standard directa",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    rate_plan = RatePlan(
        hotel_id=hotel_config.id,
        sellable_product_id=product.id,
        code="DIRECT-FLEX",
        name="Directa flexible",
        currency_code="ARS",
        is_active=True,
    )
    db.add(rate_plan)
    db.flush()

    db.add(
        RatePlanPrice(
            hotel_id=hotel_config.id,
            rate_plan_id=rate_plan.id,
            sales_channel_code="direct",
            occupancy=2,
            currency_code="ARS",
            base_amount=120.0,
            tax_inclusive=False,
        )
    )

    tax_policy = TaxPolicy(
        hotel_id=hotel_config.id,
        code="ARG",
        name="Argentina",
        taxes_included=False,
        apply_vat_by_default=False,
        foreign_guest_tax_exempt=False,
        is_active=True,
    )
    db.add(tax_policy)
    db.flush()
    db.add(
        TaxRule(
            hotel_id=hotel_config.id,
            tax_policy_id=tax_policy.id,
            guest_scope="all",
            tax_code="VAT",
            tax_name="IVA",
            tax_type="percentage",
            amount=21.0,
            priority=1,
        )
    )
    db.flush()

    room = db.query(Room).filter(Room.category_id == sample_categories[0].id).first()
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=room.id,
        sellable_product_id=product.id,
        rate_plan_id=rate_plan.id,
        tax_policy_id=tax_policy.id,
        pricing_channel_code="direct",
        num_adults=2,
        check_in_date=date(2026, 4, 1),
        check_out_date=date(2026, 4, 3),
    )

    res = create_reservation(db, data, hotel_id=hotel_config.id)
    db.flush()

    assert res.rate_plan_id == rate_plan.id
    assert res.sellable_product_id == product.id
    assert res.tax_policy_id == tax_policy.id
    assert res.subtotal_amount == 240.0
    assert res.tax_amount == 50.4
    assert res.total_amount == 290.4
    assert res.net_amount == 290.4
    assert res.currency_code == "ARS"


class TestStateTransitions:
    """Tests for reservation state machine transitions."""

    def test_valid_transition_pending_to_deposit(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 3),
        )
        res = create_reservation(db, data)
        result = transition_reservation_status(db, res, ReservationStatusEnum.DEPOSIT_PAID)
        assert result.status == ReservationStatusEnum.DEPOSIT_PAID

    def test_invalid_transition_pending_to_checked_in(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 3),
        )
        res = create_reservation(db, data)
        with pytest.raises(ReservationError, match="Cannot transition"):
            transition_reservation_status(db, res, ReservationStatusEnum.CHECKED_IN)

    def test_invalid_transition_from_terminal_state(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 3),
        )
        res = create_reservation(db, data)
        transition_reservation_status(db, res, ReservationStatusEnum.CANCELLED)
        with pytest.raises(ReservationError, match="Cannot transition"):
            transition_reservation_status(db, res, ReservationStatusEnum.PENDING)

    def test_cancel_not_allowed_after_checkin(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 3),
        )
        res = create_reservation(db, data)

        # Move through the normal flow up to check-in
        transition_reservation_status(db, res, ReservationStatusEnum.FULLY_PAID)
        transition_reservation_status(db, res, ReservationStatusEnum.CHECKED_IN)
        original_room = res.room_id

        with pytest.raises(ReservationError, match="Cannot transition"):
            transition_reservation_status(db, res, ReservationStatusEnum.CANCELLED)

        assert res.status == ReservationStatusEnum.CHECKED_IN
        assert res.room_id == original_room  # Room link is preserved

        # Once checked-out, cancellation is still blocked
        transition_reservation_status(db, res, ReservationStatusEnum.CHECKED_OUT)
        with pytest.raises(ReservationError, match="Cannot transition"):
            transition_reservation_status(db, res, ReservationStatusEnum.CANCELLED)
