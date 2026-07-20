#!/usr/bin/env python3
"""Validate same-SHA provider evidence before cloud QA is allowed to run."""

from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_ops.qa_bootstrap_contract import (
    BOOTSTRAP_CONFIGURATION_KEYS,
    BOOTSTRAP_CONFIGURATION_VERSION,
)


PRODUCTION_HOSTS = {"app.hotels-pms.com", "hotels-pms.com", "api.hotels-pms.com"}
EXPECTED_SOURCES = {"render-api", "supabase-management-api", "vercel-api"}
EXPECTED_WORKFLOW_PATH = ".github/workflows/verify-preview-providers.yml"
EXPECTED_ENVIRONMENT = "preview-qa"
SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}")
LEASE_ID_RE = re.compile(r"[A-Za-z0-9_-]{22,128}")
REQUIRED_SECRET_NAMES = {
    "DATABASE_URL",
    "JWT_SECRET",
    "FRONTEND_URL",
    "CORS_ORIGINS",
} | set(BOOTSTRAP_CONFIGURATION_KEYS)
BASELINE_RENDER_ENV_NAMES = {
    "QA_BASELINE_ONLY",
    "QA_BASELINE_LEASE_ID",
    "QA_BASELINE_LEASE_TARGET_SHA",
    "QA_BASELINE_LEASE_TARGET_BRANCH",
}
BASELINE_LEASE_FIELDS = {
    "baseline_lease_id",
    "baseline_lease_target_sha",
    "baseline_lease_target_branch",
}
MAX_MANIFEST_AGE = timedelta(hours=1)
MAX_DEPLOYMENT_AGE = timedelta(hours=24)
FUTURE_SKEW = timedelta(minutes=5)


