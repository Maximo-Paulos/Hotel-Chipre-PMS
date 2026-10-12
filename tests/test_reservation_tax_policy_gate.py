from datetime import date

import pytest

from app.models.commercial import TaxPolicy, TaxRule
from app.models.hotel_config import HotelConfiguration
from app.services.reservation_service import (
    ReservationError,
    calculate_reservation_pricing,
)


def test_daily_rate_quote_requires_an_active_hotel_tax_policy(db, sample_categories):
    db.query(TaxPolicy).filter(TaxPolicy.hotel_id == 1).delete(synchronize_session=False)
    db.flush()

    with pytest.raises(ReservationError, match="configurar y activar una política impositiva"):
        calculate_reservation_pricing(
            db,
            category_id=sample_categories[0].id,
            check_in=date(2026, 10, 10),
            check_out=date(2026, 10, 11),
            hotel_id=1,
        )


def test_quote_requires_explicit_hotel_deposit_policy_confirmation(db, sample_categories):
    config = db.get(HotelConfiguration, 1)
    assert config is not None
    config.deposit_policy_configured = False
    db.flush()

    with pytest.raises(ReservationError, match="configurar y confirmar sus reglas de depósito y cancelación"):
        calculate_reservation_pricing(
            db,
            category_id=sample_categories[0].id,
            check_in=date(2026, 10, 10),
            check_out=date(2026, 10, 11),
            hotel_id=1,
        )


def test_daily_rate_quote_applies_hotel_tax_policy_and_saves_policy_id(db, sample_categories):
    policy = db.query(TaxPolicy).filter(TaxPolicy.hotel_id == 1).one()
    policy.apply_vat_by_default = True
    policy.vat_rate = 21.0
    policy.taxes_included = False
    db.flush()

    quote = calculate_reservation_pricing(
        db,
        category_id=sample_categories[0].id,
        check_in=date(2026, 10, 10),
        check_out=date(2026, 10, 11),
        hotel_id=1,
    )

    assert quote.subtotal_amount == 100.0
    assert quote.tax_amount == 21.0
    assert quote.total_amount == 121.0
    assert quote.tax_policy_id == policy.id


def test_daily_rate_quote_splits_tax_from_inclusive_hotel_price(db, sample_categories):
    policy = db.query(TaxPolicy).filter(TaxPolicy.hotel_id == 1).one()
    policy.apply_vat_by_default = True
    policy.vat_rate = 21.0
    policy.taxes_included = True
    db.flush()

    quote = calculate_reservation_pricing(
        db,
        category_id=sample_categories[0].id,
        check_in=date(2026, 10, 10),
        check_out=date(2026, 10, 11),
        hotel_id=1,
    )

    assert quote.subtotal_amount == 82.64
    assert quote.tax_amount == 17.36
    assert quote.total_amount == 100.0


def test_inclusive_policy_extracts_percentage_tax_and_fixed_fee_from_gross_price(db, sample_categories):
    policy = db.query(TaxPolicy).filter(TaxPolicy.hotel_id == 1).one()
    policy.apply_vat_by_default = False
    policy.taxes_included = True
    policy.rules = [
        TaxRule(
            hotel_id=1,
            tax_policy_id=policy.id,
            tax_code="VAT10",
            tax_name="IVA",
            tax_type="percentage",
            amount=10.0,
            guest_scope="all",
            priority=1,
            is_active=True,
        ),
        TaxRule(
            hotel_id=1,
            tax_policy_id=policy.id,
            tax_code="FEE_NIGHT",
            tax_name="Cargo por noche",
            tax_type="fixed",
            amount=5.0,
            guest_scope="all",
            priority=2,
            applies_when_json='{"per_night": true}',
            is_active=True,
        ),
    ]
    db.flush()

    quote = calculate_reservation_pricing(
        db,
        category_id=sample_categories[0].id,
        check_in=date(2026, 10, 10),
        check_out=date(2026, 10, 11),
        hotel_id=1,
    )

    assert quote.subtotal_amount == 86.36
    assert quote.tax_amount == 8.64
    assert quote.fee_amount == 5.0
    assert quote.total_amount == 100.0


def test_fixed_tax_rule_rejects_currency_that_differs_from_hotel_price(db, sample_categories):
    policy = db.query(TaxPolicy).filter(TaxPolicy.hotel_id == 1).one()
    policy.apply_vat_by_default = False
    policy.rules = [
        TaxRule(
            hotel_id=1,
            tax_policy_id=policy.id,
            tax_code="FEE_USD",
            tax_name="Cargo en moneda distinta",
            tax_type="fixed",
            amount=5.0,
            currency_code="USD",
            guest_scope="all",
            is_active=True,
        )
    ]
    db.flush()

    with pytest.raises(ReservationError, match="debe coincidir con la moneda de la tarifa"):
        calculate_reservation_pricing(
            db,
            category_id=sample_categories[0].id,
            check_in=date(2026, 10, 10),
            check_out=date(2026, 10, 11),
            hotel_id=1,
        )
