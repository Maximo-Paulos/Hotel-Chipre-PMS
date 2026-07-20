from __future__ import annotations

import base64
import json
import hashlib
import runpy
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.models import HotelConfiguration, HotelMembership, OnboardingState, User
from app.services.security import verify_password
from scripts import bootstrap_cloud_qa, issue_qa_provider_evidence
from scripts.agent_ops.qa_bootstrap_contract import (
    BOOTSTRAP_CONFIGURATION_VERSION,
    bootstrap_configuration_fingerprint,
)


PRIVATE_KEY_RAW = bytes(range(1, 33))
PRIVATE_KEY_OBJECT = Ed25519PrivateKey.from_private_bytes(PRIVATE_KEY_RAW)
PRIVATE_KEY = PRIVATE_KEY_OBJECT.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode("ascii")
PUBLIC_KEY = PRIVATE_KEY_OBJECT.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("ascii")
PRIVATE_KEY_BASE64 = base64.b64encode(PRIVATE_KEY_RAW).decode("ascii")
PUBLIC_KEY_BASE64 = base64.b64encode(
    PRIVATE_KEY_OBJECT.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
).decode("ascii")
CODE_SHA = "a" * 40
SERVICE_ID = "srv-preview-001"
GIT_BRANCH = "codex/feature-preview"
PREVIEW_REF = "previewpreviewpreviewab"
DEDICATED_REF = "qaqaprojectrefabcd"
BASELINE_LEASE_ID = "4Xg_G8qKL90Bct2WjR6nVmZkAwYx7PSfE3uQ1iNo5Lc"


def _bootstrap_values() -> dict[str, str]:
    return {
        "APP_ENV": "test",
        "EMAIL_PROVIDER": "null",
        "CONNECTIONS_ENABLED": "false",
        "PAYPAL_MODE": "sandbox",
        "AI_ENABLED": "false",
        "AI_PROVIDER": "disabled",
        "GEMMA_ENABLED": "false",
        "GEMMA_PROVIDER": "disabled",
        "QA_RUN_ID": "qa-test-run-001",
        "QA_EMAIL_DOMAIN": "qa.example.test",
        "QA_EMAIL_DOMAIN_IS_DEDICATED": "true",
        "QA_OWNER_EMAIL": "owner@qa.example.test",
        "QA_OWNER_PASSWORD": "OwnerQaPass001!",
        "QA_MANAGER_EMAIL": "manager@qa.example.test",
        "QA_MANAGER_PASSWORD": "ManagerQaPass002!",
        "QA_RECEPTION_EMAIL": "reception@qa.example.test",
        "QA_RECEPTION_PASSWORD": "ReceptionQaPass003!",
        "QA_HOUSEKEEPING_EMAIL": "housekeeping@qa.example.test",
        "QA_HOUSEKEEPING_PASSWORD": "HousekeepingQaPass004!",
        "QA_MASTER_ADMIN_EMAIL": "master-admin@qa.example.test",
        "QA_MASTER_ADMIN_PASSWORD": "MasterAdminQaPass005!",
        "QA_MASTER_ADMIN_PIN": "830527",
        "MASTER_ADMIN_EMAIL": "master-admin@qa.example.test",
        "MASTER_ADMIN_PASSWORD": "MasterAdminQaPass005!",
        "MASTER_ADMIN_PIN": "830527",
        "QA_RUN_MIGRATIONS": "false",
    }


def _env(tmp_path) -> dict[str, str]:
    database_path = tmp_path / "isolated-qa-bootstrap.db"
    return {
        **_bootstrap_values(),
        "DATABASE_URL": f"sqlite:///{database_path}",
        "QA_DATABASE_ISOLATED": "true",
        "QA_ALLOW_SQLITE": "true",
        "QA_EXPECTED_DATABASE_PATH": str(database_path),
    }


