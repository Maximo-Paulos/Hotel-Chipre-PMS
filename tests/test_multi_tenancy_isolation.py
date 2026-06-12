"""
Multi-tenancy isolation tests: Hotel A vs Hotel B.

Verifies that every domain table correctly scopes data per hotel_id,
and that no cross-hotel data leakage is possible at the ORM/query layer.

v72 §1.3: "No cross-hotel data leakage"

These tests create identical data under two different hotel IDs and assert:
1. Queries scoped to Hotel A never return Hotel B data.
2. Unique constraints are per-hotel (not global).
3. Deletion/mutation on Hotel A does not affect Hotel B.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models.hotel_config import HotelConfiguration
from app.models.user import User
from app.models.guest import Guest, GuestTag, GuestTagTypeEnum, GuestRatingEnum
from app.models.room import Room, RoomCategory
from app.models.reservation import (
    Reservation, ReservationStatusEnum, ReservationSourceEnum,
)
from app.models.transaction import Transaction, PaymentMethodEnum, TransactionTypeEnum, TransactionStatusEnum
from app.models.voucher import HotelVoucher, VoucherStatusEnum
from app.models.cash_register import CashSession, CashSessionStatusEnum
from app.models.waitlist import WaitlistEntry, WaitlistStatusEnum
from app.models.hotel_api_key import HotelAPIKey, APIKeyPurposeEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.company import Company


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def two_hotels(db):
    """Creates Hotel A (id=1000) and Hotel B (id=1001) with minimal shared structure."""
    ha = HotelConfiguration(id=1000, hotel_name="Hotel Alpha", subscription_active=True)
    hb = HotelConfiguration(id=1001, hotel_name="Hotel Beta", subscription_active=True)
    db.add_all([ha, hb])
    db.flush()
    return ha, hb


@pytest.fixture()
def two_hotel_categories(db, two_hotels):
    ha, hb = two_hotels
    ca = RoomCategory(hotel_id=ha.id, name="Standard", code="STD", base_price_per_night=100, max_occupancy=2)
    cb = RoomCategory(hotel_id=hb.id, name="Standard", code="STD", base_price_per_night=100, max_occupancy=2)
    db.add_all([ca, cb])
    db.flush()
    return ca, cb


@pytest.fixture()
def two_hotel_rooms(db, two_hotel_categories):
    ca, cb = two_hotel_categories
    ra = Room(hotel_id=ca.hotel_id, category_id=ca.id, room_number="101", floor=1)
    rb = Room(hotel_id=cb.hotel_id, category_id=cb.id, room_number="101", floor=1)
    db.add_all([ra, rb])
    db.flush()
    return ra, rb


def _make_guest(hotel_id, suffix, db):
    g = Guest(hotel_id=hotel_id, first_name="Ana", last_name=suffix, terms_accepted=True)
    db.add(g)
    db.flush()
    return g


def _make_reservation(hotel_id, guest_id, category_id, code, db):
    r = Reservation(
        confirmation_code=code,
        hotel_id=hotel_id,
        guest_id=guest_id,
        category_id=category_id,
        check_in_date=date(2026, 8, 1),
        check_out_date=date(2026, 8, 3),
        total_amount=200,
        amount_paid=200,
        deposit_amount=0,
        source=ReservationSourceEnum.DIRECT,
        status=ReservationStatusEnum.FULLY_PAID,
    )
    db.add(r)
    db.flush()
    return r


# ── 1. Guests are isolated per hotel ─────────────────────────────────────────

def test_guest_scoped_to_hotel(db, two_hotels):
    ha, hb = two_hotels
    ga = _make_guest(ha.id, "Alpha", db)
    gb = _make_guest(hb.id, "Beta", db)

    guests_a = db.query(Guest).filter_by(hotel_id=ha.id).all()
    guests_b = db.query(Guest).filter_by(hotel_id=hb.id).all()

    assert ga in guests_a
    assert gb not in guests_a
    assert gb in guests_b
    assert ga not in guests_b


def test_guest_dedup_unique_per_hotel_not_global(db, two_hotels):
    """Same document can exist in Hotel A and Hotel B — dedup is hotel-scoped."""
    ha, hb = two_hotels
    g1 = Guest(hotel_id=ha.id, first_name="Juan", last_name="Pérez",
               document_type="DNI", document_number="12345678", terms_accepted=True)
    g2 = Guest(hotel_id=hb.id, first_name="Juan", last_name="Pérez",
               document_type="DNI", document_number="12345678", terms_accepted=True)
    db.add_all([g1, g2])
    db.commit()  # Must NOT raise — same doc across different hotels is allowed


def test_guest_dedup_same_hotel_raises(db, two_hotels):
    """Same document within one hotel raises IntegrityError."""
    ha, _ = two_hotels
    db.add(Guest(hotel_id=ha.id, first_name="A", last_name="B",
                 document_type="DNI", document_number="99999999", terms_accepted=True))
    db.flush()
    db.add(Guest(hotel_id=ha.id, first_name="C", last_name="D",
                 document_type="DNI", document_number="99999999", terms_accepted=True))
    with pytest.raises(IntegrityError):
        db.flush()


# ── 2. Rooms are isolated per hotel ──────────────────────────────────────────

def test_rooms_scoped_to_hotel(db, two_hotel_rooms):
    ra, rb = two_hotel_rooms
    rooms_a = db.query(Room).filter_by(hotel_id=ra.hotel_id).all()
    rooms_b = db.query(Room).filter_by(hotel_id=rb.hotel_id).all()

    assert ra in rooms_a and rb not in rooms_a
    assert rb in rooms_b and ra not in rooms_b


# ── 3. Reservations are isolated per hotel ───────────────────────────────────

def test_reservations_scoped_to_hotel(db, two_hotel_categories):
    ca, cb = two_hotel_categories
    ga = _make_guest(ca.hotel_id, "GA", db)
    gb = _make_guest(cb.hotel_id, "GB", db)
    ra = _make_reservation(ca.hotel_id, ga.id, ca.id, "RES-A-001", db)
    rb = _make_reservation(cb.hotel_id, gb.id, cb.id, "RES-B-001", db)

    res_a = db.query(Reservation).filter_by(hotel_id=ca.hotel_id).all()
    res_b = db.query(Reservation).filter_by(hotel_id=cb.hotel_id).all()

    assert ra in res_a and rb not in res_a
    assert rb in res_b and ra not in res_b


# ── 4. Guest tags scoped per hotel ───────────────────────────────────────────

def test_guest_tags_scoped_to_hotel(db, two_hotels):
    ha, hb = two_hotels
    ga = _make_guest(ha.id, "TagA", db)
    gb = _make_guest(hb.id, "TagB", db)

    tag_a = GuestTag(hotel_id=ha.id, guest_id=ga.id,
                     tag_type=GuestTagTypeEnum.NO_PAGO,
                     created_at=datetime.now(timezone.utc))
    tag_b = GuestTag(hotel_id=hb.id, guest_id=gb.id,
                     tag_type=GuestTagTypeEnum.VIP,
                     created_at=datetime.now(timezone.utc))
    db.add_all([tag_a, tag_b])
    db.flush()

    tags_a = db.query(GuestTag).filter_by(hotel_id=ha.id).all()
    tags_b = db.query(GuestTag).filter_by(hotel_id=hb.id).all()

    assert tag_a in tags_a and tag_b not in tags_a
    assert tag_b in tags_b and tag_a not in tags_b


# ── 5. Cash sessions scoped per hotel ────────────────────────────────────────

def test_cash_sessions_scoped_to_hotel(db, two_hotels):
    ha, hb = two_hotels
    sa = CashSession(hotel_id=ha.id, status=CashSessionStatusEnum.OPEN,
                     opening_balance=0, currency_code="ARS",
                     opened_at=datetime.now(timezone.utc))
    sb = CashSession(hotel_id=hb.id, status=CashSessionStatusEnum.OPEN,
                     opening_balance=0, currency_code="ARS",
                     opened_at=datetime.now(timezone.utc))
    db.add_all([sa, sb])
    db.flush()

    sessions_a = db.query(CashSession).filter_by(hotel_id=ha.id).all()
    sessions_b = db.query(CashSession).filter_by(hotel_id=hb.id).all()

    assert sa in sessions_a and sb not in sessions_a
    assert sb in sessions_b and sa not in sessions_b


# ── 6. Waitlist entries scoped per hotel ─────────────────────────────────────

def test_waitlist_scoped_to_hotel(db, two_hotel_categories):
    ca, cb = two_hotel_categories
    ga = _make_guest(ca.hotel_id, "WA", db)
    gb = _make_guest(cb.hotel_id, "WB", db)

    wa = WaitlistEntry(hotel_id=ca.hotel_id, guest_id=ga.id, category_id=ca.id,
                       check_in_date=date(2026, 9, 1), check_out_date=date(2026, 9, 3),
                       status=WaitlistStatusEnum.WAITING,
                       created_at=datetime.now(timezone.utc))
    wb = WaitlistEntry(hotel_id=cb.hotel_id, guest_id=gb.id, category_id=cb.id,
                       check_in_date=date(2026, 9, 1), check_out_date=date(2026, 9, 3),
                       status=WaitlistStatusEnum.WAITING,
                       created_at=datetime.now(timezone.utc))
    db.add_all([wa, wb])
    db.flush()

    wl_a = db.query(WaitlistEntry).filter_by(hotel_id=ca.hotel_id).all()
    wl_b = db.query(WaitlistEntry).filter_by(hotel_id=cb.hotel_id).all()

    assert wa in wl_a and wb not in wl_a
    assert wb in wl_b and wa not in wl_b


# ── 7. API keys scoped per hotel ─────────────────────────────────────────────

def test_api_keys_scoped_to_hotel(db, two_hotels):
    ha, hb = two_hotels
    ka = HotelAPIKey(hotel_id=ha.id, name="whatsapp", purpose=APIKeyPurposeEnum.WHATSAPP_BOT,
                     key_prefix="aaa_1234", key_hash="h" * 64,
                     is_active=True, created_at=datetime.now(timezone.utc))
    kb = HotelAPIKey(hotel_id=hb.id, name="whatsapp", purpose=APIKeyPurposeEnum.WHATSAPP_BOT,
                     key_prefix="bbb_1234", key_hash="h" * 64,
                     is_active=True, created_at=datetime.now(timezone.utc))
    db.add_all([ka, kb])
    db.commit()

    keys_a = db.query(HotelAPIKey).filter_by(hotel_id=ha.id).all()
    keys_b = db.query(HotelAPIKey).filter_by(hotel_id=hb.id).all()

    assert ka in keys_a and kb not in keys_a
    assert kb in keys_b and ka not in keys_b


def test_api_key_name_unique_per_hotel_not_global(db, two_hotels):
    """Same key name in two hotels is allowed — uniqueness is per-hotel."""
    ha, hb = two_hotels
    db.add(HotelAPIKey(hotel_id=ha.id, name="my-key", purpose=APIKeyPurposeEnum.OTHER,
                       key_prefix="aa_1111", key_hash="x" * 64, is_active=True,
                       created_at=datetime.now(timezone.utc)))
    db.add(HotelAPIKey(hotel_id=hb.id, name="my-key", purpose=APIKeyPurposeEnum.OTHER,
                       key_prefix="bb_2222", key_hash="y" * 64, is_active=True,
                       created_at=datetime.now(timezone.utc)))
    db.commit()  # Must NOT raise — same name in different hotels is fine


def test_api_key_name_unique_within_hotel_raises(db, two_hotels):
    ha, _ = two_hotels
    db.add(HotelAPIKey(hotel_id=ha.id, name="dup-key", purpose=APIKeyPurposeEnum.OTHER,
                       key_prefix="cc_1111", key_hash="a" * 64, is_active=True,
                       created_at=datetime.now(timezone.utc)))
    db.flush()
    db.add(HotelAPIKey(hotel_id=ha.id, name="dup-key", purpose=APIKeyPurposeEnum.OTHER,
                       key_prefix="cc_2222", key_hash="b" * 64, is_active=True,
                       created_at=datetime.now(timezone.utc)))
    with pytest.raises(IntegrityError):
        db.flush()


# ── 8. Room blocks scoped per hotel ──────────────────────────────────────────

def test_room_blocks_scoped_to_hotel(db, two_hotel_rooms):
    ra, rb = two_hotel_rooms
    ba = RoomBlock(hotel_id=ra.hotel_id, room_id=ra.id,
                   reason_code=RoomBlockReasonEnum.MAINTENANCE,
                   starts_at=date(2026, 10, 1), ends_at=date(2026, 10, 5),
                   is_indefinite=False,
                   created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    bb = RoomBlock(hotel_id=rb.hotel_id, room_id=rb.id,
                   reason_code=RoomBlockReasonEnum.MAINTENANCE,
                   starts_at=date(2026, 10, 1), ends_at=date(2026, 10, 5),
                   is_indefinite=False,
                   created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    db.add_all([ba, bb])
    db.flush()

    blocks_a = db.query(RoomBlock).filter_by(hotel_id=ra.hotel_id).all()
    blocks_b = db.query(RoomBlock).filter_by(hotel_id=rb.hotel_id).all()

    assert ba in blocks_a and bb not in blocks_a
    assert bb in blocks_b and ba not in blocks_b


# ── 9. Companies scoped per hotel ────────────────────────────────────────────

def test_companies_scoped_to_hotel(db, two_hotels):
    ha, hb = two_hotels
    ca = Company(hotel_id=ha.id, legal_name="ACME SA", display_name="ACME")
    cb = Company(hotel_id=hb.id, legal_name="ACME SA", display_name="ACME")
    db.add_all([ca, cb])
    db.commit()

    cos_a = db.query(Company).filter_by(hotel_id=ha.id).all()
    cos_b = db.query(Company).filter_by(hotel_id=hb.id).all()

    assert ca in cos_a and cb not in cos_a
    assert cb in cos_b and ca not in cos_b


# ── 10. OTA dedup is hotel-scoped ────────────────────────────────────────────

def test_ota_dedup_per_hotel_not_global(db, two_hotel_categories):
    """Same OTA channel+external_id across different hotels is allowed."""
    ca, cb = two_hotel_categories
    ga = _make_guest(ca.hotel_id, "OTA-A", db)
    gb = _make_guest(cb.hotel_id, "OTA-B", db)

    ra = Reservation(
        confirmation_code="OTA-A-001",
        hotel_id=ca.hotel_id, guest_id=ga.id, category_id=ca.id,
        check_in_date=date(2026, 11, 1), check_out_date=date(2026, 11, 3),
        total_amount=200, amount_paid=0, deposit_amount=0,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking.com", external_id="BKG-999",
        status=ReservationStatusEnum.PENDING,
    )
    rb = Reservation(
        confirmation_code="OTA-B-001",
        hotel_id=cb.hotel_id, guest_id=gb.id, category_id=cb.id,
        check_in_date=date(2026, 11, 1), check_out_date=date(2026, 11, 3),
        total_amount=200, amount_paid=0, deposit_amount=0,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking.com", external_id="BKG-999",  # same OTA ID, different hotel
        status=ReservationStatusEnum.PENDING,
    )
    db.add_all([ra, rb])
    db.commit()  # Must NOT raise — OTA dedup is per-hotel


def test_ota_dedup_same_hotel_raises(db, two_hotel_categories):
    ca, _ = two_hotel_categories
    ga = _make_guest(ca.hotel_id, "OTA-DUP", db)

    db.add(Reservation(
        confirmation_code="OTA-DUP-001",
        hotel_id=ca.hotel_id, guest_id=ga.id, category_id=ca.id,
        check_in_date=date(2026, 12, 1), check_out_date=date(2026, 12, 3),
        total_amount=200, amount_paid=0, deposit_amount=0,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking.com", external_id="BKG-DUP",
        status=ReservationStatusEnum.PENDING,
    ))
    db.flush()

    db.add(Reservation(
        confirmation_code="OTA-DUP-002",
        hotel_id=ca.hotel_id, guest_id=ga.id, category_id=ca.id,
        check_in_date=date(2026, 12, 5), check_out_date=date(2026, 12, 7),
        total_amount=200, amount_paid=0, deposit_amount=0,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking.com", external_id="BKG-DUP",  # same hotel + same OTA ID
        status=ReservationStatusEnum.PENDING,
    ))
    with pytest.raises(IntegrityError):
        db.flush()


# ── 11. Vouchers scoped per hotel ────────────────────────────────────────────

def test_vouchers_scoped_to_hotel(db, two_hotel_categories):
    from app.models.voucher import HotelVoucher, VoucherStatusEnum
    ca, cb = two_hotel_categories
    ga = _make_guest(ca.hotel_id, "VCH-A", db)
    gb = _make_guest(cb.hotel_id, "VCH-B", db)

    va = HotelVoucher(hotel_id=ca.hotel_id, guest_id=ga.id,
                      voucher_code="VCH-ALPHA-001",
                      original_amount=100, remaining_amount=100,
                      currency_code="ARS", status=VoucherStatusEnum.ACTIVE)
    vb = HotelVoucher(hotel_id=cb.hotel_id, guest_id=gb.id,
                      voucher_code="VCH-ALPHA-001",  # same code, different hotel
                      original_amount=100, remaining_amount=100,
                      currency_code="ARS", status=VoucherStatusEnum.ACTIVE)
    db.add_all([va, vb])
    db.commit()  # Must NOT raise — voucher code uniqueness is per-hotel

    vouchers_a = db.query(HotelVoucher).filter_by(hotel_id=ca.hotel_id).all()
    vouchers_b = db.query(HotelVoucher).filter_by(hotel_id=cb.hotel_id).all()

    assert va in vouchers_a and vb not in vouchers_a
    assert vb in vouchers_b and va not in vouchers_b


# ── 12. Deleting Hotel A data does not affect Hotel B ────────────────────────

def test_delete_hotel_a_guest_does_not_affect_hotel_b(db, two_hotels):
    ha, hb = two_hotels
    ga = _make_guest(ha.id, "DeleteA", db)
    gb = _make_guest(hb.id, "KeepB", db)
    db.commit()

    db.delete(ga)
    db.commit()

    remaining_b = db.query(Guest).filter_by(hotel_id=hb.id).all()
    assert gb in remaining_b
    assert db.query(Guest).filter_by(hotel_id=ha.id).count() == 0
