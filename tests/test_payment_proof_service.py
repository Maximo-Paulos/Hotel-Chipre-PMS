from __future__ import annotations

import base64
from decimal import Decimal
from datetime import date
from io import BytesIO

import pytest
from PIL import Image

from app.models.guest import Guest
from app.models.audit_log import AuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.payment_proof import PaymentProof, PaymentProofBlob, PaymentProofStatusEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import PaymentMethodEnum, TransactionStatusEnum
from app.models.user import User
from app.services.payment_proof_service import (
    PaymentProofError,
    approve_transfer_proof,
    get_transfer_proof_bytes,
    reject_transfer_proof,
    submit_transfer_proof,
)


def _image_base64() -> str:
    output = BytesIO()
    Image.new("RGB", (4, 4), color=(20, 80, 120)).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _jpeg_with_exif_base64() -> str:
    output = BytesIO()
    image = Image.new("RGB", (4, 4), color=(120, 80, 20))
    exif = image.getexif()
    exif[0x010E] = "private-transfer-note"
    image.save(output, format="JPEG", exif=exif.tobytes())
    return base64.b64encode(output.getvalue()).decode("ascii")


def _reservation(db, hotel_id: int, code: str) -> Reservation:
    hotel = HotelConfiguration(
        id=hotel_id,
        subscription_active=True,
        enable_bank_transfer=True,
        enable_cash=True,
        enable_mercado_pago=True,
    )
    reviewer = User(id=20, email=f"proof-reviewer-{hotel_id}@test.com", password_hash="test", is_active=True, is_verified=True)
    submitter = User(id=10, email=f"proof-submitter-{hotel_id}@test.com", password_hash="test", is_active=True, is_verified=True)
    db.add(hotel)
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Proof category {hotel_id}",
        code=f"PROOF{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Proof", last_name="Guest")
    db.add_all([category, guest, reviewer, submitter])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=code,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 2),
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("0.00"),
        deposit_amount=Decimal("30.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_submit_transfer_proof_validates_image_and_stores_metadata(db):
    reservation = _reservation(db, 1, "PROOF-1")

    proof = submit_transfer_proof(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("30.00"),
        image_base64=_image_base64(),
        original_filename="comprobante transferencia.png",
        submitted_by_user_id=10,
    )

    assert proof.status == PaymentProofStatusEnum.PENDING.value
    assert proof.content_type == "image/png"
    assert proof.original_filename == "comprobante_transferencia.png"
    blob = db.query(PaymentProofBlob).filter(PaymentProofBlob.proof_id == proof.id).one()
    assert blob.hotel_id == 1
    assert blob.content
    assert blob.sha256_hex == proof.sha256_hex
    content, content_type, filename = get_transfer_proof_bytes(db, hotel_id=1, proof_id=proof.id)
    assert content == blob.content
    assert content_type == "image/png"
    assert filename == "comprobante_transferencia.png"
    audit = db.query(AuditLog).filter(AuditLog.table_name == "payment_proofs", AuditLog.record_id == proof.id).one()
    assert audit.actor_user_id == 10
    assert audit.payload_after and "pending" in audit.payload_after

    with pytest.raises(PaymentProofError, match="ya fue presentado"):
        submit_transfer_proof(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            amount=Decimal("30.00"),
            image_base64=_image_base64(),
            original_filename="duplicate.png",
            submitted_by_user_id=10,
        )


def test_submit_transfer_proof_reencodes_and_removes_exif(db):
    reservation = _reservation(db, 1, "PROOF-EXIF")

    proof = submit_transfer_proof(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("30.00"),
        image_base64=_jpeg_with_exif_base64(),
        original_filename="../transfer.jpg",
        submitted_by_user_id=10,
    )

    content, content_type, filename = get_transfer_proof_bytes(db, hotel_id=1, proof_id=proof.id)
    with Image.open(BytesIO(content)) as image:
        assert image.format == "JPEG"
        assert not image.getexif()
    assert content_type == "image/jpeg"
    assert filename == ".._transfer.jpg"
    assert proof.file_size_bytes == len(content)
    assert proof.sha256_hex
    assert db.query(PaymentProofBlob).filter(PaymentProofBlob.proof_id == proof.id).count() == 1


def test_proof_bytes_are_tenant_scoped(db):
    reservation = _reservation(db, 1, "PROOF-TENANT")
    proof = submit_transfer_proof(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("30.00"),
        image_base64=_image_base64(),
        original_filename="transfer.png",
        submitted_by_user_id=10,
    )

    with pytest.raises(PaymentProofError, match="no encontrado"):
        get_transfer_proof_bytes(db, hotel_id=2, proof_id=proof.id)


def test_approval_creates_completed_transfer_transaction_and_updates_balance(db):
    reservation = _reservation(db, 1, "PROOF-2")
    proof = submit_transfer_proof(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("30.00"),
        image_base64=_image_base64(),
        original_filename="transfer.png",
        submitted_by_user_id=10,
    )

    approved = approve_transfer_proof(db, hotel_id=1, proof_id=proof.id, reviewed_by_user_id=20)

    assert approved.status == PaymentProofStatusEnum.APPROVED.value
    assert approved.transaction_id is not None
    assert approved.reviewed_by_user_id == 20
    transaction = approved.transaction
    assert transaction.payment_method == PaymentMethodEnum.BANK_TRANSFER
    assert transaction.status == TransactionStatusEnum.COMPLETED
    db.refresh(reservation)
    assert reservation.amount_paid == Decimal("30.00")
    assert reservation.balance_due == Decimal("70.00")

    # Approval is idempotent and cannot duplicate the ledger transaction.
    again = approve_transfer_proof(db, hotel_id=1, proof_id=proof.id, reviewed_by_user_id=20)
    assert again.transaction_id == approved.transaction_id
    assert db.query(PaymentProof).count() == 1


def test_rejected_proof_requires_reason_and_cannot_be_approved(db):
    reservation = _reservation(db, 1, "PROOF-3")
    proof = submit_transfer_proof(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("30.00"),
        image_base64=_image_base64(),
        original_filename="transfer.png",
        submitted_by_user_id=10,
    )

    with pytest.raises(PaymentProofError, match="requiere un motivo"):
        reject_transfer_proof(db, hotel_id=1, proof_id=proof.id, reviewed_by_user_id=20, reason=" ")
    reject_transfer_proof(db, hotel_id=1, proof_id=proof.id, reviewed_by_user_id=20, reason="Importe no coincide")
    with pytest.raises(PaymentProofError, match="rechazado"):
        approve_transfer_proof(db, hotel_id=1, proof_id=proof.id, reviewed_by_user_id=20)
