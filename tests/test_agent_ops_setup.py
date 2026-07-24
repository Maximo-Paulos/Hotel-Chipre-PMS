"""Regression contracts for the repository's agent-operations setup."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tomllib
from pathlib import Path

from scripts.agent_ops.check_qa_evidence import validate_evidence_bundle


ROOT = Path(__file__).resolve().parents[1]
ROLE_DIR = ROOT / "agent-ops" / "roles"
SKILL_DIR = ROOT / ".agents" / "skills"

REQUIRED_ROLES = {
    "architecture-reviewer",
    "backend-engineer",
    "database-migrations",
    "docs-writer",
    "frontend-engineer",
    "performance-analyst",
    "qa-testing",
    "security-auditor",
    "knowledge-graph-curator",
    "cloud-qa-user",
    "devops-containers",
    "product-ceo",
    "geo-market-expansion",
    "geo-local-seo",
    "ux-ui-auditor",
    "data-visualization",
    "data-architecture-specialist",
    "release-governor",
}

REQUIRED_SKILLS = {
    "graphify-read",
    "graphify-load-context",
    "graphify-write",
    "obsidian-read",
    "obsidian-load-context",
    "obsidian-write",
    "cloud-user-qa",
    "qa-persona-bootstrap",
    "release-gate",
    "deploy-preview-check",
    "secure-integration-review",
    "ux-ui-audit",
    "product-ceo-review",
    "geo-market-expansion",
    "geo-local-seo",
    "data-visualization-review",
    "agent-setup-maintenance",
    "incident-triage",
    "scale-data-architecture",
}


def test_knowledge_vault_has_routing_and_current_state_report() -> None:
    assert (ROOT / "knowledge" / "README.md").is_file()
    assert (ROOT / "knowledge" / "00-control" / "TASK_ROUTER.md").is_file()
    assert (ROOT / "knowledge" / "00-control" / "STATUS-TODAY.md").is_file()
    assert (ROOT / "knowledge" / "30-operations" / "cloud-regression-catalog.md").is_file()


def test_agent_definitions_cover_every_required_role() -> None:
    role_files = sorted(ROLE_DIR.glob("*.json"))
    declared = {json.loads(path.read_text(encoding="utf-8"))["name"] for path in role_files}
    assert REQUIRED_ROLES <= declared


def test_required_skills_are_discoverable_from_the_canonical_library() -> None:
    for name in REQUIRED_SKILLS:
        skill = SKILL_DIR / name / "SKILL.md"
        assert skill.is_file(), f"Missing skill: {name}"
        assert f"name: {name}" in skill.read_text(encoding="utf-8")


def test_generated_agent_configurations_are_in_sync() -> None:
    command = [sys.executable, "scripts/agent_ops/render_agents.py", "--check"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_agent_toml_and_yaml_are_syntactically_valid() -> None:
    for path in (ROOT / ".codex" / "agents").glob("*.toml"):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        assert data["name"] in REQUIRED_ROLES
        assert data["developer_instructions"]
    for path in (ROOT / ".claude" / "agents").glob("*.md"):
        raw = path.read_text(encoding="utf-8")
        frontmatter = raw.split("---", 2)[1]
        lines = frontmatter.strip().splitlines()
        fields: dict[str, str | list[str]] = {}
        current_list: str | None = None
        for line in lines:
            if line.startswith("  - "):
                assert current_list is not None
                assert isinstance(fields[current_list], list)
                fields[current_list].append(line.removeprefix("  - ").strip())
                continue
            assert ":" in line, f"Invalid generated YAML line in {path}: {line}"
            key, value = (part.strip() for part in line.split(":", 1))
            assert key and value or key == "skills"
            fields[key] = [] if not value else value
            current_list = key if not value else None
        assert fields["name"] in REQUIRED_ROLES
        assert fields["skills"]


def test_claude_skill_mirror_is_in_sync() -> None:
    command = [sys.executable, "scripts/agent_ops/sync_skills.py", "--check"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_vault_links_and_context_frontmatter_are_valid() -> None:
    command = [sys.executable, "scripts/agent_ops/check_knowledge.py"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_canonical_cloud_surface_configuration_is_aligned() -> None:
    command = [sys.executable, "scripts/agent_ops/check_cloud_surface_config.py"]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_preview_manifest_example_isolation_contract() -> None:
    command = [
        sys.executable,
        "scripts/agent_ops/validate_preview_manifest.py",
        "qa/preview-manifest.example.json",
        "--skip-freshness",
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def write_complete_qa_evidence(tmp_path: Path) -> tuple[dict[str, object], Path]:
    catalog = json.loads((ROOT / "qa" / "regression-catalog.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "qa" / "preview-manifest.example.json").read_text(encoding="utf-8")
    )
    sha = manifest["code_sha"]
    results = [
        {
            "persona": persona,
            "case_id": case["id"],
            "status": "passed",
            "preview_url": manifest["app_url"],
            "precondition": "datos QA sintéticos disponibles",
            "human_action": "recorrer UI visible",
            "expected": case["expected"],
            "observed": "resultado esperado observado",
            "evidence": "sha256:"
            + hashlib.sha256(f"{case['id']}/{persona}".encode()).hexdigest(),
            "code_sha": sha,
        }
        for case in catalog["cases"]
        for persona in case["personas"]
    ]
    task_id = "qa-schema-test"
    task_dir = tmp_path / task_id
    task_dir.mkdir()
    manifest_path = task_dir / "validated-preview-manifest.json"
    manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    manifest_path.write_bytes(manifest_raw)
    evidence: dict[str, object] = {
        "task_id": task_id,
        "code_sha": sha,
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
        "executed_at": "2026-07-19T15:30:00Z",
        "results": results,
        "external_exclusions": catalog["policy"]["external_exclusions"],
        "blocked": False,
    }
    summary_path = task_dir / "summary.json"
    summary_path.write_text(json.dumps(evidence), encoding="utf-8")
    return evidence, summary_path


def run_qa_evidence_check(path: Path) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "scripts/agent_ops/check_qa_evidence.py", str(path)]
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def test_qa_evidence_schema_accepts_full_catalog(tmp_path: Path) -> None:
    _, path = write_complete_qa_evidence(tmp_path)
    _, _, errors = validate_evidence_bundle(path, attestation_mode="structural")
    assert errors == []


def test_qa_evidence_rejects_result_rows_outside_verified_preview(tmp_path: Path) -> None:
    evidence, path = write_complete_qa_evidence(tmp_path)
    evidence["results"][0]["preview_url"] = "https://app.hotels-pms.com"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    result = run_qa_evidence_check(path)

    assert result.returncode == 1
    assert "preview_url" in result.stdout
    assert "Traceback" not in result.stderr


def test_qa_evidence_rejects_malformed_result_without_traceback(tmp_path: Path) -> None:
    evidence, path = write_complete_qa_evidence(tmp_path)
    evidence["results"][0] = None
    path.write_text(json.dumps(evidence), encoding="utf-8")

    result = run_qa_evidence_check(path)

    assert result.returncode == 1
    assert "result 0" in result.stdout
    assert "Traceback" not in result.stderr
