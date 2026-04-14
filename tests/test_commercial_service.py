from __future__ import annotations

from app.models.commercial import SellableProduct
from app.schemas.commercial import (
    FxPolicyCreate,
    RatePlanCreate,
    RatePlanPriceWrite,
    SellableProductCreate,
    SellableProductUpdate,
    TaxPolicyCreate,
    TaxRuleWrite,
)
from app.services.commercial_service import (
    CommercialConfigError,
    create_fx_policy,
    create_rate_plan,
    create_sellable_product,
    create_tax_policy,
    list_sellable_products,
    update_sellable_product,
)


def test_create_sellable_product_persists_compatibilities(db, sample_categories, hotel_config):
    payload = SellableProductCreate(
        primary_room_category_id=sample_categories[0].id,
        code="DBL_SHARED",
        name="Doble compartida",
        min_occupancy=1,
        max_occupancy=2,
        compatibilities=[
            {
                "room_category_id": sample_categories[0].id,
                "compatibility_kind": "exact",
                "priority": 1,
                "allows_auto_assignment": True,
            },
            {
                "room_category_id": sample_categories[1].id,
                "compatibility_kind": "upgrade",
                "priority": 10,
                "allows_auto_assignment": True,
            },
        ],
    )

    product = create_sellable_product(db, hotel_id=hotel_config.id, payload=payload)
    db.commit()

    assert product.code == "DBL_SHARED"
    assert len(product.compatibilities) == 2
    assert [item.room_category_id for item in product.compatibilities] == [sample_categories[0].id, sample_categories[1].id]


def test_update_sellable_product_replaces_compatibilities(db, sample_categories, hotel_config):
    product = create_sellable_product(
        db,
        hotel_id=hotel_config.id,
        payload=SellableProductCreate(
            primary_room_category_id=sample_categories[0].id,
            code="DBL_PRIVATE",
            name="Doble privada",
            min_occupancy=1,
            max_occupancy=2,
            compatibilities=[
                {
                    "room_category_id": sample_categories[0].id,
                    "compatibility_kind": "exact",
                    "priority": 1,
                    "allows_auto_assignment": True,
                }
            ],
        ),
    )
    db.flush()

    updated = update_sellable_product(
        db,
        hotel_id=hotel_config.id,
        product_id=product.id,
        payload=SellableProductUpdate(
            name="Doble privada premium",
            compatibilities=[
                {
                    "room_category_id": sample_categories[1].id,
                    "compatibility_kind": "exact",
                    "priority": 1,
                    "allows_auto_assignment": True,
                }
            ],
        ),
    )
    db.commit()

    assert updated.name == "Doble privada premium"
    assert len(updated.compatibilities) == 1
    assert updated.compatibilities[0].room_category_id == sample_categories[1].id


def test_create_rate_plan_tax_policy_and_fx_policy(db, sample_categories, hotel_config):
    product = create_sellable_product(
        db,
        hotel_id=hotel_config.id,
        payload=SellableProductCreate(
            primary_room_category_id=sample_categories[0].id,
            code="TRPL_SHARED",
            name="Triple compartida",
            min_occupancy=1,
            max_occupancy=3,
            compatibilities=[],
        ),
    )
    db.flush()

    rate_plan = create_rate_plan(
        db,
        hotel_id=hotel_config.id,
        payload=RatePlanCreate(
            sellable_product_id=product.id,
            code="FLEX",
            name="Flexible",
            prices=[
                RatePlanPriceWrite(
                    sales_channel_code="booking",
                    occupancy=2,
                    currency_code="ARS",
                    base_amount=150.0,
                    tax_inclusive=False,
                )
            ],
        ),
    )
    tax_policy = create_tax_policy(
        db,
        hotel_id=hotel_config.id,
        payload=TaxPolicyCreate(
            code="ARG",
            name="Argentina",
            taxes_included=False,
            apply_vat_by_default=False,
            rules=[
                TaxRuleWrite(
                    channel_code="booking",
                    guest_scope="local",
                    tax_code="VAT",
                    tax_name="IVA",
                    tax_type="percentage",
                    amount=21.0,
                )
            ],
        ),
    )
    fx_policy = create_fx_policy(
        db,
        hotel_id=hotel_config.id,
        payload=FxPolicyCreate(
            code="OFFICIAL",
            name="Official",
            base_currency="ARS",
            preferred_source="official",
            preferred_side="sell",
            spread_pct=3.0,
        ),
    )
    db.commit()

    assert rate_plan.prices[0].base_amount == 150.0
    assert tax_policy.rules[0].tax_code == "VAT"
    assert fx_policy.preferred_side == "sell"


def test_commercial_service_rejects_foreign_room_category(db, sample_categories_hotel2, hotel_config):
    payload = SellableProductCreate(
        primary_room_category_id=sample_categories_hotel2[0].id,
        code="BAD",
        name="Bad product",
        min_occupancy=1,
        max_occupancy=2,
        compatibilities=[],
    )

    try:
        create_sellable_product(db, hotel_id=hotel_config.id, payload=payload)
    except CommercialConfigError as exc:
        assert "categoria" in str(exc).lower()
    else:
        raise AssertionError("Expected CommercialConfigError for foreign room category")


def test_list_sellable_products_is_hotel_scoped(db, sample_categories, sample_categories_hotel2, hotel_config):
    create_sellable_product(
        db,
        hotel_id=hotel_config.id,
        payload=SellableProductCreate(
            primary_room_category_id=sample_categories[0].id,
            code="H1-PROD",
            name="Hotel 1 product",
            min_occupancy=1,
            max_occupancy=2,
            compatibilities=[],
        ),
    )
    db.add(SellableProduct(
        hotel_id=2,
        primary_room_category_id=sample_categories_hotel2[0].id,
        code="H2-PROD",
        name="Hotel 2 product",
        min_occupancy=1,
        max_occupancy=2,
    ))
    db.commit()

    products = list_sellable_products(db, hotel_id=hotel_config.id)
    assert [product.code for product in products] == ["H1-PROD"]
