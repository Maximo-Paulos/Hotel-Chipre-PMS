# Multi-Agent Workflow

This repo is intended for coordinated work across Claude Code, Codex, Cowork, and CI.

## Roles
- Claude Code: planner, architect, backlog owner, reviewer of structure and coherence.
- Codex: implementation engineer, refactor engineer, test engineer, bug fixer.
- Cowork: operator, manual QA, environment runner, end-user simulation.
- GitHub/CI: final authority for merge readiness.

## Working rules
- Use the current repository state as the source of truth.
- Prefer small, scoped changes over broad rewrites.
- Do not invent product decisions.
- Keep changes testable and reviewable.
- Preserve tenant scoping, auth, and auditability.

## Workflow
1. Claude Code defines the milestone and the acceptance boundary.
2. Codex implements the smallest useful slice and adds or updates tests.
3. Cowork validates the flow in a real runtime or manual UI path.
4. CI and GitHub checks decide whether the change is merge-ready.

## Handoff expectations
- State what changed.
- State what was tested.
- State risks and open inputs.
- Do not mark work done without verification.

