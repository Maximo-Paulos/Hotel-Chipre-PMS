"""Security tests for the trusted Render QA capability provisioner."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from scripts.agent_ops.provision_qa_bootstrap import ProvisionError, provision
from scripts.agent_ops.qa_bootstrap_contract import (
    BOOTSTRAP_CONFIGURATION_VERSION,
    bootstrap_configuration_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = 1_784_467_200
DB_HOST = "db.preview.supabase.co"
DB_PORT = 5432
DB_USER = "postgres.preview"


def manifest() -> dict:
    evidence = json.loads(
        (ROOT / "qa" / "preview-manifest.example.json").read_text(encoding="utf-8")
    )
    project_ref = evidence["database"]["project_ref"]
    identity = "\x1f".join((project_ref, DB_HOST, str(DB_PORT), DB_USER)).encode()
    evidence["database"]["connection_fingerprint"] = (
        "sha256:" + hashlib.sha256(identity).hexdigest()
    )
    evidence["configuration"]["bootstrap_configuration_fingerprint"] = (
        bootstrap_configuration_fingerprint(FakeRender(evidence).env)
    )
    return evidence


def token_for(evidence: dict, **overrides: object) -> str:
    generated = evidence["generated_by"]
    backend = evidence["backend"]
    database = evidence["database"]
    configuration = evidence["configuration"]
    manifest_hash = "sha256:" + hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = {
        "token_version": "provider-evidence-ed25519-v2",
        "manifest_hash": manifest_hash,
        "code_sha": evidence["code_sha"],
        "git_branch": generated["git_branch"],
        "service_id": backend["service_id"],
        "environment_id": configuration["environment_id"],
        "render_deployment_id": backend["deployment_id"],
        "project_ref": database["project_ref"],
        "isolation_mode": database["isolation_mode"],
        "connection_fingerprint": database["connection_fingerprint"],
        "bootstrap_configuration_fingerprint": configuration[
            "bootstrap_configuration_fingerprint"
        ],
        "bootstrap_configuration_version": BOOTSTRAP_CONFIGURATION_VERSION,
        "workflow_run_id": generated["workflow_run_id"],
        "repository": generated["repository"],
        "issued_at": NOW - 10,
        "expires_at": NOW + 890,
    }
    if "baseline_lease_id" in database:
        payload.update(
            {
                "baseline_lease_id": database["baseline_lease_id"],
                "baseline_lease_target_sha": database["baseline_lease_target_sha"],
                "baseline_lease_target_branch": database["baseline_lease_target_branch"],
            }
        )
    payload.update(overrides)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    return f"{encoded}.{'A' * 86}"


def env_page(values: dict[str, str]) -> list[dict]:
    return [
        {"envVar": {"key": key, "value": value}, "cursor": f"cursor-{index}"}
        for index, (key, value) in enumerate(values.items())
    ]


class FakeRender:
    def __init__(self, evidence: dict) -> None:
        self.evidence = evidence
        self.calls: list[tuple[str, str, object | None]] = []
        self.service = {
            "id": evidence["backend"]["service_id"],
            "environmentId": evidence["configuration"]["environment_id"],
            "repo": f"https://github.com/{evidence['generated_by']['repository']}",
            "branch": evidence["generated_by"]["git_branch"],
            "type": "web_service",
            "suspended": "not_suspended",
            "serviceDetails": {
                "url": evidence["api_origin"],
                "healthCheckPath": "/health",
                "envSpecificDetails": {
                    "preDeployCommand": "python scripts/bootstrap_cloud_qa.py"
                },
            },
        }
        self.env = {
            "AI_ENABLED": "false",
            "AI_PROVIDER": "disabled",
            "APP_BASE_URL": evidence["api_origin"],
            "APP_ENV": "preview",
            "CONNECTIONS_ENABLED": "false",
            "EXTERNAL_EFFECTS_ENABLED": "false",
            "GOOGLE_LOGIN_ENABLED": "false",
            "INBOUND_PROVIDER_EVENTS_ENABLED": "false",
            "CORS_ORIGINS": evidence["app_url"],
            "DATABASE_URL": (
                f"postgresql+psycopg2://{DB_USER}:synthetic-secret@"
                f"{DB_HOST}:{DB_PORT}/postgres"
            ),
            "EMAIL_PROVIDER": "null",
            "FRONTEND_URL": evidence["app_url"],
            "GEMMA_ENABLED": "false",
            "GEMMA_PROVIDER": "disabled",
            "INTEGRATIONS_ENCRYPTION_KEY": "cXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXE=",
            "JWT_SECRET": "qa-jwt-secret-that-is-at-least-32-bytes-long",
            "MASTER_ADMIN_COOKIE_SECURE": "true",
            "MASTER_ADMIN_EMAIL": "master-admin@qa.example.test",
            "MASTER_ADMIN_PASSWORD": "MasterAdminQaPass005!",
            "MASTER_ADMIN_PIN": "830527",
            "READ_MODEL_CACHE_ENABLED": "false",
            "MONGO_ENABLED": "false",
            "CASSANDRA_ENABLED": "false",
            "NEO4J_ENABLED": "false",
            "PAYPAL_MODE": "sandbox",
            "QA_DATABASE_ISOLATED": "true",
            "QA_DATABASE_BRANCH_REF": evidence["database"]["project_ref"],
            "QA_EXPECTED_DATABASE_HOST": DB_HOST,
            "QA_EXPECTED_DATABASE_PORT": str(DB_PORT),
            "QA_EXPECTED_DATABASE_NAME": "postgres",
            "QA_EXPECTED_DATABASE_USER": DB_USER,
            "QA_EMAIL_DOMAIN": "qa.example.test",
            "QA_EMAIL_DOMAIN_IS_DEDICATED": "true",
            "QA_HOUSEKEEPING_EMAIL": "housekeeping@qa.example.test",
            "QA_HOUSEKEEPING_PASSWORD": "HousekeepingQaPass004!",
            "QA_MANAGER_EMAIL": "manager@qa.example.test",
            "QA_MANAGER_PASSWORD": "ManagerQaPass002!",
            "QA_MASTER_ADMIN_EMAIL": "master-admin@qa.example.test",
            "QA_MASTER_ADMIN_PASSWORD": "MasterAdminQaPass005!",
            "QA_MASTER_ADMIN_PIN": "830527",
            "QA_OWNER_EMAIL": "owner@qa.example.test",
            "QA_OWNER_PASSWORD": "OwnerQaPass001!",
            "QA_CO_OWNER_EMAIL": "co-owner@qa.example.test",
            "QA_CO_OWNER_PASSWORD": "CoOwnerQaPass006!",
            "QA_PROVIDER_EVIDENCE_PUBLIC_KEY": "qa-ed25519-public-key",
            "QA_RECEPTION_EMAIL": "reception@qa.example.test",
            "QA_RECEPTION_PASSWORD": "ReceptionQaPass003!",
            "QA_RUN_ID": "qa-test-run-001",
            "QA_RUN_MIGRATIONS": "false",
        }
        if evidence["database"]["branch_type"] == "dedicated-qa-project":
            self.env.update(
                {
                    "QA_BASELINE_ONLY": "true",
                    "QA_BASELINE_LEASE_ID": evidence["database"]["baseline_lease_id"],
                    "QA_BASELINE_LEASE_TARGET_SHA": evidence["database"][
                        "baseline_lease_target_sha"
                    ],
                    "QA_BASELINE_LEASE_TARGET_BRANCH": evidence["database"][
                        "baseline_lease_target_branch"
                    ],
                }
            )
        self.current_deploy = {
            "id": evidence["backend"]["deployment_id"],
            "status": "live",
            "commit": {"id": evidence["code_sha"]},
            "finishedAt": "2026-07-19T14:45:00Z",
        }
        self.bootstrap_deploy = {
            "id": "dep-bootstrap",
            "status": "live",
            "commit": {"id": evidence["code_sha"]},
            "finishedAt": "2026-07-19T15:05:00Z",
        }

    def request(self, method: str, path: str, payload: object | None = None):
        self.calls.append((method, path, payload))
        service_id = self.evidence["backend"]["service_id"]
        current_id = self.evidence["backend"]["deployment_id"]
        if method == "GET" and path == f"/services/{service_id}":
            return self.service
        if method == "GET" and path == f"/services/{service_id}/env-vars":
            return env_page(self.env)
        if method == "GET" and path == f"/services/{service_id}/deploys/{current_id}":
            return self.current_deploy
        if method == "GET" and path == f"/services/{service_id}/deploys/dep-bootstrap":
            return self.bootstrap_deploy
        if method == "PUT":
            return {"key": "QA_PROVIDER_EVIDENCE_TOKEN", "value": "redacted"}
        if method == "POST":
            return {"id": "dep-bootstrap", "status": "queued"}
        if method == "DELETE" and path == (
            f"/services/{service_id}/env-vars/QA_PROVIDER_EVIDENCE_TOKEN"
        ):
            return None
        raise AssertionError(f"Unexpected Render call: {method} {path}")


class HealthResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, *args):
        return b'{"status":"healthy"}'


class FakeRenderCleanupFailure(FakeRender):
    def request(self, method: str, path: str, payload: object | None = None):
        if method == "DELETE":
            self.calls.append((method, path, payload))
            raise ProvisionError("simulated cleanup failure")
        return super().request(method, path, payload)


class FakeRenderPutResponseLost(FakeRender):
    """Render applied the token, but the runner never received the PUT response."""

    def request(self, method: str, path: str, payload: object | None = None):
        if method == "PUT":
            self.calls.append((method, path, payload))
            self.env["QA_PROVIDER_EVIDENCE_TOKEN"] = "installed-before-network-loss"
            raise ProvisionError("simulated lost PUT response")
        if method == "DELETE":
            self.calls.append((method, path, payload))
            self.env.pop("QA_PROVIDER_EVIDENCE_TOKEN", None)
            return None
        return super().request(method, path, payload)


def _mutating_calls(render: FakeRender) -> list[tuple[str, str, object | None]]:
    return [call for call in render.calls if call[0] in {"PUT", "POST", "DELETE"}]


def _apply_drift(render: FakeRender, drift: str) -> None:
    if drift == "service_id":
        render.service["id"] = "srv-drifted"
    elif drift == "environment_id":
        render.service["environmentId"] = "env-drifted"
    elif drift == "repository":
        render.service["repo"] = "https://github.com/attacker/other-repo"
    elif drift == "branch":
        render.service["branch"] = "attacker/branch"
    elif drift == "service_url":
        render.service["serviceDetails"]["url"] = "https://drifted.onrender.com"
    elif drift == "health_path":
        render.service["serviceDetails"]["healthCheckPath"] = "/other-health"
    elif drift == "pre_deploy":
        render.service["serviceDetails"]["envSpecificDetails"]["preDeployCommand"] = ""
    elif drift == "app_env":
        render.env["APP_ENV"] = "production"
    elif drift == "api_url":
        render.env["APP_BASE_URL"] = "https://drifted.onrender.com"
    elif drift == "frontend_url":
        render.env["FRONTEND_URL"] = "https://drifted.vercel.app"
    elif drift == "cors":
        render.env["CORS_ORIGINS"] = "https://drifted.vercel.app"
    elif drift == "isolation":
        render.env["QA_DATABASE_ISOLATED"] = "false"
    elif drift == "project_ref":
        render.env["QA_DATABASE_BRANCH_REF"] = "differentprojectref"
    elif drift == "database_host":
        render.env["QA_EXPECTED_DATABASE_HOST"] = "db.other.supabase.co"
    elif drift == "database_port":
        render.env["QA_EXPECTED_DATABASE_PORT"] = "6543"
    elif drift == "database_name":
        render.env["QA_EXPECTED_DATABASE_NAME"] = "other"
    elif drift == "database_user":
        render.env["QA_EXPECTED_DATABASE_USER"] = "attacker"
    elif drift == "database_fingerprint":
        render.env["DATABASE_URL"] = render.env["DATABASE_URL"].replace(DB_HOST, "db.other.supabase.co")
        render.env["QA_EXPECTED_DATABASE_HOST"] = "db.other.supabase.co"
    elif drift == "bootstrap_configuration":
        render.env["QA_RUN_ID"] = "qa-drifted-run"
    elif drift == "baseline_only":
        render.env["QA_BASELINE_ONLY"] = "false"
    elif drift == "baseline_lease_id":
        render.env["QA_BASELINE_LEASE_ID"] = "vTjklYwWvPso75WuXI4q5BdQZGyAdJcGGGL9fNQ9HKs"
    elif drift == "baseline_lease_sha":
        render.env["QA_BASELINE_LEASE_TARGET_SHA"] = "b" * 40
    elif drift == "baseline_lease_branch":
        render.env["QA_BASELINE_LEASE_TARGET_BRANCH"] = "other/branch"
    elif drift == "deployment_id":
        render.current_deploy["id"] = "dep-drifted"
    elif drift == "deployment_status":
        render.current_deploy["status"] = "build_in_progress"
    elif drift == "deployment_commit":
        render.current_deploy["commit"] = {"id": "b" * 40}
    else:  # pragma: no cover - test helper guard
        raise AssertionError(f"unknown drift: {drift}")


def test_only_revalidated_qa_service_receives_token_and_exact_target_redeploy() -> None:
    evidence = manifest()
    token = token_for(evidence)
    render = FakeRender(evidence)

    provision(
        evidence,
        token,
        target_sha=evidence["code_sha"],
        production_service_id=evidence["backend"]["production_service_id"],
        render_token="unused",
        now=NOW,
        client=render,
        sleeper=lambda _: None,
        health_opener=lambda *args, **kwargs: HealthResponse(),
    )

    preview_id = evidence["backend"]["service_id"]
    assert [method for method, _, _ in render.calls[:3]] == ["GET", "GET", "GET"]
    assert render.calls[3] == (
        "PUT",
        f"/services/{preview_id}/env-vars/QA_PROVIDER_EVIDENCE_TOKEN",
        {"value": token},
    )
    assert render.calls[4] == (
        "POST", f"/services/{preview_id}/deploys", {"commitId": evidence["code_sha"]}
    )
    assert render.calls[-1] == (
        "DELETE",
        f"/services/{preview_id}/env-vars/QA_PROVIDER_EVIDENCE_TOKEN",
        None,
    )
    assert all(
        evidence["backend"]["production_service_id"] not in path
        for _, path, _ in render.calls
    )


@pytest.mark.parametrize(
    "drift",
    [
        "service_id",
        "environment_id",
        "repository",
        "branch",
        "service_url",
        "health_path",
        "pre_deploy",
        "app_env",
        "api_url",
        "frontend_url",
        "cors",
        "isolation",
        "project_ref",
        "database_host",
        "database_port",
        "database_name",
        "database_user",
        "database_fingerprint",
        "bootstrap_configuration",
        "baseline_only",
        "baseline_lease_id",
        "baseline_lease_sha",
        "baseline_lease_branch",
        "deployment_id",
        "deployment_status",
        "deployment_commit",
    ],
)
def test_any_render_drift_is_rejected_without_mutation(drift: str) -> None:
    evidence = manifest()
    render = FakeRender(evidence)
    _apply_drift(render, drift)

    with pytest.raises(ProvisionError, match="drifted|isolated|current deployment"):
        provision(
            evidence,
            token_for(evidence),
            target_sha=evidence["code_sha"],
            production_service_id=evidence["backend"]["production_service_id"],
            render_token="unused",
            now=NOW,
            client=render,
        )

    assert _mutating_calls(render) == []


def test_real_supabase_branch_rejects_dedicated_baseline_lease_env_without_mutation() -> None:
    evidence = manifest()
    evidence["database"]["branch_type"] = "preview"
    evidence["database"]["isolation_mode"] = "supabase-branch-per-target"
    for field in (
        "baseline_lease_id",
        "baseline_lease_target_sha",
        "baseline_lease_target_branch",
    ):
        evidence["database"].pop(field)
    render = FakeRender(evidence)
    render.env.update(
        {
            "QA_BASELINE_ONLY": "true",
            "QA_BASELINE_LEASE_ID": "4Xg_G8qKL90Bct2WjR6nVmZkAwYx7PSfE3uQ1iNo5Lc",
            "QA_BASELINE_LEASE_TARGET_SHA": evidence["code_sha"],
            "QA_BASELINE_LEASE_TARGET_BRANCH": evidence["generated_by"]["git_branch"],
        }
    )

    with pytest.raises(ProvisionError, match="carries dedicated baseline"):
        provision(
            evidence,
            token_for(evidence),
            target_sha=evidence["code_sha"],
            production_service_id=evidence["backend"]["production_service_id"],
            render_token="unused",
            now=NOW,
            client=render,
        )

    assert _mutating_calls(render) == []


def test_bootstrap_deploy_commit_mismatch_is_never_accepted_as_live() -> None:
    evidence = manifest()
    render = FakeRender(evidence)
    render.bootstrap_deploy["commit"] = {"id": "b" * 40}

    with pytest.raises(ProvisionError, match="commit does not match"):
        provision(
            evidence,
            token_for(evidence),
            target_sha=evidence["code_sha"],
            production_service_id=evidence["backend"]["production_service_id"],
            render_token="unused",
            now=NOW,
            client=render,
            sleeper=lambda _: None,
        )


def test_live_requires_finished_timestamp_after_pre_deploy() -> None:
    evidence = manifest()
    render = FakeRender(evidence)
    render.bootstrap_deploy.pop("finishedAt")

    with pytest.raises(ProvisionError, match="completion timestamp"):
        provision(
            evidence,
            token_for(evidence),
            target_sha=evidence["code_sha"],
            production_service_id=evidence["backend"]["production_service_id"],
            render_token="unused",
            now=NOW,
            client=render,
            sleeper=lambda _: None,
        )


def test_cleanup_failure_blocks_success_and_requires_token_rotation() -> None:
    evidence = manifest()
    render = FakeRenderCleanupFailure(evidence)

    with pytest.raises(ProvisionError, match="must be rotated"):
        provision(
            evidence,
            token_for(evidence),
            target_sha=evidence["code_sha"],
            production_service_id=evidence["backend"]["production_service_id"],
            render_token="unused",
            now=NOW,
            client=render,
            sleeper=lambda _: None,
            health_opener=lambda *args, **kwargs: HealthResponse(),
        )

    assert render.calls[-1][0] == "DELETE"


def test_lost_put_response_still_attempts_cleanup_of_applied_token() -> None:
    evidence = manifest()
    render = FakeRenderPutResponseLost(evidence)

    with pytest.raises(ProvisionError, match="lost PUT response"):
        provision(
            evidence,
            token_for(evidence),
            target_sha=evidence["code_sha"],
            production_service_id=evidence["backend"]["production_service_id"],
            render_token="unused",
            now=NOW,
            client=render,
        )

    assert [call[0] for call in _mutating_calls(render)] == ["PUT", "DELETE"]
    assert "QA_PROVIDER_EVIDENCE_TOKEN" not in render.env


def test_pre_deploy_failure_is_terminal() -> None:
    evidence = manifest()
    render = FakeRender(evidence)
    render.bootstrap_deploy["status"] = "pre_deploy_failed"

    with pytest.raises(ProvisionError, match="failed before bootstrap completed"):
        provision(
            evidence,
            token_for(evidence),
            target_sha=evidence["code_sha"],
            production_service_id=evidence["backend"]["production_service_id"],
            render_token="unused",
            now=NOW,
            client=render,
            sleeper=lambda _: None,
        )

    preview_id = evidence["backend"]["service_id"]
    assert render.calls[-1] == (
        "DELETE",
        f"/services/{preview_id}/env-vars/QA_PROVIDER_EVIDENCE_TOKEN",
        None,
    )


def test_expired_capability_is_rejected_before_any_render_request() -> None:
    evidence = manifest()
    render = FakeRender(evidence)

    with pytest.raises(ProvisionError, match="expired"):
        provision(
            evidence,
            token_for(evidence, issued_at=NOW - 1000, expires_at=NOW - 1),
            target_sha=evidence["code_sha"],
            production_service_id=evidence["backend"]["production_service_id"],
            render_token="unused",
            now=NOW,
            client=render,
        )

    assert render.calls == []


def test_capability_for_another_render_service_is_rejected() -> None:
    evidence = manifest()

    with pytest.raises(ProvisionError, match="service_id"):
        provision(
            evidence,
            token_for(evidence, service_id="srv-attacker"),
            target_sha=evidence["code_sha"],
            production_service_id=evidence["backend"]["production_service_id"],
            render_token="unused",
            now=NOW,
            client=FakeRender(evidence),
        )
