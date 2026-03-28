"""
Tests for database models — validates schema creation, constraints, relationships.
"""
import pytest
from datetime import date, datetime, timezone

from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest, GuestCompanion
from app.models.reservation import Reservation, ReservationStatusEnum, VALID_TRANSITIONS
from app.models.transaction import Transaction, PaymentMethodEnum, TransactionStatusEnum, TransactionTypeEnum
from app.models.hotel_config import HotelConfiguration


class TestRoomModels:
    """Tests for Room and RoomCategory models."""

    def test_create_category(self, db, sample_categories):
        """Verify categories are created with correct attributes."""
        cat = sample_categories[0]
        assert cat.id is not None
        assert cat.name == "Standard Double"
        assert cat.code == "STD_DBL"
        assert cat.base_price_per_night == 100.0
        assert cat.max_occupancy == 2

    def test_create_room(self, db, sample_rooms, sample_categories):
        """Verify rooms are created and linked to categories."""
        room = sample_rooms[0]
        assert room.id is not None
        assert room.room_number == "101"
        assert room.floor == 1
        assert room.category_id == sample_categories[0].id
        assert room.status == RoomStatusEnum.AVAILABLE
        assert room.is_active is True

    def test_room_category_relationship(self, db, sample_rooms, sample_categories):
        """Verify bidirectional Room ↔ RoomCategory relationship."""
        cat_std = sample_categories[0]
        std_rooms = [r for r in sample_rooms if r.category_id == cat_std.id]
        assert len(std_rooms) == 20  # 10 on floor 1, 10 on floor 2

    def test_total_38_rooms(self, db, sample_rooms):
        """Verify the hotel has exactly 38 rooms."""
        assert len(sample_rooms) == 38

    def test_room_repr(self, db, sample_rooms):
        """Verify room string representation."""
        room = sample_rooms[0]
        assert "101" in repr(room)

    def test_category_repr(self, db, sample_categories):
        """Verify category string representation."""
        cat = sample_categories[0]
        assert "Standard Double" in repr(cat)
        assert "STD_DBL" in repr(cat)


class TestGuestModel:
    """Tests for Guest and GuestCompanion models."""

    def test_create_guest_full(self, db, sample_guest):
        """Verify guest with full data."""
        assert sample_guest.id is not None
        assert sample_guest.first_name == "Carlos"
        assert sample_guest.last_name == "Pérez"
        assert sample_guest.full_name == "Carlos Pérez"
        assert sample_guest.document_type == "DNI"
        assert sample_guest.document_number == "30456789"
        assert sample_guest.has_valid_identity is True

    def test_guest_missing_identity(self, db, sample_guest_incomplete):
        """Verify the has_valid_identity property detects missing documents."""
        assert sample_guest_incomplete.has_valid_identity is False

    def test_guest_companions(self, db, sample_guest):
        """Create companions and verify relationship."""
        comp1 = GuestCompanion(
            guest_id=sample_guest.id,
            first_name="Ana",
            last_name="Pérez",
            document_type="DNI",
            document_number="40123456",
            relationship_to_guest="spouse",
        )
        comp2 = GuestCompanion(
            guest_id=sample_guest.id,
            first_name="Lucas",
            last_name="Pérez",
            relationship_to_guest="child",
        )
        db.add_all([comp1, comp2])
        db.flush()

        assert len(sample_guest.companions) == 2
        assert sample_guest.companions[0].full_name == "Ana Pérez"

    def test_guest_timestamps(self, db, sample_guest):
        """Verify auto-generated timestamps."""
        assert sample_guest.created_at is not None
        assert sample_guest.updated_at is not None


