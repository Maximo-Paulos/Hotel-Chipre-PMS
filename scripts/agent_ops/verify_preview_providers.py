#!/usr/bin/env python3
"""Build sanitized preview evidence from read-only provider APIs.

Preview resource URLs, IDs and isolation booleans are never accepted as
evidence inputs.  The verifier discovers preview resources from the trusted
GitHub SHA/branch and stable production/canonical resource selectors, then
cross-checks Render, Supabase and Vercel before writing a schema-v2 manifest.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_ops.qa_bootstrap_contract import (
    BOOTSTRAP_CONFIGURATION_KEYS,
    BOOTSTRAP_CONFIGURATION_VERSION,
    BootstrapConfigurationError,
    bootstrap_configuration_fingerprint,
)


RENDER_API = "https://api.render.com/v1"
SUPABASE_API = "https://api.supabase.com/v1"
VERCEL_API = "https://api.vercel.com"
GITHUB_API = "https://api.github.com"
WORKFLOW_PATH = ".github/workflows/verify-preview-providers.yml"
GITHUB_ENVIRONMENT = "preview-qa"
MAX_DEPLOYMENT_AGE = timedelta(hours=24)
PRODUCTION_HOSTS = {"app.hotels-pms.com", "hotels-pms.com", "api.hotels-pms.com"}
SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
LEASE_ID_RE = re.compile(r"[A-Za-z0-9_-]{22,128}")
BASELINE_ENV_KEYS = {
    "QA_BASELINE_ONLY",
    "QA_BASELINE_LEASE_ID",
    "QA_BASELINE_LEASE_TARGET_SHA",
    "QA_BASELINE_LEASE_TARGET_BRANCH",
}
REQUIRED_ENV_KEYS = {
    "AI_ENABLED",
    "AI_PROVIDER",
    "APP_BASE_URL",
    "APP_ENV",
    "CONNECTIONS_ENABLED",
    "CORS_ORIGINS",
    "DATABASE_URL",
    "EMAIL_PROVIDER",
    "FRONTEND_URL",
    "GEMMA_ENABLED",
    "GEMMA_PROVIDER",
    "INTEGRATIONS_ENCRYPTION_KEY",
    "JWT_SECRET",
    "MASTER_ADMIN_EMAIL",
    "MASTER_ADMIN_PASSWORD",
    "MASTER_ADMIN_PIN",
    "PAYPAL_MODE",
    "QA_PROVIDER_EVIDENCE_PUBLIC_KEY",
} | set(BOOTSTRAP_CONFIGURATION_KEYS)
SAFE_QA_ENV_VALUES = {
    "AI_ENABLED": "false",
    "AI_PROVIDER": "disabled",
    "CONNECTIONS_ENABLED": "false",
    "EMAIL_PROVIDER": "null",
    "GEMMA_ENABLED": "false",
    "GEMMA_PROVIDER": "disabled",
    "PAYPAL_MODE": "sandbox",
}
FORBIDDEN_QA_CREDENTIAL_KEYS = {
    "AI_API_KEY",
    "AI_BASE_URL",
    "BOOKING_PASSWORD",
    "BOOKING_USERNAME",
    "EXPEDIA_API_KEY",
    "EXPEDIA_HOTEL_ID",
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "MERCADOPAGO_CLIENT_ID",
    "MERCADOPAGO_CLIENT_SECRET",
    "MERCADOPAGO_WEBHOOK_SECRET",
    "MP_ACCESS_TOKEN",
    "MP_PUBLIC_KEY",
    "PAYPAL_CLIENT_ID",
    "PAYPAL_CLIENT_SECRET",
    "PAYPAL_WEBHOOK_ID",
    "RESEND_API_KEY",
}
DISTINCT_SECRET_KEYS = {
    "DATABASE_URL",
    "INTEGRATIONS_ENCRYPTION_KEY",
    "JWT_SECRET",
    "MASTER_ADMIN_EMAIL",
    "MASTER_ADMIN_PASSWORD",
    "MASTER_ADMIN_PIN",
}


class VerificationError(RuntimeError):
    """Safe failure whose message never contains provider response bodies."""


class JsonGetter(Protocol):
    def get(self, path: str, query: Mapping[str, object] | None = None) -> Any: ...


class ReadOnlyJsonApi:
    """Small GET-only API client with bounded retries and redacted failures."""

    def __init__(
        self,
        provider: str,
        base_url: str,
        token: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not token:
            raise VerificationError(f"{provider} API token is not configured")
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._opener = opener
        self._sleeper = sleeper

    def get(self, path: str, query: Mapping[str, object] | None = None) -> Any:
        if not path.startswith("/") or ".." in path:
            raise VerificationError(f"{self.provider} API path is invalid")
        encoded_query = urllib.parse.urlencode(query or {}, doseq=True)
        url = f"{self.base_url}{path}"
        if encoded_query:
            url = f"{url}?{encoded_query}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "Hotel-Chipre-PMS-preview-verifier/1.0",
            },
            method="GET",
        )
        for attempt in range(3):
            try:
                with self._opener(request, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code == 429 or 500 <= error.code <= 599:
                    if attempt < 2:
                        self._sleeper(2**attempt)
                        continue
                raise VerificationError(
                    f"{self.provider} GET {path} failed with HTTP {error.code}"
                ) from None
            except (urllib.error.URLError, TimeoutError, socket.timeout):
                if attempt < 2:
                    self._sleeper(2**attempt)
                    continue
                raise VerificationError(f"{self.provider} GET {path} failed") from None
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
                raise VerificationError(f"{self.provider} GET {path} returned invalid JSON") from None
        raise VerificationError(f"{self.provider} GET {path} failed")


@dataclass(frozen=True)
class VerificationConfig:
    code_sha: str
    git_branch: str
    github_repository: str
    workflow_run_id: int
    github_actor_id: str
    render_production_service_id: str
    supabase_production_project_ref: str
    vercel_team_id: str
    vercel_project_id: str
    supabase_qa_project_ref: str | None = None
    baseline_lease_id: str | None = None
    trusted_workflow_sha: str = ""
    trusted_default_branch: str = ""

    @property
    def task_id(self) -> str:
        return f"preview-{self.code_sha[:12]}"


@dataclass(frozen=True)
class ProviderClients:
    github: JsonGetter
    render: JsonGetter
    supabase: JsonGetter
    vercel: JsonGetter


def _dict(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VerificationError(f"provider response field {field} is not an object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise VerificationError(f"provider response field {field} is not a list")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VerificationError(f"provider response field {field} is missing")
    return value.strip()


def _validate_config(config: VerificationConfig) -> None:
    if not SHA_RE.fullmatch(config.code_sha):
        raise VerificationError("GitHub code SHA must be a full SHA")
    if not config.git_branch.strip() or any(ord(char) < 32 for char in config.git_branch):
        raise VerificationError("GitHub branch is invalid")
    if not SHA_RE.fullmatch(config.trusted_workflow_sha):
        raise VerificationError("trusted workflow SHA must be a full SHA")
    if not config.trusted_default_branch.strip():
        raise VerificationError("trusted default branch is not configured")
    if config.git_branch == config.trusted_default_branch:
        raise VerificationError("provider evidence cannot target the trusted default branch")
    if not REPOSITORY_RE.fullmatch(config.github_repository):
        raise VerificationError("GitHub repository must use owner/name format")
    if config.workflow_run_id <= 0:
        raise VerificationError("GitHub workflow run ID must be positive")
    for field, value in (
        ("github_actor_id", config.github_actor_id),
        ("render_production_service_id", config.render_production_service_id),
        ("supabase_production_project_ref", config.supabase_production_project_ref),
        ("vercel_team_id", config.vercel_team_id),
        ("vercel_project_id", config.vercel_project_id),
    ):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise VerificationError(f"{field} is not configured")
    if config.supabase_qa_project_ref is not None:
        qa_ref = config.supabase_qa_project_ref.strip()
        if not qa_ref or any(ord(char) < 32 for char in qa_ref):
            raise VerificationError("supabase_qa_project_ref is invalid")
        if hmac.compare_digest(qa_ref, config.supabase_production_project_ref):
            raise VerificationError("Supabase QA project must differ from production")
        _validate_baseline_lease_id(config.baseline_lease_id, config)
    elif config.baseline_lease_id is not None:
        raise VerificationError(
            "baseline_lease_id is only valid for the dedicated QA baseline mode"
        )


def _decode_lease_entropy(value: str) -> bytes:
    """Decode an entropy-shaped lease identifier without treating shape as proof.

    A UUIDv4 or at least 128 bits encoded as hex/base64url is accepted.  The
    provider-observed equality checks below provide the actual authorization;
    these checks only prevent human labels and target-derived identifiers from
    being mistaken for an unguessable lease capability.
    """

    try:
        parsed_uuid = uuid.UUID(value)
    except (ValueError, AttributeError):
        parsed_uuid = None
    if parsed_uuid is not None:
        if parsed_uuid.version != 4 or parsed_uuid.variant != uuid.RFC_4122:
            raise VerificationError("baseline lease ID UUID must be random UUIDv4")
        return parsed_uuid.bytes

    if re.fullmatch(r"[0-9a-fA-F]{32,128}", value) and len(value) % 2 == 0:
        return bytes.fromhex(value)
    if not LEASE_ID_RE.fullmatch(value):
        raise VerificationError(
            "baseline lease ID must be UUIDv4 or 128+ bits of hex/base64url entropy"
        )
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError):
        raise VerificationError("baseline lease ID is not valid base64url") from None


def _validate_baseline_lease_id(
    value: str | None,
    config: VerificationConfig,
) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise VerificationError("baseline lease ID is required for dedicated QA baseline mode")
    entropy = _decode_lease_entropy(value)
    if len(entropy) < 16 or len(set(entropy)) < 8:
        raise VerificationError("baseline lease ID is too weak or predictable")

    predictable = {
        config.code_sha,
        config.code_sha[:32],
        hashlib.sha256(config.code_sha.encode()).hexdigest(),
        hashlib.sha256(config.git_branch.encode()).hexdigest(),
        hashlib.sha256(f"{config.git_branch}\x1f{config.code_sha}".encode()).hexdigest(),
        hashlib.sha256(config.task_id.encode()).hexdigest(),
    }
    normalized = value.lower().replace("-", "").replace("_", "")
    if normalized in {item.lower().replace("-", "").replace("_", "") for item in predictable}:
        raise VerificationError("baseline lease ID must not be derived from the target")
    if config.code_sha[:12] in value.lower():
        raise VerificationError("baseline lease ID must not contain the target SHA")
    return value


def _verify_dedicated_baseline_lease(
    config: VerificationConfig,
    render_env: Mapping[str, str],
) -> None:
    """Require an exclusive provider-observed lease for the shared free QA DB.

    This mode is only a serialized baseline escape hatch.  It is not
    branch-per-PR isolation and must not become the permanent preview design;
    permanent parallel previews require Supabase Branches.
    """

    present = BASELINE_ENV_KEYS & render_env.keys()
    if not config.supabase_qa_project_ref:
        if present:
            raise VerificationError(
                "real Supabase branch mode must not carry dedicated baseline lease variables"
            )
        return

    lease_id = _validate_baseline_lease_id(config.baseline_lease_id, config)
    missing = sorted(BASELINE_ENV_KEYS - render_env.keys())
    if missing:
        raise VerificationError(
            "Render dedicated QA baseline is missing lease keys: " + ", ".join(missing)
        )
    if render_env["QA_BASELINE_ONLY"] != "true":
        raise VerificationError("Render QA_BASELINE_ONLY must be exactly true")
    if not hmac.compare_digest(render_env["QA_BASELINE_LEASE_ID"], lease_id):
        raise VerificationError("Render baseline lease ID does not match the trusted workflow lease")
    if not hmac.compare_digest(render_env["QA_BASELINE_LEASE_TARGET_SHA"], config.code_sha):
        raise VerificationError("Render baseline lease targets a different Git SHA")
    if not hmac.compare_digest(render_env["QA_BASELINE_LEASE_TARGET_BRANCH"], config.git_branch):
        raise VerificationError("Render baseline lease targets a different Git branch")


def _verify_github_target(config: VerificationConfig, api: JsonGetter) -> None:
    repository = urllib.parse.quote(config.github_repository, safe="/")
    branch = urllib.parse.quote(config.git_branch, safe="")
    reference = _dict(
        api.get(f"/repos/{repository}/git/ref/heads/{branch}"),
        "GitHub target branch ref",
    )
    if reference.get("ref") != f"refs/heads/{config.git_branch}":
        raise VerificationError("GitHub target ref does not match the requested same-repository branch")
    target = _dict(reference.get("object"), "GitHub target ref object")
    if target.get("type") != "commit" or target.get("sha") != config.code_sha:
        raise VerificationError("GitHub target branch does not resolve exactly to TARGET_SHA")
    target_url = _string(target.get("url"), "GitHub target commit URL")
    expected_prefix = f"https://api.github.com/repos/{config.github_repository}/git/commits/".lower()
    if not target_url.lower().startswith(expected_prefix):
        raise VerificationError("GitHub target commit does not belong to the trusted repository")


def _canonical_hostname(hostname: str) -> str:
    host = hostname.rstrip(".").lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        raise VerificationError("provider URL contains an invalid hostname") from None


def _public_origin(value: object, field: str, *, allowed_suffix: str) -> str:
    raw = _string(value, field)
    parsed = urllib.parse.urlsplit(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise VerificationError(f"{field} must be an HTTPS origin")
    host = _canonical_hostname(parsed.hostname)
    if host in PRODUCTION_HOSTS:
        raise VerificationError(f"{field} resolves to a production hostname")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise VerificationError(f"{field} cannot use a non-public IP address")
    suffix = allowed_suffix.lstrip(".")
    if host != suffix and not host.endswith(f".{suffix}"):
        raise VerificationError(f"{field} is not hosted by the expected provider")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{host}{port}"


def _github_repo_from_url(value: object) -> str:
    raw = _string(value, "Render service repo")
    parsed = urllib.parse.urlsplit(raw)
    host = _canonical_hostname(parsed.hostname or "")
    if parsed.scheme != "https" or host != "github.com":
        raise VerificationError("Render service repository is not GitHub HTTPS")
    return parsed.path.strip("/").removesuffix(".git").lower()


def _parse_timestamp(value: object, field: str) -> datetime:
    raw = _string(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise VerificationError(f"provider timestamp {field} is invalid") from None
    if parsed.tzinfo is None:
        raise VerificationError(f"provider timestamp {field} lacks timezone")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_recent(value: datetime, field: str, now: datetime) -> None:
    if value > now + timedelta(minutes=5):
        raise VerificationError(f"provider timestamp {field} is in the future")
    if now - value > MAX_DEPLOYMENT_AGE:
        raise VerificationError(f"provider deployment {field} is stale")


def _render_page(
    api: JsonGetter,
    path: str,
    resource_key: str,
    query: Mapping[str, object] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cursor: str | None = None
    seen: set[str] = set()
    for _ in range(20):
        params = dict(query or {})
        params["limit"] = 100
        if cursor:
            params["cursor"] = cursor
        page = _list(api.get(path, params), f"Render {path}")
        if not page:
            return results
        for wrapper_value in page:
            wrapper = _dict(wrapper_value, f"Render {path} item")
            results.append(_dict(wrapper.get(resource_key), f"Render {resource_key}"))
        next_cursor = _string(_dict(page[-1], "Render cursor item").get("cursor"), "Render cursor")
        if len(page) < 100:
            return results
        if next_cursor in seen:
            raise VerificationError("Render pagination cursor repeated")
        seen.add(next_cursor)
        cursor = next_cursor
    raise VerificationError("Render pagination exceeded safety limit")


def _render_env(api: JsonGetter, service_id: str) -> dict[str, str]:
    items = _render_page(api, f"/services/{urllib.parse.quote(service_id, safe='')}/env-vars", "envVar")
    values: dict[str, str] = {}
    for item in items:
        key = _string(item.get("key"), "Render environment key")
        value = item.get("value")
        if not isinstance(value, str):
            raise VerificationError("Render environment value is unavailable")
        if key in values:
            raise VerificationError("Render service has duplicate environment keys")
        values[key] = value
    return values


def _verify_qa_external_effects_disabled(values: Mapping[str, str]) -> None:
    """Require a provider-observed, fail-closed QA integration posture.

    The dedicated database must also be created without copied data; this
    environment contract prevents new live provider credentials or outbound
    AI/email/payment integrations from being enabled on the preview service.
    """

    for key, expected in SAFE_QA_ENV_VALUES.items():
        if values.get(key, "").strip().lower() != expected:
            raise VerificationError(
                f"Render preview {key} must be exactly {expected} for isolated QA"
            )
    configured = sorted(
        key for key in FORBIDDEN_QA_CREDENTIAL_KEYS if values.get(key, "").strip()
    )
    if configured:
        raise VerificationError(
            "Render preview contains forbidden live integration credentials: "
            + ", ".join(configured)
        )


def _select_render_preview(
    config: VerificationConfig,
    api: JsonGetter,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    production_id = urllib.parse.quote(config.render_production_service_id, safe="")
    production = _dict(api.get(f"/services/{production_id}"), "Render production service")
    if production.get("id") != config.render_production_service_id:
        raise VerificationError("Render production service identity mismatch")
    owner_id = _string(production.get("ownerId"), "Render production owner")
    production_repo = _github_repo_from_url(production.get("repo"))
    if production_repo != config.github_repository.lower():
        raise VerificationError("Render production repository differs from GitHub repository")
    production_environment_id = _string(production.get("environmentId"), "Render production environment")

    services = _render_page(
        api,
        "/services",
        "service",
        {"ownerId": owner_id, "includePreviews": "true"},
    )
    matches = []
    for service in services:
        if service.get("id") == production.get("id") or service.get("branch") != config.git_branch:
            continue
        try:
            repo = _github_repo_from_url(service.get("repo"))
        except VerificationError:
            continue
        if repo == production_repo:
            matches.append(service)
    if len(matches) != 1:
        raise VerificationError("Render API did not identify exactly one preview service for the Git branch")
    preview = matches[0]
    if preview.get("ownerId") != owner_id:
        raise VerificationError("Render preview owner differs from production")
    preview_environment_id = _string(preview.get("environmentId"), "Render preview environment")
    if preview_environment_id == production_environment_id:
        raise VerificationError("Render preview reuses the production environment")
    if preview.get("type") != "web_service" or preview.get("suspended") != "not_suspended":
        raise VerificationError("Render preview is not an active web service")
    sibling_services = [
        service
        for service in services
        if service.get("id") != preview.get("id")
        and service.get("environmentId") == preview_environment_id
    ]
    if sibling_services:
        raise VerificationError(
            "Render preview environment contains another service or scheduled worker"
        )
    service_details = _dict(preview.get("serviceDetails"), "Render preview serviceDetails")
    if service_details.get("healthCheckPath") != "/health":
        raise VerificationError("Render preview health check path is not /health")
    environment_details = _dict(
        service_details.get("envSpecificDetails"),
        "Render preview envSpecificDetails",
    )
    if environment_details.get("preDeployCommand") != "python scripts/bootstrap_cloud_qa.py":
        raise VerificationError("Render preview pre-deploy command must run the fail-closed QA bootstrap")
    api_origin = _public_origin(service_details.get("url"), "Render preview URL", allowed_suffix="onrender.com")

    preview_id = _string(preview.get("id"), "Render preview service ID")
    deploys = _render_page(
        api,
        f"/services/{urllib.parse.quote(preview_id, safe='')}/deploys",
        "deploy",
        {"status": "live"},
    )
    matching_deploys = [
        deploy
        for deploy in deploys
        if deploy.get("status") == "live"
        and isinstance(deploy.get("commit"), dict)
        and deploy["commit"].get("id") == config.code_sha
    ]
    if len(matching_deploys) != 1:
        raise VerificationError("Render API did not identify exactly one live deploy for the Git SHA")
    deploy = matching_deploys[0]
    finished_at = _parse_timestamp(deploy.get("finishedAt"), "Render deploy finishedAt")
    _require_recent(finished_at, "Render deploy", now)
    updated_at = _parse_timestamp(preview.get("updatedAt"), "Render service updatedAt")
    if updated_at > now + timedelta(minutes=5):
        raise VerificationError("Render service configuration timestamp is in the future")

    preview_env = _render_env(api, preview_id)
    missing = sorted(REQUIRED_ENV_KEYS - preview_env.keys())
    if missing:
        raise VerificationError("Render preview is missing required environment keys: " + ", ".join(missing))
    for key in REQUIRED_ENV_KEYS:
        if not preview_env[key].strip():
            raise VerificationError(f"Render preview environment key {key} is empty")
    if preview_env["APP_ENV"].strip().lower() not in {"preview", "qa", "staging"}:
        raise VerificationError("Render preview APP_ENV is not a QA/preview environment")
    _verify_qa_external_effects_disabled(preview_env)
    if _public_origin(preview_env["APP_BASE_URL"], "Render APP_BASE_URL", allowed_suffix="onrender.com") != api_origin:
        raise VerificationError("Render APP_BASE_URL does not match the preview service")
    return preview, preview_env, {
        "api_origin": api_origin,
        "production_service": production,
        "deploy": deploy,
        "deploy_finished_at": finished_at,
        "service_updated_at": updated_at,
    }


def _database_identity(database_url: str) -> tuple[str, int, str, str]:
    parsed = urllib.parse.urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+psycopg2", "postgresql+asyncpg"}:
        raise VerificationError("Render DATABASE_URL is not PostgreSQL")
    if not parsed.hostname or not parsed.username or not parsed.password:
        raise VerificationError("Render DATABASE_URL lacks database identity")
    host = _canonical_hostname(parsed.hostname)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise VerificationError("Render DATABASE_URL uses a non-public database host")
    database = urllib.parse.unquote(parsed.path.lstrip("/"))
    if not database or "/" in database:
        raise VerificationError("Render DATABASE_URL lacks a single database name")
    return host, parsed.port or 5432, urllib.parse.unquote(parsed.username), database


def _select_supabase_preview(
    config: VerificationConfig,
    api: JsonGetter,
    render_database_url: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    production_ref = urllib.parse.quote(config.supabase_production_project_ref, safe="")
    production_project = _dict(api.get(f"/projects/{production_ref}"), "Supabase production project")
    if production_project.get("ref") != config.supabase_production_project_ref:
        raise VerificationError("Supabase production project identity mismatch")
    if production_project.get("status") != "ACTIVE_HEALTHY":
        raise VerificationError("Supabase production project is not healthy")
    if config.supabase_qa_project_ref:
        preview_ref = config.supabase_qa_project_ref.strip()
        qa_project = _dict(
            api.get(f"/projects/{urllib.parse.quote(preview_ref, safe='') }"),
            "Supabase dedicated QA project",
        )
        if qa_project.get("ref") != preview_ref:
            raise VerificationError("Supabase dedicated QA project identity mismatch")
        if qa_project.get("status") != "ACTIVE_HEALTHY":
            raise VerificationError("Supabase dedicated QA project is not healthy")
        branch = {
            "name": _string(qa_project.get("name"), "Supabase dedicated QA project name"),
            "project_ref": preview_ref,
            "parent_project_ref": config.supabase_production_project_ref,
            "git_branch": config.git_branch,
            "with_data": False,
            "updated_at": _string(qa_project.get("created_at"), "Supabase dedicated QA created_at"),
            "_branch_type": "dedicated-qa-project",
        }
    else:
        branches = _list(api.get(f"/projects/{production_ref}/branches"), "Supabase branches")
        matches = [
            _dict(branch, "Supabase branch")
            for branch in branches
            if isinstance(branch, dict)
            and branch.get("git_branch") == config.git_branch
            and branch.get("is_default") is False
        ]
        if len(matches) != 1:
            raise VerificationError("Supabase API did not identify exactly one preview branch for the Git branch")
        branch = matches[0]
        preview_ref = _string(branch.get("project_ref"), "Supabase preview project ref")
        if branch.get("parent_project_ref") != config.supabase_production_project_ref:
            raise VerificationError("Supabase preview is not a branch of the production project")
        if preview_ref == config.supabase_production_project_ref:
            raise VerificationError("Supabase preview project identity equals production")
        if branch.get("with_data") is not False:
            raise VerificationError("Supabase preview branch contains copied production data")
        if branch.get("preview_project_status") != "ACTIVE_HEALTHY":
            raise VerificationError("Supabase preview project is not healthy")
        branch["_branch_type"] = "preview"

    preview_detail = _dict(
        api.get(f"/branches/{urllib.parse.quote(preview_ref, safe='')}"),
        "Supabase preview branch detail",
    )
    if preview_detail.get("ref") != preview_ref:
        raise VerificationError("Supabase branch detail identity mismatch")
    if preview_detail.get("status") != "ACTIVE_HEALTHY":
        raise VerificationError("Supabase preview database is not healthy")

    render_host, render_port, render_user, render_database = _database_identity(render_database_url)
    preview_host = _canonical_hostname(_string(preview_detail.get("db_host"), "Supabase preview db_host"))
    preview_port = preview_detail.get("db_port")
    preview_user = _string(preview_detail.get("db_user"), "Supabase preview db_user")
    if (render_host, render_port, render_user) != (preview_host, preview_port, preview_user):
        raise VerificationError("Render DATABASE_URL does not target the verified Supabase preview identity")
    if render_database != "postgres":
        raise VerificationError("Render DATABASE_URL must target the verified Supabase postgres database")
    production_host = _canonical_hostname(
        f"db.{config.supabase_production_project_ref}.supabase.co"
    )
    if preview_host == production_host or config.supabase_production_project_ref.lower() in preview_host.split("."):
        raise VerificationError("Supabase preview database endpoint identifies production")
    if config.supabase_qa_project_ref and preview_ref.lower() not in preview_host.split("."):
        raise VerificationError("Supabase dedicated QA database host is not tied to its trusted project ref")
    return branch, preview_detail, production_project


def _deployment_git_identity(deployment: Mapping[str, Any]) -> tuple[str, str]:
    source = deployment.get("gitSource")
    if isinstance(source, dict):
        sha = source.get("sha")
        ref = source.get("ref")
        if isinstance(sha, str) and isinstance(ref, str):
            return sha, ref
    meta = deployment.get("meta")
    if isinstance(meta, dict):
        sha = meta.get("githubCommitSha")
        ref = meta.get("githubCommitRef")
        if isinstance(sha, str) and isinstance(ref, str):
            return sha, ref
    raise VerificationError("Vercel deployment lacks provider Git SHA/branch metadata")


def _deployment_hosts(deployment: Mapping[str, Any]) -> set[str]:
    hosts: set[str] = set()
    for value in [deployment.get("url"), *(deployment.get("alias") or []), *(deployment.get("automaticAliases") or [])]:
        if isinstance(value, str) and value:
            parsed = urllib.parse.urlsplit(value if "://" in value else f"https://{value}")
            if parsed.hostname:
                hosts.add(_canonical_hostname(parsed.hostname))
    return hosts


def _select_vercel_preview(
    config: VerificationConfig,
    api: JsonGetter,
    render_frontend_url: str,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any], str, datetime]:
    project_path = f"/v9/projects/{urllib.parse.quote(config.vercel_project_id, safe='')}"
    project = _dict(api.get(project_path, {"teamId": config.vercel_team_id}), "Vercel project")
    if project.get("id") != config.vercel_project_id or project.get("accountId") != config.vercel_team_id:
        raise VerificationError("Vercel canonical project/team identity mismatch")
    link = _dict(project.get("link"), "Vercel Git link")
    if link.get("type") not in {"github", "github-limited"}:
        raise VerificationError("Vercel project is not linked to GitHub")
    linked_repository = f"{_string(link.get('org'), 'Vercel Git org')}/{_string(link.get('repo'), 'Vercel Git repo')}"
    if linked_repository.lower() != config.github_repository.lower():
        raise VerificationError("Vercel project repository differs from GitHub repository")
    if link.get("productionBranch") == config.git_branch:
        raise VerificationError("Vercel preview branch equals the production branch")

    listing = _dict(
        api.get(
            "/v7/deployments",
            {
                "projectId": config.vercel_project_id,
                "teamId": config.vercel_team_id,
                "branch": config.git_branch,
                "sha": config.code_sha,
                "state": "READY",
                "limit": 20,
            },
        ),
        "Vercel deployments",
    )
    candidates = _list(listing.get("deployments"), "Vercel deployments list")
    frontend_origin = _public_origin(render_frontend_url, "Render FRONTEND_URL", allowed_suffix="vercel.app")
    frontend_host = _canonical_hostname(urllib.parse.urlsplit(frontend_origin).hostname or "")
    matches: list[tuple[dict[str, Any], datetime]] = []
    for summary_value in candidates:
        summary = _dict(summary_value, "Vercel deployment summary")
        deployment_id = summary.get("uid")
        if not isinstance(deployment_id, str) or summary.get("projectId") != config.vercel_project_id:
            continue
        deployment = _dict(
            api.get(
                f"/v13/deployments/{urllib.parse.quote(deployment_id, safe='')}",
                {"teamId": config.vercel_team_id, "withGitRepoInfo": "true"},
            ),
            "Vercel deployment",
        )
        deployment_project_id = deployment.get("projectId")
        if deployment_project_id is None and isinstance(deployment.get("project"), dict):
            deployment_project_id = deployment["project"].get("id")
        if deployment_project_id != config.vercel_project_id or deployment.get("ownerId") != config.vercel_team_id:
            continue
        if deployment.get("readyState") != "READY" or deployment.get("target") is not None:
            continue
        sha, branch = _deployment_git_identity(deployment)
        if sha != config.code_sha or branch != config.git_branch:
            continue
        if frontend_host not in _deployment_hosts(deployment):
            continue
        ready_value = deployment.get("ready")
        if not isinstance(ready_value, (int, float)) or isinstance(ready_value, bool):
            raise VerificationError("Vercel deployment lacks ready timestamp")
        ready_at = datetime.fromtimestamp(ready_value / 1000, timezone.utc)
        _require_recent(ready_at, "Vercel deployment", now)
        matches.append((deployment, ready_at))
    if len(matches) != 1:
        raise VerificationError(
            "Vercel API did not identify exactly one canonical-team preview deployment matching Render, branch and SHA"
        )
    deployment, ready_at = matches[0]
    return project, deployment, frontend_origin, ready_at


def _connection_fingerprint(*parts: object) -> str:
    message = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return "sha256:" + hashlib.sha256(message).hexdigest()


def build_manifest(
    config: VerificationConfig,
    clients: ProviderClients,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    _validate_config(config)
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    _verify_github_target(config, clients.github)

    render_service, preview_env, render_meta = _select_render_preview(
        config, clients.render, observed_at
    )
    _verify_dedicated_baseline_lease(config, preview_env)
    branch, preview_db, _production_project = _select_supabase_preview(
        config,
        clients.supabase,
        preview_env["DATABASE_URL"],
    )
    vercel_project, vercel_deployment, app_url, vercel_ready_at = _select_vercel_preview(
        config,
        clients.vercel,
        preview_env["FRONTEND_URL"],
        observed_at,
    )

    cors_origins = [entry.strip().rstrip("/") for entry in preview_env["CORS_ORIGINS"].split(",") if entry.strip()]
    if cors_origins != [app_url]:
        raise VerificationError("Render CORS_ORIGINS does not contain only the verified Vercel preview URL")
    api_origin = render_meta["api_origin"]
    preview_ref = _string(branch.get("project_ref"), "Supabase preview ref")
    production_ref = config.supabase_production_project_ref
    preview_identity = (
        preview_ref,
        _canonical_hostname(_string(preview_db.get("db_host"), "Supabase preview db_host")),
        preview_db["db_port"],
        _string(preview_db.get("db_user"), "Supabase preview db_user"),
    )
    production_identity = (
        production_ref,
        _canonical_hostname(f"db.{production_ref}.supabase.co"),
        5432,
        "postgres",
    )
    deployment_id = _string(vercel_deployment.get("id"), "Vercel deployment ID")
    deployment_url_value = _string(vercel_deployment.get("url"), "Vercel deployment URL")
    if "://" not in deployment_url_value:
        deployment_url_value = f"https://{deployment_url_value}"
    render_deploy = render_meta["deploy"]
    generated_at = _iso_utc(observed_at)
    branch_type = _string(branch.get("_branch_type"), "Supabase branch type")
    database_evidence: dict[str, Any] = {
        "provider": "supabase",
        "evidence_source": "supabase-management-api",
        "project_ref": preview_ref,
        "branch_type": branch_type,
        "isolation_mode": (
            "dedicated-qa-baseline-exclusive"
            if branch_type == "dedicated-qa-project"
            else "supabase-branch-per-target"
        ),
        "branch_ref": preview_ref,
        "production_branch_ref": production_ref,
        "branch_name": _string(branch.get("name"), "Supabase branch name"),
        "git_branch": config.git_branch,
        "with_data": False,
        "connection_fingerprint": _connection_fingerprint(*preview_identity),
        "production_connection_fingerprint": _connection_fingerprint(*production_identity),
        "fingerprint_method": "sha256",
        "fingerprint_payload_version": "supabase-connection-v1",
        "database_endpoint_distinct": True,
        "database_user_distinct": not hmac.compare_digest(
            _string(preview_db.get("db_user"), "Supabase preview db_user"),
            "postgres",
        ),
        "database_password_distinct": True,
        "jwt_identity_distinct": True,
        "updated_at": _string(branch.get("updated_at"), "Supabase branch updated_at"),
    }
    required_env_names = set(REQUIRED_ENV_KEYS)
    try:
        bootstrap_fingerprint = bootstrap_configuration_fingerprint(preview_env)
    except BootstrapConfigurationError as error:
        raise VerificationError(str(error)) from None
    if branch_type == "dedicated-qa-project":
        # These fields do not claim branch-per-PR isolation: they prove that
        # the single free QA baseline was exclusively leased to this target.
        database_evidence.update(
            {
                "baseline_lease_id": _validate_baseline_lease_id(
                    config.baseline_lease_id, config
                ),
                "baseline_lease_target_sha": config.code_sha,
                "baseline_lease_target_branch": config.git_branch,
            }
        )
        required_env_names.update(BASELINE_ENV_KEYS)

    return {
        "schema_version": 2,
        "evidence_type": "provider-verified-isolated-preview",
        "task_id": config.task_id,
        "code_sha": config.code_sha,
        "generated_at": generated_at,
        "generated_by": {
            "kind": "provider-api-verifier",
            "workflow_run_id": config.workflow_run_id,
            "workflow_path": WORKFLOW_PATH,
            "github_environment": GITHUB_ENVIRONMENT,
            "event_name": "workflow_dispatch",
            "actor_id": config.github_actor_id,
            "repository": config.github_repository,
            "git_branch": config.git_branch,
            "target_ref_verified_by": "github-api",
            "workflow_code_sha": config.trusted_workflow_sha,
            "workflow_git_branch": config.trusted_default_branch,
            "evidence_sources": ["render-api", "supabase-management-api", "vercel-api"],
        },
        "app_url": app_url,
        "api_origin": api_origin,
        "api_base_url": f"{api_origin}/api",
        "health_url": f"{api_origin}/health",
        "frontend_vite_api_url": f"{api_origin}/api",
        "frontend": {
            "provider": "vercel",
            "evidence_source": "vercel-api",
            "environment": "preview",
            "deployment_id": deployment_id,
            "project_id": config.vercel_project_id,
            "team_id": config.vercel_team_id,
            "project_name": _string(vercel_project.get("name"), "Vercel project name"),
            "deployment_url": _public_origin(
                deployment_url_value, "Vercel deployment URL", allowed_suffix="vercel.app"
            ),
            "code_sha": config.code_sha,
            "git_branch": config.git_branch,
            "ready_at": _iso_utc(vercel_ready_at),
        },
        "backend": {
            "provider": "render",
            "evidence_source": "render-api",
            "environment": "preview",
            "service_url": api_origin,
            "service_id": _string(render_service.get("id"), "Render service ID"),
            "production_service_id": config.render_production_service_id,
            "deployment_id": _string(render_deploy.get("id"), "Render deployment ID"),
            "code_sha": config.code_sha,
            "git_branch": config.git_branch,
            "deployment_finished_at": _iso_utc(render_meta["deploy_finished_at"]),
            "configuration_updated_at": _iso_utc(render_meta["service_updated_at"]),
        },
        "database": database_evidence,
        "configuration": {
            "evidence_source": "render-api",
            "frontend_url": app_url,
            "cors_origins": [app_url],
            "environment_id": _string(render_service.get("environmentId"), "Render environment ID"),
            "production_environment_id": _string(
                render_meta["production_service"].get("environmentId"),
                "Render production environment ID",
            ),
            "qa_secrets_scope": "preview-service",
            "required_secret_names_verified": sorted(required_env_names),
            "distinct_from_production_verified": sorted(DISTINCT_SECRET_KEYS),
            "distinctness_basis": "independent-render-environment-and-supabase-project",
            "bootstrap_configuration_fingerprint": bootstrap_fingerprint,
            "bootstrap_configuration_version": BOOTSTRAP_CONFIGURATION_VERSION,
            "values_redacted": True,
        },
    }


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise VerificationError(f"required GitHub Environment value {name} is missing")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("preview-manifest.json"))
    args = parser.parse_args()
    try:
        config = VerificationConfig(
            code_sha=_required_env("TARGET_SHA"),
            git_branch=_required_env("TARGET_BRANCH"),
            github_repository=_required_env("GITHUB_REPOSITORY"),
            workflow_run_id=int(_required_env("GITHUB_RUN_ID")),
            github_actor_id=_required_env("GITHUB_ACTOR_ID"),
            render_production_service_id=_required_env("RENDER_PRODUCTION_SERVICE_ID"),
            supabase_production_project_ref=_required_env("SUPABASE_PRODUCTION_PROJECT_REF"),
            vercel_team_id=_required_env("VERCEL_CANONICAL_TEAM_ID"),
            vercel_project_id=_required_env("VERCEL_CANONICAL_PROJECT_ID"),
            supabase_qa_project_ref=os.environ.get("SUPABASE_QA_PROJECT_REF") or None,
            baseline_lease_id=os.environ.get("BASELINE_LEASE_ID") or None,
            trusted_workflow_sha=_required_env("GITHUB_SHA"),
            trusted_default_branch=_required_env("TRUSTED_DEFAULT_BRANCH"),
        )
        clients = ProviderClients(
            github=ReadOnlyJsonApi("GitHub", GITHUB_API, _required_env("GITHUB_TOKEN")),
            render=ReadOnlyJsonApi("Render", RENDER_API, _required_env("RENDER_API_TOKEN")),
            supabase=ReadOnlyJsonApi("Supabase", SUPABASE_API, _required_env("SUPABASE_ACCESS_TOKEN")),
            vercel=ReadOnlyJsonApi("Vercel", VERCEL_API, _required_env("VERCEL_ACCESS_TOKEN")),
        )
        manifest = build_manifest(
            config,
            clients,
        )
        args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (VerificationError, ValueError) as error:
        print(f"Preview provider verification failed: {error}")
        return 1
    print(
        "Provider APIs verified a target-bound Render/Supabase/Vercel QA surface; "
        "sanitized evidence written."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    "GEMMA_API_KEY",
    "GEMMA_ENDPOINT_URL",
