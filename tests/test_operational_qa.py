from __future__ import annotations

import json
import hashlib

from scripts.agent_ops import operational_qa


def test_initializes_non_certifying_run_with_private_artifact_namespace(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(operational_qa, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(operational_qa, "ARTIFACTS_ROOT", tmp_path / "artifacts")

    run_dir = operational_qa.initialize("ops-test-001", "a" * 40)

    metadata = json.loads((run_dir / "run-metadata.json").read_text())
    assert metadata["release_gate_eligible"] is False
    assert metadata["certification"] == "none"
    assert (run_dir / "report.md").read_text().startswith(operational_qa.REPORT_HEADER)
    assert operational_qa.validate(run_dir) == []


def test_validator_rejects_production_lookalike_release_claim(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(operational_qa, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(operational_qa, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    run_dir = operational_qa.initialize("ops-test-002", "b" * 40)
    path = run_dir / "run-metadata.json"
    metadata = json.loads(path.read_text())
    metadata["release_gate_eligible"] = True
    path.write_text(json.dumps(metadata))

    assert any("non-certifying" in error for error in operational_qa.validate(run_dir))


def test_complete_run_requires_every_catalog_combination(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(operational_qa, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(operational_qa, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    run_dir = operational_qa.initialize("ops-test-003", "c" * 40)

    errors = operational_qa.validate(run_dir, require_complete=True)

    assert any("completed_at" in error for error in errors)
    assert any("missing matrix combinations" in error for error in errors)


def test_validator_checks_artifact_file_hash_and_redaction(tmp_path, monkeypatch) -> None:
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setattr(operational_qa, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(operational_qa, "ARTIFACTS_ROOT", artifacts_root)
    run_dir = operational_qa.initialize("ops-test-004", "d" * 40)
    screenshot = artifacts_root / "ops-test-004" / "screenshots" / "home.png"
    screenshot.write_bytes(b"redacted screenshot")
    digest = "sha256:" + hashlib.sha256(screenshot.read_bytes()).hexdigest()
    index_path = run_dir / "artifact-index.json"
    index = json.loads(index_path.read_text())
    index["artifacts"] = [
        {
            "artifact_id": "home-desktop",
            "relative_path": "screenshots/home.png",
            "sha256": digest,
            "redaction_state": "verified",
        }
    ]
    index_path.write_text(json.dumps(index), encoding="utf-8")

    assert operational_qa.validate(run_dir) == []

    screenshot.write_bytes(b"changed after indexing")
    assert any("hash does not match" in error for error in operational_qa.validate(run_dir))


def test_validator_rejects_observation_outside_matrix(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(operational_qa, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(operational_qa, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    run_dir = operational_qa.initialize("ops-test-005", "e" * 40)
    observations_path = run_dir / "observations.json"
    document = json.loads(observations_path.read_text())
    document["observations"] = [
        {
            "operational_case_id": "ops-marketing-home",
            "persona": "owner",
            "device_profile": "desktop-chrome-current",
            "target_url": "https://hotels-pms.com/",
            "preconditions": [],
            "human_actions": ["open"],
            "expected": "home",
            "observed": "home",
            "status": "NOT_APPLICABLE",
            "severity": "NONE",
            "artifact_ids": [],
            "code_sha": "e" * 40,
            "created_record_refs": [],
            "cleanup_state": "not_required",
        }
    ]
    observations_path.write_text(json.dumps(document), encoding="utf-8")

    assert any("outside the operational matrix" in error for error in operational_qa.validate(run_dir))
