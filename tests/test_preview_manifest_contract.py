"""Regression tests for the isolated preview evidence contract."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.agent_ops.validate_preview_manifest import validate_manifest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "agent_ops" / "validate_preview_manifest.py"
LEGACY_VALIDATOR = ROOT / "scripts" / "agent_ops" / "check_preview_manifest.py"
EXAMPLE = ROOT / "qa" / "preview-manifest.example.json"


def example_manifest() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def validate(tmp_path: Path, manifest: object, *args: str) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "preview-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path), "--skip-freshness", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_example_is_sha_task_and_artifact_run_bound(tmp_path: Path) -> None:
    manifest = example_manifest()
    output = tmp_path / "github-output"
    result = validate(
        tmp_path,
        manifest,
        "--expected-sha",
        manifest["code_sha"],
        "--expected-task-id",
        manifest["task_id"],
        "--expected-workflow-run-id",
        str(manifest["generated_by"]["workflow_run_id"]),
        "--expected-baseline-lease-id",
        manifest["database"]["baseline_lease_id"],
        "--github-output",
        str(output),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    emitted = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    assert emitted == {
        "app_url": manifest["app_url"],
        "api_origin": manifest["api_origin"],
        "api_base_url": manifest["api_base_url"],
        "health_url": manifest["health_url"],
        "app_host": "hotel-chipre-pms-git-feature-123.vercel.app",
        "api_host": "hotel-chipre-pms-api-pr-123.onrender.com",
    }


def test_api_base_may_equal_origin_without_breaking_health_url(tmp_path: Path) -> None:
    manifest = example_manifest()
    manifest["api_base_url"] = manifest["api_origin"]
    manifest["frontend_vite_api_url"] = manifest["api_origin"]

    result = validate(tmp_path, manifest)

    assert result.returncode == 0, result.stdout + result.stderr


def test_api_base_rejects_arbitrary_path_and_health_under_api(tmp_path: Path) -> None:
    manifest = example_manifest()
    manifest["api_base_url"] = f'{manifest["api_origin"]}/v1'
    manifest["frontend_vite_api_url"] = manifest["api_base_url"]
    manifest["health_url"] = f'{manifest["api_origin"]}/api/health'

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    assert "api_base_url" in result.stdout
    assert "health_url" in result.stdout


def test_legacy_boolean_self_attestation_is_rejected(tmp_path: Path) -> None:
    legacy = {
        "schema_version": 1,
        "task_id": "feature-123",
        "code_sha": "abcdef1",
        "app_url": "https://hotel-chipre-pms-git-feature-123.vercel.app",
        "api_url": "https://hotel-chipre-pms-api-pr-123.onrender.com",
        "supabase_branch_ref": "pr-123",
        "database_isolated": True,
        "qa_secrets_isolated": True,
    }

    result = validate(tmp_path, legacy)

    assert result.returncode == 1
    assert "provider-api-verifier" in result.stdout
    assert "backend" in result.stdout
    assert "database" in result.stdout


def test_legacy_entrypoint_delegates_to_the_strong_contract(tmp_path: Path) -> None:
    manifest = example_manifest()
    path = tmp_path / "preview-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    accepted = subprocess.run(
        [sys.executable, str(LEGACY_VALIDATOR), str(path), "--skip-freshness"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr

    manifest["schema_version"] = 1
    path.write_text(json.dumps(manifest), encoding="utf-8")
    rejected = subprocess.run(
        [sys.executable, str(LEGACY_VALIDATOR), str(path), "--skip-freshness"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode == 1
    assert "schema_version must be 2" in rejected.stdout


def test_production_urls_are_rejected_everywhere(tmp_path: Path) -> None:
    manifest = example_manifest()
    manifest["api_origin"] = "https://api.hotels-pms.com"
    manifest["api_base_url"] = "https://api.hotels-pms.com/api"
    manifest["frontend_vite_api_url"] = "https://api.hotels-pms.com/api"
    manifest["health_url"] = "https://api.hotels-pms.com/health"

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    assert result.stdout.count("must not use a production host") >= 4


def test_backend_sha_and_preview_service_must_be_distinct(tmp_path: Path) -> None:
    manifest = example_manifest()
    manifest["backend"]["code_sha"] = "0" * 40
    manifest["backend"]["service_url"] = "https://unrelated-backend.onrender.com"
    manifest["backend"]["service_id"] = manifest["backend"]["production_service_id"]

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    assert "backend.code_sha" in result.stdout
    assert "backend.service_url" in result.stdout
    assert "preview service must differ" in result.stdout


def test_database_branch_and_connection_must_differ_from_production(tmp_path: Path) -> None:
    manifest = example_manifest()
    database = manifest["database"]
    database["branch_ref"] = database["production_branch_ref"]
    database["connection_fingerprint"] = database["production_connection_fingerprint"]

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    assert "preview branch must differ" in result.stdout
    assert "preview connection must differ" in result.stdout


def test_dedicated_baseline_requires_lease_mode_and_exact_target(tmp_path: Path) -> None:
    manifest = example_manifest()
    database = manifest["database"]
    database["isolation_mode"] = "supabase-branch-per-target"
    database["baseline_lease_target_sha"] = "0" * 40
    database["baseline_lease_target_branch"] = "codex/other-target"

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    assert "dedicated-qa-baseline-exclusive" in result.stdout
    assert "baseline_lease_target_sha" in result.stdout
    assert "baseline_lease_target_branch" in result.stdout


@pytest.mark.parametrize(
    "field",
    ["baseline_lease_id", "baseline_lease_target_sha", "baseline_lease_target_branch"],
)
def test_dedicated_baseline_rejects_missing_lease_field(
    tmp_path: Path,
    field: str,
) -> None:
    manifest = example_manifest()
    del manifest["database"][field]

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    assert field in result.stdout


@pytest.mark.parametrize("lease_id", ["lease-123", "a" * 32])
def test_dedicated_baseline_rejects_weak_lease_id(
    tmp_path: Path,
    lease_id: str,
) -> None:
    manifest = example_manifest()
    manifest["database"]["baseline_lease_id"] = lease_id

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    assert "baseline_lease_id" in result.stdout


def test_real_branch_mode_forbids_all_baseline_lease_fields(tmp_path: Path) -> None:
    manifest = example_manifest()
    database = manifest["database"]
    database["branch_type"] = "preview"
    database["isolation_mode"] = "supabase-branch-per-target"
    names = manifest["configuration"]["required_secret_names_verified"]
    manifest["configuration"]["required_secret_names_verified"] = [
        name for name in names if not name.startswith("QA_BASELINE_")
    ]

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    for field in (
        "baseline_lease_id",
        "baseline_lease_target_sha",
        "baseline_lease_target_branch",
    ):
        assert f"database.{field} is forbidden" in result.stdout


def test_real_branch_mode_without_baseline_fields_is_valid(tmp_path: Path) -> None:
    manifest = example_manifest()
    database = manifest["database"]
    database["branch_type"] = "preview"
    database["isolation_mode"] = "supabase-branch-per-target"
    for field in (
        "baseline_lease_id",
        "baseline_lease_target_sha",
        "baseline_lease_target_branch",
    ):
        del database[field]
    names = manifest["configuration"]["required_secret_names_verified"]
    manifest["configuration"]["required_secret_names_verified"] = [
        name for name in names if not name.startswith("QA_BASELINE_")
    ]

    result = validate(tmp_path, manifest)

    assert result.returncode == 0, result.stdout + result.stderr


def test_trusted_workflow_lease_must_equal_manifest_lease(tmp_path: Path) -> None:
    manifest = example_manifest()

    result = validate(
        tmp_path,
        manifest,
        "--expected-baseline-lease-id",
        "K7pV2bN9wQ4mX6sD8fH1jL3cR5tY0uA2eG9iO7zC4Bk",
    )

    assert result.returncode == 1
    assert "does not match the trusted workflow lease" in result.stdout


def test_frontend_url_cors_and_secret_scope_must_match_provider_evidence(tmp_path: Path) -> None:
    manifest = example_manifest()
    configuration = manifest["configuration"]
    configuration["frontend_url"] = "https://other-preview.vercel.app"
    configuration["cors_origins"] = ["*"]
    configuration["qa_secrets_scope"] = "production"
    configuration["required_secret_names_verified"] = ["DATABASE_URL"]

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    assert "frontend_url" in result.stdout
    assert "cors_origins" in result.stdout
    assert "qa_secrets_scope" in result.stdout
    assert "required_secret_names_verified" in result.stdout


def test_provider_evidence_sources_and_artifact_run_cannot_be_text_claims(tmp_path: Path) -> None:
    manifest = example_manifest()
    manifest["generated_by"]["kind"] = "workflow-dispatch-input"
    manifest["backend"]["evidence_source"] = "user-input"
    manifest["database"]["evidence_source"] = "user-input"
    manifest["configuration"]["evidence_source"] = "user-input"

    result = validate(
        tmp_path,
        manifest,
        "--expected-workflow-run-id",
        str(manifest["generated_by"]["workflow_run_id"] + 1),
    )

    assert result.returncode == 1
    assert "provider-api-verifier" in result.stdout
    assert "artifact run" in result.stdout
    assert "render-api" in result.stdout
    assert "supabase-management-api" in result.stdout


def test_manifest_provenance_and_freshness_are_enforced() -> None:
    manifest = example_manifest()
    generated = datetime.fromisoformat(manifest["generated_at"].replace("Z", "+00:00"))
    manifest["generated_by"]["workflow_path"] = ".github/workflows/untrusted.yml"

    errors = validate_manifest(manifest, now=generated + timedelta(hours=2))

    assert "generated_at is stale" in errors
    assert any("workflow_path" in error for error in errors)


def test_manifest_future_timestamp_is_rejected() -> None:
    manifest = example_manifest()
    generated = datetime.fromisoformat(manifest["generated_at"].replace("Z", "+00:00"))

    errors = validate_manifest(manifest, now=generated - timedelta(minutes=6))

    assert "generated_at is in the future" in errors


def test_malformed_nested_types_are_rejected_without_traceback(tmp_path: Path) -> None:
    manifest = example_manifest()
    manifest["generated_by"]["evidence_sources"] = [{}]
    manifest["configuration"]["required_secret_names_verified"] = [{}]

    result = validate(tmp_path, manifest)

    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_pr_workflow_is_static_only_and_cannot_read_provider_artifacts() -> None:
    workflow = (ROOT / ".github" / "workflows" / "preview-qa.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "validate_preview_manifest.py" in workflow
    assert "contents: read" in workflow
    assert "actions: read" not in workflow
    assert "workflow_dispatch" not in workflow
    assert "download-artifact" not in workflow
    assert "environment: preview-qa" not in workflow
    assert "${{ secrets." not in workflow
    assert "npm ci" not in workflow