def _mapping(value: object, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def _non_empty(value: object, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _canonical_host(value: str, field: str, errors: list[str]) -> str:
    host = value.rstrip(".").lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        errors.append(f"{field} hostname is invalid")
        return ""


def _https_preview_url(
    value: object,
    field: str,
    errors: list[str],
    *,
    allowed_paths: set[str],
    provider_suffix: str,
) -> str:
    raw = _non_empty(value, field, errors)
    if not raw:
        return ""
    parsed = urlsplit(raw)
    try:
        port = parsed.port
    except ValueError:
        errors.append(f"{field} contains an invalid port")
        return raw
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or any(ord(character) < 32 for character in raw)
        or port not in {None, 443}
    ):
        errors.append(f"{field} must be a credential-free HTTPS URL on port 443")
        return raw
    host = _canonical_host(parsed.hostname, field, errors)
    if host in PRODUCTION_HOSTS:
        errors.append(f"{field} must not use a production host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        errors.append(f"{field} must not use a private, loopback, link-local, or reserved IP")
    suffix = provider_suffix.lstrip(".")
    if host and host != suffix and not host.endswith(f".{suffix}"):
        errors.append(f"{field} must use the verified {provider_suffix} provider domain")
    if parsed.path not in allowed_paths:
        expected = ", ".join(repr(path) for path in sorted(allowed_paths))
        errors.append(f"{field} path must be one of: {expected}")
    normalized_path = "" if parsed.path in {"", "/"} else parsed.path.rstrip("/")
    return f"https://{host}{normalized_path}" if host else raw


def _timestamp(value: object, field: str, errors: list[str]) -> datetime | None:
    raw = _non_empty(value, field, errors)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be an ISO-8601 timestamp")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{field} must include a timezone")
        return None
    return parsed.astimezone(timezone.utc)


def _validate_baseline_lease_id(
    value: object,
    code_sha: str,
    branch: str,
    task_id: str,
    errors: list[str],
) -> str:
    lease_id = _non_empty(value, "database.baseline_lease_id", errors)
    if not lease_id:
        return ""
    entropy: bytes | None = None
    try:
        parsed_uuid = uuid.UUID(lease_id)
    except (ValueError, AttributeError):
        parsed_uuid = None
    if parsed_uuid is not None:
        if parsed_uuid.version == 4 and parsed_uuid.variant == uuid.RFC_4122:
            entropy = parsed_uuid.bytes
        else:
            errors.append("database.baseline_lease_id UUID must be random UUIDv4")
    elif re.fullmatch(r"[0-9a-fA-F]{32,128}", lease_id) and len(lease_id) % 2 == 0:
        entropy = bytes.fromhex(lease_id)
    elif LEASE_ID_RE.fullmatch(lease_id):
        try:
            entropy = base64.urlsafe_b64decode(lease_id + "=" * (-len(lease_id) % 4))
        except (ValueError, TypeError):
            errors.append("database.baseline_lease_id must be valid base64url")
    else:
        errors.append(
            "database.baseline_lease_id must be UUIDv4 or 128+ bits of hex/base64url entropy"
        )

    if entropy is not None and (len(entropy) < 16 or len(set(entropy)) < 8):
        errors.append("database.baseline_lease_id is too weak or predictable")
    predictable = {
        code_sha,
        code_sha[:32],
        hashlib.sha256(code_sha.encode()).hexdigest(),
        hashlib.sha256(branch.encode()).hexdigest(),
        hashlib.sha256(f"{branch}\x1f{code_sha}".encode()).hexdigest(),
        hashlib.sha256(task_id.encode()).hexdigest(),
    }
    normalized = lease_id.lower().replace("-", "").replace("_", "")
    if normalized in {item.lower().replace("-", "").replace("_", "") for item in predictable}:
        errors.append("database.baseline_lease_id must not be derived from the target")
    if code_sha[:12] and code_sha[:12] in lease_id.lower():
        errors.append("database.baseline_lease_id must not contain the target SHA")
    return lease_id


def _validate_observation_time(
    observed: datetime | None,
    field: str,
    generated_at: datetime | None,
    errors: list[str],
    *,
    require_recent: bool,
) -> None:
    if observed is None or generated_at is None:
        return
    if observed > generated_at + FUTURE_SKEW:
        errors.append(f"{field} cannot be later than generated_at")
    if require_recent and generated_at - observed > MAX_DEPLOYMENT_AGE:
        errors.append(f"{field} is stale")


def validate_manifest(
    manifest: object,
    *,
    expected_sha: str | None = None,
    expected_task_id: str | None = None,
    expected_workflow_run_id: int | None = None,
    expected_repository: str | None = None,
    expected_branch: str | None = None,
    expected_workflow_sha: str | None = None,
    expected_default_branch: str | None = None,
    expected_baseline_lease_id: str | None = None,
    now: datetime | None = None,
    enforce_freshness: bool = True,
) -> list[str]:
    errors: list[str] = []
    root = _mapping(manifest, "manifest", errors)
    if root.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    if root.get("evidence_type") != "provider-verified-isolated-preview":
        errors.append("evidence_type must be provider-verified-isolated-preview")

    task_id = _non_empty(root.get("task_id"), "task_id", errors)
    if expected_task_id and task_id != expected_task_id:
        errors.append("task_id does not match expected task")
    code_sha = _non_empty(root.get("code_sha"), "code_sha", errors)
    if code_sha and not SHA_RE.fullmatch(code_sha):
        errors.append("code_sha must be a full 40- or 64-character Git SHA")
    if expected_sha and code_sha != expected_sha:
        errors.append("code_sha does not match expected SHA")
    generated_at = _timestamp(root.get("generated_at"), "generated_at", errors)
    reference_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if enforce_freshness and generated_at:
        if generated_at > reference_time + FUTURE_SKEW:
            errors.append("generated_at is in the future")
        if reference_time - generated_at > MAX_MANIFEST_AGE:
            errors.append("generated_at is stale")

    generated_by = _mapping(root.get("generated_by"), "generated_by", errors)
    if generated_by.get("kind") != "provider-api-verifier":
        errors.append("generated_by.kind must be provider-api-verifier")
    workflow_run_id = generated_by.get("workflow_run_id")
    if not isinstance(workflow_run_id, int) or isinstance(workflow_run_id, bool) or workflow_run_id <= 0:
        errors.append("generated_by.workflow_run_id must be a positive integer")
    if expected_workflow_run_id is not None and workflow_run_id != expected_workflow_run_id:
        errors.append("generated_by.workflow_run_id does not match the evidence artifact run")
    if generated_by.get("workflow_path") != EXPECTED_WORKFLOW_PATH:
        errors.append(f"generated_by.workflow_path must be {EXPECTED_WORKFLOW_PATH}")
    if generated_by.get("github_environment") != EXPECTED_ENVIRONMENT:
        errors.append(f"generated_by.github_environment must be {EXPECTED_ENVIRONMENT}")
    if generated_by.get("event_name") != "workflow_dispatch":
        errors.append("generated_by.event_name must be workflow_dispatch")
    actor_id = _non_empty(generated_by.get("actor_id"), "generated_by.actor_id", errors)
    if actor_id and not actor_id.isdigit():
        errors.append("generated_by.actor_id must be numeric")
    repository = _non_empty(generated_by.get("repository"), "generated_by.repository", errors)
    branch = _non_empty(generated_by.get("git_branch"), "generated_by.git_branch", errors)
    if generated_by.get("target_ref_verified_by") != "github-api":
        errors.append("generated_by.target_ref_verified_by must be github-api")
    workflow_code_sha = _non_empty(
        generated_by.get("workflow_code_sha"), "generated_by.workflow_code_sha", errors
    )
    if workflow_code_sha and not SHA_RE.fullmatch(workflow_code_sha):
        errors.append("generated_by.workflow_code_sha must be a full Git SHA")
    workflow_git_branch = _non_empty(
        generated_by.get("workflow_git_branch"), "generated_by.workflow_git_branch", errors
    )
    if workflow_git_branch and workflow_git_branch == branch:
        errors.append("trusted workflow branch must differ from the target branch")
    if expected_workflow_sha and workflow_code_sha != expected_workflow_sha:
        errors.append("generated_by.workflow_code_sha does not match the trusted workflow run")
    if expected_default_branch and workflow_git_branch != expected_default_branch:
        errors.append("generated_by.workflow_git_branch does not match the repository default branch")
    if expected_repository and repository.lower() != expected_repository.lower():
        errors.append("generated_by.repository does not match expected repository")
    if expected_branch and branch != expected_branch:
        errors.append("generated_by.git_branch does not match expected branch")
    sources = generated_by.get("evidence_sources")
    if (
        not isinstance(sources, list)
        or len(sources) != 3
        or not all(isinstance(source, str) for source in sources)
        or set(sources) != EXPECTED_SOURCES
    ):
        errors.append("generated_by.evidence_sources must contain exactly Render, Supabase, and Vercel APIs")

    app_url = _https_preview_url(
        root.get("app_url"), "app_url", errors, allowed_paths={"", "/"}, provider_suffix="vercel.app"
    )
    api_origin = _https_preview_url(
        root.get("api_origin"), "api_origin", errors, allowed_paths={"", "/"}, provider_suffix="onrender.com"
    )
    api_base_url = _https_preview_url(
        root.get("api_base_url"), "api_base_url", errors, allowed_paths={"", "/", "/api", "/api/"}, provider_suffix="onrender.com"
    )
    health_url = _https_preview_url(
        root.get("health_url"), "health_url", errors, allowed_paths={"/health"}, provider_suffix="onrender.com"
    )
    vite_api_url = _https_preview_url(
        root.get("frontend_vite_api_url"), "frontend_vite_api_url", errors,
        allowed_paths={"", "/", "/api", "/api/"}, provider_suffix="onrender.com",
    )
    if api_origin and api_base_url not in {api_origin, f"{api_origin}/api"}:
        errors.append("api_base_url must equal api_origin or api_origin + /api")
    if api_base_url and vite_api_url != api_base_url:
        errors.append("frontend_vite_api_url must exactly equal api_base_url")
    if api_origin and health_url != f"{api_origin}/health":
        errors.append("health_url must equal api_origin + /health")

    frontend = _mapping(root.get("frontend"), "frontend", errors)
    for field, expected in (
        ("provider", "vercel"), ("evidence_source", "vercel-api"), ("environment", "preview")
    ):
        if frontend.get(field) != expected:
            errors.append(f"frontend.{field} must be {expected}")
    _non_empty(frontend.get("deployment_id"), "frontend.deployment_id", errors)
    _non_empty(frontend.get("project_id"), "frontend.project_id", errors)
    _non_empty(frontend.get("team_id"), "frontend.team_id", errors)
    if frontend.get("code_sha") != code_sha:
        errors.append("frontend.code_sha must exactly equal code_sha")
    if frontend.get("git_branch") != branch:
        errors.append("frontend.git_branch must exactly equal generated_by.git_branch")
    deployment_url = _https_preview_url(
        frontend.get("deployment_url"), "frontend.deployment_url", errors,
        allowed_paths={"", "/"}, provider_suffix="vercel.app",
    )
    frontend_ready = _timestamp(frontend.get("ready_at"), "frontend.ready_at", errors)
    _validate_observation_time(frontend_ready, "frontend.ready_at", generated_at, errors, require_recent=True)

    backend = _mapping(root.get("backend"), "backend", errors)
    for field, expected in (
        ("provider", "render"), ("evidence_source", "render-api"), ("environment", "preview")
    ):
        if backend.get(field) != expected:
            errors.append(f"backend.{field} must be {expected}")
    if backend.get("service_url") != api_origin:
        errors.append("backend.service_url must exactly equal api_origin")
    service_id = _non_empty(backend.get("service_id"), "backend.service_id", errors)
    production_service_id = _non_empty(backend.get("production_service_id"), "backend.production_service_id", errors)
    if service_id and service_id == production_service_id:
        errors.append("backend preview service must differ from the production service")
    _non_empty(backend.get("deployment_id"), "backend.deployment_id", errors)
    if backend.get("code_sha") != code_sha:
        errors.append("backend.code_sha must exactly equal code_sha")
    if backend.get("git_branch") != branch:
        errors.append("backend.git_branch must exactly equal generated_by.git_branch")
    backend_deployed = _timestamp(backend.get("deployment_finished_at"), "backend.deployment_finished_at", errors)
    backend_configured = _timestamp(backend.get("configuration_updated_at"), "backend.configuration_updated_at", errors)
    _validate_observation_time(backend_deployed, "backend.deployment_finished_at", generated_at, errors, require_recent=True)
    _validate_observation_time(backend_configured, "backend.configuration_updated_at", generated_at, errors, require_recent=False)

    database = _mapping(root.get("database"), "database", errors)
    if database.get("provider") != "supabase" or database.get("evidence_source") != "supabase-management-api":
        errors.append("database must be verified by supabase-management-api")
    branch_type = database.get("branch_type")
    if branch_type not in {"preview", "dedicated-qa-project"}:
        errors.append("database.branch_type must be preview or dedicated-qa-project")
    project_ref = _non_empty(database.get("project_ref"), "database.project_ref", errors)
    branch_ref = _non_empty(database.get("branch_ref"), "database.branch_ref", errors)
    production_ref = _non_empty(database.get("production_branch_ref"), "database.production_branch_ref", errors)
    if project_ref and project_ref == production_ref:
        errors.append("database QA project must differ from production")
    if branch_ref and branch_ref == production_ref:
        errors.append("database preview branch must differ from production")
    if project_ref and branch_ref and project_ref != branch_ref:
        errors.append("database.project_ref must exactly equal database.branch_ref")
    if database.get("git_branch") != branch:
        errors.append("database.git_branch must exactly equal generated_by.git_branch")
    if branch_type == "dedicated-qa-project":
        # This proves exclusive, serialized use of one QA baseline only.  It
        # must never be interpreted as branch-per-PR isolation; permanent
        # parallel previews require Supabase Branches.
        if database.get("isolation_mode") != "dedicated-qa-baseline-exclusive":
            errors.append(
                "database.isolation_mode must be dedicated-qa-baseline-exclusive for dedicated QA"
            )
        lease_id = _validate_baseline_lease_id(
            database.get("baseline_lease_id"), code_sha, branch, task_id, errors
        )
        if database.get("baseline_lease_target_sha") != code_sha:
            errors.append("database.baseline_lease_target_sha must exactly equal code_sha")
        if database.get("baseline_lease_target_branch") != branch:
            errors.append(
                "database.baseline_lease_target_branch must exactly equal generated_by.git_branch"
            )
        if expected_baseline_lease_id is not None and lease_id != expected_baseline_lease_id:
            errors.append("database.baseline_lease_id does not match the trusted workflow lease")
    elif branch_type == "preview":
        if database.get("isolation_mode") != "supabase-branch-per-target":
            errors.append(
                "database.isolation_mode must be supabase-branch-per-target for a real preview branch"
            )
        for field in sorted(BASELINE_LEASE_FIELDS):
            if field in database:
                errors.append(f"database.{field} is forbidden for real Supabase branch mode")
        if expected_baseline_lease_id is not None:
            errors.append("trusted baseline lease cannot be used with real Supabase branch mode")
    if database.get("with_data") is not False:
        errors.append("database.with_data must be false")
    if database.get("fingerprint_method") != "sha256":
        errors.append("database.fingerprint_method must be sha256")
    if database.get("fingerprint_payload_version") != "supabase-connection-v1":
        errors.append("database.fingerprint_payload_version must be supabase-connection-v1")
    preview_fingerprint = _non_empty(database.get("connection_fingerprint"), "database.connection_fingerprint", errors)
    production_fingerprint = _non_empty(
        database.get("production_connection_fingerprint"), "database.production_connection_fingerprint", errors
    )
    for field, value in (("connection_fingerprint", preview_fingerprint), ("production_connection_fingerprint", production_fingerprint)):
        if value and not FINGERPRINT_RE.fullmatch(value):
            errors.append(f"database.{field} must be an opaque sha256 fingerprint")
    if preview_fingerprint and preview_fingerprint == production_fingerprint:
        errors.append("database preview connection must differ from production")
    for field in ("database_endpoint_distinct", "database_password_distinct", "jwt_identity_distinct"):
        if database.get(field) is not True:
            errors.append(f"database.{field} must be true")
    if not isinstance(database.get("database_user_distinct"), bool):
        errors.append("database.database_user_distinct must be a boolean")
    database_updated = _timestamp(database.get("updated_at"), "database.updated_at", errors)
    _validate_observation_time(database_updated, "database.updated_at", generated_at, errors, require_recent=False)

    configuration = _mapping(root.get("configuration"), "configuration", errors)
    if configuration.get("evidence_source") != "render-api":
        errors.append("configuration.evidence_source must be render-api")
    if configuration.get("frontend_url") != app_url or configuration.get("cors_origins") != [app_url]:
        errors.append("configuration.frontend_url and configuration.cors_origins must match only app_url")
    environment_id = _non_empty(configuration.get("environment_id"), "configuration.environment_id", errors)
    production_environment_id = _non_empty(
        configuration.get("production_environment_id"), "configuration.production_environment_id", errors
    )
    if environment_id and environment_id == production_environment_id:
        errors.append("preview configuration environment must differ from production")
    if configuration.get("qa_secrets_scope") != "preview-service":
        errors.append("configuration.qa_secrets_scope must be preview-service")
    if configuration.get("values_redacted") is not True:
        errors.append("configuration.values_redacted must be true")
    names = configuration.get("required_secret_names_verified")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names) or not REQUIRED_SECRET_NAMES <= set(names):
        errors.append("configuration.required_secret_names_verified lacks required names")
    elif branch_type == "dedicated-qa-project" and not BASELINE_RENDER_ENV_NAMES <= set(names):
        errors.append(
            "configuration.required_secret_names_verified lacks dedicated baseline lease names"
        )
    elif branch_type == "preview" and BASELINE_RENDER_ENV_NAMES & set(names):
        errors.append(
            "configuration.required_secret_names_verified must not claim baseline lease names in branch mode"
        )
    distinct_names = configuration.get("distinct_from_production_verified")
    if not isinstance(distinct_names, list) or not {"DATABASE_URL", "JWT_SECRET"} <= set(distinct_names):
        errors.append("configuration.distinct_from_production_verified lacks required isolation")
    if configuration.get("distinctness_basis") != "provider-value-comparison-and-independent-resource-boundaries":
        errors.append(
            "configuration.distinctness_basis must use confidential provider value comparison "
            "and independent resource boundaries"
        )
    bootstrap_fingerprint = configuration.get("bootstrap_configuration_fingerprint")
    if not isinstance(bootstrap_fingerprint, str) or not FINGERPRINT_RE.fullmatch(
        bootstrap_fingerprint
    ):
        errors.append("configuration.bootstrap_configuration_fingerprint must be opaque sha256")
    if configuration.get("bootstrap_configuration_version") != BOOTSTRAP_CONFIGURATION_VERSION:
        errors.append(
            f"configuration.bootstrap_configuration_version must be {BOOTSTRAP_CONFIGURATION_VERSION}"
        )
    return errors


