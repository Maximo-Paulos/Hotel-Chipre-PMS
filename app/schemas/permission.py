from pydantic import BaseModel, Field


class RolePermissionOverrideRequest(BaseModel):
    role: str = Field(min_length=1, max_length=50)
    permission_code: str = Field(min_length=1, max_length=100)
    allowed: bool
    expected_version: int | None = Field(default=None, ge=0)


class UserPermissionOverrideRequest(BaseModel):
    permission_code: str = Field(min_length=1, max_length=100)
    allowed: bool
    expected_version: int | None = Field(default=None, ge=0)


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
