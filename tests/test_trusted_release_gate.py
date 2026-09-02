"""Security regression tests for the pull_request_target release gate."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.agent_ops.qa_evidence_attestation import (
    build_attestation,
    public_key_pem,
)

from scripts.agent_ops.trusted_release_gate import (
    GitHubClient,
    TrustedGateError,
    finalize_gate,
    prepare_gate,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "a" * 40
HEAD_SHA = "c" * 40
OLD_APP_BLOB = "2" * 40
NEW_APP_BLOB = "3" * 40
SUMMARY_BLOB = "4" * 40
MANIFEST_BLOB = "5" * 40
WORKFLOW_BLOB = "6" * 40
BASE_WORKFLOW_BLOB = "f" * 40
SECOND_SUMMARY_BLOB = "7" * 40
LATER_APP_BLOB = "8" * 40
ATTESTATION_BLOB = "9" * 40
TRUSTED_KEY_BLOB = "d" * 40
HEAD_KEY_BLOB = "e" * 40
TRUSTED_KEY_PATH = "qa/trust/qa-evidence-public-key.pem"
WORKFLOW_PATH = ".github/workflows/verify-preview-providers.yml"


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def evidence_bytes() -> tuple[dict, dict, bytes, bytes, datetime]:
    catalog = json.loads((ROOT / "qa" / "regression-catalog.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "qa" / "preview-manifest.example.json").read_text(encoding="utf-8")
    )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    generated = now - timedelta(hours=1)
    manifest["generated_at"] = iso(generated)
    manifest["frontend"]["ready_at"] = iso(generated - timedelta(minutes=10))
    manifest["backend"]["deployment_finished_at"] = iso(generated - timedelta(minutes=15))
    manifest["backend"]["configuration_updated_at"] = iso(generated - timedelta(minutes=20))
    manifest["database"]["updated_at"] = iso(generated - timedelta(minutes=25))
    manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
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
            "code_sha": manifest["code_sha"],
        }
        for case in catalog["cases"]
        for persona in case["personas"]
        for device in case["devices"]
    ]
    summary = {
        "task_id": "trusted-release-contract",
        "code_sha": manifest["code_sha"],
        "provider_evidence": {
            "manifest_file": "validated-preview-manifest.json",
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
        "external_exclusions": catalog["policy"]["external_exclusions"],
        "blocked": False,
    }
    summary_raw = json.dumps(summary).encode()
    return summary, manifest, summary_raw, manifest_raw, now


class FakeGitHub:
    def __init__(self, tmp_path: Path) -> None:
        self.summary, self.manifest, summary_raw, manifest_raw, self.now = evidence_bytes()
        self.repository = self.manifest["generated_by"]["repository"]
        self.default_branch = self.manifest["generated_by"]["workflow_git_branch"]
        self.head_branch = self.manifest["generated_by"]["git_branch"]
        self.code_sha = self.manifest["code_sha"]
        self.workflow_sha = self.manifest["generated_by"]["workflow_code_sha"]
        self.task_dir = f"qa/evidence/{self.summary['task_id']}"
        self.private_key = Ed25519PrivateKey.generate()
        self.base_checkout_root = tmp_path / "base-checkout"
        base_key_path = self.base_checkout_root / TRUSTED_KEY_PATH
        base_key_path.parent.mkdir(parents=True)
        self.public_key_bytes = public_key_pem(self.private_key.public_key())
        base_key_path.write_bytes(self.public_key_bytes)
        local_task = tmp_path / "attestation-input" / self.summary["task_id"]
        local_task.mkdir(parents=True)
        local_summary = local_task / "summary.json"
        local_summary.write_bytes(summary_raw)
        (local_task / "validated-preview-manifest.json").write_bytes(manifest_raw)
        artifact_root = tmp_path / "operator-artifacts"
        artifact_root.mkdir()
        for index, result in enumerate(self.summary["results"]):
            content = (
                f"{result['case_id']}/{result['persona']}/{result['device']}"
            ).encode()
            assert result["evidence"] == "sha256:" + hashlib.sha256(content).hexdigest()
            (artifact_root / f"evidence-{index:04d}.bin").write_bytes(content)
        self.attestation = build_attestation(
            local_summary,
            artifact_root,
            self.private_key,
            signed_at=self.now,
        )
        attestation_raw = json.dumps(self.attestation, sort_keys=True).encode()
        self.workflow_source = (
            "jobs:\n  verify:\n"
            "    if: github.ref_name == github.event.repository.default_branch\n"
            "    environment: preview-qa\n"
            "    steps:\n      - uses: actions/checkout@v4\n"
            "        with:\n          ref: ${{ github.sha }}\n"
            "          persist-credentials: false\n"
        ).encode()
        self.blobs = {
            SUMMARY_BLOB: summary_raw,
            MANIFEST_BLOB: manifest_raw,
            WORKFLOW_BLOB: self.workflow_source,
            BASE_WORKFLOW_BLOB: b"name: a different trusted workflow\n",
            OLD_APP_BLOB: b"old app",
            NEW_APP_BLOB: b"new app",
            LATER_APP_BLOB: b"later app",
            SECOND_SUMMARY_BLOB: summary_raw,
            ATTESTATION_BLOB: attestation_raw,
            TRUSTED_KEY_BLOB: self.public_key_bytes,
            HEAD_KEY_BLOB: public_key_pem(Ed25519PrivateKey.generate().public_key()),
        }
        self.trees = {
            BASE_SHA: {
                "app/main.py": ("blob", OLD_APP_BLOB),
                TRUSTED_KEY_PATH: ("blob", TRUSTED_KEY_BLOB),
                WORKFLOW_PATH: ("blob", WORKFLOW_BLOB),
            },
            self.code_sha: {
                "app/main.py": ("blob", NEW_APP_BLOB),
                TRUSTED_KEY_PATH: ("blob", TRUSTED_KEY_BLOB),
                WORKFLOW_PATH: ("blob", WORKFLOW_BLOB),
            },
            HEAD_SHA: {
                "app/main.py": ("blob", NEW_APP_BLOB),
                TRUSTED_KEY_PATH: ("blob", TRUSTED_KEY_BLOB),
                WORKFLOW_PATH: ("blob", WORKFLOW_BLOB),
                f"{self.task_dir}/summary.json": ("blob", SUMMARY_BLOB),
                f"{self.task_dir}/validated-preview-manifest.json": ("blob", MANIFEST_BLOB),
                f"{self.task_dir}/attestation.json": ("blob", ATTESTATION_BLOB),
            },
            self.workflow_sha: {
                WORKFLOW_PATH: ("blob", WORKFLOW_BLOB)
            },
        }
        self.run_conclusion = "success"
        self.head_repository = self.repository
        self.workflow_is_ancestor = True

    def repository_metadata(self):
        return {"default_branch": self.default_branch}

    def pull_request(self, number: int):
        assert number == 25
        return {
            "state": "open",
            "base": {
                "sha": BASE_SHA,
                "ref": self.default_branch,
                "repo": {"full_name": self.repository},
            },
            "head": {
                "sha": HEAD_SHA,
                "ref": self.head_branch,
                "repo": {"full_name": self.head_repository},
            },
        }

    def tree(self, commit_sha: str):
        return self.trees[commit_sha]

    def blob(self, blob_sha: str):
        return self.blobs[blob_sha]

    def compare(self, base_sha: str, head_sha: str):
        if (base_sha, head_sha) == (self.code_sha, HEAD_SHA):
            return {"status": "ahead", "merge_base_commit": {"sha": self.code_sha}}
        if (base_sha, head_sha) == (self.workflow_sha, BASE_SHA):
            if self.workflow_is_ancestor:
                return {"status": "ahead", "merge_base_commit": {"sha": self.workflow_sha}}
            return {"status": "diverged", "merge_base_commit": {"sha": BASE_SHA}}
        raise AssertionError(f"unexpected comparison: {base_sha}...{head_sha}")

    def artifact(self, artifact_id: int):
        assert artifact_id == self.summary["provider_evidence"]["artifact_id"]
        return {
            "id": artifact_id,
            "name": f"preview-provider-evidence-{self.code_sha}",
            "expired": False,
            "size_in_bytes": len(self.blobs[MANIFEST_BLOB]),
            "workflow_run": {
                "id": self.summary["provider_evidence"]["workflow_run_id"],
                "head_sha": self.workflow_sha,
            },
        }

    def workflow_run(self, run_id: int):
        assert run_id == self.summary["provider_evidence"]["workflow_run_id"]
        return {
            "workflow_id": 42,
            "path": ".github/workflows/verify-preview-providers.yml",
            "event": "workflow_dispatch",
            "status": "completed",
            "conclusion": self.run_conclusion,
            "head_branch": self.default_branch,
            "head_repository": {"full_name": self.repository},
            "head_sha": self.workflow_sha,
            "actor": {"id": int(self.manifest["generated_by"]["actor_id"])},
        }

    def workflow(self):
        return {
            "id": 42,
            "path": ".github/workflows/verify-preview-providers.yml",
            "state": "active",
        }


def prepare(fake: FakeGitHub, tmp_path: Path):
    return prepare_gate(
        fake,
        repository=fake.repository,
        pr_number=25,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        base_branch=fake.default_branch,
        output_dir=tmp_path / "trusted-input",
        now=fake.now,
        base_checkout_root=fake.base_checkout_root,
    )


def test_trusted_prepare_and_finalize_accept_only_byte_identical_provider_artifact(
    tmp_path: Path,
) -> None:
    fake = FakeGitHub(tmp_path)

    prepared = prepare(fake, tmp_path)

    assert prepared.evidence_required is True
    assert prepared.artifact_id == fake.summary["provider_evidence"]["artifact_id"]
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    (artifact_dir / "preview-manifest.json").write_bytes(fake.blobs[MANIFEST_BLOB])
    assert finalize_gate(
        tmp_path / "trusted-input",
        artifact_dir,
        now=fake.now,
        base_checkout_root=fake.base_checkout_root,
    ) == fake.summary["task_id"]


def test_finalize_rejects_artifact_with_different_bytes(tmp_path: Path) -> None:
    fake = FakeGitHub(tmp_path)
    prepare(fake, tmp_path)
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    (artifact_dir / "preview-manifest.json").write_bytes(b"{}")

    with pytest.raises(TrustedGateError, match="bytes do not match"):
        finalize_gate(
            tmp_path / "trusted-input",
            artifact_dir,
            now=fake.now,
            base_checkout_root=fake.base_checkout_root,
        )


def test_prepare_rejects_release_change_after_qa_code_sha(tmp_path: Path) -> None:
    fake = FakeGitHub(tmp_path)
    fake.trees[HEAD_SHA]["app/main.py"] = ("blob", LATER_APP_BLOB)

    with pytest.raises(TrustedGateError, match="changed after cloud QA"):
        prepare(fake, tmp_path)


def test_prepare_rejects_unsuccessful_provider_workflow(tmp_path: Path) -> None:
    fake = FakeGitHub(tmp_path)
    fake.run_conclusion = "failure"

    with pytest.raises(TrustedGateError, match="was not successful"):
        prepare(fake, tmp_path)


def test_prepare_rejects_fork_without_reading_head_blobs(tmp_path: Path) -> None:
    fake = FakeGitHub(tmp_path)
    fake.head_repository = "attacker/fork"

    with pytest.raises(TrustedGateError, match="fork pull requests"):
        prepare(fake, tmp_path)


def test_prepare_requires_exactly_one_changed_summary(tmp_path: Path) -> None:
    fake = FakeGitHub(tmp_path)
    fake.trees[HEAD_SHA]["qa/evidence/second/summary.json"] = ("blob", SECOND_SUMMARY_BLOB)

    with pytest.raises(TrustedGateError, match="exactly one"):
        prepare(fake, tmp_path)


def test_prepare_rejects_provider_workflow_sha_not_ancestor_of_pr_base(
    tmp_path: Path,
) -> None:
    fake = FakeGitHub(tmp_path)
    fake.workflow_is_ancestor = False

    with pytest.raises(TrustedGateError, match="not an ancestor"):
        prepare(fake, tmp_path)


def test_prepare_rejects_provider_workflow_blob_different_from_pr_base(
    tmp_path: Path,
) -> None:
    fake = FakeGitHub(tmp_path)
    fake.trees[BASE_SHA][WORKFLOW_PATH] = ("blob", BASE_WORKFLOW_BLOB)

    with pytest.raises(TrustedGateError, match="does not exactly match"):
        prepare(fake, tmp_path)


def test_prepare_rejects_unsigned_or_missing_operator_attestation(tmp_path: Path) -> None:
    fake = FakeGitHub(tmp_path)
    del fake.trees[HEAD_SHA][f"{fake.task_dir}/attestation.json"]

    with pytest.raises(TrustedGateError, match="attestation.json must change"):
        prepare(fake, tmp_path)


def test_prepare_rejects_altered_operator_signature(tmp_path: Path) -> None:
    fake = FakeGitHub(tmp_path)
    attestation = json.loads(fake.blobs[ATTESTATION_BLOB])
    signature = attestation["signature"]["value"]
    attestation["signature"]["value"] = ("A" if signature[0] != "A" else "B") + signature[1:]
    fake.blobs[ATTESTATION_BLOB] = json.dumps(attestation).encode()

    with pytest.raises(TrustedGateError, match="signature is invalid"):
        prepare(fake, tmp_path)


def test_prepare_rejects_public_key_changed_in_pr_head(tmp_path: Path) -> None:
    fake = FakeGitHub(tmp_path)
    fake.trees[HEAD_SHA][TRUSTED_KEY_PATH] = ("blob", HEAD_KEY_BLOB)

    with pytest.raises(TrustedGateError, match="trust key cannot change"):
        prepare(fake, tmp_path)


def test_prepare_refuses_head_key_substitution_for_base_checkout_key(tmp_path: Path) -> None:
    fake = FakeGitHub(tmp_path)
    base_key_path = fake.base_checkout_root / TRUSTED_KEY_PATH
    base_key_path.write_bytes(fake.blobs[HEAD_KEY_BLOB])

    with pytest.raises(TrustedGateError, match="does not match the PR base blob"):
        prepare(fake, tmp_path)


def test_github_client_error_never_discloses_token_or_body() -> None:
    token = "github-actions-token-secret"
    response_secret = b"private-provider-response"

    def forbidden(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, io.BytesIO(response_secret)
        )

    client = GitHubClient("owner/repository", token, opener=forbidden)

    with pytest.raises(TrustedGateError) as captured:
        client.repository_metadata()
    message = str(captured.value)
    assert token not in message
    assert response_secret.decode() not in message


def test_workflow_keeps_pr_checkout_immutable_and_defers_cloud_qa_to_production() -> None:
    workflow = (ROOT / ".github" / "workflows" / "trusted-release-gate.yml").read_text(
        encoding="utf-8"
    )

    assert "pull_request_target:" in workflow
    checkout_lines = [
        line.strip() for line in workflow.splitlines() if "uses: actions/checkout@" in line
    ]
    assert len(checkout_lines) == 1
    checkout_ref = checkout_lines[0].split("actions/checkout@", 1)[1].split()[0]
    assert len(checkout_ref) == 40
    int(checkout_ref, 16)
    assert "ref: ${{ github.event.pull_request.base.sha }}" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha }}" not in workflow
    assert "persist-credentials: false" in workflow
    assert ".github/workflows/verify-preview-providers.yml" in workflow
    assert "production Render QA cycle runs automatically" in workflow
    assert "RENDER_QA_SERVICE_ID" not in workflow
    assert "trusted_release_gate.py prepare" not in workflow
    assert "trusted_release_gate.py finalize" not in workflow
    assert "download-artifact" not in workflow
    assert "run: ${{" not in workflow
    assert "secrets." not in workflow
