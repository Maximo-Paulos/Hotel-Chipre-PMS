#!/usr/bin/env python3
"""Install one short-lived QA capability on a verified Render preview only."""

from __future__ import annotations

import argparse
import base64
import hashlib
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
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_ops.qa_bootstrap_contract import (
    BOOTSTRAP_CONFIGURATION_VERSION,
    BootstrapConfigurationError,
    bootstrap_configuration_fingerprint,
)


RENDER_API = "https://api.render.com/v1"
SHA_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
TERMINAL_FAILURES = {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}
EXPECTED_PRE_DEPLOY_COMMAND = "python scripts/bootstrap_cloud_qa.py"
POSTGRES_SCHEMES = {
    "postgres",
    "postgresql",
    "postgresql+psycopg2",
    "postgresql+asyncpg",
}
BASELINE_LEASE_ENV_KEYS = {
    "QA_BASELINE_ONLY",
    "QA_BASELINE_LEASE_ID",
    "QA_BASELINE_LEASE_TARGET_SHA",
    "QA_BASELINE_LEASE_TARGET_BRANCH",
}


class ProvisionError(RuntimeError):
    pass


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _decode_token_payload(token: str) -> dict[str, Any]:
    parts = token.strip().split(".")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in parts):
        raise ProvisionError("QA bootstrap capability format is invalid")
    try:
        raw = base64.urlsafe_b64decode(parts[0] + "=" * (-len(parts[0]) % 4))
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise ProvisionError("QA bootstrap capability payload is invalid") from None
    if not isinstance(payload, dict):
        raise ProvisionError("QA bootstrap capability payload is not an object")
    return payload


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProvisionError(f"Render {field} is invalid")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProvisionError(f"Render {field} is invalid")
    return value


def _canonical_hostname(value: str, field: str) -> str:
    try:
        return value.rstrip(".").lower().encode("idna").decode("ascii")
    except UnicodeError:
        raise ProvisionError(f"{field} hostname is invalid") from None


