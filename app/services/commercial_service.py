"""
Commercial configuration service.

This service owns the hotel-scoped CRUD rules for sellable products, rate
plans and key commercial policies.
"""
from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.models.commercial import (
    FxPolicy,
    ProductRoomCompatibility,
    RatePlan,
    RatePlanPrice,
    SellableProduct,
    TaxPolicy,
    TaxRule,
)


class CommercialConfigError(ValueError):
    """Raised when hotel-scoped commercial configuration is invalid."""


def list_sellable_products(db: Session, *, hotel_id: int) -> list[SellableProduct]:
    return (
        db.query(SellableProduct)
        .options(selectinload(SellableProduct.compatibilities))
        .filter(SellableProduct.hotel_id == hotel_id)
        .order_by(SellableProduct.sort_order.asc(), SellableProduct.id.asc())
        .all()
    )


def create_sellable_product(db: Session, *, hotel_id: int, payload) -> SellableProduct:
    _validate_room_category_id(db, hotel_id, payload.primary_room_category_id)
    product = SellableProduct(hotel_id=hotel_id, **payload.model_dump(exclude={"compatibilities"}))
    db.add(product)
    db.flush()
    _replace_product_compatibilities(db, hotel_id=hotel_id, product=product, compatibilities=payload.compatibilities)
    db.flush()
    return _get_sellable_product(db, hotel_id=hotel_id, product_id=product.id)


def update_sellable_product(db: Session, *, hotel_id: int, product_id: int, payload) -> SellableProduct:
    product = _get_sellable_product(db, hotel_id=hotel_id, product_id=product_id)
    data = payload.model_dump(exclude_unset=True, exclude={"compatibilities"})
    if "primary_room_category_id" in data:
        _validate_room_category_id(db, hotel_id, data["primary_room_category_id"])
    for field, value in data.items():
        setattr(product, field, value)
    if payload.compatibilities is not None:
        _replace_product_compatibilities(db, hotel_id=hotel_id, product=product, compatibilities=payload.compatibilities)
    db.flush()
    return _get_sellable_product(db, hotel_id=hotel_id, product_id=product.id)


def list_rate_plans(db: Session, *, hotel_id: int) -> list[RatePlan]:
    return (
        db.query(RatePlan)
        .options(selectinload(RatePlan.prices))
        .filter(RatePlan.hotel_id == hotel_id)
        .order_by(RatePlan.id.asc())
        .all()
    )


def create_rate_plan(db: Session, *, hotel_id: int, payload) -> RatePlan:
    _validate_sellable_product_id(db, hotel_id, payload.sellable_product_id)
    rate_plan = RatePlan(hotel_id=hotel_id, **payload.model_dump(exclude={"prices"}))
    db.add(rate_plan)
    db.flush()
    _replace_rate_plan_prices(db, hotel_id=hotel_id, rate_plan=rate_plan, prices=payload.prices)
    db.flush()
    return _get_rate_plan(db, hotel_id=hotel_id, rate_plan_id=rate_plan.id)


def update_rate_plan(db: Session, *, hotel_id: int, rate_plan_id: int, payload) -> RatePlan:
    rate_plan = _get_rate_plan(db, hotel_id=hotel_id, rate_plan_id=rate_plan_id)
    data = payload.model_dump(exclude_unset=True, exclude={"prices"})
    if "sellable_product_id" in data:
        _validate_sellable_product_id(db, hotel_id, data["sellable_product_id"])
    for field, value in data.items():
        setattr(rate_plan, field, value)
    if payload.prices is not None:
        _replace_rate_plan_prices(db, hotel_id=hotel_id, rate_plan=rate_plan, prices=payload.prices)
    db.flush()
    return _get_rate_plan(db, hotel_id=hotel_id, rate_plan_id=rate_plan.id)


def list_tax_policies(db: Session, *, hotel_id: int) -> list[TaxPolicy]:
    return (
        db.query(TaxPolicy)
        .options(selectinload(TaxPolicy.rules))
        .filter(TaxPolicy.hotel_id == hotel_id)
        .order_by(TaxPolicy.id.asc())
        .all()
    )


def create_tax_policy(db: Session, *, hotel_id: int, payload) -> TaxPolicy:
    policy = TaxPolicy(hotel_id=hotel_id, **payload.model_dump(exclude={"rules"}))
    db.add(policy)
    db.flush()
    _replace_tax_rules(db, hotel_id=hotel_id, policy=policy, rules=payload.rules)
    db.flush()
    return _get_tax_policy(db, hotel_id=hotel_id, policy_id=policy.id)


