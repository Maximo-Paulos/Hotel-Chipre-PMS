"""Focused regression tests for the TECH-0063 OLTP audit fixes."""

from app.models.cash_register import CashMovement
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.transaction import Transaction


def _index_names(model) -> set[str]:
    return {index.name for index in model.__table__.indexes}


def test_hot_path_composite_indexes_exist_in_models():
    assert "ix_room_hotel_deleted_at" in _index_names(Room)
    assert "ix_transactions_hotel_status_created_at" in _index_names(Transaction)
    assert "ix_cash_movements_hotel_session_recorded_at" in _index_names(CashMovement)
    assert "ix_reservation_hotel_check_in" in _index_names(Reservation)
    assert "ix_reservation_hotel_check_out" in _index_names(Reservation)
