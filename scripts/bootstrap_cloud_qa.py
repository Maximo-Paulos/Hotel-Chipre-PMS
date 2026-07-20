"""Create the isolated synthetic identities used by cloud QA.

This script is intentionally fail-closed.  It only runs when the target is
explicitly identified as an isolated QA database and its non-secret connection
identity is different from the production database identity.

Secrets are read from environment variables and are never printed.  See
``scripts/README.qa-bootstrap.md`` for the required variables.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy.engine import make_url


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.agent_ops.qa_bootstrap_contract import (  # noqa: E402
    BOOTSTRAP_CONFIGURATION_VERSION,
    BootstrapConfigurationError,
    bootstrap_configuration_fingerprint,
)


class QABootstrapError(RuntimeError):
    """A safe, non-sensitive bootstrap refusal."""


@dataclass(frozen=True)
class Persona:
    name: str
    email: str = field(repr=False)
    password: str = field(repr=False)
    role: str


@dataclass(frozen=True)
class QABootstrapConfig:
    app_env: str
    database_url: str = field(repr=False)
    run_id: str
    hotel_name: str
    personas: tuple[Persona, ...] = field(repr=False)
    master_admin_email: str = field(repr=False)
    master_admin_password: str = field(repr=False)
    master_admin_pin: str = field(repr=False)
    database_role: str | None
    connection_fingerprint: str | None
    run_migrations: bool


@dataclass(frozen=True)
class QABootstrapResult:
    hotel_id: int
    users_created: int
    memberships_created: int


@dataclass(frozen=True)
class ProviderEvidence:
    manifest_schema_version: int
    code_sha: str
    service_id: str
    environment_id: str
    frontend_deployment_id: str
    project_ref: str
    branch_type: str
    branch_ref: str
    database_role: str
    connection_fingerprint: str
    production_connection_fingerprint: str
    isolation_mode: str
    baseline_lease_id: str | None
    baseline_lease_target_sha: str | None
    baseline_lease_target_branch: str | None


_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,63}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+$")
_SHA_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_DATABASE_ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_KNOWN_PRODUCTION_PROJECT_REF = "ezkljznogqpmrjxyvklr"
_EVIDENCE_TOKEN_VERSION = "provider-evidence-ed25519-v2"
_MAX_EVIDENCE_TTL_SECONDS = 3600
_BASELINE_LEASE_ENV_KEYS = {
    "QA_BASELINE_ONLY",
    "QA_BASELINE_LEASE_ID",
    "QA_BASELINE_LEASE_TARGET_SHA",
    "QA_BASELINE_LEASE_TARGET_BRANCH",
}
_HOTEL_PERSONAS = (
    ("owner", "QA_OWNER", "owner"),
    ("manager", "QA_MANAGER", "manager"),
    ("reception", "QA_RECEPTION", "receptionist"),
    ("housekeeping", "QA_HOUSEKEEPING", "housekeeping"),
)


def _required(env: Mapping[str, str], name: str) -> str:
    value = (env.get(name) or "").strip()
    if not value:
        raise QABootstrapError(f"{name} is required")
    return value


def _flag(env: Mapping[str, str], name: str, *, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _required_port(env: Mapping[str, str], name: str) -> int:
    raw = _required(env, name)
    try:
        port = int(raw)
    except ValueError as exc:
        raise QABootstrapError(f"{name} must be a valid TCP port") from exc
    if not 1 <= port <= 65535:
        raise QABootstrapError(f"{name} must be a valid TCP port")
    return port


def _validate_email(email: str, *, name: str, domain: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise QABootstrapError(f"{name} must be a valid synthetic QA email")
    if normalized.rsplit("@", 1)[1] != domain:
        raise QABootstrapError(f"{name} must use QA_EMAIL_DOMAIN")
    return normalized


def _validate_password(password: str, *, name: str) -> str:
    if len(password) < 12:
        raise QABootstrapError(f"{name} must contain at least 12 characters")
    if not any(char.islower() for char in password):
        raise QABootstrapError(f"{name} must contain a lowercase character")
    if not any(char.isupper() for char in password):
        raise QABootstrapError(f"{name} must contain an uppercase character")
    if not any(char.isdigit() for char in password):
        raise QABootstrapError(f"{name} must contain a digit")
    return password


def _postgres_identity(database_url: str) -> tuple[str, int, str, str]:
    try:
        url = make_url(database_url)
        port = int(url.port or 5432)
    except Exception as exc:
        raise QABootstrapError("DATABASE_URL is not a valid PostgreSQL URL") from exc
    if not url.drivername.lower().startswith("postgresql"):
        raise QABootstrapError("cloud QA bootstrap requires PostgreSQL")
    identity = (
        (url.host or "").lower(),
        port,
        str(url.database or ""),
        str(url.username or ""),
    )
    if not all((identity[0], identity[2], identity[3])):
        raise QABootstrapError("PostgreSQL target identity is incomplete")
    return identity


def _canonical_database_host(hostname: str) -> str:
    host = hostname.rstrip(".").lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise QABootstrapError("DATABASE_URL contains an invalid hostname") from exc


def database_connection_fingerprint(
    database_url: str,
    *,
    project_ref: str,
) -> str:
    """Reproduce the provider's ``supabase-connection-v1`` SHA-256."""

    host, port, database, username = _postgres_identity(database_url)
    if database != "postgres":
        raise QABootstrapError("cloud QA DATABASE_URL must use database postgres")
    normalized_ref = project_ref.strip().lower()
    if not normalized_ref:
        raise QABootstrapError("provider project_ref is required for fingerprinting")
    payload = "\x1f".join(
        (
            normalized_ref,
            _canonical_database_host(host),
            str(port),
            username,
        )
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}"


