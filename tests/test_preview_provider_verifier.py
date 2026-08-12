"""Critical security tests for the read-only preview provider verifier."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import urllib.error
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.agent_ops.verify_preview_providers import (
    GITHUB_ENVIRONMENT,
    WORKFLOW_PATH,
    ProviderClients,
    ReadOnlyJsonApi,
    VerificationConfig,
    VerificationError,
    _verify_dedicated_baseline_lease,
    _public_origin,
    _connection_fingerprint,
    build_manifest,
)
from scripts.agent_ops.validate_preview_manifest import validate_manifest
from scripts.agent_ops.verify_preview_bundle import BundleVerificationError, verify_asset_payloads


NOW = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)
SHA = "abcdef1234567890abcdef1234567890abcdef12"
TRUSTED_SHA = "1111111111111111111111111111111111111111"
BRANCH = "codex/feature-preview"
APP_URL = "https://hotel-chipre-pms-git-feature-team.vercel.app"
API_URL = "https://hotel-chipre-pms-api-pr-123.onrender.com"
LEASE_ID = "4Xg_G8qKL90Bct2WjR6nVmZkAwYx7PSfE3uQ1iNo5Lc"
OTHER_LEASE_ID = "K7pV2bN9wQ4mX6sD8fH1jL3cR5tY0uA2eG9iO7zC4Bk"
QA_FERNET_KEY = "cXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXE="
PRODUCTION_FERNET_KEY = "cHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHA="
QA_JWT_SECRET = "qa-jwt-secret-that-is-at-least-32-bytes-long"
PRODUCTION_JWT_SECRET = "production-jwt-secret-that-is-distinct-and-long"


class FakeApi:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, path: str, query=None):
        self.calls.append((path, dict(query or {})))
        if path not in self.responses:
            raise AssertionError(f"Unexpected API path: {path}")
        return copy.deepcopy(self.responses[path])


def wrapper(key: str, value: dict, cursor: str = "cursor-1") -> dict:
    return {key: value, "cursor": cursor}


def env_page(values: dict[str, str]) -> list[dict]:
    return [wrapper("envVar", {"key": key, "value": value}, f"cursor-{index}") for index, (key, value) in enumerate(values.items())]


def fixtures() -> tuple[VerificationConfig, ProviderClients, dict[str, FakeApi]]:
    preview_db_url = "postgresql+psycopg2://postgres.preview:qa-db-pass@db.preview.supabase.co:5432/postgres"
    preview_env = {
        "AI_ENABLED": "false",
        "AI_PROVIDER": "disabled",
        "APP_BASE_URL": API_URL,
        "APP_ENV": "preview",
        "CONNECTIONS_ENABLED": "false",
        "EXTERNAL_EFFECTS_ENABLED": "false",
        "GOOGLE_LOGIN_ENABLED": "false",
        "INBOUND_PROVIDER_EVENTS_ENABLED": "false",
        "CORS_ORIGINS": APP_URL,
        "DATABASE_URL": preview_db_url,
        "EMAIL_PROVIDER": "null",
        "FRONTEND_URL": APP_URL,
        "GEMMA_ENABLED": "false",
        "GEMMA_PROVIDER": "disabled",
        "INTEGRATIONS_ENCRYPTION_KEY": QA_FERNET_KEY,
        "JWT_SECRET": QA_JWT_SECRET,
        "MASTER_ADMIN_EMAIL": "master-admin@qa.example.test",
        "MASTER_ADMIN_COOKIE_SECURE": "true",
        "MASTER_ADMIN_PASSWORD": "MasterAdminQaPass005!",
        "MASTER_ADMIN_PIN": "830527",
        "READ_MODEL_CACHE_ENABLED": "false",
        "MONGO_ENABLED": "false",
        "CASSANDRA_ENABLED": "false",
        "NEO4J_ENABLED": "false",
        "PAYPAL_MODE": "sandbox",
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
    production_env = {
        **preview_env,
        "DATABASE_URL": "postgresql://postgres.production:prod-db-pass@db.production.supabase.co:5432/postgres",
        "INTEGRATIONS_ENCRYPTION_KEY": PRODUCTION_FERNET_KEY,
        "JWT_SECRET": PRODUCTION_JWT_SECRET,
        "MASTER_ADMIN_EMAIL": "prod-master@example.test",
        "MASTER_ADMIN_PASSWORD": "prod-master-password",
        "MASTER_ADMIN_PIN": "987654",
    }
    production_service = {
        "id": "srv-production",
        "ownerId": "tea-canonical",
        "repo": "https://github.com/Maximo-Paulos/Hotel-Chipre-PMS",
        "branch": "main",
        "environmentId": "env-production",
        "type": "web_service",
        "suspended": "not_suspended",
        "serviceDetails": {
            "url": "https://api.hotels-pms.com",
            "healthCheckPath": "/health",
            "envSpecificDetails": {"preDeployCommand": ""},
        },
        "updatedAt": "2026-07-19T14:00:00Z",
    }
    preview_service = {
        "id": "srv-preview",
        "ownerId": "tea-canonical",
        "repo": "https://github.com/Maximo-Paulos/Hotel-Chipre-PMS",
        "branch": BRANCH,
        "environmentId": "env-preview",
        "type": "web_service",
        "suspended": "not_suspended",
        "serviceDetails": {
            "url": API_URL,
            "healthCheckPath": "/health",
            "envSpecificDetails": {"preDeployCommand": "python scripts/bootstrap_cloud_qa.py"},
        },
        "updatedAt": "2026-07-19T14:30:00Z",
    }
    render = FakeApi(
        {
            "/services/srv-production": production_service,
            "/services": [wrapper("service", production_service), wrapper("service", preview_service)],
            "/services/srv-preview/deploys": [
                wrapper(
                    "deploy",
                    {
                        "id": "dep-render-preview",
                        "status": "live",
                        "commit": {"id": SHA},
                        "finishedAt": "2026-07-19T14:40:00Z",
                    },
                )
            ],
            "/services/srv-preview/env-vars": env_page(preview_env),
            "/services/srv-production/env-vars": env_page(production_env),
        }
    )
    branch = {
        "id": "11111111-1111-4111-8111-111111111111",
        "name": "feature-preview",
        "project_ref": "previewpreviewpreviewab",
        "parent_project_ref": "productionproduction",
        "is_default": False,
        "git_branch": BRANCH,
        "persistent": False,
        "status": "MIGRATIONS_PASSED",
        "created_at": "2026-07-19T14:00:00Z",
        "updated_at": "2026-07-19T14:35:00Z",
        "with_data": False,
        "preview_project_status": "ACTIVE_HEALTHY",
    }
    supabase = FakeApi(
        {
            "/projects/productionproduction": {
                "ref": "productionproduction",
                "status": "ACTIVE_HEALTHY",
            },
            "/projects/productionproduction/branches": [branch],
            "/branches/previewpreviewpreviewab": {
                "ref": "previewpreviewpreviewab",
                "status": "ACTIVE_HEALTHY",
                "db_host": "db.preview.supabase.co",
                "db_port": 5432,
                "db_user": "postgres.preview",
                "db_pass": "qa-db-pass",
                "jwt_secret": "qa-supabase-jwt",
            },
            "/branches/productionproduction": {
                "ref": "productionproduction",
                "status": "ACTIVE_HEALTHY",
                "db_host": "db.production.supabase.co",
                "db_port": 5432,
                "db_user": "postgres.production",
                "db_pass": "prod-db-pass",
                "jwt_secret": "prod-supabase-jwt",
            },
        }
    )
    vercel = FakeApi(
        {
            "/v9/projects/prj-canonical": {
                "id": "prj-canonical",
                "name": "hotel-chipre-pms",
                "accountId": "team-canonical",
                "link": {
                    "type": "github",
                    "org": "Maximo-Paulos",
                    "repo": "Hotel-Chipre-PMS",
                    "productionBranch": "main",
                },
            },
            "/v7/deployments": {
                "deployments": [
                    {
                        "uid": "dpl-preview",
                        "projectId": "prj-canonical",
                        "readyState": "READY",
                    }
                ]
            },
            "/v13/deployments/dpl-preview": {
                "id": "dpl-preview",
                "projectId": "prj-canonical",
                "ownerId": "team-canonical",
                "readyState": "READY",
                "target": None,
                "url": "hotel-chipre-pms-unique.vercel.app",
                "alias": ["hotel-chipre-pms-git-feature-team.vercel.app"],
                "gitSource": {"type": "github", "sha": SHA, "ref": BRANCH},
                "ready": int((NOW - timedelta(minutes=10)).timestamp() * 1000),
            },
        }
    )
    github = FakeApi(
        {
            "/repos/Maximo-Paulos/Hotel-Chipre-PMS/git/ref/heads/codex%2Ffeature-preview": {
                "ref": f"refs/heads/{BRANCH}",
                "object": {
                    "type": "commit",
                    "sha": SHA,
                    "url": f"https://api.github.com/repos/Maximo-Paulos/Hotel-Chipre-PMS/git/commits/{SHA}",
                },
            }
        }
    )
    config = VerificationConfig(
        code_sha=SHA,
        git_branch=BRANCH,
        github_repository="Maximo-Paulos/Hotel-Chipre-PMS",
        workflow_run_id=123456789,
        github_actor_id="12345",
        render_production_service_id="srv-production",
        supabase_production_project_ref="productionproduction",
        vercel_team_id="team-canonical",
        vercel_project_id="prj-canonical",
        trusted_workflow_sha=TRUSTED_SHA,
        trusted_default_branch="main",
    )
    clients = ProviderClients(github=github, render=render, supabase=supabase, vercel=vercel)
    return config, clients, {"github": github, "render": render, "supabase": supabase, "vercel": vercel}


def set_render_preview_env(apis: dict[str, FakeApi], key: str, value: str) -> None:
    page = apis["render"].responses["/services/srv-preview/env-vars"]
    assert isinstance(page, list)
    for wrapper_item in page:
        if wrapper_item["envVar"]["key"] == key:
            wrapper_item["envVar"]["value"] = value
            return
    page.append(wrapper("envVar", {"key": key, "value": value}, f"cursor-{len(page)}"))


def configure_dedicated_baseline(
    config: VerificationConfig,
    apis: dict[str, FakeApi],
    *,
    lease_id: str = LEASE_ID,
) -> VerificationConfig:
    qa_ref = "qaqaprojectrefabcd"
    config = replace(
        config,
        supabase_qa_project_ref=qa_ref,
        baseline_lease_id=lease_id,
    )
    set_render_preview_env(
        apis,
        "DATABASE_URL",
        f"postgresql://postgres:qa-db-pass@db.{qa_ref}.supabase.co:5432/postgres",
    )
    for key, value in (
        ("QA_BASELINE_ONLY", "true"),
        ("QA_BASELINE_LEASE_ID", lease_id),
        ("QA_BASELINE_LEASE_TARGET_SHA", SHA),
        ("QA_BASELINE_LEASE_TARGET_BRANCH", BRANCH),
    ):
        set_render_preview_env(apis, key, value)
    apis["supabase"].responses[f"/projects/{qa_ref}"] = {
        "ref": qa_ref,
        "name": "hotel-chipre-qa",
        "status": "ACTIVE_HEALTHY",
        "created_at": "2026-07-19T14:35:00Z",
    }
    apis["supabase"].responses[f"/projects/{qa_ref}/config/database/pooler"] = [
        {
            "db_host": f"db.{qa_ref}.supabase.co",
            "db_port": 5432,
            "db_user": "postgres",
            "db_name": "postgres",
            "connection_string": (
                f"postgresql://postgres:[YOUR-PASSWORD]@db.{qa_ref}.supabase.co:5432/postgres"
            ),
        }
    ]
    return config


def test_happy_path_compares_production_secrets_without_serializing_values() -> None:
    config, clients, apis = fixtures()

    manifest = build_manifest(config, clients, now=NOW)

    assert validate_manifest(
        manifest,
        expected_sha=SHA,
        expected_task_id=f"preview-{SHA[:12]}",
        expected_workflow_run_id=config.workflow_run_id,
        expected_repository=config.github_repository,
        expected_branch=BRANCH,
        expected_workflow_sha=TRUSTED_SHA,
        expected_default_branch="main",
        now=NOW + timedelta(minutes=1),
    ) == []

    assert manifest["generated_by"]["workflow_path"] == WORKFLOW_PATH
    assert manifest["generated_by"]["github_environment"] == GITHUB_ENVIRONMENT
    assert manifest["generated_by"]["evidence_sources"] == [
        "render-api",
        "supabase-management-api",
        "vercel-api",
    ]
    assert manifest["frontend"]["project_id"] == "prj-canonical"
    assert manifest["frontend"]["team_id"] == "team-canonical"
    assert manifest["frontend"]["code_sha"] == SHA
    assert manifest["backend"]["deployment_id"] == "dep-render-preview"
    assert manifest["database"]["isolation_mode"] == "supabase-branch-per-target"
    assert not any(
        key.startswith("baseline_lease_") for key in manifest["database"]
    )
    assert manifest["database"]["fingerprint_method"] == "sha256"
    assert manifest["database"]["connection_fingerprint"] != manifest["database"]["production_connection_fingerprint"]
    assert "/services/srv-production/env-vars" in {
        path for path, _ in apis["render"].calls
    }
    assert "/branches/productionproduction" not in {
        path for path, _ in apis["supabase"].calls
    }
    serialized = json.dumps(manifest)
    for secret in (
        "qa-db-pass",
        "prod-db-pass",
        QA_JWT_SECRET,
        PRODUCTION_JWT_SECRET,
        QA_FERNET_KEY,
        PRODUCTION_FERNET_KEY,
        "qa-supabase-jwt",
        "MasterAdminQaPass005!",
        "postgres.preview",
        "db.preview.supabase.co",
    ):
        assert secret not in serialized


@pytest.mark.parametrize(
    ("key", "unsafe_value"),
    [
        ("AI_ENABLED", "true"),
        ("AI_PROVIDER", "openai"),
        ("CONNECTIONS_ENABLED", "true"),
        ("EMAIL_PROVIDER", "resend"),
        ("GEMMA_ENABLED", "true"),
        ("GEMMA_PROVIDER", "google_gemini_api"),
        ("MASTER_ADMIN_COOKIE_SECURE", "false"),
        ("READ_MODEL_CACHE_ENABLED", "true"),
        ("MONGO_ENABLED", "true"),
        ("CASSANDRA_ENABLED", "true"),
        ("NEO4J_ENABLED", "true"),
        ("PAYPAL_MODE", "live"),
    ],
)
def test_preview_rejects_external_effects_enabled(
    key: str,
    unsafe_value: str,
) -> None:
    config, clients, apis = fixtures()
    set_render_preview_env(apis, key, unsafe_value)

    with pytest.raises(VerificationError, match=key):
        build_manifest(config, clients, now=NOW)


@pytest.mark.parametrize(
    "credential_key",
    [
        "BOOKING_PASSWORD",
        "EXPEDIA_API_KEY",
        "GEMMA_API_KEY",
        "GEMMA_ENDPOINT_URL",
        "GMAIL_CLIENT_SECRET",
        "MERCADOPAGO_CLIENT_SECRET",
        "MP_ACCESS_TOKEN",
        "PAYPAL_CLIENT_SECRET",
        "QA_PROVIDER_EVIDENCE_PRIVATE_KEY",
        "QA_PROVIDER_EVIDENCE_TOKEN",
        "REDIS_URL",
        "MONGO_URL",
        "CASSANDRA_HOSTS",
        "NEO4J_URI",
        "RESEND_API_KEY",
    ],
)
def test_preview_rejects_live_integration_credentials(credential_key: str) -> None:
    config, clients, apis = fixtures()
    set_render_preview_env(apis, credential_key, "must-not-be-accepted")

    with pytest.raises(VerificationError, match="forbidden live integration credentials"):
        build_manifest(config, clients, now=NOW)


def test_preview_environment_rejects_worker_or_scheduled_sibling() -> None:
    config, clients, apis = fixtures()
    services = apis["render"].responses["/services"]
    assert isinstance(services, list)
    services.append(
        wrapper(
            "service",
            {
                "id": "srv-preview-worker",
                "ownerId": "tea-canonical",
                "repo": "https://github.com/Maximo-Paulos/Hotel-Chipre-PMS",
                "branch": "worker-only-branch",
                "environmentId": "env-preview",
                "type": "background_worker",
                "suspended": "not_suspended",
            },
            "cursor-worker",
        )
    )

    with pytest.raises(VerificationError, match="scheduled worker"):
        build_manifest(config, clients, now=NOW)


def test_public_database_fingerprint_uses_the_versioned_canonical_payload() -> None:
    payload = "qaqaprojectrefabcd\x1fdb.qaqaprojectrefabcd.supabase.co\x1f5432\x1fpostgres"

    assert _connection_fingerprint(
        "qaqaprojectrefabcd", "db.qaqaprojectrefabcd.supabase.co", 5432, "postgres"
    ) == f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"


def test_dedicated_free_qa_project_manifest_passes_the_consumer_contract() -> None:
    config, clients, apis = fixtures()
    config = configure_dedicated_baseline(config, apis)

    manifest = build_manifest(config, clients, now=NOW)

    assert manifest["database"]["branch_type"] == "dedicated-qa-project"
    assert manifest["database"]["isolation_mode"] == "dedicated-qa-baseline-exclusive"
    assert manifest["database"]["baseline_lease_id"] == LEASE_ID
    assert f"/branches/{manifest['database']['project_ref']}" not in {
        path for path, _ in apis["supabase"].calls
    }
    assert f"/projects/{manifest['database']['project_ref']}/config/database/pooler" in {
        path for path, _ in apis["supabase"].calls
    }
    assert validate_manifest(
        manifest,
        expected_sha=SHA,
        expected_branch=BRANCH,
        expected_baseline_lease_id=LEASE_ID,
        now=NOW,
    ) == []


@pytest.mark.parametrize("app_env", ["qa", "staging", "production"])
def test_provider_requires_exact_preview_app_env(app_env: str) -> None:
    config, clients, apis = fixtures()
    set_render_preview_env(apis, "APP_ENV", app_env)

    with pytest.raises(VerificationError, match="exactly preview"):
        build_manifest(config, clients, now=NOW)


@pytest.mark.parametrize(
    ("key", "preview_value"),
    [
        ("JWT_SECRET", PRODUCTION_JWT_SECRET),
        ("INTEGRATIONS_ENCRYPTION_KEY", PRODUCTION_FERNET_KEY),
        ("MASTER_ADMIN_EMAIL", "prod-master@example.test"),
        ("MASTER_ADMIN_PASSWORD", "prod-master-password"),
        ("MASTER_ADMIN_PIN", "987654"),
    ],
)
def test_provider_rejects_preview_secret_equal_to_production(
    key: str,
    preview_value: str,
) -> None:
    config, clients, apis = fixtures()
    set_render_preview_env(apis, key, preview_value)

    with pytest.raises(VerificationError, match=f"{key} equals production"):
        build_manifest(config, clients, now=NOW)


def test_provider_rejects_preview_database_password_equal_to_production() -> None:
    config, clients, apis = fixtures()
    set_render_preview_env(
        apis,
        "DATABASE_URL",
        "postgresql://postgres.preview:prod-db-pass@db.preview.supabase.co:5432/postgres",
    )

    with pytest.raises(VerificationError, match="database password equals production"):
        build_manifest(config, clients, now=NOW)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("JWT_SECRET", "too-short", "JWT_SECRET"),
        (
            "INTEGRATIONS_ENCRYPTION_KEY",
            "ZGVmYXVsdC1pbnRlZ3JhdGlvbnMta2V5LXNlY3JldA==",
            "INTEGRATIONS_ENCRYPTION_KEY",
        ),
        ("MASTER_ADMIN_PASSWORD", "short", "MASTER_ADMIN_PASSWORD"),
        ("MASTER_ADMIN_PIN", "1234", "MASTER_ADMIN_PIN"),
    ],
)
def test_provider_rejects_weak_preview_secrets(
    key: str,
    value: str,
    message: str,
) -> None:
    config, clients, apis = fixtures()
    set_render_preview_env(apis, key, value)

    with pytest.raises(VerificationError, match=message):
        build_manifest(config, clients, now=NOW)


def test_dedicated_baseline_refuses_missing_render_lease_observation() -> None:
    config, clients, apis = fixtures()
    config = configure_dedicated_baseline(config, apis)
    page = apis["render"].responses["/services/srv-preview/env-vars"]
    assert isinstance(page, list)
    page[:] = [
        item
        for item in page
        if item["envVar"]["key"] != "QA_BASELINE_LEASE_TARGET_BRANCH"
    ]

    with pytest.raises(VerificationError, match="missing lease keys"):
        build_manifest(config, clients, now=NOW)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("QA_BASELINE_ONLY", "True", "exactly true"),
        ("QA_BASELINE_LEASE_ID", OTHER_LEASE_ID, "lease ID does not match"),
        ("QA_BASELINE_LEASE_TARGET_SHA", "0" * 40, "different Git SHA"),
        ("QA_BASELINE_LEASE_TARGET_BRANCH", "codex/other-target", "different Git branch"),
    ],
)
def test_dedicated_baseline_refuses_provider_lease_mismatch(
    key: str,
    value: str,
    message: str,
) -> None:
    config, clients, apis = fixtures()
    config = configure_dedicated_baseline(config, apis)
    set_render_preview_env(apis, key, value)

    with pytest.raises(VerificationError, match=message):
        build_manifest(config, clients, now=NOW)


@pytest.mark.parametrize(
    "lease_id",
    [
        "baseline-123",
        "a" * 32,
        SHA,
        hashlib.sha256(f"{BRANCH}\x1f{SHA}".encode()).hexdigest(),
    ],
)
def test_dedicated_baseline_refuses_weak_or_target_derived_lease(lease_id: str) -> None:
    config, clients, apis = fixtures()
    config = configure_dedicated_baseline(config, apis, lease_id=lease_id)

    with pytest.raises(VerificationError, match="lease ID"):
        build_manifest(config, clients, now=NOW)


def test_real_branch_mode_refuses_stale_dedicated_baseline_variables() -> None:
    config, clients, apis = fixtures()
    set_render_preview_env(apis, "QA_BASELINE_ONLY", "true")

    with pytest.raises(VerificationError, match="branch mode must not carry"):
        build_manifest(config, clients, now=NOW)


def test_concurrent_target_cannot_reuse_an_existing_baseline_lease() -> None:
    config, _, apis = fixtures()
    config = configure_dedicated_baseline(config, apis)
    competing = replace(config, code_sha="f" * 40)
    page = apis["render"].responses["/services/srv-preview/env-vars"]
    assert isinstance(page, list)
    observed_env = {item["envVar"]["key"]: item["envVar"]["value"] for item in page}

    with pytest.raises(VerificationError, match="different Git SHA"):
        _verify_dedicated_baseline_lease(competing, observed_env)


def test_ready_frontend_bundle_with_old_api_is_rejected() -> None:
    with pytest.raises(BundleVerificationError, match="production or historical"):
        verify_asset_payloads(
            [b'const current="https://hotel-chipre-pms-api-pr-123.onrender.com/api";'
             b'const stale="https://hotel-chipre-pms-api.onrender.com/api";'],
            "https://hotel-chipre-pms-api-pr-123.onrender.com/api",
        )


def test_vercel_team_or_project_drift_is_never_certified() -> None:
    config, clients, apis = fixtures()
    apis["vercel"].responses["/v9/projects/prj-canonical"]["accountId"] = "team-other"

    with pytest.raises(VerificationError, match="canonical project/team identity mismatch"):
        build_manifest(config, clients, now=NOW)


def test_target_branch_must_resolve_to_exact_sha_in_same_repository() -> None:
    config, clients, apis = fixtures()
    response = apis["github"].responses[
        "/repos/Maximo-Paulos/Hotel-Chipre-PMS/git/ref/heads/codex%2Ffeature-preview"
    ]
    response["object"]["sha"] = "0" * 40

    with pytest.raises(VerificationError, match="resolve exactly"):
        build_manifest(config, clients, now=NOW)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.hotels-pms.com./",
        "https://127.0.0.1/",
        "https://10.0.0.1/",
        "https://169.254.169.254/",
        "https://[::1]/",
        "https://[fe80::1]/",
    ],
)
def test_trailing_dot_production_and_private_ip_origins_are_rejected(url: str) -> None:
    with pytest.raises(VerificationError):
        _public_origin(url, "preview", allowed_suffix="onrender.com")


@pytest.mark.parametrize("offset", [timedelta(days=-2), timedelta(minutes=10)])
def test_stale_or_future_vercel_deployment_is_rejected(offset: timedelta) -> None:
    config, clients, apis = fixtures()
    ready_at = NOW + offset
    apis["vercel"].responses["/v13/deployments/dpl-preview"]["ready"] = int(ready_at.timestamp() * 1000)

    with pytest.raises(VerificationError, match="Vercel deployment.*(?:stale|future)"):
        build_manifest(config, clients, now=NOW)


def test_production_supabase_endpoint_is_rejected_before_evidence_is_written() -> None:
    config, clients, apis = fixtures()
    preview = apis["supabase"].responses["/branches/previewpreviewpreviewab"]
    preview["db_host"] = "db.productionproduction.supabase.co"
    set_render_preview_env(
        apis,
        "DATABASE_URL",
        "postgresql://postgres.preview:qa-db-pass@db.productionproduction.supabase.co:5432/postgres",
    )

    with pytest.raises(VerificationError, match="identifies production"):
        build_manifest(config, clients, now=NOW)


def test_http_failures_do_not_disclose_token_or_response_body() -> None:
    token = "provider-token-secret"
    body_secret = b"provider-response-secret"

    def forbidden(request, timeout):
        assert request.get_method() == "GET"
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(body_secret))

    api = ReadOnlyJsonApi("Render", "https://api.render.com/v1", token, opener=forbidden)

    with pytest.raises(VerificationError) as captured:
        api.get("/services/srv-preview")
    message = str(captured.value)
    assert token not in message
    assert body_secret.decode() not in message


def test_workflow_has_no_human_evidence_inputs_and_publishes_sha_bound_artifact() -> None:
    workflow = open(".github/workflows/verify-preview-providers.yml", encoding="utf-8").read()

    assert "target_branch:" in workflow
    assert "target_sha:" in workflow
    assert "baseline_lease_id:" not in workflow
    assert "manage_qa_baseline_lease.py acquire" in workflow
    assert "BASELINE_LEASE_ID: ${{ steps.lease.outputs.lease_id }}" in workflow
    assert "--expected-baseline-lease-id \"$BASELINE_LEASE_ID\"" in workflow
    assert "app_url:" not in workflow
    assert "api_url:" not in workflow
    assert "preview-provider-evidence-${{ inputs.target_sha }}" in workflow
    assert "environment: preview-qa" in workflow
    assert "if: github.ref_name == github.event.repository.default_branch" in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "ref: ${{ inputs.target_branch }}" not in workflow
    assert "scripts/agent_ops/verify_preview_providers.py" in workflow
    assert "TARGET_SHA" in workflow and "TARGET_BRANCH" in workflow
    assert "secrets.RENDER_API_TOKEN" in workflow
    assert "secrets.SUPABASE_ACCESS_TOKEN" in workflow
    assert "secrets.VERCEL_ACCESS_TOKEN" in workflow
    assert "secrets.QA_PROVIDER_EVIDENCE_PRIVATE_KEY" in workflow
    assert "QA_PROVIDER_EVIDENCE_HMAC_KEY" not in workflow
    assert "qa-bootstrap-token-${{ inputs.target_sha }}" not in workflow
    assert "download-artifact" not in workflow
    assert "verify_preview_bundle.py verify" in workflow
    assert "Re-verify provider state after bootstrap" in workflow
    assert "Re-verify providers immediately before evidence upload" in workflow
    assert workflow.count("scripts/agent_ops/verify_preview_providers.py") == 3
    assert "compare_preview_manifests.py" in workflow
    assert "manage_qa_baseline_lease.py release" in workflow
    assert "if: always() && steps.lease.outputs.lease_id != ''" in workflow


def test_dedicated_baseline_workflow_serializes_targets_without_cancellation() -> None:
    workflow = open(".github/workflows/verify-preview-providers.yml", encoding="utf-8").read()

    assert "group: preview-qa-dedicated-baseline" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "group: preview-qa-dedicated-baseline-${{" not in workflow
    assert "test -n \"$SUPABASE_QA_PROJECT_REF\"" in workflow
    assert "not branch-per-PR isolation" in workflow
    assert "Permanent parallel previews require Supabase" in workflow


def test_pr_controlled_code_cannot_receive_provider_credentials_or_execute_in_verifier() -> None:
    producer = open(".github/workflows/verify-preview-providers.yml", encoding="utf-8").read()
    consumer = open(".github/workflows/preview-qa.yml", encoding="utf-8").read()

    assert "ref: ${{ github.sha }}" in producer
    assert "ref: ${{ inputs.target_branch }}" not in producer
    assert "ref: ${{ inputs.target_sha }}" not in producer
    assert "github.ref_name == github.event.repository.default_branch" in producer
    assert "persist-credentials: false" in producer
    for secret in (
        "RENDER_API_TOKEN",
        "SUPABASE_ACCESS_TOKEN",
        "VERCEL_ACCESS_TOKEN",
        "QA_PROVIDER_EVIDENCE_PRIVATE_KEY",
    ):
        assert f"secrets.{secret}" in producer
        assert f"secrets.{secret}" not in consumer
    assert "environment: preview-qa" not in consumer
    assert "actions: read" not in consumer
    assert "workflow_dispatch" not in consumer
    assert "download-artifact" not in consumer
    assert "npm ci" not in consumer


def test_untrusted_contract_installs_the_exact_hash_locked_linux_runtime() -> None:
    workflow = open(".github/workflows/preview-qa.yml", encoding="utf-8").read()

    assert "--require-hashes" in workflow
    assert "--only-binary=:all:" in workflow
    assert "-r requirements-qa-trusted.txt" in workflow


def test_bootstrap_capability_never_crosses_a_workflow_or_artifact_boundary() -> None:
    workflow_path = Path(".github/workflows/verify-preview-providers.yml")
    workflow = workflow_path.read_text(encoding="utf-8")

    assert not Path(".github/workflows/provision-qa-bootstrap.yml").exists()
    assert "github.ref_name == github.event.repository.default_branch" in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "ref: ${{ inputs.target_branch }}" not in workflow
    assert "secrets.RENDER_API_TOKEN" in workflow
    assert "secrets.QA_PROVIDER_EVIDENCE_PRIVATE_KEY" in workflow
    assert "provision_qa_bootstrap.py" in workflow
    assert "qa-provider-evidence.token" in workflow
    assert "Upload short-lived" not in workflow
    assert "download-artifact" not in workflow
    assert "rm -f \"$RUNNER_TEMP/qa-provider-evidence.token\"" in workflow
    assert "QA_PROVIDER_EVIDENCE_HMAC_KEY" not in workflow