def _provider_manifest(
    database_url: str,
    *,
    bootstrap_env: dict[str, str] | None = None,
    schema_version: int = 2,
    branch_type: str = "preview",
    project_ref: str = PREVIEW_REF,
) -> dict:
    production_url = (
        "postgresql://postgres:prod-secret@"
        "db.production.supabase.co:5432/postgres"
    )
    manifest = {
        "schema_version": schema_version,
        "evidence_type": "provider-verified-isolated-preview",
        "task_id": "qa-bootstrap-tests",
        "code_sha": CODE_SHA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": {
            "kind": "provider-api-verifier",
            "workflow_run_id": 12345,
            "workflow_path": ".github/workflows/verify-preview-providers.yml",
            "github_environment": "preview-qa",
            "event_name": "workflow_dispatch",
            "actor_id": "12345",
            "repository": "Maximo-Paulos/Hotel-Chipre-PMS",
            "git_branch": GIT_BRANCH,
            "evidence_sources": [
                "render-api",
                "supabase-management-api",
                "vercel-api",
            ],
        },
        "app_url": "https://hotel-chipre-pms-git-feature-team.vercel.app",
        "api_origin": "https://hotel-chipre-pms-api-pr-123.onrender.com",
        "api_base_url": "https://hotel-chipre-pms-api-pr-123.onrender.com/api",
        "health_url": "https://hotel-chipre-pms-api-pr-123.onrender.com/health",
        "frontend_vite_api_url": "https://hotel-chipre-pms-api-pr-123.onrender.com/api",
        "frontend": {
            "provider": "vercel",
            "evidence_source": "vercel-api",
            "environment": "preview",
            "deployment_id": "dpl-preview-001",
            "project_id": "prj-canonical",
            "team_id": "team-canonical",
            "project_name": "hotel-chipre-pms",
            "deployment_url": "https://hotel-chipre-pms-unique.vercel.app",
            "code_sha": CODE_SHA,
            "git_branch": GIT_BRANCH,
            "ready_at": datetime.now(timezone.utc).isoformat(),
        },
        "backend": {
            "provider": "render",
            "evidence_source": "render-api",
            "environment": "preview",
            "service_id": SERVICE_ID,
            "production_service_id": "srv-production-001",
            "deployment_id": "dep-preview-001",
            "code_sha": CODE_SHA,
            "git_branch": GIT_BRANCH,
            "deployment_finished_at": datetime.now(timezone.utc).isoformat(),
            "configuration_updated_at": datetime.now(timezone.utc).isoformat(),
        },
        "database": {
            "provider": "supabase",
            "evidence_source": "supabase-management-api",
            "project_ref": project_ref,
            "branch_type": branch_type,
            "isolation_mode": (
                "dedicated-qa-baseline-exclusive"
                if branch_type == "dedicated-qa-project"
                else "supabase-branch-per-target"
            ),
            "branch_ref": project_ref,
            "production_branch_ref": "productionproduction",
            "branch_name": "feature-preview",
            "git_branch": GIT_BRANCH,
            "with_data": False,
            "fingerprint_method": "sha256",
            "fingerprint_payload_version": "supabase-connection-v1",
            "connection_fingerprint": bootstrap_cloud_qa.database_connection_fingerprint(
                database_url,
                project_ref=project_ref,
            ),
            "production_connection_fingerprint": bootstrap_cloud_qa.database_connection_fingerprint(
                production_url,
                project_ref="productionproduction",
            ),
            "database_endpoint_distinct": True,
            "database_user_distinct": False,
            "database_password_distinct": True,
            "jwt_identity_distinct": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        "configuration": {
            "evidence_source": "render-api",
            "frontend_url": "https://hotel-chipre-pms-git-feature-team.vercel.app",
            "cors_origins": ["https://hotel-chipre-pms-git-feature-team.vercel.app"],
            "environment_id": "env-preview-001",
            "production_environment_id": "env-production-001",
            "qa_secrets_scope": "preview-service",
            "required_secret_names_verified": ["DATABASE_URL", "JWT_SECRET"],
            "distinct_from_production_verified": ["DATABASE_URL", "JWT_SECRET"],
            "bootstrap_configuration_fingerprint": bootstrap_configuration_fingerprint(
                bootstrap_env or _bootstrap_values()
            ),
            "bootstrap_configuration_version": BOOTSTRAP_CONFIGURATION_VERSION,
            "values_redacted": True,
        },
    }
    if branch_type == "dedicated-qa-project":
        manifest["database"].update(
            {
                "baseline_lease_id": BASELINE_LEASE_ID,
                "baseline_lease_target_sha": CODE_SHA,
                "baseline_lease_target_branch": GIT_BRANCH,
            }
        )
    return manifest


