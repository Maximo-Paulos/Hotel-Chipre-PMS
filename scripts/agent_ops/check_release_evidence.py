#!/usr/bin/env python3
"""Require one provider-bound QA bundle after every release-relevant change."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_ops.check_qa_evidence import SHA_RE, validate_evidence_bundle


EVIDENCE_ROOT = ROOT / "qa" / "evidence"
SUMMARY_PATH_RE = re.compile(r"qa/evidence/[^/]+/summary\.json")
EVIDENCE_OUTPUT_RE = re.compile(
    r"qa/evidence/[^/]+/(?:summary\.json|validated-preview-manifest\.json|attestation\.json)"
)
class ReleaseEvidenceError(RuntimeError):
    pass


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()


def resolve_commit(value: str) -> str:
    try:
        resolved = git("rev-parse", "--verify", f"{value}^{{commit}}")
    except subprocess.CalledProcessError:
        raise ReleaseEvidenceError(f"Git commit is unavailable: {value}") from None
    if not SHA_RE.fullmatch(resolved):
        raise ReleaseEvidenceError("Git did not resolve a full 40- or 64-character commit SHA")
    return resolved


def changed_paths(base: str, head: str) -> list[str]:
    try:
        output = git("diff", "--name-only", "--no-renames", f"{base}..{head}")
    except subprocess.CalledProcessError:
        raise ReleaseEvidenceError("Unable to compare release commits") from None
    return [path for path in output.splitlines() if path]


def is_release_relevant_path(path: str) -> bool:
    """Fail closed: only the three generated evidence files are non-runtime.

    A release can be affected by entrypoints, provider configuration, generated
    assets, hooks, dependency metadata or a future file not covered by an
    allowlist. Treat every tracked path as invalidating older QA unless it is a
    fixed-name output of the evidence bundle itself.
    """

    normalized = path.removeprefix("./")
    return EVIDENCE_OUTPUT_RE.fullmatch(normalized) is None


def validate_explicit_summary_path(path: Path, *, evidence_root: Path = EVIDENCE_ROOT) -> Path:
    candidate = path if path.is_absolute() else ROOT / path
    resolved_root = evidence_root.resolve()
    resolved = candidate.resolve()
    if resolved.name != "summary.json" or resolved.parent.parent != resolved_root:
        raise ReleaseEvidenceError(
            "explicit evidence must be qa/evidence/<task_id>/summary.json"
        )
    return resolved


def select_summary(
    explicit: Path | None,
    *,
    candidate_paths: list[str] | None = None,
    evidence_root: Path = EVIDENCE_ROOT,
) -> Path:
    if explicit is not None:
        return validate_explicit_summary_path(explicit, evidence_root=evidence_root)
    if candidate_paths is None:
        candidates = sorted(evidence_root.glob("*/summary.json"))
    else:
        candidates = sorted(
            ROOT / path for path in candidate_paths if SUMMARY_PATH_RE.fullmatch(path)
        )
    if len(candidates) != 1:
        raise ReleaseEvidenceError(
            f"exactly one QA summary candidate is required; found {len(candidates)}. "
            "Pass an explicit qa/evidence/<task_id>/summary.json when selecting intentionally."
        )
    return validate_explicit_summary_path(candidates[0], evidence_root=evidence_root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "evidence",
        nargs="?",
        type=Path,
        help="explicit qa/evidence/<task_id>/summary.json selection",
    )
    parser.add_argument("--base", help="base commit; skips evidence only when no relevant path changed")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--repository")
    parser.add_argument("--branch")
    parser.add_argument("--default-branch")
    args = parser.parse_args()
    try:
        head = resolve_commit(args.head)
        base = resolve_commit(args.base) if args.base else None
        pr_changes = changed_paths(base, head) if base else None
        relevant_pr_changes = (
            [path for path in pr_changes if is_release_relevant_path(path)]
            if pr_changes is not None
            else None
        )
        if args.evidence is None and relevant_pr_changes == []:
            print("No release-relevant files changed; cloud evidence is not required for this diff.")
            return 0
        evidence_path = select_summary(args.evidence, candidate_paths=pr_changes)
        summary, _, errors = validate_evidence_bundle(
            evidence_path,
            expected_repository=args.repository,
            expected_branch=args.branch,
            expected_default_branch=args.default_branch,
        )
        if errors:
            print("QA evidence rejected:")
            print("\n".join(f"- {error}" for error in errors))
            return 1
        evidence_sha = summary.get("code_sha")
        if not isinstance(evidence_sha, str) or not SHA_RE.fullmatch(evidence_sha):
            raise ReleaseEvidenceError("evidence code_sha is not a full Git SHA")
        try:
            git("merge-base", "--is-ancestor", evidence_sha, head)
        except subprocess.CalledProcessError:
            raise ReleaseEvidenceError(
                f"Evidence SHA {evidence_sha} is not an ancestor of {head}"
            ) from None
        later_changes = changed_paths(evidence_sha, head)
        invalidating = [path for path in later_changes if is_release_relevant_path(path)]
        if invalidating:
            print("Release-relevant files changed after the cloud QA code SHA:")
            print("\n".join(f"- {path}" for path in invalidating))
            return 1
    except (OSError, json.JSONDecodeError, ReleaseEvidenceError) as error:
        print(f"Release evidence rejected: {error}")
        return 1
    print(f"Release evidence remains valid through {head}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
