"""Fail-closed safety guard for PostgreSQL tests that mutate schema or data.

Remote Supabase targets require a short-lived Ed25519 provider token.  A local
JSON file is deliberately accepted only for a loopback PostgreSQL fixture; it
must never be treated as proof that a cloud database is isolated.
"""
from __future__ import annotations

import hmac
import json
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import unquote, urlparse

from scripts.bootstrap_cloud_qa import (
    QABootstrapError,
    verify_provider_evidence_token,
)


CANONICAL_PRODUCTION_REF = "ezkljznogqpmrjxyvklr"


class PostgresTargetSafetyError(RuntimeError):
    """The PostgreSQL test target cannot be proven isolated and disposable."""


_PRODUCTION_BRANCH_TOKENS = {"main", "master", "prod", "production", "default", "live"}
_TRUE_VALUES = {"1", "true", "yes"}
_ALLOWED_REMOTE_HOST_SUFFIXES = (".supabase.co", ".pooler.supabase.com")
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_DISPOSABLE_DATABASE_TOKENS = {"test", "qa", "preview", "pr", "branch", "ephemeral"}
_REQUIRED_EVIDENCE_FIELDS = {
    "schema_version",
    "provider",
    "evidence_source",
    "environment",
    "branch_ref",
    "production_ref",
    "host",
    "port",
    "database",
    "role",
    "database_isolated",
    "data_classification",
}


def _enabled(value: str | None) -> bool:
    return (value or "").strip().casefold() in _TRUE_VALUES


def _canonical_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _identity_contains(identity: str, value: str) -> bool:
    canonical_value = _canonical_identity(value)
    return bool(canonical_value) and canonical_value in _canonical_identity(identity)


def _load_local_evidence(environment: Mapping[str, str]) -> dict[str, object]:
    evidence_file = (environment.get("POSTGRES_TEST_PROVIDER_EVIDENCE_FILE") or "").strip()
    if not evidence_file:
        raise PostgresTargetSafetyError("local isolation evidence is required")
    try:
        raw = Path(evidence_file).read_text(encoding="utf-8")
        evidence = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PostgresTargetSafetyError("local isolation evidence is unreadable") from error
    if not isinstance(evidence, dict):
        raise PostgresTargetSafetyError("local isolation evidence must be an object")
    if _REQUIRED_EVIDENCE_FIELDS - set(evidence):
        raise PostgresTargetSafetyError("local isolation evidence is incomplete")
    if evidence.get("schema_version") != 1:
        raise PostgresTargetSafetyError("local isolation evidence version is unsupported")
    if evidence.get("database_isolated") is not True:
        raise PostgresTargetSafetyError("local evidence does not attest an isolated database")
    if evidence.get("data_classification") != "synthetic-only":
        raise PostgresTargetSafetyError("local evidence does not restrict data to synthetic-only")
    if evidence.get("environment") != "test":
        raise PostgresTargetSafetyError("local evidence environment is not disposable")
    return evidence


