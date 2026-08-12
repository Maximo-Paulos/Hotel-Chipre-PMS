#!/usr/bin/env python3
"""Generate the ignored, synthetic-only local cloud QA persona file."""

from __future__ import annotations

import argparse
import os
import re
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / ".env.qa.local"
DEFAULT_DOMAIN = "qa.hotels-pms.com"
DEFAULT_APP_URL = "https://app-preview.example.invalid"
DEFAULT_API_URL = "https://api-preview.example.invalid"
PERSONAS = (
    "owner",
    "co-owner",
    "manager",
    "reception",
    "housekeeping",
    "isolation-owner",
    "master-admin",
)
ALLOWED_KEYS = (
    "QA_APP_URL",
    "QA_API_URL",
    "QA_RUN_ID",
    "QA_EMAIL_DOMAIN",
    "QA_EMAIL_DOMAIN_IS_DEDICATED",
    "QA_OWNER_EMAIL",
    "QA_OWNER_PASSWORD",
    "QA_CO_OWNER_EMAIL",
    "QA_CO_OWNER_PASSWORD",
    "QA_MANAGER_EMAIL",
    "QA_MANAGER_PASSWORD",
    "QA_RECEPTION_EMAIL",
    "QA_RECEPTION_PASSWORD",
    "QA_HOUSEKEEPING_EMAIL",
    "QA_HOUSEKEEPING_PASSWORD",
    "QA_ISOLATION_OWNER_EMAIL",
    "QA_ISOLATION_OWNER_PASSWORD",
    "QA_MASTER_ADMIN_EMAIL",
    "QA_MASTER_ADMIN_PASSWORD",
    "QA_MASTER_ADMIN_PIN",
)
_DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{1,251}[a-z0-9])?\.[a-z]{2,63}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,63}$")


class QALocalEnvError(RuntimeError):
    """Raised when the local persona file cannot be created safely."""


def _validate_domain(value: str) -> str:
    domain = value.strip().lower()
    if not _DOMAIN_RE.fullmatch(domain):
        raise QALocalEnvError("QA email domain must be a valid dedicated domain")
    if domain == "hotels-pms.com" or not domain.endswith(".hotels-pms.com"):
        raise QALocalEnvError("QA email domain must be a dedicated hotels-pms.com subdomain")
    return domain


def _validate_https_url(value: str, *, name: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized.startswith("https://") or "\n" in normalized or "\r" in normalized:
        raise QALocalEnvError(f"{name} must be one HTTPS origin")
    return normalized


def _new_run_id(now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"qa-{timestamp}-{secrets.token_hex(3)}"


def _strong_password() -> str:
    # Prefix guarantees the bootstrap's upper/lower/digit requirements while the
    # random suffix supplies the entropy. The value is never logged.
    return "Qa9!" + secrets.token_urlsafe(30)


def build_values(
    *,
    app_url: str = DEFAULT_APP_URL,
    api_url: str = DEFAULT_API_URL,
    domain: str = DEFAULT_DOMAIN,
    run_id: str | None = None,
) -> dict[str, str]:
    qa_domain = _validate_domain(domain)
    qa_run_id = (run_id or _new_run_id()).strip()
    if not _RUN_ID_RE.fullmatch(qa_run_id):
        raise QALocalEnvError("QA run id must be a 6-64 character safe identifier")

    values: dict[str, str] = {
        "QA_APP_URL": _validate_https_url(app_url, name="QA app URL"),
        "QA_API_URL": _validate_https_url(api_url, name="QA API URL"),
        "QA_RUN_ID": qa_run_id,
        "QA_EMAIL_DOMAIN": qa_domain,
        "QA_EMAIL_DOMAIN_IS_DEDICATED": "true",
    }
    for persona in PERSONAS:
        prefix = persona.upper().replace("-", "_")
        local_part = persona.replace("-", "_")
        values[f"QA_{prefix}_EMAIL"] = f"{local_part}-{qa_run_id}@{qa_domain}"
        values[f"QA_{prefix}_PASSWORD"] = _strong_password()
    values["QA_MASTER_ADMIN_PIN"] = str(secrets.randbelow(900_000) + 100_000)

    if tuple(values) != ALLOWED_KEYS:
        raise QALocalEnvError("internal QA environment schema does not match .env.qa.example")
    if len({values[f"QA_{p.upper().replace('-', '_')}_PASSWORD"] for p in PERSONAS}) != len(PERSONAS):
        raise QALocalEnvError("generated QA passwords must be distinct")
    return values


def _render(values: Mapping[str, str]) -> bytes:
    if tuple(values) != ALLOWED_KEYS:
        raise QALocalEnvError("refusing to write unexpected QA environment keys")
    for key, value in values.items():
        if not value or "\n" in value or "\r" in value:
            raise QALocalEnvError(f"{key} contains an invalid value")
    return ("\n".join(f"{key}={values[key]}" for key in ALLOWED_KEYS) + "\n").encode()


def _assert_replaceable(path: Path, *, rotate: bool) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise QALocalEnvError("refusing to replace a symlink or non-regular QA environment file")
    if not rotate:
        raise QALocalEnvError("QA environment file already exists; use --rotate explicitly")


def write_env(path: Path, values: Mapping[str, str], *, rotate: bool = False) -> None:
    output = path.expanduser()
    if not output.is_absolute():
        output = Path.cwd() / output
    output.parent.mkdir(parents=True, exist_ok=True)
    _assert_replaceable(output, rotate=rotate)
    payload = _render(values)
    temporary = output.with_name(f".{output.name}.tmp-{secrets.token_hex(8)}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600, follow_symlinks=False)
        _assert_replaceable(output, rotate=rotate)
        os.replace(temporary, output)
        os.chmod(output, 0o600, follow_symlinks=False)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--app-url", default=DEFAULT_APP_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--domain", default=DEFAULT_DOMAIN)
    parser.add_argument("--run-id")
    parser.add_argument("--rotate", action="store_true")
    args = parser.parse_args()
    try:
        values = build_values(
            app_url=args.app_url,
            api_url=args.api_url,
            domain=args.domain,
            run_id=args.run_id,
        )
        write_env(args.output, values, rotate=args.rotate)
    except QALocalEnvError as exc:
        print(f"QA local environment was not created: {exc}", file=os.sys.stderr)
        return 2
    print(f"Created synthetic QA persona file at {args.output} (secrets redacted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
