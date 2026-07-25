from __future__ import annotations

import json

import pytest

from app.decorators.audit_hooks import audited_change
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.guest import DocumentTypeEnum, Guest, GuestCompanion, GuestRatingEnum
from app.models.hotel_config import HotelConfiguration
from app.services import audit_log_service


GUEST_PII_FIELDS = {
    "first_name",
    "last_name",
    "document_type",
    "document_number",
    "nationality",
    "date_of_birth",
    "gender",
    "email",
    "phone",
    "address_line1",
    "address_line2",
    "city",
    "state_province",
    "postal_code",
    "country",
    "digital_signature",
    "special_requests",
    "observations",
}
COMPANION_PII_FIELDS = {
    "first_name",
    "last_name",
    "document_type",
    "document_number",
    "nationality",
    "date_of_birth",
    "relationship_to_guest",
}


def _guest_with_companion(db, hotel_id: int) -> tuple[Guest, GuestCompanion]:
    db.add(HotelConfiguration(id=hotel_id, hotel_name=f"Audit hotel {hotel_id}", subscription_active=True))
    db.flush()
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Audit",
        last_name="Guest",
        document_type=DocumentTypeEnum.PASSPORT,
        document_number="DOC-AUDIT",
        nationality="Argentina",
        email="audit@example.test",
        phone="555-0100",
        address_line1="Example address",
        country="Argentina",
        digital_signature="signature-data",
        special_requests="Late arrival",
        observations="Internal free text",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    companion = GuestCompanion(
        guest_id=guest.id,
        first_name="Companion",
        last_name="Guest",
        document_type=DocumentTypeEnum.DNI,
        document_number="DOC-COMPANION",
        nationality="Argentina",
        relationship_to_guest="spouse",
    )
    db.add(companion)
    db.flush()
    return guest, companion


def test_direct_guest_and_companion_audits_exclude_pii(db):
    guest, companion = _guest_with_companion(db, 8201)
    guest_payload = {**audit_log_service.model_snapshot(guest), "first_name": guest.first_name}
    companion_payload = {**audit_log_service.model_snapshot(companion), "first_name": companion.first_name}

    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=8201,
        table_name="guests",
        record_id=guest.id,
        action=AuditActionEnum.CREATE,
        payload_after=guest_payload,
    )
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=8201,
        table_name="guest_companions",
        record_id=companion.id,
        action=AuditActionEnum.CREATE,
        payload_after=companion_payload,
    )

    guest_payload = json.loads(
        db.query(AuditLog).filter_by(table_name="guests", record_id=guest.id).one().payload_after
    )
    companion_payload = json.loads(
        db.query(AuditLog).filter_by(table_name="guest_companions", record_id=companion.id).one().payload_after
    )
    assert not GUEST_PII_FIELDS.intersection(guest_payload)
    assert not COMPANION_PII_FIELDS.intersection(companion_payload)
    assert guest_payload["id"] == guest.id
    assert guest_payload["hotel_id"] == 8201
    assert guest_payload["rating"] == GuestRatingEnum.NORMAL.value
    assert guest_payload["terms_accepted"] is True
    assert companion_payload == {"guest_id": guest.id, "id": companion.id}


@pytest.mark.parametrize(
    ("table_name", "pii_fields"),
    (("guests", GUEST_PII_FIELDS), ("guest_companions", COMPANION_PII_FIELDS)),
)
def test_decorator_mongo_projection_excludes_guest_pii(db, monkeypatch, table_name, pii_fields):
    guest, companion = _guest_with_companion(db, 8202)
    projected_docs: list[dict] = []
    monkeypatch.setattr("app.decorators.audit_hooks.project_audit_to_mongo", projected_docs.append)

    @audited_change(table_name=table_name, action=AuditActionEnum.UPDATE)
    def change_entity(db, *, hotel_id: int, record_id: int):
        entity = db.get(Guest if table_name == "guests" else GuestCompanion, record_id)
        if table_name == "guests":
            entity.rating = GuestRatingEnum.EXCELENTE
        db.flush()
        return entity

    entity = guest if table_name == "guests" else companion
    change_entity(db, hotel_id=8202, record_id=entity.id)

    assert len(projected_docs) == 1
    projection = projected_docs[0]
    for payload_name in ("payload_before", "payload_after"):
        payload = json.loads(projection[payload_name])
        assert not pii_fields.intersection(payload)
    assert projection["hotel_id"] == 8202
    assert projection["record_id"] == entity.id