def _cloud_env(
    tmp_path,
    *,
    schema_version: int = 2,
    branch_type: str = "preview",
) -> dict[str, str]:
    project_ref = PREVIEW_REF if branch_type == "preview" else DEDICATED_REF
    database_user = "postgres"
    database_host = (
        "db.preview.supabase.co"
        if branch_type == "preview"
        else f"db.{project_ref}.supabase.co"
    )
    database_url = (
        f"postgresql+psycopg2://{database_user}:secret@{database_host}/postgres"
    )
    bootstrap_env = {**_bootstrap_values(), "APP_ENV": "preview"}
    manifest = _provider_manifest(
        database_url,
        bootstrap_env=bootstrap_env,
        schema_version=schema_version,
        branch_type=branch_type,
        project_ref=project_ref,
    )
    token = issue_qa_provider_evidence.issue_provider_evidence_token(
        manifest,
        private_key=PRIVATE_KEY,
        now=int(time.time()),
        nonce="00112233445566778899aabbccddeeff",
    )
    env = _env(tmp_path)
    env.update(
        {
            "APP_ENV": "preview",
            "DATABASE_URL": database_url,
            "QA_EXPECTED_DATABASE_HOST": database_host,
            "QA_EXPECTED_DATABASE_PORT": "5432",
            "QA_EXPECTED_DATABASE_NAME": "postgres",
            "QA_EXPECTED_DATABASE_USER": database_user,
            "QA_DATABASE_BRANCH_REF": project_ref,
            "QA_PROVIDER_EVIDENCE_TOKEN": token,
            "QA_PROVIDER_EVIDENCE_PUBLIC_KEY": PUBLIC_KEY,
            "RENDER_SERVICE_ID": SERVICE_ID,
            "RENDER_GIT_COMMIT": CODE_SHA,
        }
    )
    if branch_type == "dedicated-qa-project":
        env.update(
            {
                "QA_BASELINE_ONLY": "true",
                "QA_BASELINE_LEASE_ID": BASELINE_LEASE_ID,
                "QA_BASELINE_LEASE_TARGET_SHA": CODE_SHA,
                "QA_BASELINE_LEASE_TARGET_BRANCH": GIT_BRANCH,
            }
        )
    return env


def test_fingerprint_exactly_matches_supabase_connection_v1_contract():
    database_url = (
        "postgresql://postgres.preview:first-password@"
        "DB.Preview.Example.:5432/postgres"
    )
    expected_payload = (
        f"{PREVIEW_REF}\x1fdb.preview.example\x1f5432\x1fpostgres.preview"
    ).encode("utf-8")
    expected = "sha256:" + hashlib.sha256(expected_payload).hexdigest()

    assert bootstrap_cloud_qa.database_connection_fingerprint(
        database_url,
        project_ref=PREVIEW_REF,
    ) == expected
    assert bootstrap_cloud_qa.database_connection_fingerprint(
        database_url.replace("first-password", "different-password"),
        project_ref=PREVIEW_REF,
    ) == expected


def test_fingerprint_rejects_non_postgres_database_name():
    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="database postgres"):
        bootstrap_cloud_qa.database_connection_fingerprint(
            "postgresql://postgres.preview:secret@db.preview.example/hotel_qa",
            project_ref=PREVIEW_REF,
        )


def test_raw_base64_ed25519_keys_issue_and_verify(tmp_path):
    env = _cloud_env(tmp_path)
    manifest = _provider_manifest(env["DATABASE_URL"], bootstrap_env=env)
    env["QA_PROVIDER_EVIDENCE_TOKEN"] = (
        issue_qa_provider_evidence.issue_provider_evidence_token(
            manifest,
            private_key=PRIVATE_KEY_BASE64,
        )
    )
    env["QA_PROVIDER_EVIDENCE_PUBLIC_KEY"] = PUBLIC_KEY_BASE64

    assert bootstrap_cloud_qa.load_config(env).database_role == "postgres"