def _verify_remote_provider_evidence(
    environment: Mapping[str, str],
    *,
    dsn: str,
    branch_ref: str,
    production_ref: str,
) -> None:
    token = (environment.get("POSTGRES_TEST_PROVIDER_EVIDENCE_TOKEN") or "").strip()
    if not token:
        raise PostgresTargetSafetyError("signed provider evidence token is required")
    public_key = (environment.get("QA_PROVIDER_EVIDENCE_PUBLIC_KEY") or "").strip()
    if not public_key:
        raise PostgresTargetSafetyError("provider evidence public key is required")
    expected_service_id = (environment.get("RENDER_SERVICE_ID") or "").strip()
    if not expected_service_id:
        raise PostgresTargetSafetyError("expected Render service identity is required")
    expected_code_sha = (environment.get("RENDER_GIT_COMMIT") or "").strip()
    if not expected_code_sha:
        raise PostgresTargetSafetyError("expected Render code SHA is required")

    try:
        evidence = verify_provider_evidence_token(
            token,
            public_key=public_key,
            database_url=dsn,
            expected_service_id=expected_service_id,
            expected_code_sha=expected_code_sha,
            bootstrap_env=environment,
        )
    except QABootstrapError as error:
        # The provider helper already redacts sensitive values.  Keep this
        # boundary generic so future helper diagnostics cannot expose the DSN.
        raise PostgresTargetSafetyError("signed provider evidence is invalid") from error

    if (
        not hmac.compare_digest(evidence.project_ref, branch_ref.casefold())
        or not hmac.compare_digest(evidence.branch_ref, branch_ref.casefold())
    ):
        raise PostgresTargetSafetyError("signed provider evidence does not match the QA branch")
    if production_ref != CANONICAL_PRODUCTION_REF:
        raise PostgresTargetSafetyError("the production reference is not canonical")
    if evidence.branch_type not in {"preview", "dedicated-qa-project"}:
        raise PostgresTargetSafetyError("signed provider evidence branch type is invalid")


