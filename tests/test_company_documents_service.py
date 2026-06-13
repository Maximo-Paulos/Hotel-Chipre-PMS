from datetime import date
from decimal import Decimal
import re

import pytest

from app.models.company import Company
from app.models.company_document import CompanyDocumentStatusEnum, CompanyDocumentTypeEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.reservation import ReservationCreate
from app.services.company_document_service import (
    CompanyDocumentError,
    create_document,
    list_documents_for_company,
    list_documents_for_reservation,
    set_signature_status,
)
from app.services.reservation_service import create_reservation


def _company(db, *, hotel_id: int, display_name: str = "Acme", **kwargs) -> Company:
    tax_suffix = re.sub(r"[^A-Za-z0-9]+", "-", display_name).strip("-").lower()
    company = Company(
        hotel_id=hotel_id,
        legal_name=f"{display_name} SA",
        display_name=display_name,
        tax_id=f"{hotel_id}-{tax_suffix}",
        contact_name="Corporate desk",
        contact_email="corp@example.com",
        contact_phone="+541100000000",
        **kwargs,
    )
    db.add(company)
    db.flush()
    return company


def _user(db, user_id: int) -> User:
    user = User(
        id=user_id,
        email=f"user{user_id}@example.com",
        password_hash="test-hash",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def test_company_document_signature_status_flow(db, hotel_config, sample_guest, sample_rooms, sample_categories):
    _user(db, 7)
    _user(db, 9)
    company = _company(db, hotel_id=hotel_config.id, requires_signature=True)
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            company_id=company.id,
            check_in_date=date(2026, 7, 1),
            check_out_date=date(2026, 7, 3),
        ),
        hotel_id=hotel_config.id,
    )

    document = create_document(
        db,
        hotel_id=hotel_config.id,
        user_id=7,
        reservation_id=reservation.id,
        company_id=company.id,
        doc_type=CompanyDocumentTypeEnum.SIGNATURE_REQUIRED,
        file_name="voucher.pdf",
        file_url="s3://hotel-docs/voucher.pdf",
        requires_signature=True,
        notes="Print for guest",
    )

    assert document.status == CompanyDocumentStatusEnum.PENDING

    signed = set_signature_status(
        db,
        hotel_id=hotel_config.id,
        user_id=9,
        document_id=document.id,
        status=CompanyDocumentStatusEnum.SIGNED,
    )

    assert signed.status == CompanyDocumentStatusEnum.SIGNED
    assert signed.signed_by_user_id == 9
    assert signed.signed_at is not None
    audit = db.query(SecurityAuditLog).filter(SecurityAuditLog.action == "company_document.signature_status_changed").one()
    assert audit.hotel_id == hotel_config.id
    assert audit.user_id == 9
    assert str(document.id) in (audit.details or "")

    with pytest.raises(CompanyDocumentError, match="Invalid signature status transition"):
        set_signature_status(
            db,
            hotel_id=hotel_config.id,
            user_id=9,
            document_id=document.id,
            status=CompanyDocumentStatusEnum.REJECTED,
        )


def test_company_documents_are_hotel_scoped(db, hotel_config, sample_guest, sample_rooms, sample_categories, sample_categories_hotel2, sample_rooms_hotel2):
    _user(db, 1)
    company_h1 = _company(db, hotel_id=1, display_name="Acme H1")
    reservation_h1 = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[1].id,
            company_id=company_h1.id,
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 2),
        ),
        hotel_id=1,
    )
    document = create_document(
        db,
        hotel_id=1,
        user_id=1,
        reservation_id=reservation_h1.id,
        company_id=company_h1.id,
        doc_type=CompanyDocumentTypeEnum.VOUCHER_PDF,
        file_name="h1.pdf",
    )

    assert [doc.id for doc in list_documents_for_company(db, hotel_id=1, company_id=company_h1.id)] == [document.id]
    assert list_documents_for_company(db, hotel_id=2, company_id=company_h1.id) == []
    assert [doc.id for doc in list_documents_for_reservation(db, hotel_id=1, reservation_id=reservation_h1.id)] == [document.id]
    assert list_documents_for_reservation(db, hotel_id=2, reservation_id=reservation_h1.id) == []


def test_company_base_price_applies_as_reservation_default_but_overridable(db, hotel_config, sample_guest, sample_rooms, sample_categories):
    company = _company(db, hotel_id=hotel_config.id, base_price=Decimal("175.00"))

    default_rate_reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[2].id,
            company_id=company.id,
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 4),
        ),
        hotel_id=hotel_config.id,
    )

    assert default_rate_reservation.total_amount == Decimal("525.00")
    assert default_rate_reservation.subtotal_amount == Decimal("525.00")
    assert default_rate_reservation.deposit_amount == Decimal("157.50")

    overridden = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[3].id,
            company_id=company.id,
            total_amount=Decimal("999.00"),
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 4),
        ),
        hotel_id=hotel_config.id,
    )

    assert overridden.total_amount == Decimal("999.00")
    assert overridden.subtotal_amount == Decimal("999.00")


def test_corporate_reservation_is_allocation_locked(db, hotel_config, sample_guest, sample_rooms, sample_categories):
    deferred_company = _company(db, hotel_id=hotel_config.id, display_name="Deferred Co", payment_deferred=True)
    signature_company = _company(db, hotel_id=hotel_config.id, display_name="Signature Co", requires_signature=True)
    regular_company = _company(db, hotel_id=hotel_config.id, display_name="Regular Co")

    deferred = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[4].id,
            company_id=deferred_company.id,
            check_in_date=date(2026, 10, 1),
            check_out_date=date(2026, 10, 2),
        ),
        hotel_id=hotel_config.id,
    )
    signature = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[5].id,
            company_id=signature_company.id,
            check_in_date=date(2026, 10, 1),
            check_out_date=date(2026, 10, 2),
        ),
        hotel_id=hotel_config.id,
    )
    regular = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[6].id,
            company_id=regular_company.id,
            check_in_date=date(2026, 10, 1),
            check_out_date=date(2026, 10, 2),
        ),
        hotel_id=hotel_config.id,
    )

    assert deferred.allocation_locked is True
    assert signature.allocation_locked is True
    assert regular.allocation_locked is False