@pytest.mark.parametrize("branch_type", ["preview", "dedicated-qa-project"])
def test_issuer_consumes_real_provider_build_manifest_for_both_database_modes(branch_type):
    provider_module = runpy.run_path(
        str(Path(__file__).with_name("test_preview_provider_verifier.py"))
    )
    config, clients, apis = provider_module["fixtures"]()
    observed_at = provider_module["NOW"]
    database_url = (
        "postgresql+psycopg2://postgres.preview:qa-db-pass@"
        "db.preview.supabase.co:5432/postgres"
    )

    if branch_type == "dedicated-qa-project":
        qa_ref = DEDICATED_REF
        config = provider_module["configure_dedicated_baseline"](
            config,
            apis,
            lease_id=BASELINE_LEASE_ID,
        )
        database_url = (
            f"postgresql://postgres:qa-db-pass@db.{qa_ref}.supabase.co:5432/postgres"
        )

    manifest = provider_module["build_manifest"](
        config,
        clients,
        now=observed_at,
    )
    render_env_page = apis["render"].responses["/services/srv-preview/env-vars"]
    bootstrap_env = {
        item["envVar"]["key"]: item["envVar"]["value"]
        for item in render_env_page
    }
    token = issue_qa_provider_evidence.issue_provider_evidence_token(
        manifest,
        private_key=PRIVATE_KEY,
        now=int(observed_at.timestamp()),
        nonce="00112233445566778899aabbccddeeff",
    )

    evidence = bootstrap_cloud_qa.verify_provider_evidence_token(
        token,
        public_key=PUBLIC_KEY,
        database_url=database_url,
        expected_service_id="srv-preview",
        expected_code_sha=provider_module["SHA"],
        bootstrap_env=bootstrap_env,
        now=int(observed_at.timestamp()),
    )

    assert evidence.branch_type == branch_type


def test_load_config_rejects_production_even_when_isolated_flag_is_set(tmp_path):
    env = _env(tmp_path)
    env["APP_ENV"] = "production"

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="production APP_ENV"):
        bootstrap_cloud_qa.load_config(env)


def test_load_config_rejects_unmarked_database(tmp_path):
    env = _env(tmp_path)
    env["QA_DATABASE_ISOLATED"] = "false"

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="QA_DATABASE_ISOLATED"):
        bootstrap_cloud_qa.load_config(env)


def test_load_config_rejects_known_live_production_ref_even_with_fake_qa_attestations(tmp_path):
    env = _cloud_env(tmp_path)
    env.update(
        {
            "APP_ENV": "preview",
            "DATABASE_URL": (
                "postgresql+psycopg2://hotel_qa_bootstrap:secret@"
                "db.ezkljznogqpmrjxyvklr.supabase.co/postgres"
            ),
            "QA_EXPECTED_DATABASE_HOST": "db.ezkljznogqpmrjxyvklr.supabase.co",
            "QA_EXPECTED_DATABASE_PORT": "5432",
            "QA_EXPECTED_DATABASE_NAME": "postgres",
            "QA_EXPECTED_DATABASE_USER": "hotel_qa_bootstrap",
            "QA_PRODUCTION_DATABASE_HOST": "fake-production.example.test",
            "QA_PRODUCTION_DATABASE_REF": "fake-production-ref",
        }
    )

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="known production project ref"):
        bootstrap_cloud_qa.load_config(env)


@pytest.mark.parametrize(
    ("schema_version", "branch_type"),
    [(2, "preview"), (2, "dedicated-qa-project"), (3, "preview")],
)
def test_load_config_accepts_provider_verified_manifest_modes(
    tmp_path, schema_version, branch_type
):
    env = _cloud_env(
        tmp_path,
        schema_version=schema_version,
        branch_type=branch_type,
    )

    config = bootstrap_cloud_qa.load_config(env)

    assert config.app_env == "preview"
    assert len(config.personas) == 4
    assert config.database_role == "postgres"
    assert config.connection_fingerprint == bootstrap_cloud_qa.database_connection_fingerprint(
        env["DATABASE_URL"],
        project_ref=env["QA_DATABASE_BRANCH_REF"],
    )


