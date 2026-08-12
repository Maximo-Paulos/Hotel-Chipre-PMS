"""Regression tests for the provider-bound release evidence gate."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.agent_ops.check_qa_evidence import validate_evidence_bundle
from scripts.agent_ops.check_release_evidence import (
    ReleaseEvidenceError,
    is_release_relevant_path,
    select_summary,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "qa" / "regression-catalog.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((ROOT / "qa" / "preview-manifest.example.json").read_text(encoding="utf-8"))


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def write_bundle(tmp_path: Path) -> tuple[Path, dict, dict, datetime]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    generated = now - timedelta(hours=1)
    manifest = json.loads(json.dumps(EXAMPLE))
    manifest["generated_at"] = iso(generated)
    manifest["frontend"]["ready_at"] = iso(generated - timedelta(minutes=10))
    manifest["backend"]["deployment_finished_at"] = iso(generated - timedelta(minutes=15))
    manifest["backend"]["configuration_updated_at"] = iso(generated - timedelta(minutes=20))
    manifest["database"]["updated_at"] = iso(generated - timedelta(minutes=25))
    task_id = "release-evidence-contract"
    task_dir = tmp_path / task_id
    task_dir.mkdir(parents=True)
    manifest_path = task_dir / "validated-preview-manifest.json"
    manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    manifest_path.write_bytes(manifest_raw)
    code_sha = manifest["code_sha"]
    results = [
        {
            "persona": persona,
            "case_id": case["id"],
            "device": device,
            "status": "passed",
            "preview_url": manifest["app_url"],
            "precondition": "persona QA sintética activa",
            "human_action": "recorrer la UI visible",
            "expected": case["expected"],
            "observed": "resultado esperado observado",
            "severity": "none",
            "screenshot": None,
            "evidence": "sha256:"
            + hashlib.sha256(f"{case['id']}/{persona}/{device}".encode()).hexdigest(),
            "code_sha": code_sha,
        }
        for case in CATALOG["cases"]
        for persona in case["personas"]
        for device in case["devices"]
    ]
    summary = {
        "task_id": task_id,
        "code_sha": code_sha,
        "provider_evidence": {
            "manifest_file": manifest_path.name,
            "manifest_sha256": "sha256:" + hashlib.sha256(manifest_raw).hexdigest(),
            "workflow_run_id": manifest["generated_by"]["workflow_run_id"],
            "artifact_id": 987654321,
            "task_id": manifest["task_id"],
            "repository": manifest["generated_by"]["repository"],
            "git_branch": manifest["generated_by"]["git_branch"],
            "workflow_code_sha": manifest["generated_by"]["workflow_code_sha"],
            "workflow_git_branch": manifest["generated_by"]["workflow_git_branch"],
        },
        "preview": {
            "app_url": manifest["app_url"],
            "api_origin": manifest["api_origin"],
            "api_url": manifest["api_base_url"],
            "health_url": manifest["health_url"],
            "vercel_project_id": manifest["frontend"]["project_id"],
            "vercel_deployment_id": manifest["frontend"]["deployment_id"],
            "render_service_id": manifest["backend"]["service_id"],
            "render_deployment_id": manifest["backend"]["deployment_id"],
            "render_environment_id": manifest["configuration"]["environment_id"],
            "supabase_project_ref": manifest["database"]["project_ref"],
            "supabase_branch_ref": manifest["database"]["branch_ref"],
        },
        "executed_at": iso(generated + timedelta(minutes=30)),
        "results": results,
        "external_exclusions": CATALOG["policy"]["external_exclusions"],
        "blocked": False,
    }
    summary_path = task_dir / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    return summary_path, summary, manifest, now


def rewrite_summary(path: Path, summary: dict) -> None:
    path.write_text(json.dumps(summary), encoding="utf-8")


def rewrite_manifest(path: Path, summary: dict, manifest: dict) -> None:
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    (path.parent / "validated-preview-manifest.json").write_bytes(raw)
    summary["provider_evidence"]["manifest_sha256"] = "sha256:" + hashlib.sha256(raw).hexdigest()
    rewrite_summary(path, summary)


def errors_for(path: Path, now: datetime, **kwargs: object) -> list[str]:
    return validate_evidence_bundle(path, now=now, **kwargs)[2]


def test_complete_bundle_is_bound_to_manifest_and_provider_identity(tmp_path: Path) -> None:
    path, summary, manifest, now = write_bundle(tmp_path)

    errors = errors_for(
        path,
        now,
        expected_repository=manifest["generated_by"]["repository"],
        expected_branch=manifest["generated_by"]["git_branch"],
        expected_default_branch=manifest["generated_by"]["workflow_git_branch"],
        expected_artifact_id=summary["provider_evidence"]["artifact_id"],
    )

    assert errors == []


def test_short_code_sha_is_rejected(tmp_path: Path) -> None:
    path, summary, _, now = write_bundle(tmp_path)
    summary["code_sha"] = "abcdef1"
    rewrite_summary(path, summary)

    assert any("full 40- or 64" in error for error in errors_for(path, now))


def test_manifest_byte_hash_is_required(tmp_path: Path) -> None:
    path, _, _, now = write_bundle(tmp_path)
    manifest_path = path.parent / "validated-preview-manifest.json"
    manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")

    assert any("manifest_sha256 does not match" in error for error in errors_for(path, now))


def test_workflow_run_and_artifact_ids_are_bound(tmp_path: Path) -> None:
    path, summary, _, now = write_bundle(tmp_path)
    summary["provider_evidence"]["workflow_run_id"] += 1
    summary["provider_evidence"]["artifact_id"] = 0
    rewrite_summary(path, summary)

    errors = errors_for(path, now, expected_artifact_id=987654321)

    assert any("workflow_run_id" in error for error in errors)
    assert any("artifact_id must be a positive integer" in error for error in errors)
    assert any("selected provider artifact" in error for error in errors)


def test_manifest_is_revalidated_with_workflow_provenance(tmp_path: Path) -> None:
    path, summary, manifest, now = write_bundle(tmp_path)
    manifest["generated_by"]["workflow_path"] = ".github/workflows/untrusted.yml"
    rewrite_manifest(path, summary, manifest)

    assert any("workflow_path" in error for error in errors_for(path, now))


@pytest.mark.parametrize(
    "field",
    [
        "app_url",
        "api_origin",
        "api_url",
        "health_url",
        "vercel_project_id",
        "vercel_deployment_id",
        "render_service_id",
        "render_deployment_id",
        "render_environment_id",
        "supabase_project_ref",
        "supabase_branch_ref",
    ],
)
def test_every_preview_provider_identity_must_match_exactly(tmp_path: Path, field: str) -> None:
    path, summary, _, now = write_bundle(tmp_path)
    summary["preview"][field] = "different-provider-identity"
    rewrite_summary(path, summary)

    assert any(f"preview.{field}" in error for error in errors_for(path, now))


@pytest.mark.parametrize(
    ("executed_at", "message"),
    [
        ("2026-07-19T18:30:00+03:00", "must use UTC"),
        ("before-generated", "ISO-8601 UTC"),
    ],
)
def test_executed_at_requires_explicit_utc(
    tmp_path: Path, executed_at: str, message: str
) -> None:
    path, summary, _, now = write_bundle(tmp_path)
    summary["executed_at"] = executed_at
    rewrite_summary(path, summary)

    assert any(message in error for error in errors_for(path, now))


def test_executed_at_must_follow_manifest_and_finish_within_24_hours(tmp_path: Path) -> None:
    path, summary, manifest, now = write_bundle(tmp_path)
    generated = datetime.fromisoformat(manifest["generated_at"].replace("Z", "+00:00"))
    summary["executed_at"] = iso(generated - timedelta(seconds=1))
    rewrite_summary(path, summary)
    assert any("at or after" in error for error in errors_for(path, now))

    summary["executed_at"] = iso(generated + timedelta(hours=24, seconds=1))
    rewrite_summary(path, summary)
    assert any("within 24 hours" in error for error in errors_for(path, now + timedelta(days=2)))


def test_future_execution_time_is_rejected(tmp_path: Path) -> None:
    path, summary, _, now = write_bundle(tmp_path)
    summary["executed_at"] = iso(now + timedelta(minutes=6))
    rewrite_summary(path, summary)

    assert any("future" in error for error in errors_for(path, now))


def test_each_evidence_reference_is_a_real_sha256_shape(tmp_path: Path) -> None:
    path, summary, _, now = write_bundle(tmp_path)
    summary["results"][0]["evidence"] = "sha256:not-a-digest"
    rewrite_summary(path, summary)

    assert any("sha256:<64" in error for error in errors_for(path, now))


def test_duplicate_or_weakened_catalog_rows_are_rejected(tmp_path: Path) -> None:
    path, summary, _, now = write_bundle(tmp_path)
    summary["results"][0]["expected"] = "anything is acceptable"
    summary["results"].append(dict(summary["results"][0]))
    rewrite_summary(path, summary)

    errors = errors_for(path, now)

    assert any("weakens" in error for error in errors)
    assert any("duplicate catalog row" in error for error in errors)


def test_summary_selection_requires_exactly_one_candidate_or_explicit_path(tmp_path: Path) -> None:
    evidence_root = tmp_path / "qa" / "evidence"
    first = evidence_root / "first" / "summary.json"
    second = evidence_root / "second" / "summary.json"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    with pytest.raises(ReleaseEvidenceError, match="exactly one"):
        select_summary(None, evidence_root=evidence_root)
    assert select_summary(first, evidence_root=evidence_root) == first.resolve()


@pytest.mark.parametrize(
    "path",
    [
        "app/services/reservations.py",
        "frontend/src/pages/Reservations.tsx",
        "frontend/e2e/smoke.spec.ts",
        "frontend/index.html",
        "frontend/vite.config.mjs",
        "frontend/vercel.json",
        "frontend/public/robots.txt",
        "alembic/versions/123.py",
        ".github/workflows/preview-qa.yml",
        ".github/actions/provider-check/action.yml",
        "scripts/agent_ops/check_qa_evidence.py",
        "scripts/knowledge/generate_inventories.py",
        "scripts/bootstrap_cloud_qa.py",
        "qa/regression-catalog.json",
        "qa/trust/qa-evidence-public-key.pem",
        "tests/test_release_evidence_contract.py",
        "agent-ops/roles/cloud-qa-user.json",
        "vercel.json",
        "Dockerfile.backend",
        "Dockerfile.frontend",
        "Procfile",
        "start.sh",
    ],
)
def test_release_relevant_surfaces_invalidate_older_evidence(path: str) -> None:
    assert is_release_relevant_path(path)


def test_versioned_evidence_files_do_not_invalidate_the_code_sha() -> None:
    assert not is_release_relevant_path("qa/evidence/task/summary.json")
    assert not is_release_relevant_path("qa/evidence/task/validated-preview-manifest.json")
    assert not is_release_relevant_path("qa/evidence/task/attestation.json")


def test_release_workflow_uses_head_sha_without_exposing_checkout_token() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-gate.yml").read_text(encoding="utf-8")

    assert "persist-credentials: false" in workflow
    assert "github.event.pull_request.head.sha" in workflow
    assert "github.event.pull_request.head.ref" in workflow
    assert "check_release_evidence.py" in workflow
    assert "--base \"$BASE_SHA\"" in workflow
    assert "find qa/evidence" not in workflow
    assert "github.token" not in workflow
    assert "secrets." not in workflow
