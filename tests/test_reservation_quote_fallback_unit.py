"""Pure unit coverage for reservation quote fallback metadata."""

from datetime import date
from types import SimpleNamespace

from app.services import reservation_quote_service


def test_company_base_price_is_exposed_as_fallback_breakdown_source(monkeypatch):
    check_in = date(2030, 2, 10)
    check_out = date(2030, 2, 12)
    daily_pricing = SimpleNamespace(
        nights=2,
        nightly_rate=120.0,
        total_amount=240.0,
        deposit_amount=0.0,
        subtotal_amount=240.0,
        tax_amount=0.0,
        fee_amount=0.0,
        commission_amount=0.0,
        net_amount=240.0,
        currency_code="ARS",
        pricing_source="daily_rates",
        pricing_snapshot=None,
        tax_policy_id=None,
    )
    company_pricing = SimpleNamespace(
        **{
            **vars(daily_pricing),
            "nightly_rate": 80.0,
            "total_amount": 160.0,
            "subtotal_amount": 160.0,
            "net_amount": 160.0,
            "pricing_source": "company_base_price",
        }
    )
    company = SimpleNamespace(payment_deferred=False)

    monkeypatch.setattr(
        reservation_quote_service,
        "calculate_reservation_pricing",
        lambda *args, **kwargs: daily_pricing,
    )
    monkeypatch.setattr(
        reservation_quote_service,
        "_resolve_reservation_company",
        lambda *args, **kwargs: company,
    )
    monkeypatch.setattr(
        reservation_quote_service,
        "_apply_corporate_pricing",
        lambda *args, **kwargs: company_pricing,
    )
    monkeypatch.setattr(
        reservation_quote_service,
        "build_pricing_revision",
        lambda *args, **kwargs: "revision",
    )
    monkeypatch.setattr(
        reservation_quote_service,
        "issue_quote_token",
        lambda *args, **kwargs: "token",
    )

    quote = reservation_quote_service.build_reservation_quote(
        object(),
        hotel_id=1,
        category_id=2,
        check_in_date=check_in,
        check_out_date=check_out,
        company_id=3,
    )

    assert quote["breakdown"] == [
        {"date": "2030-02-10", "price": 80.0, "source": "company_base_price"},
        {"date": "2030-02-11", "price": 80.0, "source": "company_base_price"},
    ]
    assert quote["nightly_rate"] == 80.0
    assert quote["total_amount"] == 160.0
