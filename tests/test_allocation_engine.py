"""
Tests for the Allocation Engine (OR-Tools CP-SAT + greedy fallback).
"""
import pytest
from datetime import date, timedelta
import app.services.allocation_engine as allocation_engine
from app.services.allocation_engine import (
    ReservationSlot, RoomSlot, run_allocation,
    _run_allocation_greedy, _check_overlap,
    _overlapping_reservation_pairs, _reservation_indexes_by_horizon_day,
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


def test_reservation_day_index_clips_to_half_open_horizon():
    start = date(2026, 4, 10)
    reservations = [
        make_res(1, 1, start - timedelta(days=2), start + timedelta(days=2)),
        make_res(2, 1, start + timedelta(days=1), start + timedelta(days=4)),
        make_res(3, 1, start + timedelta(days=4), start + timedelta(days=5)),
        make_res(4, 1, start - timedelta(days=5), start),
    ]

    coverage = _reservation_indexes_by_horizon_day(reservations, start, 4)

    assert coverage == [[0], [0, 1], [1], [1]]


def test_overlapping_reservation_pairs_use_half_open_dates_and_keep_original_indexes():
    start = date(2026, 4, 10)
    reservations = [
        make_res(1, 1, start + timedelta(days=4), start + timedelta(days=6)),
        make_res(2, 1, start, start + timedelta(days=2)),
        make_res(3, 1, start + timedelta(days=1), start + timedelta(days=4)),
        make_res(4, 1, start + timedelta(days=2), start + timedelta(days=3)),
        make_res(5, 1, start + timedelta(days=5), start + timedelta(days=5)),
        make_res(6, 1, start + timedelta(days=5), start + timedelta(days=6)),
    ]

    assert set(_overlapping_reservation_pairs(reservations)) == {(1, 2), (2, 3), (0, 5)}


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

    def test_capacity_constraint_assigns_only_room_with_enough_occupancy(self):
        rooms = [
            RoomSlot(room_id=1, room_number="101", category_id=1, max_occupancy=2),
            RoomSlot(room_id=2, room_number="102", category_id=1, max_occupancy=4),
        ]
        reservations = [
            ReservationSlot(
                reservation_id=1,
                category_id=1,
                check_in=date(2026, 4, 1),
                check_out=date(2026, 4, 3),
                current_room_id=None,
                is_locked=False,
                num_guests=3,
            )
        ]

        result = _run_allocation_greedy(reservations, rooms)

        assert result.success is True
        assert result.assignments[1] == 2

    def test_sequential_fits_one_room(self):
        rooms = make_rooms(1, 1)
        reservations = [make_res(i,1,date(2026,4,1)+timedelta(days=i*3),date(2026,4,1)+timedelta(days=i*3+2)) for i in range(5)]
        result = _run_allocation_greedy(reservations, rooms)
        assert result.success is True
        assert all(rid == 1 for rid in result.assignments.values())


class TestCPSATAllocation:
    def test_non_mobility_reservations_skip_floor_search(self, monkeypatch):
        pytest.importorskip("ortools.sat.python.cp_model")
        checked_reservation_ids = []
        original = allocation_engine._lowest_available_compatible_floor

        def capture(reservation, rooms, reservations):
            checked_reservation_ids.append(reservation.reservation_id)
            return original(reservation, rooms, reservations)

        monkeypatch.setattr(allocation_engine, "_lowest_available_compatible_floor", capture)
        start = date(2026, 4, 1)
        reservations = [
            make_res(index, 1, start + timedelta(days=index * 3), start + timedelta(days=index * 3 + 2))
            for index in range(1, 5)
        ]
        reservations[-1].mobility_restriction = True

        rooms = make_rooms(1, 3) + [
            RoomSlot(
                room_id=4,
                room_number="R4",
                category_id=1,
                floor=1,
                is_accessible=True,
            )
        ]

        result = run_allocation(reservations, rooms)

        assert result.success is True
        assert checked_reservation_ids == [reservations[-1].reservation_id]
        assigned_room = next(room for room in rooms if room.room_id == result.assignments[4])
        assert assigned_room.is_accessible is True
        assert assigned_room.floor == 1

    def test_cpsat_builds_only_compatible_room_and_gap_variables(self, monkeypatch):
        cp_model = pytest.importorskip("ortools.sat.python.cp_model")
        original_solver = cp_model.CpSolver
        observed = {}

        class CapturingSolver(original_solver):
            def Solve(self, model, *args, **kwargs):
                names = [variable.name for variable in model.Proto().variables]
                observed["assignment_variables"] = sum(name.startswith("x_") for name in names)
                observed["gap_variables"] = sum(name.startswith("gap_") for name in names)
                observed["total_variables"] = len(names)
                return super().Solve(model, *args, **kwargs)

        monkeypatch.setattr(cp_model, "CpSolver", CapturingSolver)
        rooms = [
            RoomSlot(room_id=index + 1, room_number=f"R{index + 1:02d}", category_id=index // 20 + 1)
            for index in range(40)
        ]
        start = date(2026, 4, 1)
        reservations = [
            make_res(
                index + 1,
                index // 20 + 1,
                start + timedelta(days=index * 3),
                start + timedelta(days=index * 3 + 2),
            )
            for index in range(40)
        ]

        result = run_allocation(reservations, rooms)

        assert result.success is True
        assert observed["assignment_variables"] == 800
        assert observed["gap_variables"] < len(rooms) * 80
        assert observed["total_variables"] < len(rooms) * 120

    def test_cpsat_uses_one_worker_with_the_starter_memory_budget(self, monkeypatch):
        cp_model = pytest.importorskip("ortools.sat.python.cp_model")
        original_solver = cp_model.CpSolver
        observed = {}

        class CapturingSolver(original_solver):
            def Solve(self, model, *args, **kwargs):
                observed["num_workers"] = self.parameters.num_workers
                return super().Solve(model, *args, **kwargs)

        monkeypatch.setattr(cp_model, "CpSolver", CapturingSolver)
        result = run_allocation(
            [make_res(1, 1, date(2026, 4, 1), date(2026, 4, 3))],
            make_rooms(1, 1),
        )

        assert result.success is True
        assert observed["num_workers"] == 1

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

    def test_cpsat_capacity_constraint_assigns_only_room_with_enough_occupancy(self):
        rooms = [
            RoomSlot(room_id=1, room_number="101", category_id=1, max_occupancy=2),
            RoomSlot(room_id=2, room_number="102", category_id=1, max_occupancy=4),
        ]
        reservations = [
            ReservationSlot(
                reservation_id=1,
                category_id=1,
                check_in=date(2026, 4, 1),
                check_out=date(2026, 4, 3),
                current_room_id=None,
                is_locked=False,
                num_guests=3,
            )
        ]

        result = run_allocation(reservations, rooms)

        assert result.success is True
        assert result.assignments[1] == 2

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
