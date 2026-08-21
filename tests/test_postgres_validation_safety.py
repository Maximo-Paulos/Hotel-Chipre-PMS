"""Safety contract for destructive PostgreSQL validation tests.

These tests never connect to a database. They exercise only the target guard
that runs before the PostgreSQL fixtures create or drop schema objects.
"""
from __future__ import annotations

import ast
import inspect
import json
import time
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import tests.conftest as postgres_conftest
import tests.test_postgres_validation as postgres_validation
from scripts import bootstrap_cloud_qa, issue_qa_provider_evidence
from scripts.agent_ops.qa_bootstrap_contract import (
    BOOTSTRAP_CONFIGURATION_VERSION,
    bootstrap_configuration_fingerprint,
)
from tests.postgres_test_safety import (
    CANONICAL_PRODUCTION_REF,
    PostgresTargetSafetyError,
    validate_postgres_test_target,
)


SAFE_HOST = "aws-0-us-east-1.pooler.supabase.com"
SAFE_BRANCH_REF = "branchqa123"
SAFE_ROLE = "postgres.branchqa123"
SAFE_DATABASE = "postgres"
SAFE_DSN = f"postgresql+psycopg2://{SAFE_ROLE}@{SAFE_HOST}:5432/{SAFE_DATABASE}"
SAFE_SERVICE_ID = "srv-preview-qa"
SAFE_CODE_SHA = "a" * 40
PRIVATE_KEY_OBJECT = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
PRIVATE_KEY = PRIVATE_KEY_OBJECT.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode("ascii")
PUBLIC_KEY = PRIVATE_KEY_OBJECT.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("ascii")


def _bootstrap_environment() -> dict[str, str]:
    return {
        "AI_ENABLED": "false",
        "AI_PROVIDER": "disabled",
        "APP_ENV": "test",
        "CONNECTIONS_ENABLED": "false",
        "EXTERNAL_EFFECTS_ENABLED": "false",
        "GOOGLE_LOGIN_ENABLED": "false",
        "APPLE_LOGIN_ENABLED": "false",
        "INBOUND_PROVIDER_EVENTS_ENABLED": "false",
        "EMAIL_PROVIDER": "null",
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
        "QA_PROVIDER_EVIDENCE_PUBLIC_KEY": PUBLIC_KEY,
        "QA_RECEPTION_EMAIL": "reception@qa.example.test",
        "QA_RECEPTION_PASSWORD": "ReceptionQaPass003!",
        "QA_RUN_ID": "qa-postgres-safety",
        "QA_RUN_MIGRATIONS": "false",
    }