def test_provider_capability_rejects_bootstrap_persona_or_run_drift(tmp_path):
    env = _cloud_env(tmp_path)
    env["QA_RUN_ID"] = "qa-drifted-run-002"

    with pytest.raises(
        bootstrap_cloud_qa.QABootstrapError,
        match="bootstrap configuration fingerprint does not match",
    ):
        bootstrap_cloud_qa.load_config(env)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("QA_BASELINE_ONLY", "false", "exactly true"),
        (
            "QA_BASELINE_LEASE_ID",
            "vTjklYwWvPso75WuXI4q5BdQZGyAdJcGGGL9fNQ9HKs",
            "lease ID does not match",
        ),
        ("QA_BASELINE_LEASE_TARGET_SHA", "b" * 40, "another Git SHA"),
        ("QA_BASELINE_LEASE_TARGET_BRANCH", "other/branch", "another Git branch"),
    ],
)
def test_dedicated_baseline_refuses_runtime_lease_drift(
    tmp_path, field, value, message
):
    env = _cloud_env(tmp_path, branch_type="dedicated-qa-project")
    env[field] = value

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match=message):
        bootstrap_cloud_qa.load_config(env)


def test_dedicated_baseline_refuses_missing_runtime_lease_key(tmp_path):
    env = _cloud_env(tmp_path, branch_type="dedicated-qa-project")
    env.pop("QA_BASELINE_LEASE_TARGET_BRANCH")

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="missing required lease"):
        bootstrap_cloud_qa.load_config(env)


def test_real_supabase_branch_refuses_dedicated_baseline_lease_env(tmp_path):
    env = _cloud_env(tmp_path, branch_type="preview")
    env.update(
        {
            "QA_BASELINE_ONLY": "true",
            "QA_BASELINE_LEASE_ID": BASELINE_LEASE_ID,
            "QA_BASELINE_LEASE_TARGET_SHA": CODE_SHA,
            "QA_BASELINE_LEASE_TARGET_BRANCH": GIT_BRANCH,
        }
    )

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="must not carry"):
        bootstrap_cloud_qa.load_config(env)


def test_load_config_rejects_branch_ref_different_from_provider_evidence(tmp_path):
    env = _cloud_env(tmp_path)
    env["QA_DATABASE_BRANCH_REF"] = "different-ref-001"

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="does not match QA_DATABASE_BRANCH_REF"):
        bootstrap_cloud_qa.load_config(env)


def test_load_config_rejects_missing_provider_evidence(tmp_path):
    env = _cloud_env(tmp_path)
    env.pop("QA_PROVIDER_EVIDENCE_TOKEN")

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="QA_PROVIDER_EVIDENCE_TOKEN"):
        bootstrap_cloud_qa.load_config(env)


def test_load_config_rejects_tampered_provider_evidence(tmp_path):
    env = _cloud_env(tmp_path)
    token = env["QA_PROVIDER_EVIDENCE_TOKEN"]
    env["QA_PROVIDER_EVIDENCE_TOKEN"] = f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}"

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="signature is invalid"):
        bootstrap_cloud_qa.load_config(env)


def test_load_config_rejects_provider_token_for_another_render_service(tmp_path):
    env = _cloud_env(tmp_path)
    env["RENDER_SERVICE_ID"] = "srv-another-preview"

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="service does not match Render"):
        bootstrap_cloud_qa.load_config(env)


def test_render_consumer_rejects_presence_of_producer_private_key(tmp_path):
    env = _cloud_env(tmp_path)
    env["QA_PROVIDER_EVIDENCE_PRIVATE_KEY"] = PRIVATE_KEY

    with pytest.raises(
        bootstrap_cloud_qa.QABootstrapError,
        match="PRIVATE_KEY must not be available",
    ):
        bootstrap_cloud_qa.load_config(env)