def validate_postgres_test_target(
    dsn: str,
    environment: Mapping[str, str],
) -> str:
    """Return ``dsn`` only when provider evidence proves a disposable QA target.

    Error messages deliberately describe only the failed invariant. They never
    interpolate the DSN, username, password, host, database, role, or branch ref.
    """
    if not _enabled(environment.get("ALLOW_DESTRUCTIVE_POSTGRES_TESTS")):
        raise PostgresTargetSafetyError("destructive PostgreSQL opt-in is required")
    if not _enabled(environment.get("POSTGRES_TEST_ISOLATION_CONFIRMED")):
        raise PostgresTargetSafetyError("explicit PostgreSQL isolation confirmation is required")

    explicit_dsn = (environment.get("POSTGRES_TEST_DATABASE_URL_EXPLICIT") or "").strip()
    if not explicit_dsn:
        raise PostgresTargetSafetyError("an explicit database URL is required")
    if not dsn or not hmac.compare_digest(dsn.encode("utf-8"), explicit_dsn.encode("utf-8")):
        raise PostgresTargetSafetyError("DATABASE_URL_TEST does not match the explicit database URL")

    try:
        parsed = urlparse(dsn)
        hostname = (parsed.hostname or "").casefold()
        username = unquote(parsed.username or "")
        port = parsed.port
    except (ValueError, UnicodeError) as error:
        raise PostgresTargetSafetyError("the PostgreSQL test target URL is malformed") from error
    if not parsed.scheme.startswith("postgresql") or not hostname:
        raise PostgresTargetSafetyError("the explicit database URL must be PostgreSQL with a host")
    if port != 5432:
        raise PostgresTargetSafetyError("PostgreSQL QA tests require a direct or session-mode port")

    database_name = unquote(parsed.path.lstrip("/").split("/", 1)[0])
    if not database_name:
        raise PostgresTargetSafetyError("the PostgreSQL test target must include a database name")

    expected_host = (environment.get("POSTGRES_TEST_EXPECTED_HOST") or "").strip().casefold()
    expected_role = (environment.get("POSTGRES_TEST_EXPECTED_ROLE") or "").strip()
    expected_database = (environment.get("POSTGRES_TEST_EXPECTED_DATABASE") or "").strip()
    if not expected_host:
        raise PostgresTargetSafetyError("an exact expected host is required")
    if not expected_role:
        raise PostgresTargetSafetyError("an exact expected role is required")
    if not expected_database:
        raise PostgresTargetSafetyError("an exact expected database is required")
    if hostname != expected_host:
        raise PostgresTargetSafetyError("the PostgreSQL test host does not match the expected host")
    if username != expected_role:
        raise PostgresTargetSafetyError("the PostgreSQL test role does not match the expected role")
    if database_name != expected_database:
        raise PostgresTargetSafetyError("the PostgreSQL test database does not match the expected database")

    branch_ref = (environment.get("POSTGRES_TEST_ISOLATED_BRANCH_REF") or "").strip()
    production_ref = (environment.get("POSTGRES_TEST_PRODUCTION_REF") or "").strip()
    if not branch_ref:
        raise PostgresTargetSafetyError("an isolated branch reference is required")
    if not production_ref:
        raise PostgresTargetSafetyError("the canonical production reference is required")
    if production_ref != CANONICAL_PRODUCTION_REF:
        raise PostgresTargetSafetyError("the production reference is not canonical")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}", branch_ref):
        raise PostgresTargetSafetyError("the isolated branch reference has an invalid format")
    if _canonical_identity(branch_ref) == _canonical_identity(production_ref):
        raise PostgresTargetSafetyError("the QA and production references must be distinct")

    normalized_ref = branch_ref.casefold()
    ref_tokens = set(filter(None, re.split(r"[^a-z0-9]+", normalized_ref)))
    if (
        ref_tokens & _PRODUCTION_BRANCH_TOKENS
        or normalized_ref.startswith(("prod", "production", "main", "master"))
    ):
        raise PostgresTargetSafetyError("a production-like branch reference is forbidden")

    host_tokens = set(filter(None, re.split(r"[^a-z0-9]+", hostname)))
    if host_tokens & _PRODUCTION_BRANCH_TOKENS:
        raise PostgresTargetSafetyError("a production-like host is forbidden")
    is_loopback = hostname in _LOOPBACK_HOSTS
    is_allowed_supabase = any(hostname.endswith(suffix) for suffix in _ALLOWED_REMOTE_HOST_SUFFIXES)
    if not is_loopback and not is_allowed_supabase:
        raise PostgresTargetSafetyError("the PostgreSQL test host is not an allowed QA provider host")

    target_identity = "|".join((hostname, username, database_name))
    if _identity_contains(target_identity, production_ref):
        raise PostgresTargetSafetyError("the target matches the known production database")
    if not _identity_contains(target_identity, branch_ref):
        raise PostgresTargetSafetyError("the isolated branch reference is not present in the target identity")

    if is_loopback:
        database_tokens = set(filter(None, re.split(r"[^a-z0-9]+", database_name.casefold())))
        if not database_tokens & _DISPOSABLE_DATABASE_TOKENS:
            raise PostgresTargetSafetyError("the local PostgreSQL database is not explicitly disposable")
    else:
        role_has_ref = _identity_contains(username, branch_ref)
        host_has_ref = _identity_contains(hostname, branch_ref)
        if not (role_has_ref or host_has_ref):
            raise PostgresTargetSafetyError("the Supabase branch identity is ambiguous")
        if not username.casefold().startswith("postgres"):
            raise PostgresTargetSafetyError("the Supabase QA role is not an expected branch role")

    if is_loopback:
        evidence = _load_local_evidence(environment)
        provider = evidence.get("provider")
        evidence_source = evidence.get("evidence_source")
        if provider != "local-postgres" or evidence_source != "local-ephemeral-fixture":
            raise PostgresTargetSafetyError("local provider evidence source is invalid")
        expected_evidence = {
            "branch_ref": branch_ref,
            "production_ref": production_ref,
            "host": hostname,
            "port": port,
            "database": database_name,
            "role": username,
        }
        for field, expected_value in expected_evidence.items():
            if evidence.get(field) != expected_value:
                raise PostgresTargetSafetyError("local isolation evidence does not match the target")
    else:
        # A repository-local JSON document is self-attested and therefore is
        # never accepted as cloud-provider proof.  The signed token binds the
        # Supabase target to the verified Render service and exact code SHA.
        _verify_remote_provider_evidence(
            environment,
            dsn=dsn,
            branch_ref=branch_ref,
            production_ref=production_ref,
        )

    return dsn
