"""Regression tests for final provider-evidence continuity."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.agent_ops.compare_preview_manifests import (
    ManifestContinuityError,
    main,
    verify_manifest_continuity,
)


ROOT = Path(__file__).resolve().parents[1]


def example() -> dict:
    return json.loads((ROOT / "qa" / "preview-manifest.example.json").read_text())


def test_only_a_newer_observation_timestamp_may_change() -> None:
    probed = example()
    final = copy.deepcopy(probed)
    final["generated_at"] = "2026-07-19T15:01:00Z"

    verify_manifest_continuity(probed, final)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        (None, "app_url", "https://different.vercel.app"),
        (None, "api_origin", "https://different.onrender.com"),
        ("frontend", "deployment_id", "dpl-drifted"),
        ("backend", "deployment_id", "dep-drifted"),
        ("backend", "configuration_updated_at", "2026-07-19T15:00:30Z"),
        ("database", "connection_fingerprint", "sha256:" + "3" * 64),
        ("database", "baseline_lease_id", "K7pV2bN9wQ4mX6sD8fH1jL3cR5tY0uA2eG9iO7zC4Bk"),
        ("configuration", "bootstrap_configuration_fingerprint", "sha256:" + "4" * 64),
        ("generated_by", "git_branch", "codex/different"),
    ],
)
def test_any_provider_subject_drift_is_rejected(
    section: str | None,
    field: str,
    value: str,
) -> None:
    probed = example()
    final = copy.deepcopy(probed)
    final["generated_at"] = "2026-07-19T15:01:00Z"
    target = final if section is None else final[section]
    target[field] = value

    with pytest.raises(ManifestContinuityError, match="drifted"):
        verify_manifest_continuity(probed, final)


def test_final_observation_cannot_predate_probes() -> None:
    probed = example()
    final = copy.deepcopy(probed)
    final["generated_at"] = "2026-07-19T14:59:00Z"

    with pytest.raises(ManifestContinuityError, match="predates"):
        verify_manifest_continuity(probed, final)


def test_workflow_verifies_production_sha_before_upload() -> None:
    workflow = (ROOT / ".github/workflows/verify-preview-providers.yml").read_text()
    verify_at = workflow.index("verify_production_render.py")
    upload_at = workflow.index("Upload sanitized production Render evidence")

    assert verify_at < upload_at
    assert "--wait-seconds 1800" in workflow
    assert "production-render-manifest.json" in workflow[verify_at:upload_at]
    assert "production-render-evidence-${{ env.TARGET_SHA }}" in workflow


def test_cli_rejects_symlinked_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "manifest.json"
    source.write_text(json.dumps(example()))
    link = tmp_path / "link.json"
    link.symlink_to(source)
    monkeypatch.setattr("sys.argv", ["compare", str(link), str(source)])

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 2
