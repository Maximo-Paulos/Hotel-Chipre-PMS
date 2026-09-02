from __future__ import annotations

import copy
import io
import json
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.agent_ops.verify_production_render import (
    DeploymentNotReady,
    PRODUCTION_APP_ORIGIN,
    ReadOnlyRenderApi,
    SAFE_RUNTIME_VALUES,
    VerificationConfig,
    VerificationError,
    build_manifest,
    verify,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 31, 14, 0, tzinfo=timezone.utc)
SHA = "abcdef1234567890abcdef1234567890abcdef12"
DB_SECRET = "database-secret-must-not-be-serialized"


class FakeApi:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, path: str, query=None):
        self.calls.append((path, dict(query or {})))
        if path not in self.responses:
            raise AssertionError(f"unexpected Render path: {path}")
        return copy.deepcopy(self.responses[path])


def wrapper(key: str, value: dict, cursor: str = "cursor-1") -> dict:
    return {key: value, "cursor": cursor}


def env_page(values: dict[str, str]) -> list[dict]:
    return [
        wrapper("envVar", {"key": key, "value": value}, f"cursor-{index}")
        for index, (key, value) in enumerate(values.items())
    ]


def fixtures() -> tuple[VerificationConfig, FakeApi, dict[str, str]]:
    values = {
        **SAFE_RUNTIME_VALUES,
        "APP_BASE_URL": "https://hotel-chipre-pms-api.onrender.com",
        "FRONTEND_URL": PRODUCTION_APP_ORIGIN,
        "CORS_ORIGINS": "https://hotels-pms.com,https://app.hotels-pms.com",
        "DATABASE_URL": f"postgresql://postgres:{DB_SECRET}@db.production.supabase.co:5432/postgres",
        "REDIS_URL": "redis://redis.render.internal:6379/0",
        "MASTER_ADMIN_COOKIE_SECURE": "true",
    }
    service = {
        "id": "srv-production",
        "repo": "https://github.com/Maximo-Paulos/Hotel-Chipre-PMS",
        "branch": "main",
        "environmentId": "env-production",
        "type": "web_service",
        "suspended": "not_suspended",
        "serviceDetails": {
            "url": "https://hotel-chipre-pms-api.onrender.com",
            "healthCheckPath": "/health",
        },
        "updatedAt": "2026-08-31T13:55:00Z",
    }
    deployment = {
        "id": "dep-production",
        "status": "live",
        "commit": {"id": SHA},
        "finishedAt": "2026-08-31T13:58:00Z",
    }
    api = FakeApi(
        {
            "/services/srv-production": service,
            "/services/srv-production/env-vars": env_page(values),
            "/services/srv-production/deploys": [wrapper("deploy", deployment)],
        }
    )
    config = VerificationConfig(
        code_sha=SHA,
        git_branch="main",
        github_repository="Maximo-Paulos/Hotel-Chipre-PMS",
        workflow_run_id=123456,
        github_actor_id="9876",
        render_production_service_id="srv-production",
    )
    return config, api, values


def test_production_manifest_is_live_sha_bound_and_redacted() -> None:
    config, api, _ = fixtures()

    manifest = build_manifest(config, api, now=NOW)

    assert manifest["evidence_type"] == "provider-verified-production-render"
    assert manifest["backend"]["code_sha"] == SHA
    assert manifest["backend"]["deployment_id"] == "dep-production"
    assert manifest["configuration"]["test_surface"] == "render-production-test-hotel"
    assert manifest["configuration"]["external_effects_disabled"] is True
    assert manifest["generated_by"]["evidence_sources"] == ["render-api"]
    assert DB_SECRET not in json.dumps(manifest)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("EXTERNAL_EFFECTS_ENABLED", "true"),
        ("INBOUND_PROVIDER_EVENTS_ENABLED", "true"),
        ("CONNECTIONS_ENABLED", "true"),
        ("EMAIL_PROVIDER", "resend"),
        ("PAYPAL_MODE", "live"),
        ("REALTIME_EVENTS_ENABLED", "false"),
        ("DISTRIBUTED_LOCK_REQUIRED", "false"),
    ],
)
def test_production_profile_rejects_unsafe_runtime_flags(key: str, value: str) -> None:
    config, api, values = fixtures()
    values[key] = value
    api.responses["/services/srv-production/env-vars"] = env_page(values)

    with pytest.raises(VerificationError, match=key):
        build_manifest(config, api, now=NOW)


def test_production_verifier_does_not_accept_a_branch_or_unknown_service() -> None:
    config, api, _ = fixtures()
    api.responses["/services/srv-production"]["branch"] = "feature/unsafe"

    with pytest.raises(VerificationError, match="identity or main branch"):
        build_manifest(config, api, now=NOW)


def test_production_verifier_waits_only_for_a_missing_live_sha() -> None:
    config, api, _ = fixtures()
    api.responses["/services/srv-production/deploys"] = []
    sleeps: list[float] = []

    with pytest.raises(DeploymentNotReady):
        verify(config, api, wait_seconds=0, sleeper=sleeps.append, now=NOW)

    assert sleeps == []


def test_production_verifier_can_poll_until_render_publishes_sha() -> None:
    config, api, _ = fixtures()
    api.responses["/services/srv-production/deploys"] = []
    sleeps: list[float] = []

    def wake(seconds: float) -> None:
        sleeps.append(seconds)
        api.responses["/services/srv-production/deploys"] = [
            wrapper(
                "deploy",
                {
                    "id": "dep-production",
                    "status": "live",
                    "commit": {"id": SHA},
                    "finishedAt": "2026-08-31T13:58:00Z",
                },
            )
        ]

    manifest = verify(config, api, wait_seconds=30, poll_seconds=1, sleeper=wake, now=NOW)

    assert manifest["code_sha"] == SHA
    assert sleeps == [1]


def test_read_only_render_client_redacts_token_and_response_body() -> None:
    token = "render-api-token-secret"
    body_secret = b"provider-response-secret"

    def forbidden(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(body_secret))

    api = ReadOnlyRenderApi(token, opener=forbidden, sleeper=lambda _: None)

    with pytest.raises(VerificationError) as captured:
        api.get("/services/srv-production")

    message = str(captured.value)
    assert token not in message
    assert body_secret.decode() not in message


def test_production_workflow_has_no_separate_qa_service_or_mutating_bootstrap() -> None:
    workflow = (ROOT / ".github/workflows/verify-preview-providers.yml").read_text(encoding="utf-8")

    assert "name: Production Render QA cycle" in workflow
    assert "push:" in workflow and "branches: [main]" in workflow
    assert "RENDER_PRODUCTION_SERVICE_ID" in workflow
    assert "RENDER_QA_SERVICE_ID" not in workflow
    assert "SUPABASE_QA_PROJECT_REF" not in workflow
    assert "manage_qa_baseline_lease.py" not in workflow
    assert "provision_qa_bootstrap.py" not in workflow
    assert "verify_production_render.py" in workflow
    assert "/health/datastores" in workflow
    assert "production Redis/Valkey health is not ready" in workflow
    assert "production realtime events are not enabled" in workflow
    assert "persist-credentials: false" in workflow
