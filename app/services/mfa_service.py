"""Domain operations for opt-in TOTP MFA on normal user accounts."""
from __future__ import annotations

import hmac
import re
import secrets
from datetime import datetime, timezone

import pyotp
from cryptography.fernet import InvalidToken
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.user_mfa import UserMfaRecoveryCode, UserMfaSecret
from app.services.encryption import get_encryption_fernet
from app.services.security import hash_password, verify_password

MFA_PENDING = "pending"
MFA_ACTIVE = "active"
RECOVERY_CODE_COUNT = 10
TOTP_VALID_WINDOW = 1
_TOTP_CODE_RE = re.compile(r"^\d{6}$")


class MfaSecretUnavailableError(RuntimeError):
    """The stored MFA secret cannot be decrypted with the configured key."""


def get_user_mfa_secret(db: Session, user_id: int) -> UserMfaSecret | None:
    return db.query(UserMfaSecret).filter(UserMfaSecret.user_id == user_id).first()


def get_active_mfa_secret(db: Session, user_id: int) -> UserMfaSecret | None:
    return (
        db.query(UserMfaSecret)
        .filter(UserMfaSecret.user_id == user_id, UserMfaSecret.status == MFA_ACTIVE)
        .first()
    )


def encrypt_totp_secret(secret: str) -> str:
    return get_encryption_fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_totp_secret(encrypted_secret: str) -> str:
    try:
        return get_encryption_fernet().decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise MfaSecretUnavailableError("Stored MFA secret cannot be decrypted") from exc


def _totp_step_for_code(secret: str, code: str, now: datetime | None = None) -> int | None:
    normalized_code = (code or "").strip()
    if not _TOTP_CODE_RE.fullmatch(normalized_code):
        return None

    totp = pyotp.TOTP(secret)
    current_time = now or datetime.now(timezone.utc)
    current_step = int(current_time.timestamp()) // totp.interval
    for step in range(max(0, current_step - TOTP_VALID_WINDOW), current_step + TOTP_VALID_WINDOW + 1):
        expected = totp.at(step * totp.interval)
        if hmac.compare_digest(expected, normalized_code):
            return step
    return None


def _consume_totp_code(db: Session, mfa_secret: UserMfaSecret, code: str) -> bool:
    secret = decrypt_totp_secret(mfa_secret.encrypted_secret)
    step = _totp_step_for_code(secret, code)
    if step is None:
        return False

    replay_guard = UserMfaSecret.last_used_step.is_(None)
    if mfa_secret.last_used_step is not None:
        replay_guard = UserMfaSecret.last_used_step < step
    result = db.execute(
        update(UserMfaSecret)
        .where(UserMfaSecret.id == mfa_secret.id, replay_guard)
        .values(last_used_step=step)
    )
    if result.rowcount != 1:
        return False
    mfa_secret.last_used_step = step
    return True


def _normalize_recovery_code(code: str) -> str:
    return re.sub(r"[\s-]", "", (code or "")).upper()


def _consume_recovery_code(db: Session, user_id: int, code: str) -> bool:
    normalized_code = _normalize_recovery_code(code)
    if not normalized_code:
        return False

    candidates = (
        db.query(UserMfaRecoveryCode)
        .filter(UserMfaRecoveryCode.user_id == user_id, UserMfaRecoveryCode.used_at.is_(None))
        .all()
    )
    for candidate in candidates:
        if not verify_password(normalized_code, candidate.code_hash):
            continue
        consumed_at = datetime.now(timezone.utc)
        result = db.execute(
            update(UserMfaRecoveryCode)
            .where(UserMfaRecoveryCode.id == candidate.id, UserMfaRecoveryCode.used_at.is_(None))
            .values(used_at=consumed_at)
        )
        if result.rowcount == 1:
            candidate.used_at = consumed_at
            return True
    return False


def consume_mfa_code(db: Session, user_id: int, code: str) -> bool:
    """Consume one valid TOTP timestep or one unused recovery code."""
    mfa_secret = get_active_mfa_secret(db, user_id)
    if not mfa_secret:
        return False
    if _consume_totp_code(db, mfa_secret, code):
        return True
    return _consume_recovery_code(db, user_id, code)


def generate_recovery_codes() -> list[str]:
    return [secrets.token_hex(6).upper() for _ in range(RECOVERY_CODE_COUNT)]


def add_recovery_codes(db: Session, user_id: int, mfa_secret_id: int, codes: list[str]) -> None:
    db.add_all(
        [
            UserMfaRecoveryCode(
                user_id=user_id,
                mfa_secret_id=mfa_secret_id,
                code_hash=hash_password(code),
            )
            for code in codes
        ]
    )


def replace_recovery_codes(db: Session, user_id: int, mfa_secret: UserMfaSecret) -> list[str]:
    now = datetime.now(timezone.utc)
    db.query(UserMfaRecoveryCode).filter(
        UserMfaRecoveryCode.user_id == user_id,
        UserMfaRecoveryCode.used_at.is_(None),
    ).update({UserMfaRecoveryCode.used_at: now}, synchronize_session=False)
    codes = generate_recovery_codes()
    add_recovery_codes(db, user_id, mfa_secret.id, codes)
    return codes


def enroll_user(db: Session, user_id: int) -> tuple[UserMfaSecret, str]:
    existing = get_user_mfa_secret(db, user_id)
    if existing and existing.status == MFA_ACTIVE:
        raise ValueError("MFA ya esta activo")

    secret = pyotp.random_base32()
    if existing:
        existing.encrypted_secret = encrypt_totp_secret(secret)
        existing.status = MFA_PENDING
        existing.last_used_step = None
        existing.confirmed_at = None
        existing.created_at = datetime.now(timezone.utc)
        mfa_secret = existing
    else:
        mfa_secret = UserMfaSecret(
            user_id=user_id,
            encrypted_secret=encrypt_totp_secret(secret),
            status=MFA_PENDING,
        )
        db.add(mfa_secret)
    db.flush()
    return mfa_secret, secret


def confirm_enrollment(db: Session, user_id: int, code: str) -> list[str] | None:
    mfa_secret = get_user_mfa_secret(db, user_id)
    if not mfa_secret or mfa_secret.status != MFA_PENDING:
        return None

    secret = decrypt_totp_secret(mfa_secret.encrypted_secret)
    step = _totp_step_for_code(secret, code)
    if step is None:
        return None

    result = db.execute(
        update(UserMfaSecret)
        .where(UserMfaSecret.id == mfa_secret.id, UserMfaSecret.status == MFA_PENDING)
        .values(status=MFA_ACTIVE, confirmed_at=datetime.now(timezone.utc), last_used_step=step)
    )
    if result.rowcount != 1:
        return None
    mfa_secret.status = MFA_ACTIVE
    mfa_secret.confirmed_at = datetime.now(timezone.utc)
    mfa_secret.last_used_step = step
    return_codes = generate_recovery_codes()
    add_recovery_codes(db, user_id, mfa_secret.id, return_codes)
    return return_codes


def disable_user_mfa(db: Session, user_id: int) -> bool:
    mfa_secret = get_active_mfa_secret(db, user_id)
    if not mfa_secret:
        return False
    db.query(UserMfaRecoveryCode).filter(UserMfaRecoveryCode.user_id == user_id).delete(
        synchronize_session=False
    )
    db.delete(mfa_secret)
    db.flush()
    return True
