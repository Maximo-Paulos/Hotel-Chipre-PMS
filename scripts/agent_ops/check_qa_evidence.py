#!/usr/bin/env python3
"""Validate redacted cloud QA evidence and bind it to provider evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_ops.validate_preview_manifest import validate_manifest
from scripts.agent_ops.qa_evidence_attestation import (
    ATTESTATION_NAME,
    AttestationError,
    verify_attestation,
)


CATALOG = ROOT / "qa" / "regression-catalog.json"
MANIFEST_NAME = "validated-preview-manifest.json"
TRUSTED_PUBLIC_KEY = ROOT / "qa" / "trust" / "qa-evidence-public-key.pem"
SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
TASK_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
REPOSITORY_RE = re.compile(r"[^/\s]+/[^/\s]+")
PRODUCTION_HOSTS = {"app.hotels-pms.com", "hotels-pms.com", "api.hotels-pms.com"}
FUTURE_SKEW = timedelta(minutes=5)
MAX_QA_DURATION = timedelta(hours=24)
REQUIRED_RESULT_FIELDS = {
    "persona",
    "case_id",
    "status",
    "preview_url",
    "precondition",
    "human_action",
    "expected",
    "observed",
    "evidence",
    "code_sha",
}
PROVIDER_FIELDS = {
    "manifest_file",
    "manifest_sha256",
    "workflow_run_id",
    "artifact_id",
    "task_id",
    "repository",
    "git_branch",
    "workflow_code_sha",
    "workflow_git_branch",
}
PREVIEW_BINDINGS = {
    "app_url": ("app_url",),
    "api_origin": ("api_origin",),
    "api_url": ("api_base_url",),
    "health_url": ("health_url",),
    "vercel_project_id": ("frontend", "project_id"),
    "vercel_deployment_id": ("frontend", "deployment_id"),
    "render_service_id": ("backend", "service_id"),
    "render_deployment_id": ("backend", "deployment_id"),
    "render_environment_id": ("configuration", "environment_id"),
    "supabase_project_ref": ("database", "project_ref"),
    "supabase_branch_ref": ("database", "branch_ref"),
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def mapping(value: object, field: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(errors, f"{field} must be an object")
        return {}
    return value


def positive_integer(value: object, field: str, errors: list[str]) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        fail(errors, f"{field} must be a positive integer")
        return None
    return value


def utc_timestamp(value: object, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        fail(errors, f"{field} must be an ISO-8601 UTC timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        fail(errors, f"{field} must be an ISO-8601 UTC timestamp")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        fail(errors, f"{field} must use UTC")
        return None
    return parsed.astimezone(timezone.utc)


def preview_origin(value: object, field: str, errors: list[str]) -> str | None:
    """Return the normalized origin for a credential-free HTTPS preview URL."""

    if not isinstance(value, str) or not value.strip():
        fail(errors, f"{field} must be a non-empty HTTPS URL")
        return None
    raw = value.strip()
    parsed = urlsplit(raw)
    hostname = (parsed.hostname or "").rstrip(".").lower()
    try:
        port = parsed.port
    except ValueError:
        fail(errors, f"{field} has an invalid port")
        return None
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or port not in {None, 443}
    ):
        fail(errors, f"{field} must be a credential-free HTTPS URL on port 443")
        return None
    if hostname in PRODUCTION_HOSTS:
        fail(errors, f"{field} must not point at shared production host {hostname}")
        return None
    return f"https://{hostname}"


def nested_value(root: dict[str, Any], path: tuple[str, ...]) -> object:
    value: object = root
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def load_json_object(path: Path, label: str, errors: list[str]) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(errors, f"{label} is unreadable JSON: {error}")
        return {}, b""
    if not isinstance(value, dict):
        fail(errors, f"{label} must be a JSON object")
        return {}, raw
    return value, raw


def validate_evidence_bundle(
    summary_path: Path,
    *,
    expected_sha: str | None = None,
    expected_repository: str | None = None,
    expected_branch: str | None = None,
    expected_default_branch: str | None = None,
    expected_artifact_id: int | None = None,
    now: datetime | None = None,
    attestation_mode: str = "structural",
    attestation_public_key_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Validate one summary and its fixed-name sibling provider manifest.

    ``structural`` is retained for isolated unit tests and for the local issuer
    before it signs.  User-facing CLI and trusted release-gate callers must use
    ``required`` with the trusted-base public key.
    """

    errors: list[str] = []
    if attestation_mode not in {"structural", "required"}:
        fail(errors, "attestation_mode must be structural or required")
    summary, _ = load_json_object(summary_path, "summary", errors)
    try:
        catalog_value = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(errors, f"regression catalog is unreadable JSON: {error}")
        catalog_value = {}
    catalog = mapping(catalog_value, "regression catalog", errors)
    cases = catalog.get("cases")
    if not isinstance(cases, list):
        fail(errors, "regression catalog cases must be an array")
        cases = []

    required_summary_fields = {
        "task_id",
        "code_sha",
        "provider_evidence",
        "preview",
        "executed_at",
        "results",
        "external_exclusions",
        "blocked",
    }
    missing_summary = required_summary_fields - set(summary)
    if missing_summary:
        fail(errors, "missing top-level fields: " + ", ".join(sorted(missing_summary)))

    task_id = summary.get("task_id")
    if not isinstance(task_id, str) or not TASK_RE.fullmatch(task_id):
        fail(errors, "task_id must be a portable identifier")
    elif summary_path.name != "summary.json" or summary_path.parent.name != task_id:
        fail(errors, "summary must live at qa/evidence/<task_id>/summary.json")

    code_sha = summary.get("code_sha")
    if not isinstance(code_sha, str) or not SHA_RE.fullmatch(code_sha):
        fail(errors, "code_sha must be a full 40- or 64-character Git SHA")
        code_sha = ""
    if expected_sha and code_sha != expected_sha:
        fail(errors, f"evidence SHA {code_sha} does not match expected {expected_sha}")

    provider = mapping(summary.get("provider_evidence"), "provider_evidence", errors)
    missing_provider = PROVIDER_FIELDS - set(provider)
    if missing_provider:
        fail(errors, "provider_evidence missing: " + ", ".join(sorted(missing_provider)))
    if provider.get("manifest_file") != MANIFEST_NAME:
        fail(errors, f"provider_evidence.manifest_file must be {MANIFEST_NAME}")
    manifest_path = summary_path.parent / MANIFEST_NAME
    if manifest_path.is_symlink():
        fail(errors, "validated preview manifest must not be a symlink")
    manifest, manifest_raw = load_json_object(manifest_path, "validated preview manifest", errors)
    actual_manifest_hash = "sha256:" + hashlib.sha256(manifest_raw).hexdigest()
    manifest_hash = provider.get("manifest_sha256")
    if not isinstance(manifest_hash, str) or not HASH_RE.fullmatch(manifest_hash):
        fail(errors, "provider_evidence.manifest_sha256 must be sha256:<64 lowercase hex>")
    elif manifest_hash != actual_manifest_hash:
        fail(errors, "provider_evidence.manifest_sha256 does not match the sibling manifest bytes")

    workflow_run_id = positive_integer(
        provider.get("workflow_run_id"), "provider_evidence.workflow_run_id", errors
    )
    artifact_id = positive_integer(provider.get("artifact_id"), "provider_evidence.artifact_id", errors)
    if expected_artifact_id is not None and artifact_id != expected_artifact_id:
        fail(errors, "provider_evidence.artifact_id does not match the selected provider artifact")
    provider_task_id = provider.get("task_id")
    expected_provider_task = f"preview-{code_sha[:12]}" if code_sha else ""
    if not isinstance(provider_task_id, str) or provider_task_id != expected_provider_task:
        fail(errors, "provider_evidence.task_id must be preview-<first 12 characters of code_sha>")
    repository = provider.get("repository")
    if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
        fail(errors, "provider_evidence.repository must be owner/repository")
        repository = ""
    if expected_repository and repository.lower() != expected_repository.lower():
        fail(errors, "provider_evidence.repository does not match the expected repository")
    branch = provider.get("git_branch")
    if not isinstance(branch, str) or not branch.strip():
        fail(errors, "provider_evidence.git_branch must be non-empty")
        branch = ""
    if expected_branch and branch != expected_branch:
        fail(errors, "provider_evidence.git_branch does not match the expected branch")
    workflow_sha = provider.get("workflow_code_sha")
    if not isinstance(workflow_sha, str) or not SHA_RE.fullmatch(workflow_sha):
        fail(errors, "provider_evidence.workflow_code_sha must be a full Git SHA")
        workflow_sha = ""
    default_branch = provider.get("workflow_git_branch")
    if not isinstance(default_branch, str) or not default_branch.strip():
        fail(errors, "provider_evidence.workflow_git_branch must be non-empty")
        default_branch = ""
    if expected_default_branch and default_branch != expected_default_branch:
        fail(errors, "provider_evidence.workflow_git_branch does not match the expected default branch")

    manifest_errors = validate_manifest(
        manifest,
        expected_sha=code_sha or None,
        expected_task_id=provider_task_id if isinstance(provider_task_id, str) else None,
        expected_workflow_run_id=workflow_run_id,
        expected_repository=repository or None,
        expected_branch=branch or None,
        expected_workflow_sha=workflow_sha or None,
        expected_default_branch=default_branch or None,
        enforce_freshness=False,
    )
    errors.extend(f"validated preview manifest: {error}" for error in manifest_errors)

    generated_at = utc_timestamp(manifest.get("generated_at"), "manifest.generated_at", errors)
    executed_at = utc_timestamp(summary.get("executed_at"), "executed_at", errors)
    reference_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if generated_at and executed_at:
        if executed_at < generated_at:
            fail(errors, "executed_at must be at or after manifest.generated_at")
        if executed_at - generated_at > MAX_QA_DURATION:
            fail(errors, "cloud QA must finish within 24 hours of provider verification")
        if executed_at > reference_time + FUTURE_SKEW:
            fail(errors, "executed_at is unreasonably far in the future")

    preview = mapping(summary.get("preview"), "preview", errors)
    for field, manifest_path_parts in PREVIEW_BINDINGS.items():
        expected_value = nested_value(manifest, manifest_path_parts)
        actual_value = preview.get(field)
        if not isinstance(actual_value, str) or not actual_value:
            fail(errors, f"preview.{field} must be a non-empty string")
        elif actual_value != expected_value:
            fail(errors, f"preview.{field} does not exactly match validated provider evidence")
    allowed_preview_origins: set[str] = set()
    for key in ("app_url", "api_origin", "api_url", "health_url"):
        origin = preview_origin(preview.get(key), f"preview.{key}", errors)
        if origin:
            allowed_preview_origins.add(origin)

    expected_pairs: set[tuple[str, str]] = set()
    expected_text: dict[tuple[str, str], str] = {}
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            fail(errors, f"regression catalog case {index} is malformed")
            continue
        personas = case.get("personas")
        if not isinstance(personas, list) or not all(isinstance(persona, str) for persona in personas):
            fail(errors, f"regression catalog case {case['id']} personas are malformed")
            continue
        for persona in personas:
            pair = (case["id"], persona)
            expected_pairs.add(pair)
            expected_text[pair] = str(case.get("expected", ""))

    observed_pairs: set[tuple[str, str]] = set()
    results = summary.get("results")
    if not isinstance(results, list):
        fail(errors, "results must be an array")
        results = []
    for index, result_value in enumerate(results):
        if not isinstance(result_value, dict):
            fail(errors, f"result {index} must be an object")
            continue
        result = result_value
        missing = REQUIRED_RESULT_FIELDS - set(result)
        if missing:
            fail(errors, f"result {index} missing: {', '.join(sorted(missing))}")
            continue
        case_id = result.get("case_id")
        persona = result.get("persona")
        if not isinstance(case_id, str) or not isinstance(persona, str):
            fail(errors, f"result {index} case_id and persona must be strings")
            continue
        pair = (case_id, persona)
        if pair not in expected_pairs:
            fail(errors, f"result {index} is not a catalog persona/case row")
        if pair in observed_pairs:
            fail(errors, f"duplicate catalog row: {case_id}/{persona}")
        observed_pairs.add(pair)
        if result.get("status") != "passed":
            fail(errors, f"{case_id} for {persona} is not passed: {result.get('status')}")
        if result.get("code_sha") != code_sha:
            fail(errors, f"{case_id} has mismatched result SHA")
        if pair in expected_text and result.get("expected") != expected_text[pair]:
            fail(errors, f"{case_id} for {persona} weakens or changes the catalog expectation")
        for field in ("precondition", "human_action", "observed"):
            if not isinstance(result.get(field), str) or not result[field].strip():
                fail(errors, f"result {index}.{field} must be non-empty")
        row_origin = preview_origin(result.get("preview_url"), f"result {index}.preview_url", errors)
        if row_origin and row_origin not in allowed_preview_origins:
            fail(errors, f"{case_id} for {persona} points at an unverified preview origin")
        evidence_reference = result.get("evidence")
        if not isinstance(evidence_reference, str) or not HASH_RE.fullmatch(evidence_reference):
            fail(errors, f"{case_id} for {persona} evidence must be sha256:<64 lowercase hex>")
    missing_pairs = expected_pairs - observed_pairs
    if missing_pairs:
        fail(
            errors,
            "missing catalog coverage: "
            + ", ".join(f"{case}/{persona}" for case, persona in sorted(missing_pairs)),
        )

    exclusions = summary.get("external_exclusions")
    if not isinstance(exclusions, list) or not all(isinstance(value, str) for value in exclusions):
        fail(errors, "external_exclusions must be an array of strings")
        exclusions = []
    policy = mapping(catalog.get("policy"), "regression catalog policy", errors)
    mandated = policy.get("external_exclusions")
    if not isinstance(mandated, list) or not all(isinstance(value, str) for value in mandated):
        fail(errors, "regression catalog external exclusions are malformed")
        mandated = []
    if not set(mandated).issubset(set(exclusions)):
        fail(errors, "external exclusions are incomplete")
    if summary.get("blocked") is not False:
        fail(errors, "blocked must be false for passing QA evidence")
    if attestation_mode == "required":
        attestation_path = summary_path.parent / ATTESTATION_NAME
        public_key_path = attestation_public_key_path or TRUSTED_PUBLIC_KEY
        if public_key_path.is_symlink():
            fail(errors, "trusted QA evidence public key must not be a symlink")
        else:
            try:
                public_key_value = public_key_path.read_bytes()
            except OSError:
                fail(errors, "trusted QA evidence public key is unavailable")
            else:
                try:
                    verify_attestation(
                        summary_path,
                        public_key_value,
                        attestation_path=attestation_path,
                        now=reference_time,
                    )
                except AttestationError as error:
                    fail(errors, f"QA operator attestation: {error}")
    return summary, manifest, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("--expected-sha")
    parser.add_argument("--expected-repository")
    parser.add_argument("--expected-branch")
    parser.add_argument("--expected-default-branch")
    parser.add_argument("--expected-artifact-id", type=int)
    args = parser.parse_args()
    _, _, errors = validate_evidence_bundle(
        args.summary,
        expected_sha=args.expected_sha,
        expected_repository=args.expected_repository,
        expected_branch=args.expected_branch,
        expected_default_branch=args.expected_default_branch,
        expected_artifact_id=args.expected_artifact_id,
        attestation_mode="required",
        attestation_public_key_path=TRUSTED_PUBLIC_KEY,
    )
    if errors:
        print("QA evidence rejected:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(
        "QA evidence is operator-attested and bound to its validated preview manifest."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