def _target_identity_text(identity: tuple[str, int, str, str]) -> str:
    return "|".join((identity[0], str(identity[1]), identity[2], identity[3])).lower()


def _validate_non_production_target(
    identity: tuple[str, int, str, str], *, project_ref: str | None = None
) -> None:
    identity_text = _target_identity_text(identity)
    if _KNOWN_PRODUCTION_PROJECT_REF in identity_text or (
        project_ref is not None and project_ref.lower() == _KNOWN_PRODUCTION_PROJECT_REF
    ):
        raise QABootstrapError("known production project ref is forbidden in the QA target")


def _validate_qa_database_role(
    role: str,
    *,
    provider_verified_supabase: bool,
    database_user_distinct: bool,
) -> None:
    normalized = role.strip().lower()
    if not _DATABASE_ROLE_PATTERN.fullmatch(normalized):
        raise QABootstrapError("QA database role has an invalid format")
    qa_named = any(marker in normalized for marker in ("qa", "preview", "test", "e2e"))
    if provider_verified_supabase and normalized == "postgres":
        return
    if not qa_named:
        raise QABootstrapError("non-Supabase QA databases require a dedicated QA role")
    if provider_verified_supabase and not database_user_distinct:
        raise QABootstrapError("custom Supabase QA role must be distinct from production")


def _decode_baseline_lease_entropy(value: str) -> bytes:
    try:
        parsed_uuid = uuid.UUID(value)
    except (ValueError, AttributeError):
        parsed_uuid = None
    if parsed_uuid is not None:
        if parsed_uuid.version != 4 or parsed_uuid.variant != uuid.RFC_4122:
            raise QABootstrapError("baseline lease ID UUID must be random UUIDv4")
        return parsed_uuid.bytes
    if re.fullmatch(r"[0-9a-fA-F]{32,128}", value) and len(value) % 2 == 0:
        return bytes.fromhex(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]{22,128}", value):
        raise QABootstrapError(
            "baseline lease ID must be UUIDv4 or 128+ bits of hex/base64url entropy"
        )
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError):
        raise QABootstrapError("baseline lease ID is not valid base64url") from None