def _https_origin(value: object, field: str, *, suffix: str) -> str:
    raw = _string(value, field)
    parsed = urllib.parse.urlsplit(raw)
    host = _canonical_hostname(parsed.hostname or "", field)
    if (
        parsed.scheme != "https"
        or not host.endswith(f".{suffix}")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ProvisionError(f"{field} is not an exact provider HTTPS origin")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{host}{port}"


def _github_repository(value: object) -> str:
    raw = _string(value, "service repository")
    parsed = urllib.parse.urlsplit(raw)
    host = _canonical_hostname(parsed.hostname or "", "service repository")
    repository = parsed.path.strip("/").removesuffix(".git")
    if (
        parsed.scheme != "https"
        or host != "github.com"
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
    ):
        raise ProvisionError("Render service repository does not match trusted GitHub HTTPS identity")
    return repository.lower()


def _database_identity(database_url: str) -> tuple[str, int, str, str]:
    try:
        parsed = urllib.parse.urlsplit(database_url)
        port = parsed.port or 5432
    except ValueError:
        raise ProvisionError("Render QA DATABASE_URL identity is invalid") from None
    if parsed.scheme not in POSTGRES_SCHEMES or not parsed.hostname or not parsed.username or parsed.password is None:
        raise ProvisionError("Render QA DATABASE_URL identity is invalid")
    database = urllib.parse.unquote(parsed.path.lstrip("/"))
    if database != "postgres" or "/" in database:
        raise ProvisionError("Render QA DATABASE_URL must target database postgres")
    return (
        _canonical_hostname(parsed.hostname, "Render QA DATABASE_URL"),
        port,
        database,
        urllib.parse.unquote(parsed.username),
    )


def _connection_fingerprint(project_ref: str, host: str, port: int, username: str) -> str:
    payload = "\x1f".join((project_ref, host, str(port), username)).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _validate_baseline_lease_id(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProvisionError("baseline lease ID is required for dedicated QA baseline mode")
    try:
        parsed_uuid = uuid.UUID(value)
    except (ValueError, AttributeError):
        parsed_uuid = None
    if parsed_uuid is not None:
        if parsed_uuid.version != 4 or parsed_uuid.variant != uuid.RFC_4122:
            raise ProvisionError("baseline lease ID UUID must be random UUIDv4")
        entropy = parsed_uuid.bytes
    elif re.fullmatch(r"[0-9a-fA-F]{32,128}", value) and len(value) % 2 == 0:
        entropy = bytes.fromhex(value)
    elif re.fullmatch(r"[A-Za-z0-9_-]{22,128}", value):
        try:
            entropy = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        except (ValueError, TypeError):
            raise ProvisionError("baseline lease ID is not valid base64url") from None
    else:
        raise ProvisionError(
            "baseline lease ID must be UUIDv4 or 128+ bits of hex/base64url entropy"
        )
    if len(entropy) < 16 or len(set(entropy)) < 8:
        raise ProvisionError("baseline lease ID is too weak or predictable")
    return value


def _render_env_values(payload: object) -> dict[str, str]:
    if not isinstance(payload, list):
        raise ProvisionError("Render environment response is invalid")
    values: dict[str, str] = {}
    for wrapper in payload:
        item = _object(_object(wrapper, "environment item").get("envVar"), "environment variable")
        key = _string(item.get("key"), "environment variable key")
        value = item.get("value")
        if not isinstance(value, str) or key in values:
            raise ProvisionError("Render environment response is invalid or contains duplicate keys")
        values[key] = value
    return values


def _required_env(values: dict[str, str], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise ProvisionError(f"Render QA environment variable {name} is missing")
    return value


def _validate_current_render_target(
    manifest: dict[str, Any],
    *,
    target_sha: str,
    service_id: str,
    health_url: str,
    render: "RenderClient",
) -> None:
    """Re-read and bind every mutable Render input before any write.

    This intentionally performs all provider reads before the capability PUT.
    A mismatch therefore refuses the operation without changing Render state.
    """

    backend = _object(manifest.get("backend"), "manifest backend")
    configuration = _object(manifest.get("configuration"), "manifest configuration")
    database = _object(manifest.get("database"), "manifest database")
    generated_by = _object(manifest.get("generated_by"), "manifest generator")

    quoted_service = urllib.parse.quote(service_id, safe="")
    deployment_id = _string(backend.get("deployment_id"), "manifest deployment ID")
    quoted_deployment = urllib.parse.quote(deployment_id, safe="")

    # Fetch the three mutable provider surfaces first. No PUT/POST occurs until
    # the complete snapshot has passed every identity and configuration check.
    service = _object(render.request("GET", f"/services/{quoted_service}"), "service response")
    env_values = _render_env_values(
        render.request("GET", f"/services/{quoted_service}/env-vars")
    )
    deployment = _object(
        render.request("GET", f"/services/{quoted_service}/deploys/{quoted_deployment}"),
        "deployment response",
    )

    expected_environment_id = _string(configuration.get("environment_id"), "manifest environment ID")
    expected_repository = _string(generated_by.get("repository"), "manifest repository").lower()
    expected_branch = _string(generated_by.get("git_branch"), "manifest Git branch")
    if (
        service.get("id") != service_id
        or service.get("environmentId") != expected_environment_id
        or _github_repository(service.get("repo")) != expected_repository
        or service.get("branch") != expected_branch
        or backend.get("git_branch") != expected_branch
        or database.get("git_branch") != expected_branch
        or service.get("type") != "web_service"
        or service.get("suspended") != "not_suspended"
    ):
        raise ProvisionError("Render QA service identity, environment, repository, or branch drifted")

    api_origin = _https_origin(manifest.get("api_origin"), "manifest API origin", suffix="onrender.com")
    service_origin = _https_origin(backend.get("service_url"), "manifest service URL", suffix="onrender.com")
    current_origin = _https_origin(
        _object(service.get("serviceDetails"), "serviceDetails").get("url"),
        "service URL",
        suffix="onrender.com",
    )
    app_origin = _https_origin(manifest.get("app_url"), "manifest app URL", suffix="vercel.app")
    parsed_health = urllib.parse.urlsplit(health_url)
    expected_health_url = f"{api_origin}/health"
    if (
        service_origin != api_origin
        or current_origin != api_origin
        or health_url != expected_health_url
        or parsed_health.query
        or parsed_health.fragment
        or manifest.get("api_base_url") != f"{api_origin}/api"
        or manifest.get("frontend_vite_api_url") != f"{api_origin}/api"
        or configuration.get("frontend_url") != app_origin
        or configuration.get("cors_origins") != [app_origin]
    ):
        raise ProvisionError("Render QA service or frontend URLs drifted from provider evidence")

    service_details = _object(service.get("serviceDetails"), "serviceDetails")
    environment_details = _object(service_details.get("envSpecificDetails"), "envSpecificDetails")
    if (
        service_details.get("healthCheckPath") != parsed_health.path
        or parsed_health.path != "/health"
        or environment_details.get("preDeployCommand") != EXPECTED_PRE_DEPLOY_COMMAND
    ):
        raise ProvisionError("Render QA health path or pre-deploy bootstrap command drifted")

    expected_app_env = _string(backend.get("environment"), "manifest backend environment")
    if expected_app_env != "preview" or _required_env(env_values, "APP_ENV") != expected_app_env:
        raise ProvisionError("Render QA APP_ENV drifted from provider evidence")
    if _required_env(env_values, "APP_BASE_URL") != api_origin:
        raise ProvisionError("Render QA APP_BASE_URL drifted from provider evidence")
    if _required_env(env_values, "FRONTEND_URL") != app_origin:
        raise ProvisionError("Render QA FRONTEND_URL drifted from provider evidence")
    if _required_env(env_values, "CORS_ORIGINS") != app_origin:
        raise ProvisionError("Render QA CORS_ORIGINS drifted from provider evidence")
    if _required_env(env_values, "QA_DATABASE_ISOLATED").lower() != "true":
        raise ProvisionError("Render QA database is not explicitly isolated")
    try:
        current_bootstrap_fingerprint = bootstrap_configuration_fingerprint(env_values)
    except BootstrapConfigurationError as error:
        raise ProvisionError(str(error)) from None
    if (
        configuration.get("bootstrap_configuration_version")
        != BOOTSTRAP_CONFIGURATION_VERSION
        or configuration.get("bootstrap_configuration_fingerprint")
        != current_bootstrap_fingerprint
    ):
        raise ProvisionError("Render QA bootstrap configuration drifted from provider evidence")

    project_ref = _string(database.get("project_ref"), "manifest database project ref")
    if database.get("branch_ref") != project_ref or _required_env(env_values, "QA_DATABASE_BRANCH_REF") != project_ref:
        raise ProvisionError("Render QA database project/branch ref drifted from provider evidence")
    database_url = _required_env(env_values, "DATABASE_URL")
    host, port, database_name, username = _database_identity(database_url)
    if (
        _canonical_hostname(_required_env(env_values, "QA_EXPECTED_DATABASE_HOST"), "expected database") != host
        or _required_env(env_values, "QA_EXPECTED_DATABASE_PORT") != str(port)
        or _required_env(env_values, "QA_EXPECTED_DATABASE_NAME") != database_name
        or _required_env(env_values, "QA_EXPECTED_DATABASE_USER") != username
    ):
        raise ProvisionError("Render QA DATABASE_URL host, port, database, or user drifted")
    expected_fingerprint = _string(database.get("connection_fingerprint"), "manifest database fingerprint")
    if _connection_fingerprint(project_ref, host, port, username) != expected_fingerprint:
        raise ProvisionError("Render QA DATABASE_URL fingerprint drifted from provider evidence")

    branch_type = _string(database.get("branch_type"), "manifest database branch type")
    isolation_mode = _string(database.get("isolation_mode"), "manifest database isolation mode")
    lease_fields = (
        "baseline_lease_id",
        "baseline_lease_target_sha",
        "baseline_lease_target_branch",
    )
    present_lease_env = BASELINE_LEASE_ENV_KEYS & env_values.keys()
    if branch_type == "preview":
        if isolation_mode != "supabase-branch-per-target" or any(
            field in database for field in lease_fields
        ):
            raise ProvisionError("Render QA per-branch isolation contract drifted")
        if present_lease_env:
            raise ProvisionError(
                "Render QA per-branch target carries dedicated baseline lease variables"
            )
    elif branch_type == "dedicated-qa-project":
        if isolation_mode != "dedicated-qa-baseline-exclusive":
            raise ProvisionError("Render dedicated QA baseline isolation mode drifted")
        lease_id = _validate_baseline_lease_id(database.get("baseline_lease_id"))
        lease_target_sha = _string(
            database.get("baseline_lease_target_sha"),
            "manifest baseline lease target SHA",
        )
        lease_target_branch = _string(
            database.get("baseline_lease_target_branch"),
            "manifest baseline lease target branch",
        )
        if lease_target_sha != target_sha or lease_target_branch != expected_branch:
            raise ProvisionError("Render dedicated QA baseline lease targets another task")
        if BASELINE_LEASE_ENV_KEYS - env_values.keys():
            raise ProvisionError("Render dedicated QA baseline lease variables are incomplete")
        if (
            env_values["QA_BASELINE_ONLY"] != "true"
            or env_values["QA_BASELINE_LEASE_ID"] != lease_id
            or env_values["QA_BASELINE_LEASE_TARGET_SHA"] != lease_target_sha
            or env_values["QA_BASELINE_LEASE_TARGET_BRANCH"] != lease_target_branch
        ):
            raise ProvisionError("Render dedicated QA baseline lease drifted")
    else:
        raise ProvisionError("Render QA database branch type is unsupported")

    if (
        deployment.get("id") != deployment_id
        or deployment.get("status") != "live"
        or not isinstance(deployment.get("commit"), dict)
        or deployment["commit"].get("id") != target_sha
    ):
        raise ProvisionError("Render QA current deployment drifted from provider evidence")


def _deployment_became_live(payload: object, *, deploy_id: str, target_sha: str) -> bool:
    deployment = _object(payload, "bootstrap deployment response")
    if deployment.get("id") != deploy_id:
        raise ProvisionError("Render returned a different QA bootstrap deployment identity")
    commit = deployment.get("commit")
    if not isinstance(commit, dict) or commit.get("id") != target_sha:
        raise ProvisionError("Render QA bootstrap deployment commit does not match the target SHA")
    status = deployment.get("status")
    if not isinstance(status, str) or not status:
        raise ProvisionError("Render QA bootstrap deployment status is invalid")
    if status in TERMINAL_FAILURES:
        raise ProvisionError("Render QA deploy failed before bootstrap completed")
    if status != "live":
        return False
    if not isinstance(deployment.get("finishedAt"), str) or not deployment["finishedAt"]:
        raise ProvisionError("Render QA live deployment has no completion timestamp")
    # Render cannot publish `live` after this service's configured pre-deploy
    # command fails: that path terminates as `pre_deploy_failed`. Because the
    # exact command was revalidated immediately before the deploy request,
    # `live` proves the fail-closed bootstrap completed for this exact commit.
    return True


def validate_capability(
    manifest: dict[str, Any], token: str, *, target_sha: str, production_service_id: str, now: int
) -> tuple[str, str]:
    payload = _decode_token_payload(token)
    backend = manifest.get("backend") if isinstance(manifest.get("backend"), dict) else {}
    configuration = manifest.get("configuration") if isinstance(manifest.get("configuration"), dict) else {}
    database = manifest.get("database") if isinstance(manifest.get("database"), dict) else {}
    generated_by = manifest.get("generated_by") if isinstance(manifest.get("generated_by"), dict) else {}
    service_id = str(backend.get("service_id") or "")
    if not SHA_RE.fullmatch(target_sha) or manifest.get("code_sha") != target_sha:
        raise ProvisionError("manifest is not bound to the requested target SHA")
    if not service_id or service_id == production_service_id or backend.get("production_service_id") != production_service_id:
        raise ProvisionError("Render QA service identity is not isolated from production")
    manifest_hash = "sha256:" + hashlib.sha256(_canonical_json(manifest)).hexdigest()
    expected = {
        "token_version": "provider-evidence-ed25519-v2",
        "manifest_hash": manifest_hash,
        "code_sha": target_sha,
        "git_branch": generated_by.get("git_branch"),
        "service_id": service_id,
        "environment_id": configuration.get("environment_id"),
        "render_deployment_id": backend.get("deployment_id"),
        "project_ref": database.get("project_ref"),
        "isolation_mode": database.get("isolation_mode"),
        "baseline_lease_id": database.get("baseline_lease_id"),
        "baseline_lease_target_sha": database.get("baseline_lease_target_sha"),
        "baseline_lease_target_branch": database.get("baseline_lease_target_branch"),
        "connection_fingerprint": database.get("connection_fingerprint"),
        "bootstrap_configuration_fingerprint": configuration.get(
            "bootstrap_configuration_fingerprint"
        ),
        "bootstrap_configuration_version": configuration.get(
            "bootstrap_configuration_version"
        ),
        "workflow_run_id": generated_by.get("workflow_run_id"),
        "repository": generated_by.get("repository"),
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ProvisionError(f"QA bootstrap capability {field} does not match provider evidence")
    if database.get("branch_type") == "preview" and any(
        field in payload
        for field in (
            "baseline_lease_id",
            "baseline_lease_target_sha",
            "baseline_lease_target_branch",
        )
    ):
        raise ProvisionError("QA bootstrap capability carries a baseline lease for a per-branch target")
    issued_at = payload.get("issued_at")
    expires_at = payload.get("expires_at")
    if (
        not isinstance(issued_at, int)
        or isinstance(issued_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
        or expires_at - issued_at < 60
        or expires_at - issued_at > 3600
        or issued_at > now + 30
        or expires_at <= now
    ):
        raise ProvisionError("QA bootstrap capability is expired, future-dated, or exceeds one hour")
    health_url = str(manifest.get("health_url") or "")
    parsed_health = urllib.parse.urlsplit(health_url)
    if parsed_health.scheme != "https" or not (parsed_health.hostname or "").endswith(".onrender.com") or parsed_health.path != "/health":
        raise ProvisionError("provider health URL is invalid")
    return service_id, health_url


class RenderClient:
    def __init__(self, token: str, opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        if not token:
            raise ProvisionError("RENDER_API_TOKEN is missing")
        self._token = token
        self._opener = opener

    def request(self, method: str, path: str, payload: object | None = None) -> Any:
        if method not in {"GET", "PUT", "POST", "DELETE"} or not path.startswith("/") or ".." in path:
            raise ProvisionError("Render request is outside the QA provisioning allowlist")
        body = _canonical_json(payload) if payload is not None else None
        request = urllib.request.Request(
            f"{RENDER_API}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "Hotel-Chipre-PMS-QA-bootstrap-provisioner/1.0",
            },
        )
        try:
            with self._opener(request, timeout=30) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            raise ProvisionError(f"Render {method} request failed with HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            raise ProvisionError(f"Render {method} request failed") from None
        if len(raw) > 2 * 1024 * 1024:
            raise ProvisionError("Render response exceeded the safety limit")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProvisionError("Render returned invalid JSON") from None


def provision(
    manifest: dict[str, Any], token: str, *, target_sha: str, production_service_id: str,
    render_token: str, now: int | None = None, sleeper: Callable[[float], None] = time.sleep,
    client: RenderClient | None = None,
    health_opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    current = int(time.time()) if now is None else now
    service_id, health_url = validate_capability(
        manifest, token, target_sha=target_sha, production_service_id=production_service_id, now=current
    )
    render = client or RenderClient(render_token)
    _validate_current_render_target(
        manifest,
        target_sha=target_sha,
        service_id=service_id,
        health_url=health_url,
        render=render,
    )
    quoted_service = urllib.parse.quote(service_id, safe="")
    token_path = f"/services/{quoted_service}/env-vars/QA_PROVIDER_EVIDENCE_TOKEN"
    token_installed = False
    operation_error: Exception | None = None
    cleanup_error: ProvisionError | None = None
    try:
        render.request("PUT", token_path, {"value": token.strip()})
        token_installed = True
        deployment = render.request(
            "POST", f"/services/{quoted_service}/deploys", {"commitId": target_sha}
        )
        deploy_id = deployment.get("id") if isinstance(deployment, dict) else None
        if not isinstance(deploy_id, str) or not deploy_id:
            raise ProvisionError("Render did not return the QA redeploy identity")
        quoted_deploy = urllib.parse.quote(deploy_id, safe="")
        for _ in range(90):
            status_payload = render.request(
                "GET", f"/services/{quoted_service}/deploys/{quoted_deploy}"
            )
            if _deployment_became_live(
                status_payload, deploy_id=deploy_id, target_sha=target_sha
            ):
                break
            sleeper(10)
        else:
            raise ProvisionError("Render QA deploy did not become live before timeout")
        try:
            with health_opener(health_url, timeout=30) as response:
                health = json.load(response)
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError):
            raise ProvisionError("Render QA health check failed after bootstrap deploy") from None
        if not isinstance(health, dict) or health.get("status") not in {"ok", "healthy"}:
            raise ProvisionError("Render QA health response is not healthy after bootstrap deploy")
    except Exception as error:  # cleanup must still run before propagating
        operation_error = error
    finally:
        if token_installed:
            try:
                render.request("DELETE", token_path)
            except ProvisionError as error:
                cleanup_error = error
    if cleanup_error is not None:
        raise ProvisionError(
            "Render QA bootstrap token cleanup failed; the capability must be rotated"
        ) from cleanup_error
    if operation_error is not None:
        raise operation_error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("token", type=Path)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--production-service-id", required=True)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        token = args.token.read_text(encoding="utf-8").strip()
        if not isinstance(manifest, dict):
            raise ProvisionError("manifest must contain an object")
        provision(
            manifest,
            token,
            target_sha=args.target_sha,
            production_service_id=args.production_service_id,
            render_token=os.environ.get("RENDER_API_TOKEN", ""),
        )
    except (OSError, json.JSONDecodeError, ProvisionError) as error:
        print(f"QA bootstrap provisioning refused: {error}")
        return 1
    print(
        "Render QA capability was consumed and removed; redeploy, pre-deploy bootstrap, "
        "and health check succeeded."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