def _provider_manifest(
    database_url: str,
    *,
    bootstrap_env: dict[str, str],
    branch_ref: str = SAFE_BRANCH_REF,
    code_sha: str = SAFE_CODE_SHA,
    service_id: str = SAFE_SERVICE_ID,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    timestamp = (generated_at or datetime.now(timezone.utc)).isoformat()
    production_url = (
        f"postgresql://postgres:production-secret@db.{CANONICAL_PRODUCTION_REF}.supabase.co:5432/postgres"
    )
    return {
        "schema_version": 3,
        "evidence_type": "provider-verified-isolated-preview",
        "code_sha": code_sha,
        "generated_at": timestamp,
        "generated_by": {
            "kind": "provider-api-verifier",
            "workflow_run_id": 12345,
            "workflow_path": ".github/workflows/verify-preview-providers.yml",
            "github_environment": "preview-qa",
            "event_name": "workflow_dispatch",
            "actor_id": "12345",
            "repository": "Maximo-Paulos/Hotel-Chipre-PMS",
            "git_branch": "codex/test-postgres-guard",
            "evidence_sources": [
                "render-api",
                "supabase-management-api",
                "vercel-api",
            ],
        },
        "database": {
            "provider": "supabase",
            "evidence_source": "supabase-management-api",
            "project_ref": branch_ref,
            "branch_type": "preview",
            "isolation_mode": "supabase-branch-per-target",
            "branch_ref": branch_ref,
            "production_branch_ref": CANONICAL_PRODUCTION_REF,
            "with_data": False,
            "fingerprint_method": "sha256",
            "fingerprint_payload_version": "supabase-connection-v1",
            "connection_fingerprint": bootstrap_cloud_qa.database_connection_fingerprint(
                database_url,
                project_ref=branch_ref,
            ),
            "production_connection_fingerprint": bootstrap_cloud_qa.database_connection_fingerprint(
                production_url,
                project_ref=CANONICAL_PRODUCTION_REF,
            ),
            "database_endpoint_distinct": True,
            "database_user_distinct": True,
            "database_password_distinct": True,
            "jwt_identity_distinct": True,
        },
        "backend": {
            "provider": "render",
            "evidence_source": "render-api",
            "environment": "preview",
            "service_id": service_id,
            "production_service_id": "srv-production",
            "deployment_id": "dep-preview-qa",
            "code_sha": code_sha,
            "git_branch": "codex/test-postgres-guard",
        },
        "frontend": {
            "provider": "vercel",
            "evidence_source": "vercel-api",
            "environment": "preview",
            "deployment_id": "dpl-preview-qa",
            "project_id": "prj-preview-qa",
            "team_id": "team-preview-qa",
            "code_sha": code_sha,
            "git_branch": "codex/test-postgres-guard",
        },
        "configuration": {
            "evidence_source": "render-api",
            "environment_id": "env-preview-qa",
            "production_environment_id": "env-production",
            "qa_secrets_scope": "preview-service",
            "bootstrap_configuration_fingerprint": bootstrap_configuration_fingerprint(
                {**bootstrap_env, "DATABASE_URL": database_url}
            ),
            "bootstrap_configuration_version": BOOTSTRAP_CONFIGURATION_VERSION,
        },
    }


def _local_evidence_payload(
    *,
    host: str,
    role: str,
    database: str,
    branch_ref: str,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "provider": "local-postgres",
        "evidence_source": "local-ephemeral-fixture",
        "environment": "test",
        "branch_ref": branch_ref,
        "production_ref": CANONICAL_PRODUCTION_REF,
        "host": host,
        "port": 5432,
        "database": database,
        "role": role,
        "database_isolated": True,
        "data_classification": "synthetic-only",
    }
    payload.update(overrides)
    return payload


def _safe_environment(
    tmp_path,
    *,
    local_evidence_overrides: dict[str, object] | None = None,
    token_database_url: str | None = None,
    token_project_ref: str = SAFE_BRANCH_REF,
    token_now: int | None = None,
    token_ttl_seconds: int = 900,
    **overrides: str,
) -> dict[str, str]:
    environment = {
        **_bootstrap_environment(),
        "ALLOW_DESTRUCTIVE_POSTGRES_TESTS": "1",
        "POSTGRES_TEST_ISOLATION_CONFIRMED": "1",
        "POSTGRES_TEST_DATABASE_URL_EXPLICIT": SAFE_DSN,
        "POSTGRES_TEST_EXPECTED_HOST": SAFE_HOST,
        "POSTGRES_TEST_EXPECTED_ROLE": SAFE_ROLE,
        "POSTGRES_TEST_EXPECTED_DATABASE": SAFE_DATABASE,
        "POSTGRES_TEST_ISOLATED_BRANCH_REF": SAFE_BRANCH_REF,
        "POSTGRES_TEST_PRODUCTION_REF": CANONICAL_PRODUCTION_REF,
        "RENDER_SERVICE_ID": SAFE_SERVICE_ID,
        "RENDER_GIT_COMMIT": SAFE_CODE_SHA,
    }
    environment.update(overrides)
    actual_dsn = environment.get("POSTGRES_TEST_DATABASE_URL_EXPLICIT") or SAFE_DSN
    parsed = urlparse(actual_dsn)
    host = (parsed.hostname or SAFE_HOST).casefold()
    role = unquote(parsed.username or SAFE_ROLE)
    database = unquote(parsed.path.lstrip("/").split("/", 1)[0] or SAFE_DATABASE)
    branch_ref = environment["POSTGRES_TEST_ISOLATED_BRANCH_REF"]

    if host not in {"localhost", "127.0.0.1", "::1"}:
        issued_at = int(time.time()) if token_now is None else token_now
        token_target = token_database_url or SAFE_DSN
        environment["DATABASE_URL"] = token_target
        manifest = _provider_manifest(
            token_target,
            bootstrap_env=environment,
            branch_ref=token_project_ref,
            generated_at=datetime.fromtimestamp(issued_at, tz=timezone.utc),
        )
        token = issue_qa_provider_evidence.issue_provider_evidence_token(
            manifest,
            private_key=PRIVATE_KEY,
            now=issued_at,
            ttl_seconds=token_ttl_seconds,
            nonce="00112233445566778899aabbccddeeff",
        )
        environment.setdefault("POSTGRES_TEST_PROVIDER_EVIDENCE_TOKEN", token)
        environment.setdefault("QA_PROVIDER_EVIDENCE_PUBLIC_KEY", PUBLIC_KEY)

    evidence_file = tmp_path / "local-postgres-evidence.json"
    local_evidence = _local_evidence_payload(
        host=host,
        role=role,
        database=database,
        branch_ref=branch_ref,
    )
    local_evidence.update(local_evidence_overrides or {})
    evidence_file.write_text(
        json.dumps(local_evidence),
        encoding="utf-8",
    )
    environment.setdefault("POSTGRES_TEST_PROVIDER_EVIDENCE_FILE", str(evidence_file))
    return environment


def test_accepts_explicit_supabase_qa_branch_with_signed_provider_evidence(tmp_path):
    assert validate_postgres_test_target(SAFE_DSN, _safe_environment(tmp_path)) == SAFE_DSN


def test_accepts_direct_supabase_branch_host_with_postgres_role(tmp_path):
    host = f"db.{SAFE_BRANCH_REF}.supabase.co"
    role = "postgres"
    dsn = f"postgresql://{role}@{host}:5432/{SAFE_DATABASE}"
    environment = _safe_environment(
        tmp_path,
        token_database_url=dsn,
        POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
        POSTGRES_TEST_EXPECTED_HOST=host,
        POSTGRES_TEST_EXPECTED_ROLE=role,
    )

    assert validate_postgres_test_target(dsn, environment) == dsn


def test_accepts_explicit_local_disposable_database_with_local_evidence(tmp_path):
    host = "127.0.0.1"
    role = "qa_user"
    database = "hotel_chipre_pr24_test"
    branch_ref = "pr24"
    dsn = f"postgresql://{role}@{host}:5432/{database}"
    environment = _safe_environment(
        tmp_path,
        POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
        POSTGRES_TEST_EXPECTED_HOST=host,
        POSTGRES_TEST_EXPECTED_ROLE=role,
        POSTGRES_TEST_EXPECTED_DATABASE=database,
        POSTGRES_TEST_ISOLATED_BRANCH_REF=branch_ref,
    )

    assert validate_postgres_test_target(dsn, environment) == dsn


def test_remote_target_rejects_self_attested_json_without_signed_token(tmp_path):
    environment = _safe_environment(
        tmp_path,
        POSTGRES_TEST_PROVIDER_EVIDENCE_TOKEN="",
    )
    forged = tmp_path / "forged-provider-evidence.json"
    forged.write_text(
        json.dumps(
            {
                "provider": "supabase",
                "database_isolated": True,
                "branch_ref": SAFE_BRANCH_REF,
            }
        ),
        encoding="utf-8",
    )
    environment["POSTGRES_TEST_PROVIDER_EVIDENCE_FILE"] = str(forged)

    with pytest.raises(PostgresTargetSafetyError, match="signed provider evidence token"):
        validate_postgres_test_target(SAFE_DSN, environment)


def test_remote_target_rejects_wrong_ed25519_public_key(tmp_path):
    environment = _safe_environment(tmp_path)
    environment["QA_PROVIDER_EVIDENCE_PUBLIC_KEY"] = (
        Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )

    with pytest.raises(PostgresTargetSafetyError, match="signed provider evidence is invalid"):
        validate_postgres_test_target(SAFE_DSN, environment)


def test_remote_target_rejects_expired_provider_token(tmp_path):
    now = int(time.time())
    environment = _safe_environment(
        tmp_path,
        token_now=now - 901,
        token_ttl_seconds=900,
    )

    with pytest.raises(PostgresTargetSafetyError, match="signed provider evidence is invalid"):
        validate_postgres_test_target(SAFE_DSN, environment)


def test_remote_target_rejects_token_for_different_provider_branch(tmp_path):
    environment = _safe_environment(tmp_path, token_project_ref="differentqa123")

    with pytest.raises(PostgresTargetSafetyError, match="does not match the QA branch"):
        validate_postgres_test_target(SAFE_DSN, environment)


def test_remote_target_rejects_token_bound_to_different_database_fingerprint(tmp_path):
    host = f"db.{SAFE_BRANCH_REF}.supabase.co"
    dsn = f"postgresql://{SAFE_ROLE}@{host}:5432/{SAFE_DATABASE}"
    environment = _safe_environment(
        tmp_path,
        POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
        POSTGRES_TEST_EXPECTED_HOST=host,
    )

    with pytest.raises(PostgresTargetSafetyError, match="signed provider evidence is invalid"):
        validate_postgres_test_target(dsn, environment)


@pytest.mark.parametrize(
    "overrides",
    [
        {"RENDER_SERVICE_ID": "srv-different"},
        {"RENDER_GIT_COMMIT": "b" * 40},
    ],
)
def test_remote_target_rejects_token_for_different_render_identity(tmp_path, overrides):
    with pytest.raises(PostgresTargetSafetyError, match="signed provider evidence is invalid"):
        validate_postgres_test_target(SAFE_DSN, _safe_environment(tmp_path, **overrides))


def test_pg_engine_fixture_skips_before_create_engine_when_evidence_is_missing(monkeypatch):
    called = False

    def forbidden_create_engine(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("create_engine must not run for an unproven target")

    monkeypatch.setattr(
        postgres_conftest,
        "_PG_DSN",
        "postgresql://guard_check@127.0.0.1:5432/guard_check_test",
    )
    monkeypatch.setattr(postgres_conftest, "create_engine", forbidden_create_engine)
    for variable in (
        "ALLOW_DESTRUCTIVE_POSTGRES_TESTS",
        "POSTGRES_TEST_ISOLATION_CONFIRMED",
        "POSTGRES_TEST_DATABASE_URL_EXPLICIT",
        "POSTGRES_TEST_EXPECTED_HOST",
        "POSTGRES_TEST_EXPECTED_ROLE",
        "POSTGRES_TEST_EXPECTED_DATABASE",
        "POSTGRES_TEST_ISOLATED_BRANCH_REF",
        "POSTGRES_TEST_PRODUCTION_REF",
        "POSTGRES_TEST_PROVIDER_EVIDENCE_FILE",
        "POSTGRES_TEST_PROVIDER_EVIDENCE_TOKEN",
        "QA_PROVIDER_EVIDENCE_PUBLIC_KEY",
        "RENDER_SERVICE_ID",
        "RENDER_GIT_COMMIT",
    ):
        monkeypatch.delenv(variable, raising=False)

    fixture_generator = postgres_conftest.pg_engine.__wrapped__()
    with pytest.raises(pytest.skip.Exception, match="not explicitly proven isolated"):
        next(fixture_generator)
    assert called is False


def test_destructive_postgres_operations_are_guarded_before_execution():
    fixture_source = inspect.getsource(postgres_conftest.pg_engine)
    initial_guard = fixture_source.index("_validated_pg_dsn_or_skip")
    assert initial_guard < fixture_source.index("create_engine")
    assert initial_guard < fixture_source.index("create_all")
    assert fixture_source.rindex("validate_postgres_test_target") < fixture_source.index("drop_all")

    reset_source = inspect.getsource(postgres_validation._reset_pg_to_clean_head)
    guard_position = reset_source.index("safe_dsn = validate_postgres_test_target")
    assert guard_position < reset_source.index("engine = create_engine")
    assert guard_position < reset_source.index("DROP SCHEMA")


def test_postgres_validation_has_no_tautological_true_assertions():
    tree = ast.parse(inspect.getsource(postgres_validation))
    tautologies = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert)
        and any(
            isinstance(part, ast.Constant) and part.value is True
            for part in ast.walk(node.test)
        )
    ]
    assert tautologies == []