def _validate_baseline_lease_id(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise QABootstrapError("baseline lease ID is required for dedicated QA baseline mode")
    entropy = _decode_baseline_lease_entropy(value)
    if len(entropy) < 16 or len(set(entropy)) < 8:
        raise QABootstrapError("baseline lease ID is too weak or predictable")
    return value


def _validate_isolation_contract(
    evidence: Mapping[str, Any],
    *,
    branch_type: str,
    code_sha: str,
    git_branch: str,
) -> tuple[str, str | None, str | None, str | None]:
    isolation_mode = str(evidence.get("isolation_mode") or "")
    lease_fields = (
        "baseline_lease_id",
        "baseline_lease_target_sha",
        "baseline_lease_target_branch",
    )
    if branch_type == "preview":
        if isolation_mode != "supabase-branch-per-target" or any(
            field in evidence for field in lease_fields
        ):
            raise QABootstrapError(
                "provider evidence per-branch isolation contract is invalid"
            )
        return isolation_mode, None, None, None
    if branch_type != "dedicated-qa-project" or isolation_mode != "dedicated-qa-baseline-exclusive":
        raise QABootstrapError("provider evidence dedicated baseline contract is invalid")
    lease_id = _validate_baseline_lease_id(evidence.get("baseline_lease_id"))
    lease_target_sha = str(evidence.get("baseline_lease_target_sha") or "")
    lease_target_branch = str(evidence.get("baseline_lease_target_branch") or "")
    if (
        not hmac.compare_digest(lease_target_sha, code_sha)
        or not hmac.compare_digest(lease_target_branch, git_branch)
    ):
        raise QABootstrapError("provider evidence dedicated baseline lease targets another task")
    return isolation_mode, lease_id, lease_target_sha, lease_target_branch


def canonical_provider_evidence_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encode_provider_evidence_segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise QABootstrapError("provider evidence token has invalid encoding")
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise QABootstrapError("provider evidence token has invalid encoding") from exc
    if encode_provider_evidence_segment(decoded) != value:
        raise QABootstrapError("provider evidence token has non-canonical encoding")
    return decoded


def load_provider_evidence_public_key(value: str) -> Ed25519PublicKey:
    """Load the sole Ed25519 trust anchor from PEM or base64 raw bytes."""

    normalized = value.replace("\\n", "\n").strip()
    encoded = normalized.encode("utf-8")
    if not normalized.startswith("-----BEGIN"):
        try:
            raw_key = base64.b64decode(encoded, validate=True)
            return Ed25519PublicKey.from_public_bytes(raw_key)
        except (ValueError, TypeError) as exc:
            raise QABootstrapError(
                "QA_PROVIDER_EVIDENCE_PUBLIC_KEY is not valid Ed25519 base64"
            ) from exc
    try:
        key = serialization.load_pem_public_key(encoded)
    except (TypeError, ValueError) as exc:
        raise QABootstrapError("QA_PROVIDER_EVIDENCE_PUBLIC_KEY is not valid PEM") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise QABootstrapError("QA_PROVIDER_EVIDENCE_PUBLIC_KEY must be an Ed25519 public key")
    return key


def build_provider_evidence_payload(
    manifest: Mapping[str, Any],
    *,
    now: int,
    ttl_seconds: int,
    nonce: str | None = None,
) -> dict[str, Any]:
    schema_version = manifest.get("schema_version")
    if schema_version not in {2, 3}:
        raise QABootstrapError("provider manifest schema_version must be 2 or 3")
    if manifest.get("evidence_type") != "provider-verified-isolated-preview":
        raise QABootstrapError("provider manifest evidence_type is invalid")

    generated_by = manifest.get("generated_by")
    if not isinstance(generated_by, dict) or generated_by.get("kind") != "provider-api-verifier":
        raise QABootstrapError("provider manifest generator is not trusted")
    workflow_run_id = generated_by.get("workflow_run_id")
    if (
        not isinstance(workflow_run_id, int)
        or isinstance(workflow_run_id, bool)
        or workflow_run_id <= 0
    ):
        raise QABootstrapError("provider manifest workflow run identity is invalid")
    sources = generated_by.get("evidence_sources")
    if (
        not isinstance(sources, list)
        or not all(isinstance(source, str) for source in sources)
        or len(sources) != 3
        or set(sources) != {"render-api", "supabase-management-api", "vercel-api"}
    ):
        raise QABootstrapError("provider manifest evidence sources are incomplete")
    if (
        generated_by.get("workflow_path") != ".github/workflows/verify-preview-providers.yml"
        or generated_by.get("github_environment") != "preview-qa"
        or generated_by.get("event_name") != "workflow_dispatch"
    ):
        raise QABootstrapError("provider manifest workflow provenance is invalid")
    actor_id = str(generated_by.get("actor_id") or "")
    repository = str(generated_by.get("repository") or "")
    git_branch = str(generated_by.get("git_branch") or "")
    if (
        not actor_id.isdigit()
        or "/" not in repository
        or not git_branch
        or git_branch in {"main", "master", "production"}
    ):
        raise QABootstrapError("provider manifest GitHub provenance is invalid")

    generated_at = manifest.get("generated_at")
    if not isinstance(generated_at, str):
        raise QABootstrapError("provider manifest timestamp is invalid")
    try:
        generated_timestamp = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QABootstrapError("provider manifest timestamp is invalid") from exc
    if generated_timestamp.tzinfo is None:
        raise QABootstrapError("provider manifest timestamp must include a timezone")
    generated_epoch = int(generated_timestamp.timestamp())
    if generated_epoch > now + 60 or now - generated_epoch > _MAX_EVIDENCE_TTL_SECONDS:
        raise QABootstrapError("provider manifest is stale or not yet valid")

    database = manifest.get("database")
    backend = manifest.get("backend")
    frontend = manifest.get("frontend")
    configuration = manifest.get("configuration")
    if (
        not isinstance(database, dict)
        or not isinstance(backend, dict)
        or not isinstance(frontend, dict)
        or not isinstance(configuration, dict)
    ):
        raise QABootstrapError("provider manifest sections are incomplete")
    if (
        database.get("provider") != "supabase"
        or database.get("evidence_source") != "supabase-management-api"
        or database.get("branch_type") not in {"preview", "dedicated-qa-project"}
    ):
        raise QABootstrapError("provider manifest database evidence is invalid")
    if (
        backend.get("provider") != "render"
        or backend.get("evidence_source") != "render-api"
        or backend.get("environment") != "preview"
    ):
        raise QABootstrapError("provider manifest backend evidence is invalid")
    if (
        frontend.get("provider") != "vercel"
        or frontend.get("evidence_source") != "vercel-api"
        or frontend.get("environment") != "preview"
    ):
        raise QABootstrapError("provider manifest frontend evidence is invalid")
    if (
        configuration.get("evidence_source") != "render-api"
        or configuration.get("qa_secrets_scope") != "preview-service"
    ):
        raise QABootstrapError("provider manifest configuration evidence is invalid")
    bootstrap_fingerprint = str(
        configuration.get("bootstrap_configuration_fingerprint") or ""
    )
    if (
        not _FINGERPRINT_PATTERN.fullmatch(bootstrap_fingerprint)
        or configuration.get("bootstrap_configuration_version")
        != BOOTSTRAP_CONFIGURATION_VERSION
    ):
        raise QABootstrapError("provider manifest bootstrap configuration binding is invalid")

    project_ref = str(database.get("project_ref") or "").lower()
    branch_type = str(database.get("branch_type") or "")
    branch_ref = str(database.get("branch_ref") or "").lower()
    production_branch_ref = str(database.get("production_branch_ref") or "").lower()
    database_user_distinct = database.get("database_user_distinct")
    if (
        not project_ref
        or branch_type not in {"preview", "dedicated-qa-project"}
        or not branch_ref
        or not production_branch_ref
        or project_ref != branch_ref
        or project_ref == production_branch_ref
        or branch_ref == production_branch_ref
        or database.get("with_data") is not False
        or not isinstance(database_user_distinct, bool)
    ):
        raise QABootstrapError("provider manifest branch identity is invalid")
    if project_ref == _KNOWN_PRODUCTION_PROJECT_REF:
        raise QABootstrapError("known production project ref is forbidden in QA evidence")
    if database.get("fingerprint_method") != "sha256":
        raise QABootstrapError("provider manifest fingerprint method is invalid")
    if database.get("fingerprint_payload_version") != "supabase-connection-v1":
        raise QABootstrapError("provider manifest fingerprint payload version is invalid")
    for flag in ("database_endpoint_distinct", "database_password_distinct", "jwt_identity_distinct"):
        if database.get(flag) is not True:
            raise QABootstrapError("provider manifest database isolation evidence is incomplete")

    connection_fingerprint = str(database.get("connection_fingerprint") or "")
    production_fingerprint = str(database.get("production_connection_fingerprint") or "")
    if not _FINGERPRINT_PATTERN.fullmatch(connection_fingerprint):
        raise QABootstrapError("provider manifest connection fingerprint is invalid")
    if not _FINGERPRINT_PATTERN.fullmatch(production_fingerprint):
        raise QABootstrapError("provider manifest production fingerprint is invalid")
    if hmac.compare_digest(connection_fingerprint, production_fingerprint):
        raise QABootstrapError("provider evidence identifies the production connection")

    code_sha = str(manifest.get("code_sha") or "").lower()
    service_id = str(backend.get("service_id") or "")
    production_service_id = str(backend.get("production_service_id") or "")
    environment_id = str(configuration.get("environment_id") or "")
    production_environment_id = str(configuration.get("production_environment_id") or "")
    if not _SHA_PATTERN.fullmatch(code_sha):
        raise QABootstrapError("provider manifest code SHA is invalid")
    if backend.get("code_sha") != code_sha:
        raise QABootstrapError("provider manifest backend SHA does not match")
    if backend.get("git_branch") != git_branch:
        raise QABootstrapError("provider manifest backend branch does not match")
    if not service_id or not production_service_id or service_id == production_service_id:
        raise QABootstrapError("provider manifest Render service identity is invalid")
    if (
        not environment_id
        or not production_environment_id
        or environment_id == production_environment_id
    ):
        raise QABootstrapError("provider manifest Render identity is incomplete")
    frontend_deployment_id = str(frontend.get("deployment_id") or "")
    frontend_project_id = str(frontend.get("project_id") or "")
    frontend_team_id = str(frontend.get("team_id") or "")
    backend_deployment_id = str(backend.get("deployment_id") or "")
    if (
        not backend_deployment_id
        or not frontend_deployment_id
        or not frontend_project_id
        or not frontend_team_id
        or frontend.get("code_sha") != code_sha
        or frontend.get("git_branch") != git_branch
    ):
        raise QABootstrapError("provider manifest Vercel provenance is incomplete")
    if not 60 <= ttl_seconds <= _MAX_EVIDENCE_TTL_SECONDS:
        raise QABootstrapError("provider evidence TTL must be between 60 and 3600 seconds")

    (
        isolation_mode,
        baseline_lease_id,
        baseline_lease_target_sha,
        baseline_lease_target_branch,
    ) = _validate_isolation_contract(
        database,
        branch_type=branch_type,
        code_sha=code_sha,
        git_branch=git_branch,
    )

    manifest_hash = (
        "sha256:"
        f"{hashlib.sha256(canonical_provider_evidence_json(manifest)).hexdigest()}"
    )
    payload = {
        "token_version": _EVIDENCE_TOKEN_VERSION,
        "signature_algorithm": "ed25519",
        "manifest_schema_version": schema_version,
        "evidence_type": "provider-verified-isolated-preview",
        "provider": "render+supabase+vercel",
        "code_sha": code_sha,
        "git_branch": git_branch,
        "workflow_run_id": workflow_run_id,
        "repository": repository,
        "service_id": service_id,
        "environment_id": environment_id,
        "render_deployment_id": backend_deployment_id,
        "frontend_deployment_id": frontend_deployment_id,
        "frontend_project_id": frontend_project_id,
        "frontend_team_id": frontend_team_id,
        "project_ref": project_ref,
        "branch_type": branch_type,
        "isolation_mode": isolation_mode,
        "branch_ref": branch_ref,
        "database_user_distinct": database_user_distinct,
        "database_endpoint_distinct": True,
        "database_password_distinct": True,
        "jwt_identity_distinct": True,
        "fingerprint_method": "sha256",
        "fingerprint_payload_version": "supabase-connection-v1",
        "connection_fingerprint": connection_fingerprint,
        "production_connection_fingerprint": production_fingerprint,
        "bootstrap_configuration_fingerprint": bootstrap_fingerprint,
        "bootstrap_configuration_version": BOOTSTRAP_CONFIGURATION_VERSION,
        "manifest_hash": manifest_hash,
        "issued_at": now,
        "expires_at": now + ttl_seconds,
        "nonce": nonce or secrets.token_hex(16),
    }
    if baseline_lease_id is not None:
        payload.update(
            {
                "baseline_lease_id": baseline_lease_id,
                "baseline_lease_target_sha": baseline_lease_target_sha,
                "baseline_lease_target_branch": baseline_lease_target_branch,
            }
        )
    return payload


def verify_provider_evidence_token(
    token: str,
    *,
    public_key: str,
    database_url: str,
    expected_service_id: str,
    expected_code_sha: str,
    bootstrap_env: Mapping[str, str],
    now: int | None = None,
) -> ProviderEvidence:
    parts = token.split(".")
    if len(parts) != 2:
        raise QABootstrapError("provider evidence token has invalid format")
    encoded_payload, encoded_signature = parts
    try:
        actual_signature = _b64url_decode(encoded_signature)
    except QABootstrapError as exc:
        raise QABootstrapError("provider evidence token signature is invalid") from exc
    try:
        load_provider_evidence_public_key(public_key).verify(
            actual_signature,
            encoded_payload.encode("ascii"),
        )
    except InvalidSignature as exc:
        raise QABootstrapError("provider evidence token signature is invalid")
    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QABootstrapError("provider evidence token payload is invalid") from exc
    if not isinstance(payload, dict):
        raise QABootstrapError("provider evidence token payload must be an object")

    if payload.get("token_version") != _EVIDENCE_TOKEN_VERSION:
        raise QABootstrapError("provider evidence token version is invalid")
    if payload.get("signature_algorithm") != "ed25519":
        raise QABootstrapError("provider evidence token signature algorithm is invalid")
    if payload.get("manifest_schema_version") not in {2, 3}:
        raise QABootstrapError("provider evidence manifest version is invalid")
    if payload.get("evidence_type") != "provider-verified-isolated-preview":
        raise QABootstrapError("provider evidence type is invalid")
    if payload.get("provider") != "render+supabase+vercel":
        raise QABootstrapError("provider evidence source is invalid")
    manifest_hash = str(payload.get("manifest_hash") or "")
    nonce = str(payload.get("nonce") or "")
    if not _FINGERPRINT_PATTERN.fullmatch(manifest_hash):
        raise QABootstrapError("provider evidence manifest hash is invalid")
    if not re.fullmatch(r"[0-9a-f]{32,128}", nonce):
        raise QABootstrapError("provider evidence nonce is invalid")
    if payload.get("bootstrap_configuration_version") != BOOTSTRAP_CONFIGURATION_VERSION:
        raise QABootstrapError("provider evidence bootstrap configuration version is invalid")
    bound_fingerprint = str(payload.get("bootstrap_configuration_fingerprint") or "")
    if not _FINGERPRINT_PATTERN.fullmatch(bound_fingerprint):
        raise QABootstrapError("provider evidence bootstrap configuration fingerprint is invalid")
    try:
        actual_bootstrap_fingerprint = bootstrap_configuration_fingerprint(bootstrap_env)
    except BootstrapConfigurationError as error:
        raise QABootstrapError(str(error)) from None
    if not hmac.compare_digest(bound_fingerprint, actual_bootstrap_fingerprint):
        raise QABootstrapError("provider evidence bootstrap configuration fingerprint does not match")

    issued_at = payload.get("issued_at")
    expires_at = payload.get("expires_at")
    current_time = int(time.time()) if now is None else int(now)
    if not isinstance(issued_at, int) or isinstance(issued_at, bool):
        raise QABootstrapError("provider evidence issued_at is invalid")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool):
        raise QABootstrapError("provider evidence expires_at is invalid")
    if expires_at - issued_at < 60 or expires_at - issued_at > _MAX_EVIDENCE_TTL_SECONDS:
        raise QABootstrapError("provider evidence TTL is invalid")
    if issued_at > current_time + 30 or expires_at < current_time:
        raise QABootstrapError("provider evidence token is expired or not yet valid")

    identity = _postgres_identity(database_url)
    project_ref = str(payload.get("project_ref") or "").lower()
    branch_type = str(payload.get("branch_type") or "")
    database_user_distinct = payload.get("database_user_distinct")
    if (
        not project_ref
        or branch_type not in {"preview", "dedicated-qa-project"}
        or not isinstance(database_user_distinct, bool)
    ):
        raise QABootstrapError("provider evidence database identity is invalid")
    _validate_non_production_target(identity, project_ref=project_ref)
    database_role = identity[3].lower()
    _validate_qa_database_role(
        database_role,
        provider_verified_supabase=True,
        database_user_distinct=database_user_distinct,
    )
    if not hmac.compare_digest(database_role, identity[3].lower()):
        raise QABootstrapError("provider evidence database role does not match DATABASE_URL")
    branch_ref = str(payload.get("branch_ref") or "").lower()
    if not branch_ref or branch_ref != project_ref:
        raise QABootstrapError("provider evidence branch ref does not match project_ref")
    if payload.get("fingerprint_method") != "sha256":
        raise QABootstrapError("provider evidence fingerprint method is invalid")
    if payload.get("fingerprint_payload_version") != "supabase-connection-v1":
        raise QABootstrapError("provider evidence fingerprint payload version is invalid")

    connection_fingerprint = str(payload.get("connection_fingerprint") or "")
    production_fingerprint = str(payload.get("production_connection_fingerprint") or "")
    actual_fingerprint = database_connection_fingerprint(
        database_url,
        project_ref=project_ref,
    )
    if not _FINGERPRINT_PATTERN.fullmatch(connection_fingerprint):
        raise QABootstrapError("provider evidence connection fingerprint is invalid")
    if not hmac.compare_digest(connection_fingerprint, actual_fingerprint):
        raise QABootstrapError("provider evidence fingerprint does not match DATABASE_URL")
    if not _FINGERPRINT_PATTERN.fullmatch(production_fingerprint):
        raise QABootstrapError("provider evidence production fingerprint is invalid")
    if hmac.compare_digest(connection_fingerprint, production_fingerprint):
        raise QABootstrapError("provider evidence identifies the production connection")

    code_sha = str(payload.get("code_sha") or "").lower()
    if not _SHA_PATTERN.fullmatch(code_sha) or not hmac.compare_digest(code_sha, expected_code_sha.lower()):
        raise QABootstrapError("provider evidence code SHA does not match Render")
    service_id = str(payload.get("service_id") or "")
    if not service_id or not hmac.compare_digest(service_id, expected_service_id):
        raise QABootstrapError("provider evidence service does not match Render")
    git_branch = str(payload.get("git_branch") or "")
    workflow_run_id = payload.get("workflow_run_id")
    repository = str(payload.get("repository") or "")
    if (
        not git_branch
        or git_branch in {"main", "master", "production"}
        or not isinstance(workflow_run_id, int)
        or isinstance(workflow_run_id, bool)
        or workflow_run_id <= 0
        or "/" not in repository
    ):
        raise QABootstrapError("provider evidence workflow provenance is invalid")
    (
        isolation_mode,
        baseline_lease_id,
        baseline_lease_target_sha,
        baseline_lease_target_branch,
    ) = _validate_isolation_contract(
        payload,
        branch_type=branch_type,
        code_sha=code_sha,
        git_branch=git_branch,
    )
    environment_id = str(payload.get("environment_id") or "")
    render_deployment_id = str(payload.get("render_deployment_id") or "")
    if not environment_id or not render_deployment_id:
        raise QABootstrapError("provider evidence Render identity is incomplete")
    frontend_deployment_id = str(payload.get("frontend_deployment_id") or "")
    frontend_project_id = str(payload.get("frontend_project_id") or "")
    frontend_team_id = str(payload.get("frontend_team_id") or "")
    if not frontend_deployment_id or not frontend_project_id or not frontend_team_id:
        raise QABootstrapError("provider evidence Vercel identity is incomplete")
    for flag in (
        "database_endpoint_distinct",
        "database_password_distinct",
        "jwt_identity_distinct",
    ):
        if payload.get(flag) is not True:
            raise QABootstrapError("provider evidence database isolation is incomplete")

    return ProviderEvidence(
        manifest_schema_version=int(payload["manifest_schema_version"]),
        code_sha=code_sha,
        service_id=service_id,
        environment_id=environment_id,
        frontend_deployment_id=frontend_deployment_id,
        project_ref=project_ref,
        branch_type=branch_type,
        branch_ref=branch_ref,
        database_role=database_role,
        connection_fingerprint=connection_fingerprint,
        production_connection_fingerprint=production_fingerprint,
        isolation_mode=isolation_mode,
        baseline_lease_id=baseline_lease_id,
        baseline_lease_target_sha=baseline_lease_target_sha,
        baseline_lease_target_branch=baseline_lease_target_branch,
    )


