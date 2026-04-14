"""
Tests for the Allocation Engine (OR-Tools CP-SAT + greedy fallback).
"""
import pytest
from datetime import date, timedelta
from app.services.allocation_engine import (
    ReservationSlot, RoomSlot, run_allocation,
    _run_allocation_greedy, _check_overlap,
)

def make_rooms(cat_id, count, start_id=1):
    return [RoomSlot(room_id=start_id+i, room_number=f"R{start_id+i}", category_id=cat_id) for i in range(count)]

def make_res(rid, cat, ci, co, room=None, locked=False):
    return ReservationSlot(reservation_id=rid, category_id=cat, check_in=ci, check_out=co, current_room_id=room, is_locked=locked)


class TestOverlap:
    def test_overlapping(self):
        a = make_res(1, 1, date(2026,4,1), date(2026,4,5))
        b = make_res(2, 1, date(2026,4,3), date(2026,4,7))
        assert _check_overlap(a, b) is True

    def test_adjacent_no_overlap(self):
        a = make_res(1, 1, date(2026,4,1), date(2026,4,5))
        b = make_res(2, 1, date(2026,4,5), date(2026,4,8))
        assert _check_overlap(a, b) is False

    def test_no_overlap(self):
        a = make_res(1, 1, date(2026,4,1), date(2026,4,3))
        b = make_res(2, 1, date(2026,4,10), date(2026,4,12))
        assert _check_overlap(a, b) is False


class TestGreedyAllocation:
    def test_simple_assignment(self):
        rooms = make_rooms(1, 3)
        reservations = [make_res(1,1,date(2026,4,1),date(2026,4,5)), make_res(2,1,date(2026,4,1),date(2026,4,3))]
        result = _run_allocation_greedy(reservations, rooms)
        assert result.success is True
        assert result.assignments[1] != result.assignments[2]

    def test_category_constraint(self):
        rooms = make_rooms(2, 2)
        reservations = [make_res(1, 1, date(2026,4,1), date(2026,4,5))]
        result = _run_allocation_greedy(reservations, rooms)
        assert result.success is False

    def test_locked_stays(self):
        rooms = make_rooms(1, 2)
        reservations = [
            make_res(1,1,date(2026,4,1),date(2026,4,5),room=1,locked=True),
            make_res(2,1,date(2026,4,1),date(2026,4,5)),
        ]
        result = _run_allocation_greedy(reservations, rooms)
        assert result.success is True
        assert result.assignments[1] == 1

    def test_overlap_prevented(self):
        rooms = make_rooms(1, 1)
        reservations = [make_res(1,1,date(2026,4,1),date(2026,4,5)), make_res(2,1,date(2026,4,3),date(2026,4,7))]
        result = _run_allocation_greedy(reservations, rooms)
        assert result.success is False

    def test_sequential_fits_one_room(self):
        rooms = make_rooms(1, 1)
        reservations = [make_res(i,1,date(2026,4,1)+timedelta(days=i*3),date(2026,4,1)+timedelta(days=i*3+2)) for i in range(5)]
        result = _run_allocation_greedy(reservations, rooms)
        assert result.success is True
        assert all(rid == 1 for rid in result.assignments.values())


class TestCPSATAllocation:
    def test_cpsat_simple(self):
        rooms = make_rooms(1, 3)
        reservations = [make_res(1,1,date(2026,4,1),date(2026,4,5)), make_res(2,1,date(2026,4,1),date(2026,4,3))]
        result = run_allocation(reservations, rooms)
        assert result.success is True
        assert result.assignments[1] != result.assignments[2]

    def test_cpsat_category(self):
        all_rooms = make_rooms(1,2,1) + make_rooms(2,2,3)
        reservations = [make_res(1,1,date(2026,4,1),date(2026,4,5)), make_res(2,2,date(2026,4,1),date(2026,4,5))]
        result = run_allocation(reservations, all_rooms)
        assert result.success is True
        assert result.assignments[1] in (1,2)
        assert result.assignments[2] in (3,4)

    def test_cpsat_locked_immovable(self):
        rooms = make_rooms(1, 3)
        reservations = [
            make_res(1,1,date(2026,4,1),date(2026,4,5),room=1,locked=True),
            make_res(2,1,date(2026,4,1),date(2026,4,5)),
        ]
        result = run_allocation(reservations, rooms)
        assert result.success is True
        assert result.assignments[1] == 1
        assert 1 not in result.moved_reservations

    def test_cpsat_infeasible(self):
        rooms = make_rooms(1, 1)
        reservations = [make_res(1,1,date(2026,4,1),date(2026,4,5)), make_res(2,1,date(2026,4,3),date(2026,4,7))]
        result = run_allocation(reservations, rooms)
        assert result.success is False

    def test_cpsat_compaction(self):
        rooms = make_rooms(1, 5)
        reservations = [
            make_res(1,1,date(2026,4,1),date(2026,4,3),room=1),
            make_res(2,1,date(2026,4,4),date(2026,4,6),room=2),
            make_res(3,1,date(2026,4,7),date(2026,4,9),room=3),
            make_res(4,1,date(2026,4,10),date(2026,4,12),room=4),
            make_res(5,1,date(2026,4,1),date(2026,4,12),room=5),
            make_res(6,1,date(2026,4,3),date(2026,4,4),room=3),
            make_res(7,1,date(2026,4,6),date(2026,4,7),room=4),
            make_res(8,1,date(2026,4,9),date(2026,4,10),room=5),
        ]
        result = run_allocation(reservations, rooms)
        assert result.success is True
        assert len(result.assignments) == 8
        rooms_used = set(result.assignments.values())
        assert len(rooms_used) <= 4

    def test_cpsat_empty(self):
        rooms = make_rooms(1, 3)
        result = run_allocation([], rooms)
        assert result.success is True
        assert len(result.assignments) == 0

    def test_cpsat_prefers_filling_one_night_gap_when_other_room_is_already_used(self):
        rooms = make_rooms(1, 2)
        reservations = [
            make_res(1, 1, date(2026, 4, 1), date(2026, 4, 3), room=1, locked=True),
            make_res(2, 1, date(2026, 4, 4), date(2026, 4, 6), room=1, locked=True),
            make_res(3, 1, date(2026, 4, 3), date(2026, 4, 4), room=2),
            make_res(4, 1, date(2026, 4, 10), date(2026, 4, 12), room=2, locked=True),
        ]

        result = run_allocation(reservations, rooms)

        assert result.success is True
        assert result.assignments[3] == 1

    def test_greedy_prefers_filling_one_night_gap_when_other_room_is_already_used(self):
        rooms = make_rooms(1, 2)
        reservations = [
            make_res(1, 1, date(2026, 4, 1), date(2026, 4, 3), room=1, locked=True),
            make_res(2, 1, date(2026, 4, 4), date(2026, 4, 6), room=1, locked=True),
            make_res(3, 1, date(2026, 4, 3), date(2026, 4, 4), room=2),
            make_res(4, 1, date(2026, 4, 10), date(2026, 4, 12), room=2, locked=True),
        ]

        result = _run_allocation_greedy(reservations, rooms)

        assert result.success is True
        assert result.assignments[3] == 1
