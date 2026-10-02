"""Request and read contracts for one group collection with child allocations."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.transaction import PaymentMethodEnum


class ReservationGroupPaymentAllocationRequest(BaseModel):
    reservation_id: int = Field(gt=0)
    received_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    company_night_charge_ids: list[int] = Field(default_factory=list, max_length=90)

    @model_validator(mode="after")
    def validate_company_charge_ids(self):
        if any(item <= 0 for item in self.company_night_charge_ids):
            raise ValueError("Los cargos nocturnos deben tener identificadores positivos.")
        if len(set(self.company_night_charge_ids)) != len(self.company_night_charge_ids):
            raise ValueError("No se puede repetir un cargo nocturno en la misma asignación.")
        return self


class ReservationGroupPaymentCreate(BaseModel):
    received_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    payment_method: PaymentMethodEnum
    manual_reference: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    allocations: list[ReservationGroupPaymentAllocationRequest] = Field(min_length=1, max_length=10)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @field_validator("manual_reference", "description")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_allocations_sum(self):
        reservation_ids = [item.reservation_id for item in self.allocations]
        if len(reservation_ids) != len(set(reservation_ids)):
            raise ValueError("Cada reserva puede recibir una sola asignación por cobro grupal.")
        assigned = sum((item.received_amount for item in self.allocations), Decimal("0.00"))
        if assigned != self.received_amount:
            raise ValueError("La suma de las asignaciones debe coincidir con el importe recibido.")
        if self.payment_method in {PaymentMethodEnum.MERCADO_PAGO, PaymentMethodEnum.PAYPAL}:
            raise ValueError("Los medios de pago con pasarela no están habilitados para cobros grupales.")
        return self


class ReservationGroupPaymentAllocationRead(BaseModel):
    reservation_id: int
    transaction_id: int
    received_amount: Decimal


class ReservationGroupPaymentRead(BaseModel):
    id: int
    group_id: int
    received_amount: Decimal
    currency: str
    payment_method: PaymentMethodEnum
    manual_reference: str | None = None
    description: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    allocations: list[ReservationGroupPaymentAllocationRead]