def _validate_database_target(
    env: Mapping[str, str], database_url: str, app_env: str
) -> ProviderEvidence | None:
    if app_env in {"prod", "production"}:
        raise QABootstrapError("production APP_ENV is forbidden")
    if app_env not in {"qa", "preview", "test"}:
        raise QABootstrapError("APP_ENV must be qa, preview, or test")
    if not _flag(env, "QA_DATABASE_ISOLATED"):
        raise QABootstrapError("QA_DATABASE_ISOLATED=true is required")

    try:
        url = make_url(database_url)
    except Exception as exc:
        raise QABootstrapError("DATABASE_URL is not a valid SQLAlchemy URL") from exc

    driver = url.drivername.lower()
    if driver.startswith("sqlite"):
        if app_env != "test" or not _flag(env, "QA_ALLOW_SQLITE"):
            raise QABootstrapError("SQLite is allowed only for explicit local test bootstrap")
        raw_path = url.database or ""
        if raw_path == ":memory:":
            raise QABootstrapError("in-memory SQLite is not a persistent QA target")
        actual_path = Path(raw_path).expanduser().resolve()
        expected_path = Path(_required(env, "QA_EXPECTED_DATABASE_PATH")).expanduser().resolve()
        if actual_path != expected_path:
            raise QABootstrapError("DATABASE_URL does not match QA_EXPECTED_DATABASE_PATH")
        safe_path = actual_path.as_posix().lower()
        if not any(marker in safe_path for marker in ("qa", "test", "e2e")):
            raise QABootstrapError("SQLite QA path must contain qa, test, or e2e")
        return None

    target = _postgres_identity(database_url)
    _validate_non_production_target(target)
    expected = (
        _required(env, "QA_EXPECTED_DATABASE_HOST").lower(),
        _required_port(env, "QA_EXPECTED_DATABASE_PORT"),
        _required(env, "QA_EXPECTED_DATABASE_NAME"),
        _required(env, "QA_EXPECTED_DATABASE_USER"),
    )
    if target != expected:
        raise QABootstrapError("DATABASE_URL does not match the expected QA database identity")
    branch_ref = _required(env, "QA_DATABASE_BRANCH_REF").lower()
    if not _RUN_ID_PATTERN.fullmatch(branch_ref):
        raise QABootstrapError("QA_DATABASE_BRANCH_REF is invalid")
    if (env.get("QA_PROVIDER_EVIDENCE_PRIVATE_KEY") or "").strip():
        raise QABootstrapError(
            "QA_PROVIDER_EVIDENCE_PRIVATE_KEY must not be available to the Render consumer"
        )
    evidence = verify_provider_evidence_token(
        _required(env, "QA_PROVIDER_EVIDENCE_TOKEN"),
        public_key=_required(env, "QA_PROVIDER_EVIDENCE_PUBLIC_KEY"),
        database_url=database_url,
        expected_service_id=_required(env, "RENDER_SERVICE_ID"),
        expected_code_sha=_required(env, "RENDER_GIT_COMMIT"),
        bootstrap_env=env,
    )
    if not hmac.compare_digest(evidence.branch_ref, branch_ref):
        raise QABootstrapError("provider evidence branch ref does not match QA_DATABASE_BRANCH_REF")
    present_lease_keys = _BASELINE_LEASE_ENV_KEYS & env.keys()
    if evidence.isolation_mode == "supabase-branch-per-target":
        if present_lease_keys:
            raise QABootstrapError(
                "per-branch QA target must not carry dedicated baseline lease variables"
            )
    elif evidence.isolation_mode == "dedicated-qa-baseline-exclusive":
        missing_lease_keys = sorted(_BASELINE_LEASE_ENV_KEYS - env.keys())
        if missing_lease_keys:
            raise QABootstrapError(
                "dedicated QA baseline is missing required lease variables"
            )
        if env["QA_BASELINE_ONLY"] != "true":
            raise QABootstrapError("QA_BASELINE_ONLY must be exactly true")
        if not hmac.compare_digest(
            env["QA_BASELINE_LEASE_ID"], evidence.baseline_lease_id or ""
        ):
            raise QABootstrapError("dedicated QA baseline lease ID does not match evidence")
        if not hmac.compare_digest(
            env["QA_BASELINE_LEASE_TARGET_SHA"],
            evidence.baseline_lease_target_sha or "",
        ):
            raise QABootstrapError("dedicated QA baseline lease targets another Git SHA")
        if not hmac.compare_digest(
            env["QA_BASELINE_LEASE_TARGET_BRANCH"],
            evidence.baseline_lease_target_branch or "",
        ):
            raise QABootstrapError("dedicated QA baseline lease targets another Git branch")
    else:  # Defensive guard if the evidence dataclass grows without this consumer.
        raise QABootstrapError("provider evidence isolation mode is unsupported")
    return evidence