def test_reservation_concurrency_evidence_is_no_longer_marked_pending():
    concurrency_test = postgres_validation.test_concurrent_reservation_auto_assignment_does_not_double_book
    marks = getattr(concurrency_test, "pytestmark", [])
    assert any(mark.name == "skipif" for mark in marks)
    assert "evidence_pending" not in concurrency_test.__name__


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"ALLOW_DESTRUCTIVE_POSTGRES_TESTS": "0"}, "opt-in"),
        ({"POSTGRES_TEST_ISOLATION_CONFIRMED": "0"}, "isolation confirmation"),
        ({"POSTGRES_TEST_DATABASE_URL_EXPLICIT": ""}, "explicit database URL"),
        ({"POSTGRES_TEST_EXPECTED_HOST": ""}, "expected host"),
        ({"POSTGRES_TEST_EXPECTED_ROLE": ""}, "expected role"),
        ({"POSTGRES_TEST_EXPECTED_DATABASE": ""}, "expected database"),
        ({"POSTGRES_TEST_ISOLATED_BRANCH_REF": ""}, "branch reference"),
        ({"POSTGRES_TEST_PRODUCTION_REF": ""}, "production reference"),
        ({"POSTGRES_TEST_PROVIDER_EVIDENCE_TOKEN": ""}, "signed provider evidence token"),
        ({"QA_PROVIDER_EVIDENCE_PUBLIC_KEY": ""}, "public key"),
        ({"RENDER_SERVICE_ID": ""}, "Render service identity"),
        ({"RENDER_GIT_COMMIT": ""}, "Render code SHA"),
    ],
)
def test_rejects_missing_required_safety_signals(tmp_path, overrides, expected_fragment):
    with pytest.raises(PostgresTargetSafetyError, match=expected_fragment):
        validate_postgres_test_target(SAFE_DSN, _safe_environment(tmp_path, **overrides))