def test_load_config_rejects_provider_fingerprint_for_another_target(tmp_path):
    env = _cloud_env(tmp_path)
    env["DATABASE_URL"] = env["DATABASE_URL"].replace(".co/postgres", ".co:5433/postgres")
    env["QA_EXPECTED_DATABASE_PORT"] = "5433"

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="fingerprint does not match"):
        bootstrap_cloud_qa.load_config(env)


def test_generic_provider_still_requires_an_explicit_qa_role():
    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="dedicated QA role"):
        bootstrap_cloud_qa._validate_qa_database_role(
            "postgres",
            provider_verified_supabase=False,
            database_user_distinct=False,
        )


def test_verify_provider_evidence_rejects_expired_token(tmp_path):
    env = _cloud_env(tmp_path)
    manifest = _provider_manifest(env["DATABASE_URL"], bootstrap_env=env)
    old_now = int(time.time()) - 4000
    manifest["generated_at"] = datetime.fromtimestamp(old_now, timezone.utc).isoformat()
    env["QA_PROVIDER_EVIDENCE_TOKEN"] = issue_qa_provider_evidence.issue_provider_evidence_token(
        manifest,
        private_key=PRIVATE_KEY,
        now=old_now,
        ttl_seconds=900,
        nonce="0" * 32,
    )

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="expired or not yet valid"):
        bootstrap_cloud_qa.load_config(env)


def test_consumer_rejects_signed_manifest_fingerprint_for_another_target(tmp_path):
    env = _cloud_env(tmp_path)
    manifest = _provider_manifest(env["DATABASE_URL"], bootstrap_env=env)
    manifest["database"]["connection_fingerprint"] = f"sha256:{'0' * 64}"
    env["QA_PROVIDER_EVIDENCE_TOKEN"] = (
        issue_qa_provider_evidence.issue_provider_evidence_token(
            manifest,
            private_key=PRIVATE_KEY,
        )
    )

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="fingerprint does not match"):
        bootstrap_cloud_qa.load_config(env)


def test_issue_provider_evidence_rejects_stale_manifest(tmp_path):
    env = _cloud_env(tmp_path)
    manifest = _provider_manifest(env["DATABASE_URL"], bootstrap_env=env)
    manifest["generated_at"] = datetime.fromtimestamp(
        int(time.time()) - 7200,
        timezone.utc,
    ).isoformat()

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="manifest is stale"):
        issue_qa_provider_evidence.issue_provider_evidence_token(
            manifest,
            private_key=PRIVATE_KEY,
        )


def test_provider_evidence_issuer_writes_private_file_without_printing_token(
    monkeypatch, capsys, tmp_path
):
    env = _cloud_env(tmp_path)
    manifest_path = tmp_path / "provider-manifest.json"
    manifest_path.write_text(
        json.dumps(_provider_manifest(env["DATABASE_URL"], bootstrap_env=env)),
        encoding="utf-8",
    )
    output_path = tmp_path / "provider-evidence.token"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("QA_PROVIDER_EVIDENCE_PRIVATE_KEY", PRIVATE_KEY)

    assert issue_qa_provider_evidence.main(
        [str(manifest_path), "--output", str(output_path)]
    ) == 0

    token = output_path.read_text(encoding="utf-8").strip()
    captured = capsys.readouterr()
    assert token
    assert token not in captured.out
    assert token not in captured.err
    assert output_path.stat().st_mode & 0o777 == 0o600


def test_public_key_cannot_replace_producer_private_key(monkeypatch, capsys, tmp_path):
    env = _cloud_env(tmp_path)
    manifest_path = tmp_path / "provider-manifest.json"
    manifest_path.write_text(
        json.dumps(_provider_manifest(env["DATABASE_URL"], bootstrap_env=env)),
        encoding="utf-8",
    )
    output_path = tmp_path / "provider-evidence.token"
    monkeypatch.setenv("QA_PROVIDER_EVIDENCE_PUBLIC_KEY", PUBLIC_KEY)
    monkeypatch.delenv("QA_PROVIDER_EVIDENCE_PRIVATE_KEY", raising=False)

    assert issue_qa_provider_evidence.main(
        [str(manifest_path), "--output", str(output_path)]
    ) == 2

    assert "QA_PROVIDER_EVIDENCE_PRIVATE_KEY is required" in capsys.readouterr().err
    assert not output_path.exists()