class TestReservationModel:
    """Tests for Reservation model and state machine."""

    def test_valid_transitions(self):
        """Verify the state machine transition map is correct."""
        # From PENDING
        assert ReservationStatusEnum.DEPOSIT_PAID in VALID_TRANSITIONS[ReservationStatusEnum.PENDING]
        assert ReservationStatusEnum.FULLY_PAID in VALID_TRANSITIONS[ReservationStatusEnum.PENDING]
        assert ReservationStatusEnum.CANCELLED in VALID_TRANSITIONS[ReservationStatusEnum.PENDING]

        # From DEPOSIT_PAID
        assert ReservationStatusEnum.FULLY_PAID in VALID_TRANSITIONS[ReservationStatusEnum.DEPOSIT_PAID]
        assert ReservationStatusEnum.CANCELLED in VALID_TRANSITIONS[ReservationStatusEnum.DEPOSIT_PAID]

        # From FULLY_PAID
        assert ReservationStatusEnum.CHECKED_IN in VALID_TRANSITIONS[ReservationStatusEnum.FULLY_PAID]

        # From CHECKED_IN — only checkout
        assert ReservationStatusEnum.CHECKED_OUT in VALID_TRANSITIONS[ReservationStatusEnum.CHECKED_IN]
        assert len(VALID_TRANSITIONS[ReservationStatusEnum.CHECKED_IN]) == 1

        # Terminal states
        assert len(VALID_TRANSITIONS[ReservationStatusEnum.CHECKED_OUT]) == 0
        assert len(VALID_TRANSITIONS[ReservationStatusEnum.CANCELLED]) == 0

    def test_reservation_can_transition_to(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Verify can_transition_to method."""
        res = Reservation(
            confirmation_code="TEST-001",
            guest_id=sample_guest.id,
            room_id=sample_rooms[0].id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),
            total_amount=400.0,
            status=ReservationStatusEnum.PENDING,
        )
        db.add(res)
        db.flush()

        assert res.can_transition_to(ReservationStatusEnum.DEPOSIT_PAID) is True
        assert res.can_transition_to(ReservationStatusEnum.CHECKED_IN) is False
        assert res.can_transition_to(ReservationStatusEnum.CHECKED_OUT) is False

    def test_reservation_balance_due(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Verify balance_due computed property."""
        res = Reservation(
            confirmation_code="TEST-002",
            guest_id=sample_guest.id,
            room_id=sample_rooms[0].id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 5),
            total_amount=1000.0,
            amount_paid=300.0,
        )
        db.add(res)
        db.flush()

        assert res.balance_due == 700.0
        assert res.nights == 4

    def test_reservation_nights(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Verify nights calculation."""
        res = Reservation(
            confirmation_code="TEST-003",
            guest_id=sample_guest.id,
            room_id=sample_rooms[0].id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 5, 1),
            check_out_date=date(2026, 5, 8),
            total_amount=700.0,
        )
        db.add(res)
        db.flush()
        assert res.nights == 7


class TestTransactionModel:
    """Tests for Transaction model."""

    def test_create_transaction(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Create a transaction and verify attributes."""
        res = Reservation(
            confirmation_code="TEST-TX-001",
            guest_id=sample_guest.id,
            room_id=sample_rooms[0].id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 3),
            total_amount=200.0,
            status=ReservationStatusEnum.PENDING,
        )
        db.add(res)
        db.flush()

        tx = Transaction(
            hotel_id=1,
            reservation_id=res.id,
            amount=200.0,
            currency="ARS",
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
            payment_method=PaymentMethodEnum.CASH,
            status=TransactionStatusEnum.COMPLETED,
        )
        db.add(tx)
        db.flush()

        assert tx.id is not None
        assert tx.reservation_id == res.id
        assert tx.amount == 200.0
        assert tx.payment_method == PaymentMethodEnum.CASH

    def test_transaction_reservation_relationship(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Verify Transaction → Reservation relationship."""
        res = Reservation(
            confirmation_code="TEST-TX-002",
            guest_id=sample_guest.id,
            room_id=sample_rooms[0].id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 3),
            total_amount=200.0,
        )
        db.add(res)
        db.flush()

        tx = Transaction(
            hotel_id=1,
            reservation_id=res.id,
            amount=100.0,
            currency="ARS",
            transaction_type=TransactionTypeEnum.DEPOSIT,
            payment_method=PaymentMethodEnum.MERCADO_PAGO,
            status=TransactionStatusEnum.COMPLETED,
        )
        db.add(tx)
        db.flush()

        assert tx.reservation == res
        assert len(res.transactions) == 1


class TestHotelConfigModel:
    """Tests for HotelConfiguration model."""

    def test_default_config(self, db, hotel_config):
        """Verify default configuration values."""
        assert hotel_config.deposit_percentage == 30.0
        assert hotel_config.enable_cash is True
        assert hotel_config.enable_mercado_pago is True
        assert hotel_config.enable_paypal is True
        assert hotel_config.require_document_for_checkin is True
        assert hotel_config.require_terms_acceptance is True

    def test_payment_method_enabled(self, db, hotel_config):
        """Verify the is_payment_method_enabled helper."""
        assert hotel_config.is_payment_method_enabled("cash") is True
        assert hotel_config.is_payment_method_enabled("mercado_pago") is True
        assert hotel_config.is_payment_method_enabled("bank_transfer") is False  # Default off

    def test_extra_policies_json(self, db, hotel_config):
        """Verify JSON serialization for extra_policies."""
        hotel_config.set_extra_policies({"late_checkout_fee": 50.0, "pet_policy": "allowed"})
        db.flush()

        policies = hotel_config.get_extra_policies()
        assert policies["late_checkout_fee"] == 50.0
        assert policies["pet_policy"] == "allowed"