def test_rejects_dsn_not_identical_to_explicit_target(tmp_path):
    ambiguous_dsn = "postgresql://qa_user@127.0.0.1:5432/qa_other_test"

    with pytest.raises(PostgresTargetSafetyError, match="does not match"):
        validate_postgres_test_target(ambiguous_dsn, _safe_environment(tmp_path))


@pytest.mark.parametrize(
    ("field", "value", "expected_fragment"),
    [
        ("POSTGRES_TEST_EXPECTED_HOST", "different.example.invalid", "host does not match"),
        ("POSTGRES_TEST_EXPECTED_ROLE", "different_role", "role does not match"),
        ("POSTGRES_TEST_EXPECTED_DATABASE", "different_db", "database does not match"),
    ],
)
def test_rejects_expected_target_identity_mismatch(tmp_path, field, value, expected_fragment):
    with pytest.raises(PostgresTargetSafetyError, match=expected_fragment):
        validate_postgres_test_target(SAFE_DSN, _safe_environment(tmp_path, **{field: value}))


def test_rejects_transaction_pooler_port(tmp_path):
    dsn = f"postgresql://{SAFE_ROLE}@{SAFE_HOST}:6543/{SAFE_DATABASE}"

    with pytest.raises(PostgresTargetSafetyError, match="direct or session-mode"):
        validate_postgres_test_target(
            dsn,
            _safe_environment(tmp_path, POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn),
        )


