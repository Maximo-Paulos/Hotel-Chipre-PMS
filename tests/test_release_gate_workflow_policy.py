"""Contracts for opting provider-bound PR evidence checks in by label."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVIDER_QA_LABEL = "require-provider-qa"
PROVIDER_QA_CONDITION = (
    f"contains(github.event.pull_request.labels.*.name, '{PROVIDER_QA_LABEL}')"
)


def _load_workflow(name: str) -> str:
    path = ROOT / ".github" / "workflows" / name
    return path.read_text(encoding="utf-8")


def _job_block(workflow: str, job_name: str) -> str:
    jobs_start = re.search(r"(?m)^jobs:\s*$", workflow)
    assert jobs_start, "workflow is missing its jobs section"
    jobs = workflow[jobs_start.end() :]
    job_start = re.search(rf"(?m)^  {re.escape(job_name)}:\s*$", jobs)
    assert job_start, f"workflow is missing job {job_name!r}"
    remainder = jobs[job_start.end() :]
    next_job = re.search(r"(?m)^  [A-Za-z0-9_-]+:\s*$", remainder)
    return remainder[: next_job.start()] if next_job else remainder


def test_provider_evidence_gates_are_opt_in_and_respond_to_label_changes() -> None:
    gated_workflows = (
        ("release-gate.yml", "pull_request", "operating-system"),
        ("trusted-release-gate.yml", "pull_request_target", "trusted-base-evidence"),
    )

    for workflow_name, event_name, job_name in gated_workflows:
        workflow = _load_workflow(workflow_name)
        event_signature = re.compile(
            rf"(?ms)^  {re.escape(event_name)}:\n"
            r"    types: \[[^\]]*\blabeled\b[^\]]*\bunlabeled\b[^\]]*\]$"
        )
        assert event_signature.search(workflow)
        job = _job_block(workflow, job_name)
        gate_condition = re.compile(
            rf"(?m)^    if: {re.escape(PROVIDER_QA_CONDITION)}$"
        )
        assert gate_condition.search(job)
        assert re.search(r"(?m)^    steps:\s*$", job), (
            f"{workflow_name}:{job_name} lost its validations"
        )


def test_regular_pr_backend_frontend_and_e2e_checks_remain_enabled() -> None:
    workflow = _load_workflow("pr-validation.yml")
    assert re.search(r"(?ms)^on:\n  pull_request:\s*$", workflow)
    assert not re.search(r"(?m)^  push:\s*$", workflow)

    job_blocks = {
        name: _job_block(workflow, name) for name in ("backend", "frontend", "e2e")
    }
    assert all(
        not re.search(r"(?m)^    if:", block) for block in job_blocks.values()
    )

    assert re.search(
        r"(?ms)^      - name: Run backend tests\n"
        r"        run: python -m pytest -q$",
        job_blocks["backend"],
    )

    for step_name in (
        "Run frontend lint",
        "Run frontend typecheck",
        "Run frontend tests",
        "Run frontend build",
    ):
        assert f"- name: {step_name}" in job_blocks["frontend"]

    assert re.search(
        r"(?ms)^      - name: Run E2E journeys\n"
        r"(?:        env:\n(?:          .*\n)+)?"
        r"        run: npx playwright test",
        job_blocks["e2e"],
    )