def load_config(env: Mapping[str, str] | None = None) -> QABootstrapConfig:
    source = os.environ if env is None else env
    app_env = _required(source, "APP_ENV").lower()
    database_url = _required(source, "DATABASE_URL")
    provider_evidence = _validate_database_target(source, database_url, app_env)

    run_id = _required(source, "QA_RUN_ID")
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise QABootstrapError("QA_RUN_ID must be 6-64 safe identifier characters")

    email_domain = _required(source, "QA_EMAIL_DOMAIN").lower()
    if "@" in email_domain or "." not in email_domain:
        raise QABootstrapError("QA_EMAIL_DOMAIN must be a domain name")
    if not _flag(source, "QA_EMAIL_DOMAIN_IS_DEDICATED"):
        raise QABootstrapError("QA_EMAIL_DOMAIN_IS_DEDICATED=true is required")

    personas: list[Persona] = []
    for name, env_prefix, role in _HOTEL_PERSONAS:
        email = _validate_email(
            _required(source, f"{env_prefix}_EMAIL"),
            name=f"{env_prefix}_EMAIL",
            domain=email_domain,
        )
        password = _validate_password(
            _required(source, f"{env_prefix}_PASSWORD"),
            name=f"{env_prefix}_PASSWORD",
        )
        personas.append(Persona(name=name, email=email, password=password, role=role))

    master_email = _validate_email(
        _required(source, "QA_MASTER_ADMIN_EMAIL"),
        name="QA_MASTER_ADMIN_EMAIL",
        domain=email_domain,
    )
    master_password = _validate_password(
        _required(source, "QA_MASTER_ADMIN_PASSWORD"),
        name="QA_MASTER_ADMIN_PASSWORD",
    )
    master_pin = _required(source, "QA_MASTER_ADMIN_PIN")
    if len(master_pin) < 6 or not master_pin.isdigit():
        raise QABootstrapError("QA_MASTER_ADMIN_PIN must contain at least 6 digits")

    if len({persona.email for persona in personas} | {master_email}) != 5:
        raise QABootstrapError("all five QA persona emails must be distinct")
    if len({persona.password for persona in personas} | {master_password}) != 5:
        raise QABootstrapError("all five QA persona passwords must be distinct")

    runtime_master_email = _required(source, "MASTER_ADMIN_EMAIL").lower()
    runtime_master_password = _required(source, "MASTER_ADMIN_PASSWORD")
    runtime_master_pin = _required(source, "MASTER_ADMIN_PIN")
    if not hmac.compare_digest(master_email, runtime_master_email):
        raise QABootstrapError("MASTER_ADMIN_EMAIL must match the QA master-admin identity")
    if not hmac.compare_digest(master_password, runtime_master_password):
        raise QABootstrapError("MASTER_ADMIN_PASSWORD must match the QA master-admin identity")
    if not hmac.compare_digest(master_pin, runtime_master_pin):
        raise QABootstrapError("MASTER_ADMIN_PIN must match the QA master-admin identity")

    hotel_name = f"Hotel QA {run_id}"
    return QABootstrapConfig(
        app_env=app_env,
        database_url=database_url,
        run_id=run_id,
        hotel_name=hotel_name,
        personas=tuple(personas),
        master_admin_email=master_email,
        master_admin_password=master_password,
        master_admin_pin=master_pin,
        database_role=provider_evidence.database_role if provider_evidence else None,
        connection_fingerprint=(
            provider_evidence.connection_fingerprint if provider_evidence else None
        ),
        run_migrations=_flag(source, "QA_RUN_MIGRATIONS"),
    )