def test_rejects_unapproved_remote_host(tmp_path):
    host = "qa-db.example.invalid"
    dsn = f"postgresql://{SAFE_ROLE}@{host}:5432/{SAFE_DATABASE}"

    with pytest.raises(PostgresTargetSafetyError, match="allowed QA provider host"):
        validate_postgres_test_target(
            dsn,
            _safe_environment(
                tmp_path,
                POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
                POSTGRES_TEST_EXPECTED_HOST=host,
            ),
        )


def test_rejects_production_like_host_even_with_other_signals(tmp_path):
    host = "production-db.supabase.co"
    dsn = f"postgresql://{SAFE_ROLE}@{host}:5432/{SAFE_DATABASE}"

    with pytest.raises(PostgresTargetSafetyError, match="production-like host"):
        validate_postgres_test_target(
            dsn,
            _safe_environment(
                tmp_path,
                POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
                POSTGRES_TEST_EXPECTED_HOST=host,
            ),
        )


@pytest.mark.parametrize("branch_ref", ["main", "production", "prod-branch", "master"])
def test_rejects_production_like_branch_references(tmp_path, branch_ref):
    with pytest.raises(PostgresTargetSafetyError, match="production-like"):
        validate_postgres_test_target(
            SAFE_DSN,
            _safe_environment(tmp_path, POSTGRES_TEST_ISOLATED_BRANCH_REF=branch_ref),
        )