def test_provider_evidence_issuer_refuses_unignored_repository_output(tmp_path):
    output_path = issue_qa_provider_evidence.ROOT_DIR / "qa-provider-evidence.token"

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="must use artifacts/qa"):
        issue_qa_provider_evidence.write_private_token(output_path, "not-a-real-token")

    assert not output_path.exists()


def test_config_repr_redacts_dsn_emails_passwords_and_pin(tmp_path):
    config = bootstrap_cloud_qa.load_config(_env(tmp_path))

    rendered = repr(config)

    assert config.database_url not in rendered
    assert config.master_admin_email not in rendered
    assert config.master_admin_password not in rendered
    assert config.master_admin_pin not in rendered
    assert all(persona.email not in rendered for persona in config.personas)
    assert all(persona.password not in rendered for persona in config.personas)


def test_load_config_requires_runtime_master_admin_match(tmp_path):
    env = _env(tmp_path)
    env["MASTER_ADMIN_PIN"] = "999999"

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="MASTER_ADMIN_PIN"):
        bootstrap_cloud_qa.load_config(env)


def test_upsert_is_idempotent_and_creates_all_database_personas(db, tmp_path):
    config = bootstrap_cloud_qa.load_config(_env(tmp_path))

    first = bootstrap_cloud_qa.upsert_qa_data(db, config)
    second = bootstrap_cloud_qa.upsert_qa_data(db, config)

    assert first.users_created == 4
    assert first.memberships_created == 4
    assert second.users_created == 0
    assert second.memberships_created == 0
    assert db.query(HotelConfiguration).count() == 1
    assert db.query(User).count() == 4
    assert db.query(HotelMembership).count() == 4

    expected_roles = {
        "owner@qa.example.test": "owner",
        "manager@qa.example.test": "manager",
        "reception@qa.example.test": "receptionist",
        "housekeeping@qa.example.test": "housekeeping",
    }
    users = {user.email: user for user in db.query(User).all()}
    memberships = {
        membership.user.email: membership
        for membership in db.query(HotelMembership).all()
    }
    for persona in config.personas:
        assert users[persona.email].role == expected_roles[persona.email]
        assert users[persona.email].is_active is True
        assert users[persona.email].is_verified is True
        assert verify_password(persona.password, users[persona.email].password_hash)
        assert memberships[persona.email].role == expected_roles[persona.email]
        assert memberships[persona.email].status == "active"
        assert memberships[persona.email].hotel_id == first.hotel_id

    assert config.master_admin_email not in users
    hotel = db.get(HotelConfiguration, first.hotel_id)
    assert hotel.get_extra_policies()["_qa_bootstrap"] == {
        "isolated": True,
        "run_id": config.run_id,
        "synthetic": True,
    }
    onboarding = db.get(OnboardingState, first.hotel_id)
    assert onboarding.finished is False
    assert {staff["role"] for staff in onboarding.get_staff()} == set(expected_roles.values())
    assert onboarding.get_payment_methods() == {"cash": {"enabled": True}}
    assert all(not channel["enabled"] for channel in onboarding.get_ota_channels().values())


def test_rerun_preserves_onboarding_completed_by_a_human(db, tmp_path):
    config = bootstrap_cloud_qa.load_config(_env(tmp_path))
    first = bootstrap_cloud_qa.upsert_qa_data(db, config)
    onboarding = db.get(OnboardingState, first.hotel_id)
    onboarding.finished = True
    onboarding.owner_name = "Owner entered through visible QA"
    onboarding.set_hotel_identity(
        {
            "name": "Hotel edited through visible QA",
            "address": "Synthetic visible address",
            "city": "Visible QA",
            "country": "AR",
        }
    )
    onboarding.set_payment_methods({"cash": {"enabled": True}, "card": {"enabled": True}})
    db.commit()

    bootstrap_cloud_qa.upsert_qa_data(db, replace(config))

    db.refresh(onboarding)
    assert onboarding.finished is True
    assert onboarding.owner_name == "Owner entered through visible QA"
    assert onboarding.get_hotel_identity()["name"] == "Hotel edited through visible QA"
    assert onboarding.get_payment_methods() == {
        "cash": {"enabled": True},
        "card": {"enabled": True},
    }


