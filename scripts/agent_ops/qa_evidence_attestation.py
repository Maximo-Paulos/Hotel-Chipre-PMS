#!/usr/bin/env python3
"""Issue and verify operator-signed cloud-QA evidence attestations.

The issuer is intentionally local: before signing, it proves that every
``sha256:...`` referenced by ``summary.json`` is the digest of one regular file
below an operator-selected artifact root.  Symlinks are rejected.  The signed
payload binds the exact summary and provider-manifest bytes, the target
identity, the artifact inventory, the signing time, and the Ed25519 public-key
fingerprint.

Private key material is accepted only from ``QA_EVIDENCE_OPERATOR_PRIVATE_KEY``
or a non-symlink file outside the repository / under ignored ``artifacts/qa``.
It is never accepted as a command-line value and is never printed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ATTESTATION_NAME = "attestation.json"
MANIFEST_NAME = "validated-preview-manifest.json"
PRIVATE_KEY_ENV = "QA_EVIDENCE_OPERATOR_PRIVATE_KEY"
ATTESTATION_TYPE = "hotel-chipre-cloud-qa-operator-ed25519"
SIGNATURE_ALGORITHM = "ed25519"
SIGNING_DOMAIN = b"Hotel-Chipre-PMS/qa-evidence-attestation/v1\x00"
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
TASK_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}")
MAX_ATTESTATION_AGE = timedelta(hours=24)
FUTURE_SKEW = timedelta(minutes=5)
MAX_ARTIFACT_FILES = 10_000
MAX_SINGLE_ARTIFACT_BYTES = 1024 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 2 * 1024 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024


class AttestationError(RuntimeError):
    """Fail-closed error whose messages never include key material."""


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: object, field: str) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise AttestationError(f"{field} is not canonical base64url")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError):
        raise AttestationError(f"{field} is not canonical base64url") from None
    if _b64url_encode(decoded) != value:
        raise AttestationError(f"{field} is not canonical base64url")
    return decoded


def _read_regular_nofollow(
    path: Path,
    label: str,
    *,
    maximum_bytes: int,
    require_nonempty: bool = True,
    require_owner_only: bool = False,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise AttestationError(f"{label} is missing, symlinked, or unreadable") from None
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AttestationError(f"{label} is missing or not a regular file")
        if require_owner_only and before.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise AttestationError(f"{label} permissions must be owner-only")
        if (require_nonempty and before.st_size <= 0) or before.st_size > maximum_bytes:
            raise AttestationError(f"{label} size is invalid")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if len(raw) > maximum_bytes:
            raise AttestationError(f"{label} size is invalid")
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or len(raw) != before.st_size:
            raise AttestationError(f"{label} changed while it was being read")
        return raw
    except OSError:
        raise AttestationError(f"{label} cannot be read") from None
    finally:
        os.close(descriptor)


def _read_limited(path: Path, label: str) -> bytes:
    return _read_regular_nofollow(
        path,
        label,
        maximum_bytes=MAX_JSON_BYTES,
    )


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AttestationError(f"{label} is not valid JSON") from None
    if not isinstance(value, dict):
        raise AttestationError(f"{label} must be a JSON object")
    return value


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise AttestationError(f"{field} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AttestationError(f"{field} must be an ISO-8601 UTC timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise AttestationError(f"{field} must use UTC")
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_private_key(value: bytes) -> Ed25519PrivateKey:
    normalized = value.replace(b"\\n", b"\n").strip()
    if not normalized:
        raise AttestationError("operator private key is missing")
    if normalized.startswith(b"-----BEGIN"):
        try:
            key = serialization.load_pem_private_key(normalized, password=None)
        except (TypeError, ValueError):
            raise AttestationError("operator private key is not valid Ed25519 PEM") from None
        if not isinstance(key, Ed25519PrivateKey):
            raise AttestationError("operator private key must be Ed25519")
        return key
    try:
        raw = base64.b64decode(normalized, validate=True)
        return Ed25519PrivateKey.from_private_bytes(raw)
    except (TypeError, ValueError):
        raise AttestationError("operator private key is not valid Ed25519 base64") from None


def load_public_key(value: bytes) -> Ed25519PublicKey:
    normalized = value.replace(b"\\n", b"\n").strip()
    if not normalized:
        raise AttestationError("operator public key is missing")
    if normalized.startswith(b"-----BEGIN"):
        try:
            key = serialization.load_pem_public_key(normalized)
        except (TypeError, ValueError):
            raise AttestationError("operator public key is not valid Ed25519 PEM") from None
        if not isinstance(key, Ed25519PublicKey):
            raise AttestationError("operator public key must be Ed25519")
        return key
    try:
        raw = base64.b64decode(normalized, validate=True)
        return Ed25519PublicKey.from_public_bytes(raw)
    except (TypeError, ValueError):
        raise AttestationError("operator public key is not valid Ed25519 base64") from None


def public_key_bytes(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def public_key_fingerprint(key: Ed25519PublicKey) -> str:
    return _sha256(public_key_bytes(key))


def public_key_pem(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _summary_identity(
    summary: Mapping[str, Any],
    manifest_raw: bytes,
) -> tuple[str, str, str, str, int, int, str, set[str]]:
    task_id = summary.get("task_id")
    code_sha = summary.get("code_sha")
    if not isinstance(task_id, str) or not TASK_RE.fullmatch(task_id):
        raise AttestationError("summary task_id is invalid")
    if not isinstance(code_sha, str) or not SHA_RE.fullmatch(code_sha):
        raise AttestationError("summary code_sha is invalid")
    provider = summary.get("provider_evidence")
    if not isinstance(provider, dict):
        raise AttestationError("summary provider_evidence is invalid")
    repository = provider.get("repository")
    git_branch = provider.get("git_branch")
    run_id = provider.get("workflow_run_id")
    provider_artifact_id = provider.get("artifact_id")
    manifest_hash = provider.get("manifest_sha256")
    if not isinstance(repository, str) or not re.fullmatch(r"[^/\s]+/[^/\s]+", repository):
        raise AttestationError("summary provider repository is invalid")
    if not isinstance(git_branch, str) or not git_branch.strip():
        raise AttestationError("summary provider git_branch is invalid")
    for value, field in (
        (run_id, "workflow_run_id"),
        (provider_artifact_id, "artifact_id"),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise AttestationError(f"summary provider {field} is invalid")
    if provider.get("manifest_file") != MANIFEST_NAME:
        raise AttestationError(f"summary manifest_file must be {MANIFEST_NAME}")
    if manifest_hash != _sha256(manifest_raw):
        raise AttestationError("summary manifest hash does not match exact manifest bytes")

    results = summary.get("results")
    if not isinstance(results, list) or not results:
        raise AttestationError("summary results must be a non-empty array")
    evidence_hashes: set[str] = set()
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise AttestationError(f"summary result {index} is invalid")
        evidence_hash = result.get("evidence")
        if not isinstance(evidence_hash, str) or not HASH_RE.fullmatch(evidence_hash):
            raise AttestationError(f"summary result {index} evidence hash is invalid")
        if result.get("code_sha") != code_sha:
            raise AttestationError(f"summary result {index} code_sha is invalid")
        evidence_hashes.add(evidence_hash)
    return (
        task_id,
        code_sha,
        repository,
        git_branch,
        int(run_id),
        int(provider_artifact_id),
        str(summary.get("executed_at") or ""),
        evidence_hashes,
    )


def verify_local_artifacts(
    artifact_root: Path,
    expected_hashes: set[str],
) -> list[dict[str, Any]]:
    """Return a deterministic signed inventory after hashing real files."""

    if artifact_root.is_symlink():
        raise AttestationError("artifact root must not be a symlink")
    try:
        if not artifact_root.is_dir():
            raise AttestationError("artifact root is missing or not a directory")
        root = artifact_root.resolve(strict=True)
    except OSError:
        raise AttestationError("artifact root cannot be resolved") from None
    if not expected_hashes:
        raise AttestationError("summary contains no evidence hashes")

    matches: dict[str, list[tuple[str, int]]] = {digest: [] for digest in expected_hashes}
    total_bytes = 0
    file_count = 0
    try:
        entries = sorted(artifact_root.rglob("*"), key=lambda item: item.as_posix())
    except OSError:
        raise AttestationError("artifact root cannot be scanned") from None
    for entry in entries:
        if entry.is_symlink():
            raise AttestationError("artifact root must not contain symlinks")
        if entry.is_dir():
            continue
        if not entry.is_file():
            raise AttestationError("artifact root contains a non-regular entry")
        file_count += 1
        if file_count > MAX_ARTIFACT_FILES:
            raise AttestationError("artifact root contains too many files")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(entry, flags)
            before = os.fstat(descriptor)
        except OSError:
            raise AttestationError("artifact file is symlinked or unreadable") from None
        if not stat.S_ISREG(before.st_mode):
            os.close(descriptor)
            raise AttestationError("artifact root contains a non-regular entry")
        size = before.st_size
        if size < 0 or size > MAX_SINGLE_ARTIFACT_BYTES:
            os.close(descriptor)
            raise AttestationError("artifact exceeds the per-file safety limit")
        total_bytes += size
        if total_bytes > MAX_TOTAL_ARTIFACT_BYTES:
            os.close(descriptor)
            raise AttestationError("artifact root exceeds the total safety limit")
        digest = hashlib.sha256()
        try:
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
            after = os.fstat(descriptor)
        except OSError:
            os.close(descriptor)
            raise AttestationError("artifact file cannot be read") from None
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise AttestationError("artifact changed while it was being hashed")
        tagged = "sha256:" + digest.hexdigest()
        if tagged not in matches:
            continue
        resolved = entry.resolve(strict=True)
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            raise AttestationError("artifact escapes the selected artifact root") from None
        if not relative or relative.startswith("../") or any(ord(char) < 32 for char in relative):
            raise AttestationError("artifact relative path is invalid")
        matches[tagged].append((relative, size))

    missing = sorted(digest for digest, candidates in matches.items() if not candidates)
    if missing:
        raise AttestationError(
            f"{len(missing)} summary evidence hash(es) have no real local artifact"
        )
    duplicated = sorted(digest for digest, candidates in matches.items() if len(candidates) != 1)
    if duplicated:
        raise AttestationError("each evidence hash must resolve to exactly one local artifact")
    return [
        {"sha256": digest, "relative_path": matches[digest][0][0], "size_bytes": matches[digest][0][1]}
        for digest in sorted(matches)
    ]


def build_attestation(
    summary_path: Path,
    artifact_root: Path,
    private_key: Ed25519PrivateKey,
    *,
    signed_at: datetime | None = None,
) -> dict[str, Any]:
    if summary_path.is_symlink() or summary_path.name != "summary.json":
        raise AttestationError("summary must be a non-symlink summary.json")
    manifest_path = summary_path.parent / MANIFEST_NAME
    summary_raw = _read_limited(summary_path, "summary")
    manifest_raw = _read_limited(manifest_path, "validated preview manifest")
    summary = _json_object(summary_raw, "summary")
    (
        task_id,
        code_sha,
        repository,
        git_branch,
        workflow_run_id,
        provider_artifact_id,
        executed_at_raw,
        evidence_hashes,
    ) = _summary_identity(summary, manifest_raw)
    if summary_path.parent.name != task_id:
        raise AttestationError("summary directory does not match task_id")
    executed_at = _utc(executed_at_raw, "summary executed_at")
    signing_time = (signed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if signing_time < executed_at:
        raise AttestationError("attestation cannot predate cloud QA execution")
    if signing_time - executed_at > MAX_ATTESTATION_AGE:
        raise AttestationError("attestation must be signed within 24 hours of cloud QA")
    if signing_time > datetime.now(timezone.utc) + FUTURE_SKEW:
        raise AttestationError("attestation signing time cannot be in the future")
    inventory = verify_local_artifacts(artifact_root, evidence_hashes)
    public_key = private_key.public_key()
    payload = {
        "task_id": task_id,
        "code_sha": code_sha,
        "repository": repository,
        "git_branch": git_branch,
        "workflow_run_id": workflow_run_id,
        "provider_artifact_id": provider_artifact_id,
        "executed_at": executed_at_raw,
        "signed_at": _iso_utc(signing_time),
        "summary_sha256": _sha256(summary_raw),
        "manifest_sha256": _sha256(manifest_raw),
        "operator_key_fingerprint": public_key_fingerprint(public_key),
        "artifacts": inventory,
    }
    signature = private_key.sign(SIGNING_DOMAIN + _canonical_json(payload))
    return {
        "schema_version": 1,
        "attestation_type": ATTESTATION_TYPE,
        "payload": payload,
        "signature": {
            "algorithm": SIGNATURE_ALGORITHM,
            "value": _b64url_encode(signature),
        },
    }


def verify_attestation(
    summary_path: Path,
    public_key_value: bytes,
    *,
    attestation_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    manifest_path = summary_path.parent / MANIFEST_NAME
    attestation_path = attestation_path or summary_path.parent / ATTESTATION_NAME
    summary_raw = _read_limited(summary_path, "summary")
    manifest_raw = _read_limited(manifest_path, "validated preview manifest")
    attestation_raw = _read_limited(attestation_path, "QA operator attestation")
    summary = _json_object(summary_raw, "summary")
    attestation = _json_object(attestation_raw, "QA operator attestation")
    if set(attestation) != {"schema_version", "attestation_type", "payload", "signature"}:
        raise AttestationError("QA operator attestation has unexpected or missing fields")
    if attestation.get("schema_version") != 1 or attestation.get("attestation_type") != ATTESTATION_TYPE:
        raise AttestationError("QA operator attestation contract is unsupported")
    payload = attestation.get("payload")
    signature_object = attestation.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature_object, dict):
        raise AttestationError("QA operator attestation payload or signature is invalid")
    expected_payload_fields = {
        "task_id",
        "code_sha",
        "repository",
        "git_branch",
        "workflow_run_id",
        "provider_artifact_id",
        "executed_at",
        "signed_at",
        "summary_sha256",
        "manifest_sha256",
        "operator_key_fingerprint",
        "artifacts",
    }
    if set(payload) != expected_payload_fields:
        raise AttestationError("QA operator attestation payload has unexpected or missing fields")
    if set(signature_object) != {"algorithm", "value"} or signature_object.get("algorithm") != SIGNATURE_ALGORITHM:
        raise AttestationError("QA operator attestation signature contract is invalid")

    public_key = load_public_key(public_key_value)
    fingerprint = public_key_fingerprint(public_key)
    if payload.get("operator_key_fingerprint") != fingerprint or not FINGERPRINT_RE.fullmatch(fingerprint):
        raise AttestationError("QA operator attestation key fingerprint does not match trusted key")
    signature = _b64url_decode(signature_object.get("value"), "attestation signature")
    try:
        public_key.verify(signature, SIGNING_DOMAIN + _canonical_json(payload))
    except InvalidSignature:
        raise AttestationError("QA operator attestation signature is invalid") from None

    (
        task_id,
        code_sha,
        repository,
        git_branch,
        workflow_run_id,
        provider_artifact_id,
        executed_at_raw,
        evidence_hashes,
    ) = _summary_identity(summary, manifest_raw)
    exact_bindings = {
        "task_id": task_id,
        "code_sha": code_sha,
        "repository": repository,
        "git_branch": git_branch,
        "workflow_run_id": workflow_run_id,
        "provider_artifact_id": provider_artifact_id,
        "executed_at": executed_at_raw,
        "summary_sha256": _sha256(summary_raw),
        "manifest_sha256": _sha256(manifest_raw),
    }
    for field, expected in exact_bindings.items():
        if payload.get(field) != expected:
            raise AttestationError(f"QA operator attestation {field} does not match exact evidence bytes")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise AttestationError("QA operator attestation artifacts must be a non-empty array")
    observed_hashes: set[str] = set()
    previous_hash = ""
    for index, item in enumerate(artifacts):
        if not isinstance(item, dict) or set(item) != {"sha256", "relative_path", "size_bytes"}:
            raise AttestationError(f"QA operator attestation artifact {index} is invalid")
        digest = item.get("sha256")
        relative = item.get("relative_path")
        size = item.get("size_bytes")
        if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
            raise AttestationError(f"QA operator attestation artifact {index} hash is invalid")
        if digest <= previous_hash or digest in observed_hashes:
            raise AttestationError("QA operator attestation artifact hashes must be unique and sorted")
        if (
            not isinstance(relative, str)
            or not relative
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or any(ord(char) < 32 for char in relative)
        ):
            raise AttestationError(f"QA operator attestation artifact {index} path is invalid")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0 or size > MAX_SINGLE_ARTIFACT_BYTES:
            raise AttestationError(f"QA operator attestation artifact {index} size is invalid")
        observed_hashes.add(digest)
        previous_hash = digest
    if observed_hashes != evidence_hashes:
        raise AttestationError("QA operator attestation artifact hashes do not exactly match summary evidence")

    signed_at = _utc(payload.get("signed_at"), "attestation signed_at")
    executed_at = _utc(executed_at_raw, "summary executed_at")
    reference_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if signed_at < executed_at:
        raise AttestationError("QA operator attestation predates cloud QA execution")
    if signed_at - executed_at > MAX_ATTESTATION_AGE:
        raise AttestationError("QA operator attestation was not signed within 24 hours of cloud QA")
    if signed_at > reference_time + FUTURE_SKEW:
        raise AttestationError("QA operator attestation timestamp is in the future")
    if reference_time - signed_at > MAX_ATTESTATION_AGE:
        raise AttestationError("QA operator attestation is older than 24 hours")
    return payload


def _private_key_from_sources(private_key_file: Path | None) -> Ed25519PrivateKey:
    environment_value = os.environ.get(PRIVATE_KEY_ENV)
    if environment_value and private_key_file is not None:
        raise AttestationError("configure exactly one operator private key source")
    if environment_value:
        return _load_private_key(environment_value.encode("utf-8"))
    if private_key_file is None:
        raise AttestationError(
            f"operator private key is required via {PRIVATE_KEY_ENV} or --private-key-file"
        )
    if private_key_file.is_symlink():
        raise AttestationError("operator private key file must not be a symlink")
    try:
        resolved = private_key_file.resolve(strict=True)
    except OSError:
        raise AttestationError("operator private key file cannot be resolved") from None
    repository = ROOT.resolve()
    ignored_keys = (ROOT / "artifacts" / "qa").resolve()
    if resolved.is_relative_to(repository) and not resolved.is_relative_to(ignored_keys):
        raise AttestationError("operator private key inside the repository must use ignored artifacts/qa")
    value = _read_regular_nofollow(
        resolved,
        "operator private key file",
        maximum_bytes=64 * 1024,
        require_owner_only=True,
    )
    return _load_private_key(value)


def _write_attestation(path: Path, attestation: Mapping[str, Any]) -> None:
    if path.name != ATTESTATION_NAME or path.is_symlink():
        raise AttestationError(f"attestation output must be a non-symlink {ATTESTATION_NAME}")
    raw = (json.dumps(attestation, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{ATTESTATION_NAME}.{secrets.token_hex(8)}.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise AttestationError("attestation output could not be written") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--private-key-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.summary.parent / ATTESTATION_NAME
    try:
        # The issuer refuses to sign a structurally invalid QA matrix before it
        # performs the stronger local-artifact checks.
        from scripts.agent_ops.check_qa_evidence import validate_evidence_bundle

        _, _, errors = validate_evidence_bundle(
            args.summary,
            attestation_mode="structural",
        )
        if errors:
            raise AttestationError("QA evidence is structurally invalid: " + "; ".join(errors))
        private_key = _private_key_from_sources(args.private_key_file)
        attestation = build_attestation(args.summary, args.artifact_root, private_key)
        if output.resolve(strict=False) != (args.summary.parent / ATTESTATION_NAME).resolve(strict=False):
            raise AttestationError("attestation output must be the summary sibling attestation.json")
        _write_attestation(output, attestation)
    except AttestationError as error:
        print(f"QA evidence attestation refused: {error}", file=sys.stderr)
        return 1
    print("QA evidence attestation written; no private key material was emitted.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
