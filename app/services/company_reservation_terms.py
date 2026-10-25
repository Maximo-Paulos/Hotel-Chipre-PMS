"""Snapshot and manager review helpers for corporate reservation terms.

Company profiles are mutable configuration. Reservations keep the terms that
were attached to the booking, while a separate reviewed-config baseline lets
the hotel detect later profile changes without silently rewriting the booking.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation


COMPANY_TERM_FIELDS = (
    "payment_deferred",
    "deferred_days",
    "requires_voucher",
    "requires_signature",
    "base_price",
    "extra_person_nightly_surcharge",
)


def _decimal_text(value: Any) -> str | None:
    if value is None:
        return None
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def company_terms_from_profile(company: Company) -> dict[str, Any]:
    """Return only the mutable terms that can affect a company booking."""
    return {
        "payment_deferred": bool(company.payment_deferred),
        "deferred_days": int(company.deferred_days) if company.deferred_days is not None else None,
        "requires_voucher": bool(company.requires_voucher),
        "requires_signature": bool(company.requires_signature),
        "base_price": _decimal_text(company.base_price),
        "extra_person_nightly_surcharge": _decimal_text(company.extra_person_nightly_surcharge),
    }


def terms_fingerprint(terms: dict[str, Any]) -> str:
    canonical = json.dumps(terms, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reservation_economics(reservation: Reservation) -> dict[str, Any]:
    """Capture booked amounts as evidence; later config review never reprices them."""
    return {
        "currency_code": str(reservation.currency_code or "ARS").upper(),
        "total_amount": _decimal_text(reservation.total_amount),
        "subtotal_amount": _decimal_text(reservation.subtotal_amount),
        "tax_amount": _decimal_text(reservation.tax_amount),
        "fee_amount": _decimal_text(reservation.fee_amount),
        "commission_amount": _decimal_text(reservation.commission_amount),
        "net_amount": _decimal_text(reservation.net_amount),
        "deposit_amount": _decimal_text(reservation.deposit_amount),
        "pricing_snapshot": _parse_pricing_snapshot(reservation.pricing_snapshot),
    }


def _parse_pricing_snapshot(value: str | None) -> Any:
    if not value:
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        # Preserve malformed legacy evidence as text rather than losing the
        # booking price provenance while creating a company terms snapshot.
        return {"legacy_unparsed": str(value)[:4000]}
    return decoded


def build_company_terms_snapshot(
    company: Company,
    reservation: Reservation,
    *,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    terms = company_terms_from_profile(company)
    return {
        "schema_version": 1,
        "company_id": company.id,
        "captured_at": (captured_at or datetime.now(timezone.utc)).isoformat(),
        "terms": terms,
        "terms_fingerprint": terms_fingerprint(terms),
        "applied_economics": _reservation_economics(reservation),
    }


def get_company_terms_review_state(
    db: Session,
    reservation: Reservation,
    *,
    hotel_id: int,
    company: Company | None = None,
) -> dict[str, Any]:
    """Resolve current profile drift, including old reservations without snapshots."""
    if reservation.hotel_id != hotel_id:
        raise ValueError("La reserva no pertenece al hotel activo")
    if reservation.company_id is None:
        return {
            "status": "not_applicable",
            "needs_review": False,
            "blocks_checkin": False,
            "company_id": None,
            "current_terms": None,
            "snapshot": None,
            "changed_fields": [],
            "current_fingerprint": None,
            "reviewed_config_fingerprint": None,
        }
    if company is None:
        company = (
            db.query(Company)
            .filter(Company.hotel_id == hotel_id, Company.id == reservation.company_id)
            .one_or_none()
        )
    if company is None:
        raise ValueError("La empresa asociada a la reserva no está disponible en este hotel")

    snapshot = reservation.company_terms_snapshot
    current_terms = company_terms_from_profile(company)
    current_fingerprint = terms_fingerprint(current_terms)
    reviewed_config = reservation.company_terms_reviewed_config
    if not isinstance(reviewed_config, dict) and isinstance(snapshot, dict):
        reviewed_config = snapshot.get("terms")

    if not isinstance(snapshot, dict) or not isinstance(reviewed_config, dict):
        changed_fields = list(COMPANY_TERM_FIELDS)
        status = "snapshot_missing"
    else:
        changed_fields = [
            field for field in COMPANY_TERM_FIELDS
            if reviewed_config.get(field) != current_terms.get(field)
        ]
        status = "hold_for_manager_review" if changed_fields else (
            reservation.company_terms_review_state or "captured"
        )

    config = db.get(HotelConfiguration, hotel_id)
    block_checkin = bool(
        getattr(config, "block_checkin_on_company_terms_change", True)
    )
    needs_review = status in {"snapshot_missing", "hold_for_manager_review"}
    return {
        "status": status,
        "needs_review": needs_review,
        "blocks_checkin": needs_review and block_checkin,
        "company_id": company.id,
        "company_name": company.display_name,
        "current_terms": current_terms,
        "snapshot": snapshot,
        "reviewed_config": reviewed_config,
        "changed_fields": changed_fields,
        "current_fingerprint": current_fingerprint,
        "reviewed_config_fingerprint": (
            terms_fingerprint(reviewed_config) if isinstance(reviewed_config, dict) else None
        ),
        "block_checkin_on_change": block_checkin,
    }


def effective_company_terms(
    company: Company,
    reservation: Reservation,
) -> dict[str, Any]:
    """Use the agreed snapshot until a manager explicitly accepts new terms."""
    snapshot = reservation.company_terms_snapshot
    terms = snapshot.get("terms") if isinstance(snapshot, dict) else None
    if isinstance(terms, dict):
        return terms
    # Historical bookings without snapshots use the current profile only when
    # the hotel has explicitly disabled the review block.
    return company_terms_from_profile(company)
