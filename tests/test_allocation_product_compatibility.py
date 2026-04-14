from __future__ import annotations

from datetime import date

from app.models.commercial import ProductRoomCompatibility, SellableProduct
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import RoomCategory, RoomStatusEnum
from app.services.allocation_engine import build_slots_from_db
from app.services.allocation_policy_service import create_policy_version, ensure_default_policy_profile
from app.services.allocation_runtime_service import run_persisted_allocation


def _seed_product_with_compatibilities(db, hotel_id: int, category_id: int, compatibilities: list[dict]) -> SellableProduct:
    product = SellableProduct(
        hotel_id=hotel_id,
        primary_room_category_id=category_id,
        code=f"PRODUCT-{category_id}-{len(compatibilities)}",
        name="Producto vendible de prueba",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    for item in compatibilities:
        db.add(
            ProductRoomCompatibility(
                hotel_id=hotel_id,
                sellable_product_id=product.id,
                room_category_id=item["room_category_id"],
                compatibility_kind=item.get("compatibility_kind", "upgrade"),
                priority=item.get("priority", 100),
                allows_auto_assignment=item.get("allows_auto_assignment", True),
            )
        )
    db.flush()
    return product


def test_build_slots_from_db_uses_sellable_product_compatibility_priorities(
    db,
    hotel_config,
    sample_categories,
    sample_guest,
):
    product = _seed_product_with_compatibilities(
        db,
        hotel_id=hotel_config.id,
        category_id=sample_categories[0].id,
        compatibilities=[
            {"room_category_id": sample_categories[1].id, "compatibility_kind": "upgrade", "priority": 5},
            {"room_category_id": sample_categories[2].id, "compatibility_kind": "upgrade", "priority": 15},
        ],
    )

    reservation = Reservation(
        confirmation_code="COMPAT-SLOTS-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 11, 1),
        check_out_date=date(2026, 11, 3),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=100.0,
        amount_paid=0.0,
        deposit_amount=30.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    slots, _ = build_slots_from_db(
        db,
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 5),
        hotel_id=hotel_config.id,
        policy_constraints={"allow_category_fallback": True},
    )

    slot = next(item for item in slots if item.reservation_id == reservation.id)
    assert slot.allowed_category_ids == [
        sample_categories[0].id,
        sample_categories[1].id,
        sample_categories[2].id,
    ]
    assert slot.category_priority(sample_categories[0].id) == 0
    assert slot.category_priority(sample_categories[1].id) == 5
    assert slot.category_priority(sample_categories[2].id) == 15


def test_build_slots_from_db_respects_policy_when_fallback_is_disabled(
    db,
    hotel_config,
    sample_categories,
    sample_guest,
):
    product = _seed_product_with_compatibilities(
        db,
        hotel_id=hotel_config.id,
        category_id=sample_categories[0].id,
        compatibilities=[
            {"room_category_id": sample_categories[0].id, "compatibility_kind": "exact", "priority": 1},
            {"room_category_id": sample_categories[1].id, "compatibility_kind": "upgrade", "priority": 5},
        ],
    )

    reservation = Reservation(
        confirmation_code="COMPAT-SLOTS-2",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 11, 6),
        check_out_date=date(2026, 11, 8),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=100.0,
        amount_paid=0.0,
        deposit_amount=30.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    slots, _ = build_slots_from_db(
        db,
        start_date=date(2026, 11, 6),
        end_date=date(2026, 11, 10),
        hotel_id=hotel_config.id,
        policy_constraints={"allow_category_fallback": False},
    )

    slot = next(item for item in slots if item.reservation_id == reservation.id)
    assert slot.allowed_category_ids == [sample_categories[0].id]


def test_build_slots_from_db_does_not_infer_fallback_from_category_code_suffixes(
    db,
    hotel_config,
    sample_guest,
):
    shared_double = RoomCategory(
        hotel_id=hotel_config.id,
        name="Doble compartida",
        code="DBL_C",
        base_price_per_night=100.0,
        max_occupancy=2,
    )
    shared_triple = RoomCategory(
        hotel_id=hotel_config.id,
        name="Triple compartida",
        code="TPL_C",
        base_price_per_night=140.0,
        max_occupancy=3,
    )
    db.add_all([shared_double, shared_triple])
    db.flush()

    product = SellableProduct(
        hotel_id=hotel_config.id,
        primary_room_category_id=shared_double.id,
        code="DBL_SHARED",
        name="Doble bano compartido",
        min_occupancy=1,
        max_occupancy=2,
    )
    db.add(product)
    db.flush()

    reservation = Reservation(
        confirmation_code="COMPAT-NO-HEURISTIC-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=shared_double.id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 11, 8),
        check_out_date=date(2026, 11, 10),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=100.0,
        amount_paid=0.0,
        deposit_amount=30.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    slots, _ = build_slots_from_db(
        db,
        start_date=date(2026, 11, 8),
        end_date=date(2026, 11, 12),
        hotel_id=hotel_config.id,
        policy_constraints={"allow_category_fallback": True},
    )

    slot = next(item for item in slots if item.reservation_id == reservation.id)
    assert slot.allowed_category_ids == [shared_double.id]


def test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    product = _seed_product_with_compatibilities(
        db,
        hotel_id=hotel_config.id,
        category_id=sample_categories[0].id,
        compatibilities=[
            {"room_category_id": sample_categories[1].id, "compatibility_kind": "upgrade", "priority": 5},
        ],
    )

    for room in sample_rooms:
        if room.category_id == sample_categories[0].id:
            room.status = RoomStatusEnum.MAINTENANCE

    reservation = Reservation(
        confirmation_code="COMPAT-ALLOC-1",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 11, 10),
        check_out_date=date(2026, 11, 12),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=100.0,
        amount_paid=0.0,
        deposit_amount=30.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    persisted = run_persisted_allocation(
        db,
        hotel_id=hotel_config.id,
        trigger_type="compatibility_upgrade_test",
        apply=True,
        horizon_start=date(2026, 11, 10),
        horizon_end=date(2026, 11, 15),
    )
    db.commit()
    db.refresh(reservation)

    assert persisted.run.status.value == "succeeded"
    assert reservation.room_id is not None
    assert reservation.room.category_id == sample_categories[1].id


def test_run_persisted_allocation_respects_published_policy_that_disables_fallback(
    db,
    hotel_config,
    sample_categories,
    sample_rooms,
    sample_guest,
):
    product = _seed_product_with_compatibilities(
        db,
        hotel_id=hotel_config.id,
        category_id=sample_categories[0].id,
        compatibilities=[
            {"room_category_id": sample_categories[1].id, "compatibility_kind": "upgrade", "priority": 5},
        ],
    )

    for room in sample_rooms:
        if room.category_id == sample_categories[0].id:
            room.status = RoomStatusEnum.MAINTENANCE

    reservation = Reservation(
        confirmation_code="COMPAT-ALLOC-2",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=None,
        category_id=sample_categories[0].id,
        sellable_product_id=product.id,
        check_in_date=date(2026, 11, 16),
        check_out_date=date(2026, 11, 18),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=100.0,
        amount_paid=0.0,
        deposit_amount=30.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    profile = ensure_default_policy_profile(db, hotel_config.id)
    create_policy_version(
        db,
        hotel_id=hotel_config.id,
        profile_id=profile.id,
        constraints={"no_overlap": True, "respect_locked_assignments": True, "allow_category_fallback": False},
        weights={
            "prefer_exact_match": 500,
            "stability": 5,
            "room_usage_penalty": 50,
            "unassigned_penalty": 10000,
            "fallback_priority_penalty": 25,
        },
        prompt_summary="No permitir fallback de categoria",
        publish=True,
    )

    persisted = run_persisted_allocation(
        db,
        hotel_id=hotel_config.id,
        trigger_type="compatibility_no_fallback_test",
        apply=True,
        horizon_start=date(2026, 11, 16),
        horizon_end=date(2026, 11, 20),
    )
    db.commit()
    db.refresh(reservation)

    assert persisted.run.status.value == "failed"
    assert reservation.room_id is None
    assert reservation.requires_manual_review is True
