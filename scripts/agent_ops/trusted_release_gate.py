#!/usr/bin/env python3
"""Trusted base-branch gate for provider-bound cloud QA evidence.

The prepare phase reads PR-head JSON blobs through the GitHub API but never
checks out or executes the head.  The finalize phase compares the provider
artifact downloaded by the official GitHub action with those already-validated
bytes.  Only this file from the immutable base SHA is executed.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_ops.check_qa_evidence import SHA_RE, validate_evidence_bundle
from scripts.agent_ops.check_release_evidence import is_release_relevant_path
from scripts.agent_ops.qa_evidence_attestation import ATTESTATION_NAME


GITHUB_API = "https://api.github.com"
WORKFLOW_PATH = ".github/workflows/verify-preview-providers.yml"
SUMMARY_RE = re.compile(r"qa/evidence/([A-Za-z0-9][A-Za-z0-9._-]{0,79})/summary\.json")
TRUSTED_PUBLIC_KEY_REPO_PATH = "qa/trust/qa-evidence-public-key.pem"
MAX_JSON_BLOB_BYTES = 2 * 1024 * 1024
MAX_TREE_ENTRIES = 100_000


class TrustedGateError(RuntimeError):
    pass


def full_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise TrustedGateError(f"{field} must be a full 40- or 64-character Git SHA")
    return value


def positive_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise TrustedGateError(f"{field} must be a positive integer")
    return value


class GitHubClient:
    """Small read-only GitHub REST client with redacted failures."""

    def __init__(
        self,
        repository: str,
        token: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        if not re.fullmatch(r"[^/\s]+/[^/\s]+", repository):
            raise TrustedGateError("repository must be owner/repository")
        if not token:
            raise TrustedGateError("GH_TOKEN is missing")
        self.repository = repository
        self._token = token
        self._opener = opener

    def get_json(self, path: str) -> Any:
        if not path.startswith("/") or ".." in path or "\n" in path or "\r" in path:
            raise TrustedGateError("GitHub API path is invalid")
        request = urllib.request.Request(
            f"{GITHUB_API}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Hotel-Chipre-PMS-trusted-release-gate/1.0",
            },
        )
        try:
            with self._opener(request, timeout=30) as response:
                raw = response.read(MAX_JSON_BLOB_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise TrustedGateError(f"GitHub API request failed with HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            raise TrustedGateError("GitHub API request failed") from None
        if len(raw) > MAX_JSON_BLOB_BYTES:
            raise TrustedGateError("GitHub API response exceeded the safety limit")
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TrustedGateError("GitHub API returned invalid JSON") from None

    def repository_metadata(self) -> dict[str, Any]:
        value = self.get_json(f"/repos/{self.repository}")
        if not isinstance(value, dict):
            raise TrustedGateError("GitHub repository metadata is invalid")
        return value

    def pull_request(self, number: int) -> dict[str, Any]:
        value = self.get_json(f"/repos/{self.repository}/pulls/{number}")
        if not isinstance(value, dict):
            raise TrustedGateError("GitHub pull request metadata is invalid")
        return value

    def tree(self, commit_sha: str) -> dict[str, tuple[str, str]]:
        commit = self.get_json(f"/repos/{self.repository}/git/commits/{commit_sha}")
        if not isinstance(commit, dict) or commit.get("sha") != commit_sha:
            raise TrustedGateError("GitHub commit metadata does not match the requested SHA")
        tree_sha = ((commit.get("tree") or {}).get("sha")) if isinstance(commit.get("tree"), dict) else None
        tree_sha = full_sha(tree_sha, "Git tree SHA")
        encoded_tree = urllib.parse.quote(tree_sha, safe="")
        value = self.get_json(
            f"/repos/{self.repository}/git/trees/{encoded_tree}?recursive=1"
        )
        if not isinstance(value, dict) or value.get("truncated") is not False:
            raise TrustedGateError("Git tree is unavailable or truncated")
        entries = value.get("tree")
        if not isinstance(entries, list) or len(entries) > MAX_TREE_ENTRIES:
            raise TrustedGateError("Git tree entry set is invalid or too large")
        result: dict[str, tuple[str, str]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise TrustedGateError("Git tree contains a malformed entry")
            path = entry.get("path")
            kind = entry.get("type")
            sha = entry.get("sha")
            if not isinstance(path, str) or not isinstance(kind, str) or not isinstance(sha, str):
                raise TrustedGateError("Git tree contains an incomplete entry")
            if kind == "blob":
                result[path] = (kind, full_sha(sha, f"blob SHA for {path}"))
        return result

    def blob(self, blob_sha: str) -> bytes:
        value = self.get_json(f"/repos/{self.repository}/git/blobs/{blob_sha}")
        if not isinstance(value, dict) or value.get("sha") != blob_sha or value.get("encoding") != "base64":
            raise TrustedGateError("Git blob response is invalid")
        size = value.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0 or size > MAX_JSON_BLOB_BYTES:
            raise TrustedGateError("Git blob size is invalid or exceeds the safety limit")
        content = value.get("content")
        if not isinstance(content, str):
            raise TrustedGateError("Git blob content is missing")
        try:
            raw = base64.b64decode("".join(content.split()), validate=True)
        except (ValueError, UnicodeError):
            raise TrustedGateError("Git blob content is not canonical base64") from None
        if len(raw) != size:
            raise TrustedGateError("Git blob size does not match decoded content")
        return raw

    def compare(self, base_sha: str, head_sha: str) -> dict[str, Any]:
        value = self.get_json(f"/repos/{self.repository}/compare/{base_sha}...{head_sha}")
        if not isinstance(value, dict):
            raise TrustedGateError("GitHub comparison metadata is invalid")
        return value

    def artifact(self, artifact_id: int) -> dict[str, Any]:
        value = self.get_json(f"/repos/{self.repository}/actions/artifacts/{artifact_id}")
        if not isinstance(value, dict):
            raise TrustedGateError("GitHub artifact metadata is invalid")
        return value

    def workflow_run(self, run_id: int) -> dict[str, Any]:
        value = self.get_json(f"/repos/{self.repository}/actions/runs/{run_id}")
        if not isinstance(value, dict):
            raise TrustedGateError("GitHub workflow run metadata is invalid")
        return value

    def workflow(self) -> dict[str, Any]:
        value = self.get_json(f"/repos/{self.repository}/actions/workflows/verify-preview-providers.yml")
        if not isinstance(value, dict):
            raise TrustedGateError("GitHub workflow metadata is invalid")
        return value


def changed_blob_paths(
    before: dict[str, tuple[str, str]], after: dict[str, tuple[str, str]]
) -> list[str]:
    return sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )


def require_base_public_key(
    client: Any,
    base_tree: dict[str, tuple[str, str]],
    base_checkout_root: Path,
) -> Path:
    """Bind the on-disk fixed trust key to the exact PR base tree blob."""

    key_path = base_checkout_root / TRUSTED_PUBLIC_KEY_REPO_PATH
    if key_path.is_symlink():
        raise TrustedGateError("trusted QA evidence public key must not be a symlink")
    entry = base_tree.get(TRUSTED_PUBLIC_KEY_REPO_PATH)
    if not entry or entry[0] != "blob":
        raise TrustedGateError("trusted QA evidence public key is absent from the PR base")
    try:
        local_bytes = key_path.read_bytes()
    except OSError:
        raise TrustedGateError("trusted QA evidence public key is unavailable in base checkout") from None
    if not local_bytes or len(local_bytes) > 64 * 1024:
        raise TrustedGateError("trusted QA evidence public key size is invalid")
    if client.blob(entry[1]) != local_bytes:
        raise TrustedGateError("on-disk QA evidence public key does not match the PR base blob")
    return key_path


def require_pull_identity(
    repository_metadata: dict[str, Any],
    pull: dict[str, Any],
    *,
    repository: str,
    base_sha: str,
    head_sha: str,
    base_branch: str,
) -> tuple[str, str]:
    default_branch = repository_metadata.get("default_branch")
    if not isinstance(default_branch, str) or not default_branch:
        raise TrustedGateError("repository default branch is unavailable")
    base = pull.get("base") if isinstance(pull.get("base"), dict) else {}
    head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
    base_repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
    head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
    if pull.get("state") != "open":
        raise TrustedGateError("pull request is not open")
    if str(base_repo.get("full_name", "")).lower() != repository.lower():
        raise TrustedGateError("pull request base repository does not match")
    if str(head_repo.get("full_name", "")).lower() != repository.lower():
        raise TrustedGateError("fork pull requests cannot consume trusted preview evidence")
    if base.get("sha") != base_sha or head.get("sha") != head_sha:
        raise TrustedGateError("pull request SHAs do not match the trusted event")
    if base.get("ref") != base_branch or base_branch != default_branch:
        raise TrustedGateError("trusted release gate only accepts the repository default branch as base")
    head_branch = head.get("ref")
    if not isinstance(head_branch, str) or not head_branch:
        raise TrustedGateError("pull request head branch is unavailable")
    return head_branch, default_branch


def require_evidence_ancestry(client: Any, evidence_sha: str, head_sha: str) -> None:
    comparison = client.compare(evidence_sha, head_sha)
    merge_base = comparison.get("merge_base_commit")
    merge_base_sha = merge_base.get("sha") if isinstance(merge_base, dict) else None
    if comparison.get("status") not in {"ahead", "identical"} or merge_base_sha != evidence_sha:
        raise TrustedGateError("cloud QA code SHA is not an ancestor of the PR head")


def require_provider_artifact_provenance(
    client: Any,
    *,
    repository: str,
    default_branch: str,
    base_sha: str,
    base_tree: dict[str, tuple[str, str]],
    summary: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[int, int]:
    provider = summary["provider_evidence"]
    generated = manifest["generated_by"]
    code_sha = full_sha(summary.get("code_sha"), "summary code_sha")
    artifact_id = positive_integer(provider.get("artifact_id"), "provider artifact ID")
    run_id = positive_integer(provider.get("workflow_run_id"), "provider workflow run ID")
    artifact = client.artifact(artifact_id)
    expected_name = f"preview-provider-evidence-{code_sha}"
    if (
        artifact.get("id") != artifact_id
        or artifact.get("name") != expected_name
        or artifact.get("expired") is not False
    ):
        raise TrustedGateError("provider artifact name or retention state is invalid")
    size = artifact.get("size_in_bytes")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0 or size > MAX_JSON_BLOB_BYTES:
        raise TrustedGateError("provider artifact size is invalid")
    artifact_run = artifact.get("workflow_run") if isinstance(artifact.get("workflow_run"), dict) else {}
    if artifact_run.get("id") != run_id:
        raise TrustedGateError("provider artifact does not belong to the recorded workflow run")
    run = client.workflow_run(run_id)
    workflow = client.workflow()
    if workflow.get("path") != WORKFLOW_PATH or workflow.get("state") != "active":
        raise TrustedGateError("trusted provider verifier workflow is unavailable")
    if run.get("workflow_id") != workflow.get("id") or run.get("path") != WORKFLOW_PATH:
        raise TrustedGateError("provider artifact came from the wrong workflow")
    if run.get("event") != "workflow_dispatch" or run.get("status") != "completed" or run.get("conclusion") != "success":
        raise TrustedGateError("provider verifier workflow run was not successful")
    if run.get("head_branch") != default_branch:
        raise TrustedGateError("provider verifier did not run from the default branch")
    run_repository = run.get("head_repository") if isinstance(run.get("head_repository"), dict) else {}
    if str(run_repository.get("full_name", "")).lower() != repository.lower():
        raise TrustedGateError("provider verifier belongs to another repository")
    workflow_sha = full_sha(run.get("head_sha"), "provider workflow SHA")
    if workflow_sha != generated.get("workflow_code_sha"):
        raise TrustedGateError("provider workflow SHA does not match the manifest")
    actor = run.get("actor") if isinstance(run.get("actor"), dict) else {}
    if str(actor.get("id", "")) != str(generated.get("actor_id", "")):
        raise TrustedGateError("provider workflow actor does not match the manifest")
    if artifact_run.get("head_sha") != workflow_sha:
        raise TrustedGateError("artifact workflow SHA does not match its run")
    workflow_comparison = client.compare(workflow_sha, base_sha)
    workflow_merge_base = workflow_comparison.get("merge_base_commit")
    workflow_merge_base_sha = (
        workflow_merge_base.get("sha") if isinstance(workflow_merge_base, dict) else None
    )
    if (
        workflow_comparison.get("status") not in {"ahead", "identical"}
        or workflow_merge_base_sha != workflow_sha
    ):
        raise TrustedGateError("provider workflow SHA is not an ancestor of the current PR base")
    workflow_tree = client.tree(workflow_sha)
    workflow_entry = workflow_tree.get(WORKFLOW_PATH)
    base_workflow_entry = base_tree.get(WORKFLOW_PATH)
    if not workflow_entry or workflow_entry[0] != "blob":
        raise TrustedGateError("trusted provider workflow source is missing from its run SHA")
    if not base_workflow_entry or base_workflow_entry[0] != "blob":
        raise TrustedGateError("trusted provider workflow source is missing from the PR base")
    if workflow_entry != base_workflow_entry:
        raise TrustedGateError(
            "provider workflow blob does not exactly match the current PR base workflow"
        )
    return artifact_id, run_id


@dataclass(frozen=True)
class PreparedEvidence:
    artifact_id: int | None
    workflow_run_id: int | None
    evidence_required: bool
    task_id: str | None


def prepare_gate(
    client: Any,
    *,
    repository: str,
    pr_number: int,
    base_sha: str,
    head_sha: str,
    base_branch: str,
    output_dir: Path,
    now: datetime | None = None,
    base_checkout_root: Path = ROOT,
) -> PreparedEvidence:
    base_sha = full_sha(base_sha, "base SHA")
    head_sha = full_sha(head_sha, "head SHA")
    repository_metadata = client.repository_metadata()
    pull = client.pull_request(pr_number)
    head_branch, default_branch = require_pull_identity(
        repository_metadata,
        pull,
        repository=repository,
        base_sha=base_sha,
        head_sha=head_sha,
        base_branch=base_branch,
    )
    base_tree = client.tree(base_sha)
    head_tree = client.tree(head_sha)
    pr_changes = changed_blob_paths(base_tree, head_tree)
    if not any(is_release_relevant_path(path) for path in pr_changes):
        return PreparedEvidence(None, None, False, None)
    if TRUSTED_PUBLIC_KEY_REPO_PATH in pr_changes:
        raise TrustedGateError(
            "the QA evidence trust key cannot change in the same PR it protects"
        )
    trusted_public_key = require_base_public_key(client, base_tree, base_checkout_root)
    summary_candidates = [
        (path, SUMMARY_RE.fullmatch(path))
        for path in pr_changes
        if SUMMARY_RE.fullmatch(path) and path in head_tree
    ]
    if len(summary_candidates) != 1:
        raise TrustedGateError(
            f"exactly one changed QA summary is required; found {len(summary_candidates)}"
        )
    summary_path, match = summary_candidates[0]
    assert match is not None
    task_id = match.group(1)
    manifest_path = f"qa/evidence/{task_id}/validated-preview-manifest.json"
    attestation_path = f"qa/evidence/{task_id}/{ATTESTATION_NAME}"
    if manifest_path not in pr_changes or manifest_path not in head_tree:
        raise TrustedGateError("the summary sibling validated-preview-manifest.json must change in the PR")
    if attestation_path not in pr_changes or attestation_path not in head_tree:
        raise TrustedGateError("the summary sibling attestation.json must change in the PR")
    summary_raw = client.blob(head_tree[summary_path][1])
    manifest_raw = client.blob(head_tree[manifest_path][1])
    attestation_raw = client.blob(head_tree[attestation_path][1])
    output_task = output_dir / task_id
    output_task.mkdir(parents=True, exist_ok=False)
    local_summary = output_task / "summary.json"
    local_manifest = output_task / "validated-preview-manifest.json"
    local_attestation = output_task / ATTESTATION_NAME
    local_summary.write_bytes(summary_raw)
    local_manifest.write_bytes(manifest_raw)
    local_attestation.write_bytes(attestation_raw)
    summary, manifest, errors = validate_evidence_bundle(
        local_summary,
        expected_repository=repository,
        expected_branch=head_branch,
        expected_default_branch=default_branch,
        now=now,
        attestation_mode="required",
        attestation_public_key_path=trusted_public_key,
    )
    if errors:
        raise TrustedGateError("QA bundle failed trusted-base validation: " + "; ".join(errors))
    evidence_sha = full_sha(summary.get("code_sha"), "cloud QA code SHA")
    require_evidence_ancestry(client, evidence_sha, head_sha)
    evidence_tree = client.tree(evidence_sha)
    later_changes = changed_blob_paths(evidence_tree, head_tree)
    invalidating = [path for path in later_changes if is_release_relevant_path(path)]
    if invalidating:
        raise TrustedGateError(
            "release-relevant files changed after cloud QA: " + ", ".join(invalidating)
        )
    artifact_id, run_id = require_provider_artifact_provenance(
        client,
        repository=repository,
        default_branch=default_branch,
        base_sha=base_sha,
        base_tree=base_tree,
        summary=summary,
        manifest=manifest,
    )
    return PreparedEvidence(artifact_id, run_id, True, task_id)


def finalize_gate(
    input_dir: Path,
    artifact_dir: Path,
    *,
    now: datetime | None = None,
    base_checkout_root: Path = ROOT,
) -> str:
    summaries = sorted(input_dir.glob("*/summary.json"))
    if len(summaries) != 1:
        raise TrustedGateError("trusted input must contain exactly one QA summary")
    summary_path = summaries[0]
    summary, _, errors = validate_evidence_bundle(
        summary_path,
        now=now,
        attestation_mode="required",
        attestation_public_key_path=(
            base_checkout_root / TRUSTED_PUBLIC_KEY_REPO_PATH
        ),
    )
    if errors:
        raise TrustedGateError("trusted QA bundle changed before finalize: " + "; ".join(errors))
    files = [path for path in artifact_dir.rglob("*") if path.is_file()]
    if len(files) != 1 or files[0].name != "preview-manifest.json" or files[0].is_symlink():
        raise TrustedGateError("provider artifact must contain only preview-manifest.json")
    provider_bytes = files[0].read_bytes()
    if len(provider_bytes) > MAX_JSON_BLOB_BYTES:
        raise TrustedGateError("provider manifest artifact exceeds the safety limit")
    sibling_bytes = (summary_path.parent / "validated-preview-manifest.json").read_bytes()
    if provider_bytes != sibling_bytes:
        raise TrustedGateError("provider artifact bytes do not match the PR evidence manifest")
    return str(summary["task_id"])


def write_github_outputs(path: Path, prepared: PreparedEvidence) -> None:
    values = {
        "evidence_required": "true" if prepared.evidence_required else "false",
        "artifact_id": str(prepared.artifact_id or ""),
        "workflow_run_id": str(prepared.workflow_run_id or ""),
        "task_id": prepared.task_id or "",
    }
    with path.open("a", encoding="utf-8") as output:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise TrustedGateError("GitHub output contains a line break")
            output.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--repository", required=True)
    prepare.add_argument("--pr-number", required=True, type=int)
    prepare.add_argument("--base-sha", required=True)
    prepare.add_argument("--head-sha", required=True)
    prepare.add_argument("--base-branch", required=True)
    prepare.add_argument("--output-dir", required=True, type=Path)
    prepare.add_argument("--github-output", required=True, type=Path)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--input-dir", required=True, type=Path)
    finalize.add_argument("--artifact-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            client = GitHubClient(args.repository, os.environ.get("GH_TOKEN", ""))
            prepared = prepare_gate(
                client,
                repository=args.repository,
                pr_number=args.pr_number,
                base_sha=args.base_sha,
                head_sha=args.head_sha,
                base_branch=args.base_branch,
                output_dir=args.output_dir,
            )
            write_github_outputs(args.github_output, prepared)
            if not prepared.evidence_required:
                print("No release-relevant PR changes; trusted cloud evidence is not required.")
            else:
                print("Trusted base code validated PR evidence metadata and provider provenance.")
        else:
            task_id = finalize_gate(args.input_dir, args.artifact_dir)
            print(f"Trusted provider artifact bytes match the QA bundle for {task_id}.")
    except (OSError, TrustedGateError) as error:
        print(f"Trusted release gate rejected: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
