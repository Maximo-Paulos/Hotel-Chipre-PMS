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


class TemporaryActionGrantConsumeRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
