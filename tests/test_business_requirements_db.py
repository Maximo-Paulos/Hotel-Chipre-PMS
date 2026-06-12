"""
Database business-requirement tests.

Verifies that ALL tables required to fulfill the product business requirements
(product-definition.md + master-plan-pilot-to-public.md) exist and behave
correctly at the schema and persistence layer.

Covered here:
  - HotelVoucher + VoucherRedemption (§8.7 refund path 2 — hotel credit)
  - RefundRequest (§8.7 all three paths)
  - PendingOperationalAction (master plan §A1-A2 pending_actions)
  - DATABASE_FOUNDATION_COMPLETE gate assertion
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.database import Base
from app.models.hotel_config import HotelConfiguration
from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationStatusEnum, ReservationSourceEnum
from app.models.transaction import Transaction, PaymentMethodEnum, TransactionTypeEnum, TransactionStatusEnum
from app.models.user import User
from app.models.voucher import HotelVoucher, VoucherRedemption, VoucherStatusEnum
from app.models.refund import RefundRequest, RefundPathEnum, RefundStatusEnum
from app.models.pending_action import (
    PendingOperationalAction,
    PendingActionTypeEnum,
    PendingActionStatusEnum,
    PendingActionPriorityEnum,
)
from app.models.guest import GuestTag, GuestTagTypeEnum, GuestRatingEnum
from app.models.room import Room
from app.models.cash_register import CashSession, CashMovement, CashCloseReport, CashSessionStatusEnum, CashMovementTypeEnum
from app.models.waitlist import WaitlistEntry, WaitlistStatusEnum
from app.models.payment_config import PaymentSurchargeConfig
from app.models.hotel_api_key import HotelAPIKey, APIKeyPurposeEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.company import Company
from app.models.operations import RoomMovementGroup, RoomMoveEvent, BillingAdjustment


# ---------------------------------------------------------------------------
# DATABASE_FOUNDATION_COMPLETE gate
# ---------------------------------------------------------------------------

REQUIRED_TABLES = {
    # Core domain
    "hotel_configuration",
    "users",
    "hotel_memberships",
    "rooms",
    "room_categories",
    "guests",
    "guest_companions",
    "reservations",
    "reservation_additional_guests",
    # Financials
    "transactions",
    "billing_adjustments",
    "reservation_adjustments",
    "reservation_status_history",
    "room_move_events",
    # Refund system (§8.7)
    "refund_requests",
    "hotel_vouchers",
    "voucher_redemptions",
    # Pending follow-ups (master plan §A1-A2)
    "pending_operational_actions",
    # Audit trail
    "audit_logs",
    # Commercial / Pricing
    "sellable_products",
    "product_room_compatibility",
    "rate_plans",
    "rate_plan_prices",
    "tax_policies",
    "tax_rules",
    "fx_policies",
    # OTA
    "ota_providers",
    "ota_connections",
    "ota_property_mappings",
    "ota_room_mappings",
    "ota_rate_plan_mappings",
    "ota_inventory_rules",
    "ota_price_rules",
    "ota_cancellation_rules",
    "ota_commission_rules",
    "ota_currency_rates",
    "ota_reservation_links",
    "ota_sync_jobs",
    "ota_sync_events",
    # Allocation engine
    "allocation_policy_profiles",
    "allocation_policy_versions",
    "allocation_runs",
    "allocation_assignments",
    "reservation_allocation_locks",
    "allocation_explanations",
    "solver_metrics",
    "manual_override_reasons",
    "llm_policy_suggestions",
    "llm_feedback_events",
    # AI assistant
    "ai_assistant_sessions",
    "ai_assistant_messages",
    "ai_assistant_action_runs",
    "ai_assistant_insights",
    # Analytics / Reports
    "hotel_audit_events",
    "room_state_events",
    "fact_reservation_daily",
    "fact_room_occupancy_daily",
    "analytics_alert_settings",
    "analytics_export_jobs",
    # Subscriptions
    "subscriptions",
    "subscription_events",
    # Auth / Security
    "security_tokens",
    "rate_limit_events",
    # Onboarding
    "onboarding_state",
    # Integrations
    "integration_catalog",
    "integration_connections",
    "integration_events",
    # Operations
    "connections",
    # v72 gaps phase 1
    "guest_tags",
    "cash_sessions",
    "cash_movements",
    "cash_close_reports",
    "waitlist_entries",
    "payment_surcharge_configs",
    "hotel_api_keys",
    # v72 gaps phase 2
    "room_blocks",
    # v72 gaps phase 3
    "room_movement_groups",
}


def test_database_foundation_complete():
    """
    Gate assertion: all tables required by the business requirements exist.
    This test MUST pass before DATABASE_FOUNDATION_COMPLETE can be marked.
    """
    registered = set(Base.metadata.tables.keys())
    missing = REQUIRED_TABLES - registered
    assert not missing, (
        f"DATABASE_FOUNDATION_COMPLETE failed — {len(missing)} required table(s) missing:\n"
        + "\n".join(f"  - {t}" for t in sorted(missing))
    )


# ---------------------------------------------------------------------------
# HotelVoucher tests
# ---------------------------------------------------------------------------

def _make_hotel_guest_reservation(db, hotel_id: int):
    hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Hotel {hotel_id}", subscription_active=True)
    guest = Guest(hotel_id=hotel_id, first_name="Ana", last_name="Test", terms_accepted=True)
    db.add(hotel)
    db.flush()
    db.add(guest)
    db.flush()

    from app.models.room import RoomCategory
    from datetime import date
    cat = RoomCategory(hotel_id=hotel_id, name="Std", code="STD", base_price_per_night=100.0, max_occupancy=2)
    db.add(cat)
    db.flush()
    res = Reservation(
        confirmation_code=f"VCH-{hotel_id}",
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=cat.id,
        check_in_date=date(2026, 7, 1),
        check_out_date=date(2026, 7, 3),
        total_amount=200.0,
        amount_paid=200.0,
        deposit_amount=0.0,
        source=ReservationSourceEnum.DIRECT,
        status=ReservationStatusEnum.CHECKED_OUT,
    )
    db.add(res)
    db.flush()
    return hotel, guest, res


def test_hotel_voucher_table_registered():
    assert "hotel_vouchers" in Base.metadata.tables
    assert "voucher_redemptions" in Base.metadata.tables


def test_hotel_voucher_persists(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 600)
    user = User(email="staff600@test.com", password_hash="h", role="owner", is_verified=True)
    db.add(user)
    db.flush()

    voucher = HotelVoucher(
        hotel_id=600,
        guest_id=guest.id,
        source_reservation_id=res.id,
        voucher_code="VCH-ANA-001",
        original_amount=100.0,
        remaining_amount=100.0,
        currency_code="ARS",
        status=VoucherStatusEnum.ACTIVE,
        issued_by_user_id=user.id,
    )
    db.add(voucher)
    db.commit()

    saved = db.get(HotelVoucher, voucher.id)
    assert saved.voucher_code == "VCH-ANA-001"
    assert saved.remaining_amount == 100.0
    assert saved.status == VoucherStatusEnum.ACTIVE
    assert saved.is_transferable is False


def test_hotel_voucher_unique_code_per_hotel(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 601)
    db.add(HotelVoucher(
        hotel_id=601, guest_id=guest.id, voucher_code="SAME-CODE",
        original_amount=50.0, remaining_amount=50.0, currency_code="ARS",
        status=VoucherStatusEnum.ACTIVE,
    ))
    db.commit()

    # Same code, same hotel → should violate unique constraint
    db.add(HotelVoucher(
        hotel_id=601, guest_id=guest.id, voucher_code="SAME-CODE",
        original_amount=50.0, remaining_amount=50.0, currency_code="ARS",
        status=VoucherStatusEnum.ACTIVE,
    ))
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.flush()


def test_voucher_redemption_persists(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 602)
    voucher = HotelVoucher(
        hotel_id=602, guest_id=guest.id, voucher_code="VCH-REDEEM",
        original_amount=200.0, remaining_amount=200.0, currency_code="ARS",
        status=VoucherStatusEnum.ACTIVE,
    )
    db.add(voucher)
    db.flush()

    redemption = VoucherRedemption(
        hotel_id=602,
        voucher_id=voucher.id,
        reservation_id=res.id,
        amount_used=75.0,
    )
    db.add(redemption)
    # Simulate partial redemption
    voucher.remaining_amount -= 75.0
    voucher.status = VoucherStatusEnum.PARTIALLY_REDEEMED
    db.commit()

    saved_v = db.get(HotelVoucher, voucher.id)
    assert saved_v.remaining_amount == 125.0
    assert saved_v.status == VoucherStatusEnum.PARTIALLY_REDEEMED
    assert len(saved_v.redemptions) == 1
    assert saved_v.redemptions[0].amount_used == 75.0


def test_voucher_remaining_amount_cannot_be_negative(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 603)
    from sqlalchemy.exc import IntegrityError
    voucher = HotelVoucher(
        hotel_id=603, guest_id=guest.id, voucher_code="VCH-NEG",
        original_amount=50.0, remaining_amount=-1.0,
        currency_code="ARS", status=VoucherStatusEnum.ACTIVE,
    )
    db.add(voucher)
    with pytest.raises(IntegrityError):
        db.flush()


# ---------------------------------------------------------------------------
# RefundRequest tests
# ---------------------------------------------------------------------------

def test_refund_request_table_registered():
    assert "refund_requests" in Base.metadata.tables


def test_refund_request_gateway_path(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 610)
    txn = Transaction(
        hotel_id=610, reservation_id=res.id,
        amount=200.0, currency="ARS",
        transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        payment_method=PaymentMethodEnum.MERCADO_PAGO,
        status=TransactionStatusEnum.COMPLETED,
    )
    db.add(txn)
    db.flush()

    user = User(email="op610@test.com", password_hash="h", role="owner", is_verified=True)
    db.add(user)
    db.flush()

    refund = RefundRequest(
        hotel_id=610,
        reservation_id=res.id,
        original_transaction_id=txn.id,
        amount=200.0,
        currency_code="ARS",
        path=RefundPathEnum.GATEWAY,
        status=RefundStatusEnum.COMPLETED,
        gateway_refund_id="MP-REF-12345",
        gateway_response=json.dumps({"status": "approved"}),
        requested_by_user_id=user.id,
        authorized_by_user_id=user.id,
    )
    db.add(refund)
    db.commit()

    saved = db.get(RefundRequest, refund.id)
    assert saved.path == RefundPathEnum.GATEWAY
    assert saved.status == RefundStatusEnum.COMPLETED
    assert saved.gateway_refund_id == "MP-REF-12345"


def test_refund_request_voucher_path(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 611)
    voucher = HotelVoucher(
        hotel_id=611, guest_id=guest.id, voucher_code="VCH-REF-611",
        original_amount=100.0, remaining_amount=100.0, currency_code="ARS",
        status=VoucherStatusEnum.ACTIVE,
    )
    db.add(voucher)
    db.flush()

    refund = RefundRequest(
        hotel_id=611,
        reservation_id=res.id,
        amount=100.0,
        currency_code="ARS",
        path=RefundPathEnum.VOUCHER,
        status=RefundStatusEnum.COMPLETED,
        voucher_id=voucher.id,
    )
    db.add(refund)
    db.commit()

    saved = db.get(RefundRequest, refund.id)
    assert saved.path == RefundPathEnum.VOUCHER
    assert saved.voucher_id == voucher.id


def test_refund_request_manual_review_path(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 612)

    refund = RefundRequest(
        hotel_id=612,
        reservation_id=res.id,
        amount=150.0,
        currency_code="ARS",
        path=RefundPathEnum.MANUAL_REVIEW,
        status=RefundStatusEnum.PENDING,
        reason_code="gateway_timeout",
        reason_note="MP did not respond after 3 retries — needs manual follow-up",
    )
    db.add(refund)
    db.commit()

    saved = db.get(RefundRequest, refund.id)
    assert saved.path == RefundPathEnum.MANUAL_REVIEW
    assert saved.status == RefundStatusEnum.PENDING
    assert saved.authorized_by_user_id is None


# ---------------------------------------------------------------------------
# PendingOperationalAction tests
# ---------------------------------------------------------------------------

def test_pending_operational_action_table_registered():
    assert "pending_operational_actions" in Base.metadata.tables


def test_pending_action_ota_conflict(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 620)

    action = PendingOperationalAction(
        hotel_id=620,
        reservation_id=res.id,
        action_type=PendingActionTypeEnum.OTA_CONFLICT,
        status=PendingActionStatusEnum.OPEN,
        priority=PendingActionPriorityEnum.HIGH,
        title="OTA cancel received after check-in",
        description="Booking.com sent cancel for BKG-620 but reservation is already checked in.",
        source_entity_type="ota_reservation_links",
        source_entity_id=999,
        is_system_generated=True,
    )
    db.add(action)
    db.commit()

    saved = db.get(PendingOperationalAction, action.id)
    assert saved.action_type == PendingActionTypeEnum.OTA_CONFLICT
    assert saved.status == PendingActionStatusEnum.OPEN
    assert saved.priority == PendingActionPriorityEnum.HIGH
    assert saved.resolved_at is None


def test_pending_action_resolution(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 621)
    user = User(email="mgr621@test.com", password_hash="h", role="owner", is_verified=True)
    db.add(user)
    db.flush()

    action = PendingOperationalAction(
        hotel_id=621,
        reservation_id=res.id,
        action_type=PendingActionTypeEnum.MANUAL_REVIEW_REQUIRED,
        status=PendingActionStatusEnum.OPEN,
        priority=PendingActionPriorityEnum.MEDIUM,
        title="Allocation solver could not assign room",
    )
    db.add(action)
    db.flush()

    # Resolve it
    action.status = PendingActionStatusEnum.RESOLVED
    action.resolved_at = datetime.now(timezone.utc)
    action.resolved_by_user_id = user.id
    action.resolution_note = "Manually assigned to room 302."
    db.commit()

    saved = db.get(PendingOperationalAction, action.id)
    assert saved.status == PendingActionStatusEnum.RESOLVED
    assert saved.resolved_by_user_id == user.id
    assert saved.resolution_note is not None


def test_pending_action_all_types_persist(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 622)
    for action_type in PendingActionTypeEnum:
        db.add(PendingOperationalAction(
            hotel_id=622,
            action_type=action_type,
            status=PendingActionStatusEnum.OPEN,
            priority=PendingActionPriorityEnum.LOW,
            title=f"Test {action_type.value}",
        ))
    db.commit()

    count = db.query(PendingOperationalAction).filter_by(hotel_id=622).count()
    assert count == len(PendingActionTypeEnum)


def test_pending_action_hotel_cascade(db):
    # Use a standalone hotel with no rooms/categories so delete cascades cleanly.
    hotel = HotelConfiguration(id=623, hotel_name="Cascade H", subscription_active=True)
    db.add(hotel)
    db.flush()

    db.add(PendingOperationalAction(
        hotel_id=623,
        action_type=PendingActionTypeEnum.OTHER,
        status=PendingActionStatusEnum.OPEN,
        priority=PendingActionPriorityEnum.LOW,
        title="Cascade test",
    ))
    db.commit()

    count_before = db.query(PendingOperationalAction).filter_by(hotel_id=623).count()
    assert count_before == 1

    db.delete(hotel)
    db.commit()

    remaining = db.query(PendingOperationalAction).filter_by(hotel_id=623).count()
    assert remaining == 0


# ---------------------------------------------------------------------------
# v72 gaps phase 1 — guest rating, tags, dedup
# ---------------------------------------------------------------------------

def test_guest_rating_default_is_normal(db):
    hotel = HotelConfiguration(id=700, hotel_name="H700", subscription_active=True)
    db.add(hotel)
    db.flush()
    guest = Guest(hotel_id=700, first_name="Test", last_name="Guest", terms_accepted=True)
    db.add(guest)
    db.commit()
    saved = db.get(Guest, guest.id)
    assert saved.rating == GuestRatingEnum.NORMAL


def test_guest_document_unique_per_hotel(db):
    hotel = HotelConfiguration(id=701, hotel_name="H701", subscription_active=True)
    db.add(hotel)
    db.flush()
    from app.models.guest import DocumentTypeEnum
    g1 = Guest(hotel_id=701, first_name="Juan", last_name="Perez",
               document_type=DocumentTypeEnum.DNI, document_number="12345678", terms_accepted=True)
    db.add(g1)
    db.commit()
    # Same hotel + same doc → must fail
    g2 = Guest(hotel_id=701, first_name="Otro", last_name="Perez",
               document_type=DocumentTypeEnum.DNI, document_number="12345678", terms_accepted=True)
    db.add(g2)
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.flush()


def test_guest_tag_persists(db):
    hotel = HotelConfiguration(id=702, hotel_name="H702", subscription_active=True)
    db.add(hotel)
    db.flush()
    guest = Guest(hotel_id=702, first_name="Ana", last_name="Lopez", terms_accepted=True)
    db.add(guest)
    db.flush()
    tag = GuestTag(hotel_id=702, guest_id=guest.id, tag_type=GuestTagTypeEnum.VIP, note="Loyal guest")
    db.add(tag)
    db.commit()
    saved = db.get(Guest, guest.id)
    assert len(saved.tags) == 1
    assert saved.tags[0].tag_type == GuestTagTypeEnum.VIP


# ---------------------------------------------------------------------------
# v72 gaps phase 1 — room score + accessibility
# ---------------------------------------------------------------------------

def test_room_score_and_accessibility(db):
    hotel = HotelConfiguration(id=710, hotel_name="H710", subscription_active=True)
    db.add(hotel)
    db.flush()
    from app.models.room import RoomCategory, Room
    cat = RoomCategory(hotel_id=710, name="Std", code="STD", base_price_per_night=100, max_occupancy=2)
    db.add(cat)
    db.flush()
    room = Room(hotel_id=710, room_number="101", floor=1, category_id=cat.id,
                score=8, is_accessible=True)
    db.add(room)
    db.commit()
    saved = db.get(Room, room.id)
    assert saved.score == 8
    assert saved.is_accessible is True


def test_room_score_out_of_range_rejected(db):
    hotel = HotelConfiguration(id=711, hotel_name="H711", subscription_active=True)
    db.add(hotel)
    db.flush()
    from app.models.room import RoomCategory, Room
    from sqlalchemy.exc import IntegrityError
    cat = RoomCategory(hotel_id=711, name="Std", code="STD", base_price_per_night=100, max_occupancy=2)
    db.add(cat)
    db.flush()
    room = Room(hotel_id=711, room_number="102", floor=1, category_id=cat.id, score=11)
    db.add(room)
    with pytest.raises(IntegrityError):
        db.flush()


# ---------------------------------------------------------------------------
# v72 gaps phase 1 — reservation mobility_restriction
# ---------------------------------------------------------------------------

def test_reservation_mobility_restriction_field(db):
    hotel, guest, res = _make_hotel_guest_reservation(db, 720)
    res.mobility_restriction = True
    db.commit()
    saved = db.get(Reservation, res.id)
    assert saved.mobility_restriction is True


# ---------------------------------------------------------------------------
# v72 gaps phase 1 — cash register
# ---------------------------------------------------------------------------

def test_cash_session_open_persists(db):
    hotel = HotelConfiguration(id=730, hotel_name="H730", subscription_active=True)
    db.add(hotel)
    db.flush()
    session = CashSession(hotel_id=730, opening_balance=5000, currency_code="ARS",
                          opened_at=datetime.now(timezone.utc))
    db.add(session)
    db.commit()
    saved = db.get(CashSession, session.id)
    assert saved.status == CashSessionStatusEnum.OPEN
    assert float(saved.opening_balance) == 5000.0


def test_cash_movement_links_to_session(db):
    hotel = HotelConfiguration(id=731, hotel_name="H731", subscription_active=True)
    db.add(hotel)
    db.flush()
    session = CashSession(hotel_id=731, opening_balance=0, currency_code="ARS",
                          opened_at=datetime.now(timezone.utc))
    db.add(session)
    db.flush()
    mv = CashMovement(hotel_id=731, session_id=session.id, movement_type=CashMovementTypeEnum.INCOME,
                      amount=1500, description="Cobro habitación 201",
                      recorded_at=datetime.now(timezone.utc))
    db.add(mv)
    db.commit()
    saved = db.get(CashSession, session.id)
    assert len(saved.movements) == 1
    assert float(saved.movements[0].amount) == 1500.0


def test_cash_close_report_persists(db):
    hotel = HotelConfiguration(id=732, hotel_name="H732", subscription_active=True)
    db.add(hotel)
    db.flush()
    session = CashSession(hotel_id=732, opening_balance=0, currency_code="ARS",
                          opened_at=datetime.now(timezone.utc))
    db.add(session)
    db.flush()
    report = CashCloseReport(
        hotel_id=732, session_id=session.id,
        expected_balance=10000, declared_balance=9950, difference=-50,
        closed_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.commit()
    saved = db.get(CashCloseReport, report.id)
    assert float(saved.difference) == -50.0
    assert saved.difference_approved is False


# ---------------------------------------------------------------------------
# v72 gaps phase 1 — waitlist
# ---------------------------------------------------------------------------

def test_waitlist_entry_persists(db):
    from datetime import date
    hotel, guest, res = _make_hotel_guest_reservation(db, 740)
    from app.models.room import RoomCategory
    cat = db.query(RoomCategory).filter_by(hotel_id=740).first()
    entry = WaitlistEntry(
        hotel_id=740, guest_id=guest.id, category_id=cat.id,
        check_in_date=date(2026, 8, 1), check_out_date=date(2026, 8, 3),
        num_adults=2, created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    saved = db.get(WaitlistEntry, entry.id)
    assert saved.status == WaitlistStatusEnum.WAITING
    assert saved.priority == 100


# ---------------------------------------------------------------------------
# v72 gaps phase 1 — payment surcharge config
# ---------------------------------------------------------------------------

def test_payment_surcharge_config_persists(db):
    hotel = HotelConfiguration(id=750, hotel_name="H750", subscription_active=True)
    db.add(hotel)
    db.flush()
    from app.models.transaction import PaymentMethodEnum
    cfg = PaymentSurchargeConfig(
        hotel_id=750, payment_method=PaymentMethodEnum.MERCADO_PAGO,
        surcharge_pct="0.0350", is_active=True,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(cfg)
    db.commit()
    saved = db.get(PaymentSurchargeConfig, cfg.id)
    assert float(saved.surcharge_pct) == pytest.approx(0.035)


def test_payment_surcharge_unique_per_method(db):
    hotel = HotelConfiguration(id=751, hotel_name="H751", subscription_active=True)
    db.add(hotel)
    db.flush()
    from app.models.transaction import PaymentMethodEnum
    from sqlalchemy.exc import IntegrityError
    db.add(PaymentSurchargeConfig(
        hotel_id=751, payment_method=PaymentMethodEnum.CASH,
        surcharge_pct=None, surcharge_fixed="0",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    db.commit()
    db.add(PaymentSurchargeConfig(
        hotel_id=751, payment_method=PaymentMethodEnum.CASH,
        surcharge_pct=None, surcharge_fixed="0",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    ))
    with pytest.raises(IntegrityError):
        db.flush()


# ---------------------------------------------------------------------------
# v72 gaps phase 1 — hotel API keys
# ---------------------------------------------------------------------------

def test_hotel_api_key_persists(db):
    hotel = HotelConfiguration(id=760, hotel_name="H760", subscription_active=True)
    db.add(hotel)
    db.flush()
    key = HotelAPIKey(
        hotel_id=760, name="whatsapp-prod", purpose=APIKeyPurposeEnum.WHATSAPP_BOT,
        key_prefix="hck_1234", key_hash="sha256hexhashvalue" * 4,
        is_active=True, created_at=datetime.now(timezone.utc),
    )
    db.add(key)
    db.commit()
    saved = db.get(HotelAPIKey, key.id)
    assert saved.purpose == APIKeyPurposeEnum.WHATSAPP_BOT
    assert saved.key_prefix == "hck_1234"


# ---------------------------------------------------------------------------
# v72 gaps phase 2 — room_blocks (§14)
# ---------------------------------------------------------------------------

def test_room_blocks_table_registered():
    assert "room_blocks" in Base.metadata.tables


def test_room_block_persists(db):
    from datetime import date
    from app.models.room import RoomCategory
    hotel = HotelConfiguration(id=800, hotel_name="H800", subscription_active=True)
    db.add(hotel)
    db.flush()
    cat = RoomCategory(hotel_id=800, name="Std", code="STD", base_price_per_night=100, max_occupancy=2)
    db.add(cat)
    db.flush()
    from app.models.room import Room
    room = Room(hotel_id=800, category_id=cat.id, room_number="101", floor=1)
    db.add(room)
    db.flush()

    block = RoomBlock(
        hotel_id=800,
        room_id=room.id,
        reason_code=RoomBlockReasonEnum.MAINTENANCE,
        reason_note="Pipe repair",
        starts_at=date(2026, 8, 1),
        ends_at=date(2026, 8, 5),
        is_indefinite=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(block)
    db.commit()
    saved = db.get(RoomBlock, block.id)
    assert saved.reason_code == RoomBlockReasonEnum.MAINTENANCE
    assert saved.starts_at == date(2026, 8, 1)
    assert saved.is_active is True


def test_room_block_indefinite(db):
    from datetime import date
    from app.models.room import RoomCategory, Room
    hotel = HotelConfiguration(id=801, hotel_name="H801", subscription_active=True)
    db.add(hotel)
    db.flush()
    cat = RoomCategory(hotel_id=801, name="Std", code="STD", base_price_per_night=100, max_occupancy=2)
    db.add(cat)
    db.flush()
    room = Room(hotel_id=801, category_id=cat.id, room_number="201", floor=2)
    db.add(room)
    db.flush()

    block = RoomBlock(
        hotel_id=801,
        room_id=room.id,
        reason_code=RoomBlockReasonEnum.OWNER_USE,
        starts_at=date(2026, 9, 1),
        ends_at=None,
        is_indefinite=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(block)
    db.commit()
    saved = db.get(RoomBlock, block.id)
    assert saved.ends_at is None
    assert saved.is_indefinite is True


# ---------------------------------------------------------------------------
# v72 gaps phase 2 — company commercial fields (§3.3-3.5)
# ---------------------------------------------------------------------------

def test_company_commercial_fields_exist():
    cols = {c.key for c in Company.__table__.columns}
    required = {
        "contact_name", "contact_email", "contact_phone", "administrative_contact",
        "base_price", "payment_deferred", "deferred_days",
        "requires_voucher", "requires_signature",
    }
    assert required.issubset(cols), f"Missing company columns: {required - cols}"


def test_company_commercial_fields_persists(db):
    from decimal import Decimal
    hotel = HotelConfiguration(id=802, hotel_name="H802", subscription_active=True)
    db.add(hotel)
    db.flush()
    company = Company(
        hotel_id=802,
        legal_name="ACME S.A.",
        display_name="ACME",
        contact_name="Juan Pérez",
        contact_email="juan@acme.com",
        contact_phone="+54-11-1234-5678",
        base_price=Decimal("150.00"),
        payment_deferred=True,
        deferred_days=30,
        requires_voucher=True,
        requires_signature=False,
    )
    db.add(company)
    db.commit()
    saved = db.get(Company, company.id)
    assert saved.contact_name == "Juan Pérez"
    assert saved.payment_deferred is True
    assert saved.deferred_days == 30
    assert saved.requires_voucher is True
    assert float(saved.base_price) == 150.0


# ---------------------------------------------------------------------------
# v72 §2.6 — guest tag prohibido_alojar blocks check-in (tag exists in enum)
# ---------------------------------------------------------------------------

def test_guest_tag_prohibido_alojar_enum_value():
    assert GuestTagTypeEnum.PROHIBIDO_ALOJAR.value == "prohibido_alojar"
    assert GuestTagTypeEnum.ROBO_COSAS.value == "robo_cosas"
    assert GuestTagTypeEnum.REQUIERE_DEPOSITO.value == "requiere_deposito"


def test_guest_tag_prohibido_alojar_persists(db):
    hotel = HotelConfiguration(id=803, hotel_name="H803", subscription_active=True)
    db.add(hotel)
    db.flush()
    guest = Guest(hotel_id=803, first_name="Riesgo", last_name="Alto", terms_accepted=False)
    db.add(guest)
    db.flush()
    tag = GuestTag(
        hotel_id=803,
        guest_id=guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="Por orden gerencia 2026-06-12",
        created_at=datetime.now(timezone.utc),
    )
    db.add(tag)
    db.commit()
    saved = db.get(GuestTag, tag.id)
    assert saved.tag_type == GuestTagTypeEnum.PROHIBIDO_ALOJAR


# ---------------------------------------------------------------------------
# v72 §2.4 — guest search indexes exist in model
# ---------------------------------------------------------------------------

def test_guest_search_indexes_exist():
    idx_names = {idx.name for idx in Guest.__table__.indexes}
    for expected in (
        "ix_guest_hotel_last_name",
        "ix_guest_hotel_email",
        "ix_guest_hotel_phone",
        "ix_guest_hotel_document_number",
    ):
        assert expected in idx_names, f"Missing guest search index: {expected}"


# ---------------------------------------------------------------------------
# v72 §10.1 — OTA dedup unique constraint on reservations
# ---------------------------------------------------------------------------

def test_reservation_ota_dedup_constraint_exists():
    from sqlalchemy import UniqueConstraint as UC
    constraint_names = {
        c.name for c in Reservation.__table__.constraints if isinstance(c, UC)
    }
    assert "uq_reservation_ota_external_id" in constraint_names


# ---------------------------------------------------------------------------
# v72 gaps phase 3 — room_movement_groups (§5.4)
# ---------------------------------------------------------------------------

def test_room_movement_groups_table_registered():
    assert "room_movement_groups" in Base.metadata.tables


def test_room_movement_group_persists(db):
    hotel = HotelConfiguration(id=900, hotel_name="H900", subscription_active=True)
    db.add(hotel)
    db.flush()

    group = RoomMovementGroup(
        hotel_id=900,
        trigger_reason="overbooking_resolution_2026-08-01",
        notes="3 rooms moved due to same overbooking event",
        created_at=datetime.now(timezone.utc),
    )
    db.add(group)
    db.commit()
    saved = db.get(RoomMovementGroup, group.id)
    assert saved.trigger_reason == "overbooking_resolution_2026-08-01"
    assert saved.is_reverted is False


def test_billing_adjustment_amounts_are_numeric():
    from sqlalchemy import Numeric
    cols = BillingAdjustment.__table__.columns
    for col_name in ("amount", "tax_amount", "total_amount"):
        col = cols[col_name]
        assert isinstance(col.type, Numeric),             f"BillingAdjustment.{col_name} must be Numeric, got {type(col.type)}"


def test_rooms_description_field_exists():
    from app.models.room import Room
    assert "description" in Room.__table__.columns


def test_reservation_adjustment_amount_delta_is_numeric():
    from sqlalchemy import Numeric
    from app.models.operations import ReservationAdjustment
    col = ReservationAdjustment.__table__.columns["amount_delta"]
    assert isinstance(col.type, Numeric),         f"ReservationAdjustment.amount_delta must be Numeric, got {type(col.type)}"
