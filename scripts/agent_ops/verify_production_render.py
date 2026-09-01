#!/usr/bin/env python3
"""Verify the live Render production test surface without mutating it.

The production Render service is the functional cloud test surface for this
project.  This verifier is deliberately read-only: it waits for the service's
current ``main`` deployment to reach the requested SHA, checks the runtime
profile that disables external effects, and emits only redacted deployment
metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


RENDER_API = "https://api.render.com/v1"
WORKFLOW_PATH = ".github/workflows/verify-preview-providers.yml"
GITHUB_ENVIRONMENT = "preview-qa"
MAX_DEPLOYMENT_AGE = timedelta(hours=24)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
SHA_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
SERVICE_ID_RE = re.compile(r"srv-[A-Za-z0-9]+")
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
PRODUCTION_APP_ORIGIN = "https://app.hotels-pms.com"
PRODUCTION_SITE_ORIGIN = "https://hotels-pms.com"
PRODUCTION_API_HOST = "api.hotels-pms.com"
SAFE_RUNTIME_VALUES = {
    "APP_ENV": "production",
    "EXTERNAL_EFFECTS_ENABLED": "false",
    "INBOUND_PROVIDER_EVENTS_ENABLED": "false",
    "CONNECTIONS_ENABLED": "false",
    "EMAIL_PROVIDER": "null",
    "PAYPAL_MODE": "sandbox",
    "AI_ENABLED": "false",
    "AI_PROVIDER": "disabled",
    "GEMMA_ENABLED": "false",
    "GEMMA_PROVIDER": "disabled",
    "REALTIME_EVENTS_ENABLED": "true",
    "DISTRIBUTED_LOCK_ENABLED": "true",
    "DISTRIBUTED_LOCK_REQUIRED": "true",
}
REQUIRED_ENV_KEYS = {
    "APP_BASE_URL",
    "APP_ENV",
    "CONNECTIONS_ENABLED",
    "CORS_ORIGINS",
    "DATABASE_URL",
    "DISTRIBUTED_LOCK_ENABLED",
    "DISTRIBUTED_LOCK_REQUIRED",
    "EMAIL_PROVIDER",
    "EXTERNAL_EFFECTS_ENABLED",
    "FRONTEND_URL",
    "INBOUND_PROVIDER_EVENTS_ENABLED",
    "REDIS_URL",
    "REALTIME_EVENTS_ENABLED",
}


class VerificationError(RuntimeError):
    """Safe failure that never includes provider response values."""


class DeploymentNotReady(VerificationError):
    """The requested SHA is not live yet and may become live after polling."""


class JsonGetter(Protocol):
    def get(self, path: str, query: Mapping[str, object] | None = None) -> Any: ...


class ReadOnlyRenderApi:
    """Bounded GET-only Render client with redacted failures."""

    def __init__(
        self,
        token: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not isinstance(token, str) or not token:
            raise VerificationError("RENDER_API_TOKEN is not configured")
        self._token = token
        self._opener = opener
        self._sleeper = sleeper

    def get(self, path: str, query: Mapping[str, object] | None = None) -> Any:
        if not path.startswith("/") or ".." in path or "\n" in path or "\r" in path:
            raise VerificationError("Render API path is invalid")
        query_string = urllib.parse.urlencode(query or {}, doseq=True)
        url = f"{RENDER_API}{path}"
        if query_string:
            url = f"{url}?{query_string}"
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "Hotel-Chipre-PMS-production-render-verifier/1.0",
            },
            method="GET",
        )
        for attempt in range(3):
            try:
                with self._opener(request, timeout=30) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise VerificationError("Render response exceeded the safety limit")
                try:
                    return json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise VerificationError("Render returned invalid JSON") from None
            except urllib.error.HTTPError as error:
                if error.code == 429 or 500 <= error.code <= 599:
                    if attempt < 2:
                        self._sleeper(2**attempt)
                        continue
                raise VerificationError(f"Render GET request failed with HTTP {error.code}") from None
            except (urllib.error.URLError, TimeoutError, socket.timeout):
                if attempt < 2:
                    self._sleeper(2**attempt)
                    continue
                raise VerificationError("Render GET request failed") from None
        raise VerificationError("Render GET request failed")


@dataclass(frozen=True)
class VerificationConfig:
    code_sha: str
    git_branch: str
    github_repository: str
    workflow_run_id: int
    github_actor_id: str
    render_production_service_id: str
    app_url: str = PRODUCTION_APP_ORIGIN
    workflow_path: str = WORKFLOW_PATH
    github_environment: str = GITHUB_ENVIRONMENT

    @property
    def task_id(self) -> str:
        return f"production-render-{self.code_sha[:12]}"


def _non_empty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VerificationError(f"{field} is missing")
    return value.strip()


def _service_id(value: object) -> str:
    value = _non_empty(value, "Render production service ID")
    if not SERVICE_ID_RE.fullmatch(value):
        raise VerificationError("Render production service ID is invalid")
    return value


def _repository(value: object) -> str:
    value = _non_empty(value, "GitHub repository")
    if not REPOSITORY_RE.fullmatch(value):
        raise VerificationError("GitHub repository must use owner/name format")
    return value.lower()


def _render_repository(value: object) -> str:
    raw = _non_empty(value, "Render service repository")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https" or _canonical_host(parsed.hostname or "") != "github.com":
        raise VerificationError("Render service repository is not GitHub HTTPS")
    repository = parsed.path.strip("/").removesuffix(".git")
    return _repository(repository)


def _canonical_host(value: str) -> str:
    try:
        return value.rstrip(".").lower().encode("idna").decode("ascii")
    except UnicodeError:
        raise VerificationError("provider URL contains an invalid hostname") from None


def _https_origin(value: object, field: str, *, api: bool = False) -> str:
    raw = _non_empty(value, field)
    parsed = urllib.parse.urlsplit(raw)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.port not in {None, 443}
    ):
        raise VerificationError(f"{field} must be a credential-free HTTPS origin")
    host = _canonical_host(parsed.hostname)
    if api:
        if host != PRODUCTION_API_HOST and not host.endswith(".onrender.com"):
            raise VerificationError(f"{field} must be the production API or a Render origin")
    elif host != "app.hotels-pms.com":
        raise VerificationError(f"{field} must be the canonical production app")
    return f"https://{host}"


def _timestamp(value: object, field: str) -> datetime:
    raw = _non_empty(value, field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise VerificationError(f"provider timestamp {field} is invalid") from None
    if parsed.tzinfo is None:
        raise VerificationError(f"provider timestamp {field} lacks timezone")
    return parsed.astimezone(timezone.utc)


def _require_recent(value: datetime, field: str, now: datetime) -> None:
    if value > now + timedelta(minutes=5):
        raise VerificationError(f"provider timestamp {field} is in the future")
    if now - value > MAX_DEPLOYMENT_AGE:
        raise VerificationError(f"provider deployment {field} is stale")


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise VerificationError(f"Render {field} response is invalid")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise VerificationError(f"Render {field} response is invalid")
    return value


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
            wrapper = _object(wrapper_value, f"Render {path} item")
            results.append(_object(wrapper.get(resource_key), f"Render {resource_key}"))
        if len(page) < 100:
            return results
        next_cursor = _non_empty(_object(page[-1], "Render cursor item").get("cursor"), "Render cursor")
        if next_cursor in seen:
            raise VerificationError("Render pagination cursor repeated")
        seen.add(next_cursor)
        cursor = next_cursor
    raise VerificationError("Render pagination exceeded the safety limit")


def _render_env(api: JsonGetter, service_id: str) -> dict[str, str]:
    path = f"/services/{urllib.parse.quote(service_id, safe='')}/env-vars"
    values: dict[str, str] = {}
    for item in _render_page(api, path, "envVar"):
        key = _non_empty(item.get("key"), "Render environment key")
        value = item.get("value")
        if not isinstance(value, str) or key in values:
            raise VerificationError("Render environment response is invalid")
        values[key] = value
    return values


def _validate_config(config: VerificationConfig) -> None:
    if not SHA_RE.fullmatch(config.code_sha):
        raise VerificationError("target SHA must be a full lowercase Git SHA")
    if not config.git_branch or config.git_branch != "main":
        raise VerificationError("production Render QA must target the main branch")
    if not _repository(config.github_repository):
        raise VerificationError("GitHub repository is invalid")
    if config.workflow_run_id <= 0:
        raise VerificationError("GitHub workflow run ID must be positive")
    if not _non_empty(config.github_actor_id, "GitHub actor ID").isdigit():
        raise VerificationError("GitHub actor ID must be numeric")
    _service_id(config.render_production_service_id)
    if config.workflow_path != WORKFLOW_PATH:
        raise VerificationError("production Render verifier workflow path is invalid")
    if not config.github_environment:
        raise VerificationError("GitHub environment is missing")
    if _https_origin(config.app_url, "production app URL") != PRODUCTION_APP_ORIGIN:
        raise VerificationError("production Render QA app must use the canonical app")


def _verify_runtime_profile(values: Mapping[str, str]) -> None:
    missing = sorted(REQUIRED_ENV_KEYS - values.keys())
    if missing:
        raise VerificationError("Render production service is missing required environment keys: " + ", ".join(missing))
    for key, expected in SAFE_RUNTIME_VALUES.items():
        if values.get(key, "").strip().lower() != expected:
            raise VerificationError(
                f"Render production test profile requires {key}={expected}"
            )
    if values.get("MASTER_ADMIN_COOKIE_SECURE", "true").strip().lower() != "true":
        raise VerificationError("Render production test profile requires secure admin cookies")
    if not values.get("DATABASE_URL", "").strip():
        raise VerificationError("Render production service DATABASE_URL is empty")
    if not values.get("REDIS_URL", "").strip():
        raise VerificationError("Render production service REDIS_URL is empty")
    if values.get("FRONTEND_URL", "").strip().rstrip("/") != PRODUCTION_APP_ORIGIN:
        raise VerificationError("Render production FRONTEND_URL must be the canonical app")
    cors = {
        _https_origin(origin.strip(), "Render production CORS origin")
        if origin.strip().rstrip("/") == PRODUCTION_APP_ORIGIN
        else _validate_site_origin(origin.strip())
        for origin in values["CORS_ORIGINS"].split(",")
        if origin.strip()
    }
    if cors != {PRODUCTION_APP_ORIGIN, PRODUCTION_SITE_ORIGIN}:
        raise VerificationError("Render production CORS_ORIGINS must contain only the canonical site and app")
    if "*" in values["CORS_ORIGINS"]:
        raise VerificationError("Render production CORS_ORIGINS must not contain a wildcard")


def _validate_site_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "hotels-pms.com"
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.port not in {None, 443}
    ):
        raise VerificationError("Render production CORS origin is not canonical")
    return PRODUCTION_SITE_ORIGIN


def _live_deployment(
    api: JsonGetter,
    service_id: str,
    target_sha: str,
    *,
    now: datetime,
) -> dict[str, Any]:
    path = f"/services/{urllib.parse.quote(service_id, safe='')}/deploys"
    deploys = _render_page(api, path, "deploy", {"status": "live"})
    matches = [
        deploy
        for deploy in deploys
        if deploy.get("status") == "live"
        and isinstance(deploy.get("commit"), dict)
        and deploy["commit"].get("id") == target_sha
    ]
    if len(matches) != 1:
        raise DeploymentNotReady("the requested SHA is not the live Render deployment yet")
    finished_at = _timestamp(matches[0].get("finishedAt"), "Render deployment finishedAt")
    _require_recent(finished_at, "Render deployment", now)
    return matches[0]


def build_manifest(
    config: VerificationConfig,
    api: JsonGetter,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    _validate_config(config)
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    service_id = _service_id(config.render_production_service_id)
    service_path = f"/services/{urllib.parse.quote(service_id, safe='')}"
    service = _object(api.get(service_path), "production service")
    if (
        service.get("id") != service_id
        or service.get("type") != "web_service"
        or service.get("suspended") != "not_suspended"
        or service.get("branch") != config.git_branch
        or _render_repository(service.get("repo")) != _repository(config.github_repository)
    ):
        raise VerificationError("Render production service identity or main branch drifted")
    details = _object(service.get("serviceDetails"), "production service details")
    if details.get("healthCheckPath") != "/health":
        raise VerificationError("Render production health check path must be /health")
    render_origin = _https_origin(details.get("url"), "Render production service URL", api=True)
    values = _render_env(api, service_id)
    _verify_runtime_profile(values)
    api_origin = _https_origin(values.get("APP_BASE_URL"), "Render production APP_BASE_URL", api=True)
    if api_origin != render_origin and api_origin != f"https://{PRODUCTION_API_HOST}":
        raise VerificationError("Render production APP_BASE_URL does not identify the service or canonical API")
    deployment = _live_deployment(api, service_id, config.code_sha, now=observed_at)
    return {
        "schema_version": 1,
        "evidence_type": "provider-verified-production-render",
        "task_id": config.task_id,
        "code_sha": config.code_sha,
        "generated_at": observed_at.isoformat().replace("+00:00", "Z"),
        "generated_by": {
            "kind": "production-render-api-verifier",
            "workflow_run_id": config.workflow_run_id,
            "workflow_path": config.workflow_path,
            "github_environment": config.github_environment,
            "event_name": "push-or-workflow_dispatch",
            "actor_id": config.github_actor_id,
            "repository": config.github_repository,
            "git_branch": config.git_branch,
            "evidence_sources": ["render-api"],
        },
        "app_url": config.app_url,
        "api_origin": api_origin,
        "api_base_url": f"{api_origin}/api",
        "health_url": f"{api_origin}/health",
        "frontend_vite_api_url": f"{api_origin}/api",
        "backend": {
            "provider": "render",
            "evidence_source": "render-api",
            "environment": "production-test-sandbox",
            "service_url": render_origin,
            "service_id": service_id,
            "deployment_id": _non_empty(deployment.get("id"), "Render deployment ID"),
            "code_sha": config.code_sha,
            "git_branch": config.git_branch,
            "deployment_finished_at": _timestamp(
                deployment.get("finishedAt"), "Render deployment finishedAt"
            ).isoformat().replace("+00:00", "Z"),
            "configuration_updated_at": _non_empty(
                service.get("updatedAt"), "Render service updatedAt"
            ),
        },
        "configuration": {
            "evidence_source": "render-api",
            "environment_id": _non_empty(service.get("environmentId"), "Render environment ID"),
            "test_surface": "render-production-test-hotel",
            "external_effects_disabled": True,
            "required_safe_flags_verified": sorted(SAFE_RUNTIME_VALUES),
            "required_environment_names_verified": sorted(REQUIRED_ENV_KEYS),
            "values_redacted": True,
        },
    }


def verify(
    config: VerificationConfig,
    api: JsonGetter,
    *,
    wait_seconds: int = 0,
    poll_seconds: int = 20,
    sleeper: Callable[[float], None] = time.sleep,
    now: datetime | None = None,
) -> dict[str, Any]:
    if wait_seconds < 0 or wait_seconds > 1800:
        raise VerificationError("wait_seconds must be between 0 and 1800")
    if poll_seconds <= 0 or poll_seconds > 120:
        raise VerificationError("poll_seconds must be between 1 and 120")
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            return build_manifest(config, api, now=now)
        except DeploymentNotReady:
            if time.monotonic() >= deadline:
                raise
            sleeper(min(poll_seconds, max(1, deadline - time.monotonic())))


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise VerificationError(f"required environment value {name} is missing")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("production-render-manifest.json"))
    parser.add_argument("--wait-seconds", type=int, default=0)
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args()
    try:
        config = VerificationConfig(
            code_sha=_required_env("TARGET_SHA"),
            git_branch=_required_env("TARGET_BRANCH"),
            github_repository=_required_env("GITHUB_REPOSITORY"),
            workflow_run_id=int(_required_env("GITHUB_RUN_ID")),
            github_actor_id=_required_env("GITHUB_ACTOR_ID"),
            render_production_service_id=_required_env("RENDER_PRODUCTION_SERVICE_ID"),
            app_url=os.environ.get("PRODUCTION_APP_URL", PRODUCTION_APP_ORIGIN),
            github_environment=os.environ.get("QA_GITHUB_ENVIRONMENT", GITHUB_ENVIRONMENT),
        )
        manifest = verify(
            config,
            ReadOnlyRenderApi(_required_env("RENDER_API_TOKEN")),
            wait_seconds=args.wait_seconds,
            poll_seconds=args.poll_seconds,
        )
        args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, VerificationError) as error:
        print(f"Production Render verification failed: {error}")
        return 1
    print("Production Render deployment and safe test profile verified; sanitized manifest written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