def _write_github_output(path: Path, manifest: dict[str, Any]) -> None:
    for key in ("app_url", "api_origin", "api_base_url", "health_url"):
        value = str(manifest[key]).rstrip("/")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{key}={value}\n")
    for key, url_key in (("app_host", "app_url"), ("api_host", "api_origin")):
        host = urlsplit(str(manifest[url_key])).hostname or ""
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{key}={host.rstrip('.').lower()}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-sha")
    parser.add_argument("--expected-task-id")
    parser.add_argument("--expected-workflow-run-id", type=int)
    parser.add_argument("--expected-repository")
    parser.add_argument("--expected-branch")
    parser.add_argument("--expected-workflow-sha")
    parser.add_argument("--expected-default-branch")
    parser.add_argument("--expected-baseline-lease-id")
    parser.add_argument("--skip-freshness", action="store_true")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Invalid preview manifest: {error}")
        return 1
    errors = validate_manifest(
        manifest,
        expected_sha=args.expected_sha,
        expected_task_id=args.expected_task_id,
        expected_workflow_run_id=args.expected_workflow_run_id,
        expected_repository=args.expected_repository,
        expected_branch=args.expected_branch,
        expected_workflow_sha=args.expected_workflow_sha,
        expected_default_branch=args.expected_default_branch,
        expected_baseline_lease_id=args.expected_baseline_lease_id,
        enforce_freshness=not args.skip_freshness,
    )
    if errors:
        print("Preview manifest rejected:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    if args.github_output:
        _write_github_output(args.github_output, manifest)
    print(
        "Preview provider evidence is target-bound, fresh, provenance-bound, "
        "and internally consistent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