def test_rejects_noncanonical_production_reference(tmp_path):
    with pytest.raises(PostgresTargetSafetyError, match="not canonical"):
        validate_postgres_test_target(
            SAFE_DSN,
            _safe_environment(tmp_path, POSTGRES_TEST_PRODUCTION_REF="some-other-ref"),
        )


def test_rejects_known_production_reference_anywhere_in_target(tmp_path):
    role = f"postgres.{SAFE_BRANCH_REF}.{CANONICAL_PRODUCTION_REF}"
    dsn = f"postgresql://{role}@{SAFE_HOST}:5432/{SAFE_DATABASE}"

    with pytest.raises(PostgresTargetSafetyError, match="known production database"):
        validate_postgres_test_target(
            dsn,
            _safe_environment(
                tmp_path,
                POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
                POSTGRES_TEST_EXPECTED_ROLE=role,
            ),
        )


def test_rejects_qa_reference_equal_to_production_reference(tmp_path):
    production_dsn = (
        f"postgresql://postgres.{CANONICAL_PRODUCTION_REF}@"
        f"{SAFE_HOST}:5432/{SAFE_DATABASE}"
    )

    with pytest.raises(PostgresTargetSafetyError, match="must be distinct"):
        validate_postgres_test_target(
            production_dsn,
            _safe_environment(
                tmp_path,
                POSTGRES_TEST_DATABASE_URL_EXPLICIT=production_dsn,
                POSTGRES_TEST_EXPECTED_ROLE=f"postgres.{CANONICAL_PRODUCTION_REF}",
                POSTGRES_TEST_ISOLATED_BRANCH_REF=CANONICAL_PRODUCTION_REF,
            ),
        )


def test_rejects_branch_reference_absent_from_target_identity(tmp_path):
    dsn = f"postgresql://postgres.qaother@{SAFE_HOST}:5432/{SAFE_DATABASE}"

    with pytest.raises(PostgresTargetSafetyError, match="not present"):
        validate_postgres_test_target(
            dsn,
            _safe_environment(
                tmp_path,
                POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
                POSTGRES_TEST_EXPECTED_ROLE="postgres.qaother",
            ),
        )


