#!/usr/bin/env python3
"""Create and validate non-certifying QA runs on the shared sandbox domains."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "qa" / "operational" / "shared-sandbox-catalog.json"
RUNS_ROOT = ROOT / "qa" / "operational" / "runs"
ARTIFACTS_ROOT = ROOT / "artifacts" / "qa-operational"
RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{5,79}")
SHA_RE = re.compile(r"[0-9a-f]{40}")
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_APPLICABLE"}
SEVERITIES = {"P0", "P1", "P2", "P3", "NONE"}
HOSTS = {"hotels-pms.com", "app.hotels-pms.com", "api.hotels-pms.com"}
REQUIRED_OBSERVATION_FIELDS = {
    "operational_case_id",
    "persona",
    "device_profile",
    "target_url",
    "preconditions",
    "human_actions",
    "expected",
    "observed",
    "status",
    "severity",
    "artifact_ids",
    "code_sha",
    "created_record_refs",
    "cleanup_state",
}
REPORT_HEADER = "# QA operativa sobre dominios compartidos — NO ES EVIDENCIA DE RELEASE"


class OperationalQAError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _catalog() -> tuple[dict, str]:
    raw = CATALOG.read_bytes()
    value = json.loads(raw)
    return value, "sha256:" + hashlib.sha256(raw).hexdigest()


def initialize(run_id: str, code_sha: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise OperationalQAError("run id must be a portable 6-80 character identifier")
    if not SHA_RE.fullmatch(code_sha):
        raise OperationalQAError("code SHA must be a full lowercase 40-character SHA")
    run_dir = RUNS_ROOT / run_id
    if run_dir.exists():
        raise OperationalQAError("operational run already exists")
    catalog, catalog_hash = _catalog()
    artifact_root = ARTIFACTS_ROOT / run_id
    for child in ("screenshots", "traces", "videos", "dom"):
        (artifact_root / child).mkdir(parents=True, exist_ok=False)
    _write(
        run_dir / "run-metadata.json",
        {
            "schema_version": 1,
            "record_type": "operational-shared-sandbox-run",
            "certification": "none",
            "release_gate_eligible": False,
            "environment_class": "production-labelled-shared-sandbox",
            "run_id": run_id,
            "code_sha": code_sha,
            "started_at": _utc_now(),
            "completed_at": None,
            "catalog_file": str(CATALOG.relative_to(ROOT)),
            "catalog_sha256": catalog_hash,
            "case_count": len(catalog["cases"]),
            "mutation_policy": catalog["default_mutation_policy"],
            "external_exclusions": [
                "payment completion",
                "outgoing email",
                "provider webhooks",
                "OTA synchronization",
                "provider load testing",
            ],
        },
    )
    _write(
        run_dir / "observations.json",
        {"schema_version": 1, "record_type": "operational-observations", "observations": []},
    )
    _write(
        run_dir / "artifact-index.json",
        {
            "schema_version": 1,
            "artifact_root": f"artifacts/qa-operational/{run_id}",
            "artifacts": [],
        },
    )
    (run_dir / "report.md").write_text(
        REPORT_HEADER + "\n\nCampaña inicializada; resultados pendientes.\n",
        encoding="utf-8",
    )
    return run_dir


def validate(run_dir: Path, *, require_complete: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        metadata = json.loads((run_dir / "run-metadata.json").read_text(encoding="utf-8"))
        observations_doc = json.loads((run_dir / "observations.json").read_text(encoding="utf-8"))
        artifact_doc = json.loads((run_dir / "artifact-index.json").read_text(encoding="utf-8"))
        report = (run_dir / "report.md").read_text(encoding="utf-8")
        catalog, catalog_hash = _catalog()
    except (OSError, json.JSONDecodeError) as exc:
        return [f"operational run is unreadable: {exc}"]
    if metadata.get("release_gate_eligible") is not False or metadata.get("certification") != "none":
        errors.append("operational metadata must be explicitly non-certifying")
    if metadata.get("catalog_sha256") != catalog_hash:
        errors.append("catalog hash does not match the current operational catalog")
    if not report.startswith(REPORT_HEADER):
        errors.append("report is missing the mandatory non-release header")
    code_sha = metadata.get("code_sha")
    if not isinstance(code_sha, str) or not SHA_RE.fullmatch(code_sha):
        errors.append("metadata code_sha must be a full lowercase SHA")
    case_ids = {case["operational_case_id"] for case in catalog.get("cases", [])}
    expected_combinations = {
        (case["operational_case_id"], persona, device)
        for case in catalog.get("cases", [])
        for persona in case.get("personas", [])
        for device in case.get("device_profiles", [])
    }
    run_id = metadata.get("run_id")
    artifact_root = ARTIFACTS_ROOT / str(run_id)
    expected_artifact_root = f"artifacts/qa-operational/{run_id}"
    if artifact_doc.get("artifact_root") != expected_artifact_root:
        errors.append("artifact index points outside the run artifact namespace")
    artifacts = artifact_doc.get("artifacts")
    if not isinstance(artifacts, list):
        artifacts = []
        errors.append("artifact index must contain an artifacts array")
    artifact_ids: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"artifact {index} must be an object")
            continue
        artifact_id = artifact.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            errors.append(f"artifact {index} needs an artifact_id")
            continue
        if artifact_id in artifact_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        artifact_ids.add(artifact_id)
        if not HASH_RE.fullmatch(str(artifact.get("sha256", ""))):
            errors.append(f"artifact {artifact_id} needs a sha256 digest")
        if artifact.get("redaction_state") != "verified":
            errors.append(f"artifact {artifact_id} must be redaction-verified")
        relative_path = artifact.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            errors.append(f"artifact {artifact_id} needs a relative_path")
            continue
        candidate = artifact_root / relative_path
        try:
            resolved_root = artifact_root.resolve(strict=True)
            resolved_candidate = candidate.resolve(strict=True)
        except OSError:
            errors.append(f"artifact {artifact_id} file is missing")
            continue
        if candidate.is_symlink() or resolved_candidate.parent != resolved_root and resolved_root not in resolved_candidate.parents:
            errors.append(f"artifact {artifact_id} escapes the run artifact namespace")
            continue
        if not resolved_candidate.is_file():
            errors.append(f"artifact {artifact_id} must reference a regular file")
            continue
        digest = "sha256:" + hashlib.sha256(resolved_candidate.read_bytes()).hexdigest()
        if artifact.get("sha256") != digest:
            errors.append(f"artifact {artifact_id} hash does not match its file")
    observations = observations_doc.get("observations")
    if not isinstance(observations, list):
        observations = []
        errors.append("observations must be an array")
    seen: set[tuple[str, str, str]] = set()
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            errors.append(f"observation {index} must be an object")
            continue
        missing = REQUIRED_OBSERVATION_FIELDS - set(observation)
        if missing:
            errors.append(f"observation {index} missing: {', '.join(sorted(missing))}")
            continue
        case_id = observation["operational_case_id"]
        if case_id not in case_ids:
            errors.append(f"observation {index} references an unknown case")
        key = (case_id, str(observation["persona"]), str(observation["device_profile"]))
        if key not in expected_combinations:
            errors.append(f"observation {index} is outside the operational matrix")
        if key in seen:
            errors.append(f"duplicate operational observation: {'/'.join(key)}")
        seen.add(key)
        if observation["status"] not in STATUSES:
            errors.append(f"observation {index} has an invalid status")
        if observation["severity"] not in SEVERITIES:
            errors.append(f"observation {index} has an invalid severity")
        if observation["code_sha"] != code_sha:
            errors.append(f"observation {index} does not match the run SHA")
        url = urlsplit(str(observation["target_url"]))
        if url.scheme != "https" or (url.hostname or "").lower() not in HOSTS:
            errors.append(f"observation {index} must target a declared shared sandbox host")
        unknown_artifacts = set(observation["artifact_ids"]) - artifact_ids
        if unknown_artifacts:
            errors.append(f"observation {index} references unknown artifacts")
        if observation["status"] != "NOT_APPLICABLE" and not observation["artifact_ids"]:
            errors.append(f"observation {index} requires operational evidence")
    if require_complete:
        if metadata.get("completed_at") is None:
            errors.append("completed run must declare completed_at")
        missing_combinations = expected_combinations - seen
        if missing_combinations:
            formatted = ["/".join(item) for item in sorted(missing_combinations)]
            errors.append(
                "completed run is missing matrix combinations: " + ", ".join(formatted)
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--run-id", required=True)
    init_parser.add_argument("--code-sha", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("run_dir", type=Path)
    validate_parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "init":
            run_dir = initialize(args.run_id, args.code_sha)
            print(f"Initialized non-certifying operational QA run at {run_dir}")
            return 0
        errors = validate(args.run_dir, require_complete=args.require_complete)
    except OperationalQAError as exc:
        print(f"Operational QA refused: {exc}")
        return 2
    if errors:
        print("Operational QA rejected:\n" + "\n".join(f"- {error}" for error in errors))
        return 1
    print("Operational QA structure is valid and explicitly non-certifying.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
