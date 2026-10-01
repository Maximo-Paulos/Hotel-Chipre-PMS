from datetime import date, timedelta
import json

import pytest

from app.models.daily_rate import DailyRate
from app.models.company import Company
from app.schemas.reservation import ReservationCreate
from app.services.pricing_service import build_pricing_revision
from app.services.quote_token_service import QuoteTokenError, issue_quote_token, verify_quote_token
from app.services.reservation_quote_service import build_reservation_quote
from app.services.reservation_service import ReservationError, create_reservation


def _quote(db, category_id: int):
    check_in = date(2030, 1, 10)
    check_out = check_in + timedelta(days=2)
    return build_reservation_quote(
        db,
        hotel_id=1,
        category_id=category_id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=2,
    )


def test_quote_token_is_signed_and_round_trips_without_pii():
    token = issue_quote_token({"hotel_id": 1, "category_id": 2, "pricing_revision": "abc"})
    payload = verify_quote_token(token)
    assert payload["hotel_id"] == 1
    assert payload["pricing_revision"] == "abc"
    assert "email" not in json.dumps(payload)

    with pytest.raises(QuoteTokenError, match="signature"):
        verify_quote_token(f"{token[:-1]}x")

    encrypted = issue_quote_token({"hotel_id": 1, "total_amount": 987654.32}, encrypt_payload=True)
    assert encrypted.startswith("enc1.")
    assert verify_quote_token(encrypted)["total_amount"] == 987654.32
    changed = encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B")
    with pytest.raises(QuoteTokenError, match="invalid"):
        verify_quote_token(changed)


def test_quote_rejects_occupancy_above_category_capacity(db, sample_categories):
    with pytest.raises(ReservationError, match="admite hasta 2"):
        build_reservation_quote(
            db,
            hotel_id=1,
            category_id=sample_categories[0].id,
            check_in_date=date(2030, 1, 10),
            check_out_date=date(2030, 1, 12),
            occupancy=3,
        )


def test_reservation_rejects_quote_after_pricing_revision_changes(
    db, sample_categories, sample_rooms, sample_guest, hotel_config
):
    category = sample_categories[0]
    quote = _quote(db, category.id)
    assert quote["quote_token"]

    db.add(
        DailyRate(
            hotel_id=1,
            category_id=category.id,
            date=date(2030, 1, 10),
            price=999.0,
        )
    )
    db.flush()

    payload = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=category.id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2030, 1, 10),
        check_out_date=date(2030, 1, 12),
        num_adults=2,
        quote_token=quote["quote_token"],
    )
    with pytest.raises(ReservationError, match="venció"):
        create_reservation(db, payload, hotel_id=1)


def test_confirmed_reservation_stores_pricing_revision(
    db, sample_categories, sample_rooms, sample_guest, hotel_config
):
    category = sample_categories[0]
    quote = _quote(db, category.id)
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=category.id,
            room_id=sample_rooms[1].id,
            check_in_date=date(2030, 1, 10),
            check_out_date=date(2030, 1, 12),
            num_adults=2,
            quote_token=quote["quote_token"],
        ),
        hotel_id=1,
    )
    revision = build_pricing_revision(
        db,
        hotel_id=1,
        category_id=category.id,
        check_in=date(2030, 1, 10),
        check_out=date(2030, 1, 12),
        occupancy=2,
    )
    snapshot = json.loads(reservation.pricing_snapshot or "{}")
    assert snapshot["pricing_revision"] == revision
    assert snapshot["breakdown"]


def test_company_quote_is_bound_to_company_and_its_current_terms(
    db, sample_categories, sample_rooms, sample_guest, hotel_config
):
    company = Company(
        hotel_id=1,
        legal_name="Acme Travel SRL",
        display_name="Acme Travel",
        base_price=80,
    )
    db.add(company)
    db.flush()
    category = sample_categories[0]
    check_in = date(2030, 2, 10)
    check_out = check_in + timedelta(days=2)
    quote = build_reservation_quote(
        db,
        hotel_id=1,
        category_id=category.id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=2,
        company_id=company.id,
    )
    token_payload = verify_quote_token(quote["quote_token"])
    assert token_payload["company_id"] == company.id
    assert quote["total_amount"] == 160

    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=category.id,
            company_id=company.id,
            check_in_date=check_in,
            check_out_date=check_out,
            num_adults=2,
            quote_token=quote["quote_token"],
        ),
        hotel_id=1,
    )
    assert reservation.company_id == company.id
    assert reservation.total_amount == 160

    company.base_price = 70
    db.flush()
    with pytest.raises(ReservationError, match="venció"):
        create_reservation(
            db,
            ReservationCreate(
                guest_id=sample_guest.id,
                category_id=category.id,
                company_id=company.id,
                check_in_date=check_in,
                check_out_date=check_out,
                num_adults=2,
                quote_token=quote["quote_token"],
            ),
            hotel_id=1,
        )


def test_deferred_company_quote_hides_amounts_and_keeps_creation_token_opaque(
    db, sample_categories, sample_rooms, sample_guest, hotel_config
):
    company = Company(
        hotel_id=1,
        legal_name="Deferred Travel SRL",
        display_name="Deferred Travel",
        base_price=80,
        payment_deferred=True,
    )
    db.add(company)
    db.flush()
    category = sample_categories[0]
    check_in = date(2030, 3, 10)
    check_out = check_in + timedelta(days=2)

    quote = build_reservation_quote(
        db,
        hotel_id=1,
        category_id=category.id,
        check_in_date=check_in,
        check_out_date=check_out,
        occupancy=2,
        company_id=company.id,
    )

    assert quote["status"] == "ok"
    assert quote["category_id"] == category.id
    assert quote["check_in_date"] == check_in
    assert quote["check_out_date"] == check_out
    assert quote["nights"] == 2
    assert quote["company_billing_deferred"] is True
    assert quote["billing_mode"] == "external_company_invoice"
    assert quote["amounts_disclosed"] is False
    for amount_field in (
        "nightly_rate",
        "subtotal_amount",
        "tax_amount",
        "fee_amount",
        "commission_amount",
        "net_amount",
        "total_amount",
        "deposit_amount",
    ):
        assert quote[amount_field] is None
    assert quote["breakdown"] == []
    assert quote["promotions_applied"] == []

    # The token is confidential at rest on the client, while verification on
    # the server still recovers amounts needed to validate reservation create.
    assert quote["quote_token"].startswith("enc1.")
    token_payload = verify_quote_token(quote["quote_token"])
    assert token_payload["total_amount"] == 160
    assert token_payload["deposit_amount"] >= 0

    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=category.id,
            company_id=company.id,
            check_in_date=check_in,
            check_out_date=check_out,
            num_adults=2,
            quote_token=quote["quote_token"],
        ),
        hotel_id=1,
    )
    assert reservation.company_id == company.id
    assert reservation.total_amount == 0
    assert reservation.subtotal_amount == 0
    assert reservation.deposit_amount == 0
    assert reservation.tax_amount == 0
    assert reservation.fee_amount == 0
    assert reservation.commission_amount == 0
    assert reservation.net_amount == 0
    assert json.loads(reservation.pricing_snapshot or "{}") == {
        "company_invoice": {"amount_recorded_in_pms": False, "company_id": company.id}
    }
