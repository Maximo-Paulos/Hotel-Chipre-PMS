from __future__ import annotations

from decimal import Decimal

from app.models.payment_proof import PaymentProof, PaymentProofBlob, PaymentProofStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.models.permission import Permission, UserPermissionOverride
from app.services.permission_service import (
    PERMISSION_PAYMENT_PROOF_REVIEW,
    PERMISSION_REPORTS_FINANCIAL_VIEW,
)
from tests.test_cross_hotel_id_collision_api import HOTEL_A, two_hotel_client


def _proof(db, reservation_id: int, *, suffix: str) -> PaymentProof:
    proof = PaymentProof(
        hotel_id=HOTEL_A,
        reservation_id=reservation_id,
        amount=Decimal("50.00"),
        currency="ARS",
        payment_method="bank_transfer",
        status=PaymentProofStatusEnum.PENDING.value,
        storage_key=f"proof-{suffix}-key",
        content_type="image/png",
        file_size_bytes=9,
        sha256_hex=suffix * 64,
    )
    db.add(proof)
    db.flush()
    db.add(
        PaymentProofBlob(
            hotel_id=HOTEL_A,
            proof_id=proof.id,
            content=b"synthetic-proof",
            content_type="image/png",
            sha256_hex=suffix * 64,
        )
    )
    db.commit()
    return proof


def test_financial_view_alone_cannot_approve_a_payment_proof(two_hotel_client):
    client, ids = two_hotel_client
    db = ids["_test_db"]
    ids["_test_auth_state"]["role"] = "manager"
    db.add_all(
        [
            Permission(code=PERMISSION_REPORTS_FINANCIAL_VIEW, description="read financial reports"),
            Permission(code=PERMISSION_PAYMENT_PROOF_REVIEW, description="review transfer proofs"),
        ]
    )
    db.flush()
    db.add_all(
        [
            UserPermissionOverride(
                hotel_id=HOTEL_A,
                user_id=HOTEL_A,
                permission_code=PERMISSION_REPORTS_FINANCIAL_VIEW,
                allowed=True,
                updated_by_user_id=HOTEL_A,
            ),
            UserPermissionOverride(
                hotel_id=HOTEL_A,
                user_id=HOTEL_A,
                permission_code=PERMISSION_PAYMENT_PROOF_REVIEW,
                allowed=False,
                updated_by_user_id=HOTEL_A,
            ),
        ]
    )
    proof = _proof(db, ids["reservation_a"], suffix="c")

    response = client.post(f"/api/payment-proofs/{proof.id}/approve")

    assert response.status_code == 403, response.text
    db.refresh(proof)
    assert proof.status == PaymentProofStatusEnum.PENDING.value
    assert proof.transaction_id is None


def test_manager_review_capability_covers_list_image_approve_and_reject(two_hotel_client):
    client, ids = two_hotel_client
    ids["_test_auth_state"]["role"] = "manager"
    db = ids["_test_db"]
    db.query(HotelConfiguration).filter_by(id=HOTEL_A).one().enable_bank_transfer = True
    db.commit()
    approved = _proof(db, ids["reservation_a"], suffix="d")
    rejected = _proof(db, ids["reservation_a"], suffix="e")

    assert client.get("/api/payment-proofs").status_code == 200
    image = client.get(f"/api/payment-proofs/{approved.id}/image")
    assert image.status_code == 200
    assert image.content == b"synthetic-proof"

    approved_response = client.post(f"/api/payment-proofs/{approved.id}/approve")
    rejected_response = client.post(
        f"/api/payment-proofs/{rejected.id}/reject",
        json={"reason": "Synthetic amount mismatch"},
    )
    assert approved_response.status_code == 200, approved_response.text
    assert approved_response.json()["status"] == PaymentProofStatusEnum.APPROVED.value
    assert rejected_response.status_code == 200, rejected_response.text
    assert rejected_response.json()["status"] == PaymentProofStatusEnum.REJECTED.value
