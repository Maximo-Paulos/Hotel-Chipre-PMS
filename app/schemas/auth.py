import email_validator
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.config import is_test_mode


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=12)
    role: str | None = "owner"

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        # Same syntax validation EmailStr uses (email-validator, no DNS
        # deliverability check either way), except reserved test TLDs like
        # ".test" are allowed only in pytest/E2E so synthetic addresses used
        # by automated tests don't get rejected as "special-use" domains.
        try:
            validated = email_validator.validate_email(
                value,
                check_deliverability=False,
                test_environment=is_test_mode(),
            )
        except email_validator.EmailNotValidError as exc:
            raise ValueError(str(exc)) from exc
        return validated.normalized


class LoginRequest(BaseModel):
    email: str
    password: str


class MfaLoginRequest(BaseModel):
    mfa_token: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=64)


class MfaCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class MfaDisableRequest(MfaCodeRequest):
    password: str = Field(min_length=1)


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(min_length=1)


class RequestCode(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str = Field(min_length=12)


class UserInfo(BaseModel):
    id: int
    email: str
    role: str
    is_verified: bool
    is_active: bool
    permissions: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    hotel_id: int
    hotel_ids: list[int] | None = None
    user: UserInfo
    permissions: list[str] = Field(default_factory=list)
    requires_verification: bool = False
    # The CSRF half of the double-submit cookie pair, returned once so the
    # frontend can echo it as X-CSRF-Token. It cannot rely on reading the
    # cookie via document.cookie: the API and the SPA are on different sites
    # (Render vs Vercel), so the cookie is never visible to the page's JS
    # regardless of its Path/HttpOnly settings.
    csrf_token: str | None = None


class MfaChallengeResponse(BaseModel):
    requires_mfa: Literal[True] = True
    mfa_token: str
    expires_in: int


class MfaEnrollmentResponse(BaseModel):
    status: Literal["pending"] = "pending"
    secret: str
    otpauth_uri: str


class MfaRecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class ResetCodeValidationResponse(BaseModel):
    valid: bool


class UserSessionRead(BaseModel):
    id: int
    created_at: datetime
    last_seen_at: datetime
    device_label: str
    current: bool = False
