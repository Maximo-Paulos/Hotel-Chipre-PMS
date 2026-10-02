from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


VisibilityWindowHours = Literal[12, 24, 48, 72, 168]


class VisibilityWindowUpdate(BaseModel):
    """Set both sides of one role's reservation visibility window."""

    role: str = Field(min_length=1, max_length=20)
    past_hours: VisibilityWindowHours | None
    future_hours: VisibilityWindowHours | None


class VisibilityWindowRead(BaseModel):
    role: str
    past_hours: VisibilityWindowHours | None
    future_hours: VisibilityWindowHours | None
    updated_by_user_id: int | None = None
    updated_at: datetime | None = None


class RolePermissionOverrideRequest(BaseModel):
    role: str = Field(min_length=1, max_length=50)
    permission_code: str = Field(min_length=1, max_length=100)
    allowed: bool
    expected_version: int | None = Field(default=None, ge=0)


class UserPermissionOverrideRequest(BaseModel):
    permission_code: str = Field(min_length=1, max_length=100)
    allowed: bool
    expected_version: int | None = Field(default=None, ge=0)


class PermissionOverrideBatchChange(BaseModel):
    scope: Literal["role", "user"]
    operation: Literal["set", "restore"]
    permission_code: str = Field(min_length=1, max_length=100)
    role: str | None = Field(default=None, min_length=1, max_length=50)
    user_id: int | None = Field(default=None, gt=0)
    allowed: bool | None = None
    expected_version: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_target_and_operation(self):
        if self.scope == "role" and (self.role is None or self.user_id is not None):
            raise ValueError("Un cambio de rol requiere únicamente el rol")
        if self.scope == "user" and (self.user_id is None or self.role is not None):
            raise ValueError("Un cambio de usuario requiere únicamente el usuario")
        if self.operation == "set" and self.allowed is None:
            raise ValueError("Un cambio de permiso requiere el nuevo valor")
        if self.operation == "restore" and (self.allowed is not None or self.expected_version < 1):
            raise ValueError("Restaurar requiere la versión actual del override")
        return self

    model_config = {"extra": "forbid"}


class PermissionOverrideBatchRequest(BaseModel):
    changes: list[PermissionOverrideBatchChange] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def reject_duplicate_cells(self):
        keys = [
            (change.scope, change.role if change.scope == "role" else change.user_id, change.permission_code)
            for change in self.changes
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("El lote contiene permisos repetidos")
        return self

    model_config = {"extra": "forbid"}


class PermissionDecision(BaseModel):
    allowed: bool
    source: str
    locked: bool = False
    lock_reason: str | None = None


class PermissionCatalogItem(BaseModel):
    code: str
    module: str
    description: str
    legacy_aliases: list[str] = Field(default_factory=list)
    locked: bool = False
    lock_reason: str | None = None
    critical: bool = False
    step_up_required: bool = False
    delegable: bool = True


class TemporaryActionGrantRequest(BaseModel):
    permission_code: str = Field(min_length=1, max_length=100)
    resource_type: str | None = Field(default=None, max_length=100)
    resource_id: str | int | None = None
    reason: str = Field(min_length=1, max_length=2000)


class TemporaryActionGrantApproveRequest(BaseModel):
    # Required because this implementation only permits approval by accounts
    # with active MFA. The shared MFA helper also accepts one unused recovery
    # code, preserving the account-level recovery contract.
    totp_code: str = Field(min_length=1, max_length=128)
