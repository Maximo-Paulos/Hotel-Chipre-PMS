"""Contracts for opting provider-bound PR evidence checks in by label."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROVIDER_QA_LABEL = "require-provider-qa"
PROVIDER_QA_CONDITION = (
    f"contains(github.event.pull_request.labels.*.name, '{PROVIDER_QA_LABEL}')"
)


def _load_workflow(name: str) -> dict:
    path = ROOT / ".github" / "workflows" / name
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_provider_evidence_gates_are_opt_in_and_respond_to_label_changes() -> None:
    gated_workflows = (
        ("release-gate.yml", "pull_request", "operating-system"),
        ("trusted-release-gate.yml", "pull_request_target", "trusted-base-evidence"),
    )

    for workflow_name, event_name, job_name in gated_workflows:
        workflow = _load_workflow(workflow_name)
        assert {"labeled", "unlabeled"} <= set(
            workflow["on"][event_name]["types"]
        )
        job = workflow["jobs"][job_name]
        assert job["if"] == PROVIDER_QA_CONDITION
        assert job["steps"], f"{workflow_name}:{job_name} lost its validations"


def test_regular_pr_backend_frontend_and_e2e_checks_remain_enabled() -> None:
    workflow = _load_workflow("pr-validation.yml")
    jobs = workflow["jobs"]

    assert "pull_request" in workflow["on"]
    assert "push" not in workflow["on"]
    assert {"backend", "frontend", "e2e"} <= set(jobs)
    assert all("if" not in jobs[name] for name in ("backend", "frontend", "e2e"))

    backend_steps = {step.get("name"): step for step in jobs["backend"]["steps"]}
    assert backend_steps["Run backend tests"]["run"] == "python -m pytest -q"

    frontend_steps = {step.get("name") for step in jobs["frontend"]["steps"]}
    assert {
        "Run frontend lint",
        "Run frontend typecheck",
        "Run frontend tests",
        "Run frontend build",
    } <= frontend_steps

    e2e_steps = {step.get("name"): step for step in jobs["e2e"]["steps"]}
    assert e2e_steps["Run E2E journeys"]["run"].startswith("npx playwright test")