def update_tax_policy(db: Session, *, hotel_id: int, policy_id: int, payload) -> TaxPolicy:
    policy = _get_tax_policy(db, hotel_id=hotel_id, policy_id=policy_id)
    data = payload.model_dump(exclude_unset=True, exclude={"rules"})
    for field, value in data.items():
        setattr(policy, field, value)
    if payload.rules is not None:
        _replace_tax_rules(db, hotel_id=hotel_id, policy=policy, rules=payload.rules)
    db.flush()
    return _get_tax_policy(db, hotel_id=hotel_id, policy_id=policy.id)


def list_fx_policies(db: Session, *, hotel_id: int) -> list[FxPolicy]:
    return db.query(FxPolicy).filter(FxPolicy.hotel_id == hotel_id).order_by(FxPolicy.id.asc()).all()


def create_fx_policy(db: Session, *, hotel_id: int, payload) -> FxPolicy:
    policy = FxPolicy(hotel_id=hotel_id, **payload.model_dump())
    db.add(policy)
    db.flush()
    return _get_fx_policy(db, hotel_id=hotel_id, policy_id=policy.id)


def update_fx_policy(db: Session, *, hotel_id: int, policy_id: int, payload) -> FxPolicy:
    policy = _get_fx_policy(db, hotel_id=hotel_id, policy_id=policy_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(policy, field, value)
    db.flush()
    return _get_fx_policy(db, hotel_id=hotel_id, policy_id=policy.id)


def _replace_product_compatibilities(db: Session, *, hotel_id: int, product: SellableProduct, compatibilities) -> None:
    product.compatibilities.clear()
    db.flush()
    for compatibility in compatibilities:
        _validate_room_category_id(db, hotel_id, compatibility.room_category_id)
        product.compatibilities.append(
            ProductRoomCompatibility(
                hotel_id=hotel_id,
                **compatibility.model_dump(),
            )
        )


def _replace_rate_plan_prices(db: Session, *, hotel_id: int, rate_plan: RatePlan, prices) -> None:
    rate_plan.prices.clear()
    db.flush()
    for price in prices:
        rate_plan.prices.append(
            RatePlanPrice(
                hotel_id=hotel_id,
                **price.model_dump(),
            )
        )


def _replace_tax_rules(db: Session, *, hotel_id: int, policy: TaxPolicy, rules) -> None:
    policy.rules.clear()
    db.flush()
    for rule in rules:
        policy.rules.append(
            TaxRule(
                hotel_id=hotel_id,
                **rule.model_dump(),
            )
        )


def _validate_room_category_id(db: Session, hotel_id: int, room_category_id: int | None) -> None:
    if room_category_id is None:
        return
    from app.models.room import RoomCategory

    exists = (
        db.query(RoomCategory.id)
        .filter(RoomCategory.id == room_category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if not exists:
        raise CommercialConfigError("La categoria de habitacion no existe en este hotel")


def _validate_sellable_product_id(db: Session, hotel_id: int, sellable_product_id: int) -> None:
    exists = (
        db.query(SellableProduct.id)
        .filter(SellableProduct.id == sellable_product_id, SellableProduct.hotel_id == hotel_id)
        .first()
    )
    if not exists:
        raise CommercialConfigError("El producto vendible no existe en este hotel")


def _get_sellable_product(db: Session, *, hotel_id: int, product_id: int) -> SellableProduct:
    product = (
        db.query(SellableProduct)
        .options(selectinload(SellableProduct.compatibilities))
        .filter(SellableProduct.id == product_id, SellableProduct.hotel_id == hotel_id)
        .first()
    )
    if not product:
        raise CommercialConfigError("Producto vendible no encontrado")
    return product


def _get_rate_plan(db: Session, *, hotel_id: int, rate_plan_id: int) -> RatePlan:
    rate_plan = (
        db.query(RatePlan)
        .options(selectinload(RatePlan.prices))
        .filter(RatePlan.id == rate_plan_id, RatePlan.hotel_id == hotel_id)
        .first()
    )
    if not rate_plan:
        raise CommercialConfigError("Tarifa no encontrada")
    return rate_plan


def _get_tax_policy(db: Session, *, hotel_id: int, policy_id: int) -> TaxPolicy:
    policy = (
        db.query(TaxPolicy)
        .options(selectinload(TaxPolicy.rules))
        .filter(TaxPolicy.id == policy_id, TaxPolicy.hotel_id == hotel_id)
        .first()
    )
    if not policy:
        raise CommercialConfigError("Politica impositiva no encontrada")
    return policy


def _get_fx_policy(db: Session, *, hotel_id: int, policy_id: int) -> FxPolicy:
    policy = db.query(FxPolicy).filter(FxPolicy.id == policy_id, FxPolicy.hotel_id == hotel_id).first()
    if not policy:
        raise CommercialConfigError("Politica cambiaria no encontrada")
    return policy