def test_upsert_refuses_existing_hotel_without_matching_qa_marker(db, tmp_path):
    config = bootstrap_cloud_qa.load_config(_env(tmp_path))
    owner = next(persona for persona in config.personas if persona.role == "owner")
    db.add(HotelConfiguration(id=91, owner_email=owner.email, hotel_name="Unmarked"))
    db.commit()

    with pytest.raises(bootstrap_cloud_qa.QABootstrapError, match="without the matching QA marker"):
        bootstrap_cloud_qa.upsert_qa_data(db, config)


def test_main_output_redacts_database_and_all_credentials(monkeypatch, capsys, tmp_path):
    env = _env(tmp_path)
    config = bootstrap_cloud_qa.load_config(env)
    monkeypatch.setattr(
        bootstrap_cloud_qa,
        "bootstrap_database",
        lambda _: bootstrap_cloud_qa.QABootstrapResult(1, 4, 4),
    )

    bootstrap_cloud_qa.main(env)

    output = capsys.readouterr().out
    sensitive_values = [
        config.database_url,
        config.master_admin_email,
        config.master_admin_password,
        config.master_admin_pin,
        *(persona.email for persona in config.personas),
        *(persona.password for persona in config.personas),
    ]
    assert all(value not in output for value in sensitive_values)
    assert config.run_id in output


def test_cli_refusal_does_not_echo_rejected_dsn_or_credentials(monkeypatch, capsys, tmp_path):
    env = _env(tmp_path)
    env["APP_ENV"] = "production"
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    assert bootstrap_cloud_qa.cli() == 2

    output = capsys.readouterr().err
    assert env["DATABASE_URL"] not in output
    assert env["QA_OWNER_EMAIL"] not in output
    assert env["QA_OWNER_PASSWORD"] not in output
    assert "production APP_ENV is forbidden" in output


def test_local_e2e_seed_output_does_not_print_database_or_credentials(monkeypatch, capsys):
    from scripts import seed_e2e_backend

    monkeypatch.setattr(seed_e2e_backend, "run_migrations", lambda: None)
    monkeypatch.setattr(seed_e2e_backend, "upsert_seed_data", lambda: None)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", seed_e2e_backend.E2E_DATABASE_URL)
    monkeypatch.setenv("E2E_OWNER_EMAIL", "synthetic-owner@example.test")
    monkeypatch.setenv("E2E_OWNER_PASSWORD", "SyntheticOwnerPass001!")

    seed_e2e_backend.main()

    output = capsys.readouterr().out
    assert seed_e2e_backend.E2E_DATABASE_URL not in output
    assert "synthetic-owner@example.test" not in output
    assert "SyntheticOwnerPass001!" not in output


def test_rerun_repairs_only_the_matching_tagged_qa_personas(db, tmp_path):
    config = bootstrap_cloud_qa.load_config(_env(tmp_path))
    bootstrap_cloud_qa.upsert_qa_data(db, config)
    manager = db.query(User).filter(User.email == "manager@qa.example.test").one()
    manager.is_active = False
    manager.role = "housekeeping"
    membership = db.query(HotelMembership).filter(HotelMembership.user_id == manager.id).one()
    membership.status = "revoked"
    membership.role = "housekeeping"
    db.commit()

    bootstrap_cloud_qa.upsert_qa_data(db, replace(config))

    db.refresh(manager)
    db.refresh(membership)
    assert manager.is_active is True
    assert manager.role == "manager"
    assert membership.status == "active"
    assert membership.role == "manager"