@contextmanager
def _runtime_database_environment(config: QABootstrapConfig):
    previous_database_url = os.environ.get("DATABASE_URL")
    previous_app_env = os.environ.get("APP_ENV")
    os.environ["DATABASE_URL"] = config.database_url
    os.environ["APP_ENV"] = config.app_env
    try:
        yield
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        if previous_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = previous_app_env


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    alembic_config = Config(str(ROOT_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    alembic_config.set_main_option("prepend_sys_path", str(ROOT_DIR))
    command.upgrade(alembic_config, "head")


def _qa_marker(hotel) -> dict | None:
    try:
        policies = hotel.get_extra_policies()
    except (TypeError, ValueError):
        return None
    marker = policies.get("_qa_bootstrap") if isinstance(policies, dict) else None
    return marker if isinstance(marker, dict) else None


def upsert_qa_data(db, config: QABootstrapConfig) -> QABootstrapResult:
    """Idempotently create one tagged QA hotel and its four database users."""
    from sqlalchemy import func

    from app.models import (
        HotelConfiguration,
        HotelMembership,
        HotelSubscription,
        OnboardingState,
        SubscriptionPlan,
        User,
    )
    from app.services.hotel_service import ensure_plans_seeded
    from app.services.permission_service import seed_default_permissions
    from app.services.security import hash_password, verify_password

    owner_persona = next(persona for persona in config.personas if persona.role == "owner")
    hotel = (
        db.query(HotelConfiguration)
        .filter(HotelConfiguration.owner_email == owner_persona.email)
        .one_or_none()
    )
    if hotel is not None:
        marker = _qa_marker(hotel)
        if not marker or marker.get("run_id") != config.run_id or marker.get("isolated") is not True:
            raise QABootstrapError("refusing to modify an existing hotel without the matching QA marker")
    else:
        owner = db.query(User).filter(User.email == owner_persona.email).one_or_none()
        if owner is not None and db.query(HotelMembership).filter(HotelMembership.user_id == owner.id).count():
            raise QABootstrapError("refusing to reuse a QA owner attached to another hotel")
        next_hotel_id = (db.query(func.max(HotelConfiguration.id)).scalar() or 0) + 1
        hotel = HotelConfiguration(id=next_hotel_id, owner_email=owner_persona.email)
        db.add(hotel)

    hotel.hotel_name = config.hotel_name
    hotel.owner_email = owner_persona.email
    hotel.subscription_active = True
    hotel.default_currency = "ARS"
    hotel.hotel_timezone = "America/Argentina/Buenos_Aires"
    policies = hotel.get_extra_policies()
    policies["_qa_bootstrap"] = {
        "isolated": True,
        "run_id": config.run_id,
        "synthetic": True,
    }
    hotel.set_extra_policies(policies)
    db.flush()

    users_created = 0
    memberships_created = 0
    for persona in config.personas:
        user = db.query(User).filter(User.email == persona.email).one_or_none()
        if user is None:
            user = User(email=persona.email, password_hash=hash_password(persona.password))
            db.add(user)
            db.flush()
            users_created += 1
        else:
            foreign_membership = (
                db.query(HotelMembership)
                .filter(HotelMembership.user_id == user.id, HotelMembership.hotel_id != hotel.id)
                .first()
            )
            if foreign_membership is not None:
                raise QABootstrapError("refusing to reuse a QA persona attached to another hotel")
            try:
                password_matches = verify_password(persona.password, user.password_hash)
            except Exception:
                password_matches = False
            if not password_matches:
                user.password_hash = hash_password(persona.password)

        user.is_active = True
        user.is_verified = True
        user.role = persona.role

        membership = (
            db.query(HotelMembership)
            .filter(HotelMembership.hotel_id == hotel.id, HotelMembership.user_id == user.id)
            .one_or_none()
        )
        if membership is None:
            membership = HotelMembership(hotel_id=hotel.id, user_id=user.id)
            db.add(membership)
            memberships_created += 1
        membership.role = persona.role
        membership.status = "active"

    ensure_plans_seeded(db)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "starter").one()
    subscription = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel.id).one_or_none()
    if subscription is None:
        subscription = HotelSubscription(hotel_id=hotel.id, plan_id=plan.id)
        db.add(subscription)
    subscription.plan_id = plan.id
    subscription.status = "active"
    seed_default_permissions(db)

    onboarding = db.get(OnboardingState, hotel.id)
    if onboarding is None:
        onboarding = OnboardingState(hotel_id=hotel.id)
        db.add(onboarding)
        onboarding.owner_name = f"Owner QA {config.run_id}"
        onboarding.owner_email = owner_persona.email
        onboarding.owner_phone = "0000000000"
        onboarding.owner_role = "owner"
        onboarding.set_hotel_identity(
            {
                "name": config.hotel_name,
                "address": "Synthetic QA address",
                "city": "QA",
                "country": "AR",
            }
        )
        onboarding.set_deposit_policy({"deposit_percentage": 30, "enable_full_payment": True})
        onboarding.set_payment_methods({"cash": {"enabled": True}})
        onboarding.set_ota_channels({"booking": {"enabled": False}, "expedia": {"enabled": False}})
        onboarding.set_subscription_choice({"plan": "starter"})
        onboarding.set_staff(
            [
                {"name": persona.name, "email": persona.email, "role": persona.role}
                for persona in config.personas
            ]
        )
        onboarding.identity_set = True
        onboarding.policy_set = True
        onboarding.payments_set = True
        onboarding.ota_set = True
        onboarding.subscription_set = True
        # The first owner login must exercise the visible onboarding finish
        # flow. Reruns never reset this flag or overwrite human-entered state.
        onboarding.finished = False
        onboarding.updated_at = datetime.now(timezone.utc)

    db.commit()
    return QABootstrapResult(
        hotel_id=hotel.id,
        users_created=users_created,
        memberships_created=memberships_created,
    )


def bootstrap_database(config: QABootstrapConfig) -> QABootstrapResult:
    from app.database import get_session_factory, init_db

    init_db(config.database_url)
    session_factory = get_session_factory()
    with session_factory() as db:
        try:
            return upsert_qa_data(db, config)
        except Exception:
            db.rollback()
            raise


def main(env: Mapping[str, str] | None = None) -> QABootstrapResult:
    config = load_config(env)
    with _runtime_database_environment(config):
        if config.run_migrations:
            run_migrations()
        result = bootstrap_database(config)
    print(
        f"QA bootstrap complete for run_id={config.run_id}; "
        "hotel-personas=4; master-admin=runtime-env"
    )
    return result


def cli() -> int:
    try:
        main()
    except QABootstrapError as exc:
        print(f"QA bootstrap refused: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("QA bootstrap failed after safety checks; inspect redacted service logs", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