def test_rejects_ambiguous_local_database_name(tmp_path):
    host = "127.0.0.1"
    role = "qa_user"
    database = "hotel_chipre_pr24"
    branch_ref = "pr24"
    dsn = f"postgresql://{role}@{host}:5432/{database}"

    with pytest.raises(PostgresTargetSafetyError, match="not explicitly disposable"):
        validate_postgres_test_target(
            dsn,
            _safe_environment(
                tmp_path,
                POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
                POSTGRES_TEST_EXPECTED_HOST=host,
                POSTGRES_TEST_EXPECTED_ROLE=role,
                POSTGRES_TEST_EXPECTED_DATABASE=database,
                POSTGRES_TEST_ISOLATED_BRANCH_REF=branch_ref,
            ),
        )


def test_rejects_target_without_database_name(tmp_path):
    dsn = f"postgresql://{SAFE_ROLE}@{SAFE_HOST}:5432"

    with pytest.raises(PostgresTargetSafetyError, match="database name"):
        validate_postgres_test_target(
            dsn,
            _safe_environment(tmp_path, POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn),
        )


def test_local_target_rejects_unreadable_local_evidence(tmp_path):
    host = "127.0.0.1"
    role = "qa_user"
    database = "hotel_chipre_pr24_test"
    branch_ref = "pr24"
    dsn = f"postgresql://{role}@{host}:5432/{database}"
    missing = tmp_path / "missing-evidence.json"
    environment = _safe_environment(
        tmp_path,
        POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
        POSTGRES_TEST_EXPECTED_HOST=host,
        POSTGRES_TEST_EXPECTED_ROLE=role,
        POSTGRES_TEST_EXPECTED_DATABASE=database,
        POSTGRES_TEST_ISOLATED_BRANCH_REF=branch_ref,
        POSTGRES_TEST_PROVIDER_EVIDENCE_FILE=str(missing),
    )

    with pytest.raises(PostgresTargetSafetyError, match="unreadable"):
        validate_postgres_test_target(dsn, environment)


@pytest.mark.parametrize(
    ("local_overrides", "expected_fragment"),
    [
        ({"database_isolated": False}, "isolated database"),
        ({"data_classification": "unknown"}, "synthetic-only"),
        ({"environment": "production"}, "not disposable"),
        ({"evidence_source": "manual-assertion"}, "source is invalid"),
        ({"branch_ref": "different-ref"}, "does not match"),
        ({"production_ref": "different-ref"}, "does not match"),
        ({"host": "different.example.invalid"}, "does not match"),
        ({"port": 6543}, "does not match"),
        ({"database": "different"}, "does not match"),
        ({"role": "different"}, "does not match"),
    ],
)
def test_rejects_invalid_or_mismatched_local_evidence(
    tmp_path,
    local_overrides,
    expected_fragment,
):
    host = "127.0.0.1"
    role = "qa_user"
    database = "hotel_chipre_pr24_test"
    branch_ref = "pr24"
    dsn = f"postgresql://{role}@{host}:5432/{database}"
    environment = _safe_environment(
        tmp_path,
        local_evidence_overrides=local_overrides,
        POSTGRES_TEST_DATABASE_URL_EXPLICIT=dsn,
        POSTGRES_TEST_EXPECTED_HOST=host,
        POSTGRES_TEST_EXPECTED_ROLE=role,
        POSTGRES_TEST_EXPECTED_DATABASE=database,
        POSTGRES_TEST_ISOLATED_BRANCH_REF=branch_ref,
    )

    with pytest.raises(PostgresTargetSafetyError, match=expected_fragment):
        validate_postgres_test_target(dsn, environment)


def test_safety_errors_never_include_database_url_or_credentials(tmp_path):
    secret_marker = "must-not-appear"
    unsafe_dsn = f"postgresql://{SAFE_ROLE}:{secret_marker}@{SAFE_HOST}:5432/{SAFE_DATABASE}"

    with pytest.raises(PostgresTargetSafetyError) as error:
        validate_postgres_test_target(unsafe_dsn, _safe_environment(tmp_path))

    assert secret_marker not in str(error.value)
    assert unsafe_dsn not in str(error.value)
