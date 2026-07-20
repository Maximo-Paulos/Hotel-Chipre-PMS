"""Security regression tests for local QA operator attestations."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.agent_ops.qa_evidence_attestation import (
    SIGNING_DOMAIN,
    AttestationError,
    _private_key_from_sources,
    build_attestation,
    public_key_pem,
    verify_attestation,
)


def tagged(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def write_fixture(tmp_path: Path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    task_dir = tmp_path / "operator-attestation"
    task_dir.mkdir()
    manifest_raw = b'{"provider":"verified"}\n'
    (task_dir / "validated-preview-manifest.json").write_bytes(manifest_raw)
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    evidence_bytes = b"real-browser-screenshot-bytes"
    (artifact_root / "owner-dashboard.png").write_bytes(evidence_bytes)
    summary = {
        "task_id": task_dir.name,
        "code_sha": "a" * 40,
        "provider_evidence": {
            "manifest_file": "validated-preview-manifest.json",
            "manifest_sha256": tagged(manifest_raw),
            "workflow_run_id": 123,
            "artifact_id": 456,
            "repository": "owner/repository",
            "git_branch": "codex/qa-target",
        },
        "executed_at": (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        "results": [
            {
                "case_id": "dashboard",
                "persona": "owner",
                "evidence": tagged(evidence_bytes),
                "code_sha": "a" * 40,
            }
        ],
    }
    summary_path = task_dir / "summary.json"
    summary_path.write_bytes(json.dumps(summary, sort_keys=True).encode())
    private_key = Ed25519PrivateKey.generate()
    attestation = build_attestation(
        summary_path,
        artifact_root,
        private_key,
        signed_at=now,
    )
    attestation_path = task_dir / "attestation.json"
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    return summary_path, artifact_root, private_key, attestation, now


def test_operator_attestation_binds_exact_bytes_and_real_local_artifacts(tmp_path: Path) -> None:
    summary_path, _, private_key, attestation, now = write_fixture(tmp_path)

    payload = verify_attestation(
        summary_path,
        public_key_pem(private_key.public_key()),
        now=now,
    )

    assert payload == attestation["payload"]
    assert payload["summary_sha256"] == tagged(summary_path.read_bytes())
    assert payload["manifest_sha256"] == tagged(
        (summary_path.parent / "validated-preview-manifest.json").read_bytes()
    )
    assert payload["artifacts"][0]["relative_path"] == "owner-dashboard.png"


def test_issuer_refuses_evidence_hash_without_a_real_local_artifact(tmp_path: Path) -> None:
    summary_path, artifact_root, private_key, _, now = write_fixture(tmp_path)
    (artifact_root / "owner-dashboard.png").unlink()

    with pytest.raises(AttestationError, match="no real local artifact"):
        build_attestation(summary_path, artifact_root, private_key, signed_at=now)


def test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(tmp_path: Path) -> None:
    summary_path, artifact_root, private_key, _, now = write_fixture(tmp_path)
    real = artifact_root / "owner-dashboard.png"
    outside = tmp_path / "outside.png"
    real.replace(outside)
    real.symlink_to(outside)

    with pytest.raises(AttestationError, match="must not contain symlinks"):
        build_attestation(summary_path, artifact_root, private_key, signed_at=now)


def test_unsigned_or_fabricated_attestation_is_rejected(tmp_path: Path) -> None:
    summary_path, _, private_key, _, now = write_fixture(tmp_path)
    (summary_path.parent / "attestation.json").write_text(
        json.dumps({"schema_version": 1, "payload": {}}), encoding="utf-8"
    )

    with pytest.raises(AttestationError, match="unexpected or missing"):
        verify_attestation(
            summary_path,
            public_key_pem(private_key.public_key()),
            now=now,
        )


def test_altered_signature_is_rejected(tmp_path: Path) -> None:
    summary_path, _, private_key, attestation, now = write_fixture(tmp_path)
    signature = attestation["signature"]["value"]
    attestation["signature"]["value"] = ("A" if signature[0] != "A" else "B") + signature[1:]
    (summary_path.parent / "attestation.json").write_text(
        json.dumps(attestation), encoding="utf-8"
    )

    with pytest.raises(AttestationError, match="signature is invalid"):
        verify_attestation(
            summary_path,
            public_key_pem(private_key.public_key()),
            now=now,
        )


def test_signed_attestation_missing_a_summary_hash_is_rejected(tmp_path: Path) -> None:
    summary_path, _, private_key, attestation, now = write_fixture(tmp_path)
    payload = attestation["payload"]
    payload["artifacts"] = []
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = private_key.sign(SIGNING_DOMAIN + canonical)
    attestation["signature"]["value"] = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    (summary_path.parent / "attestation.json").write_text(
        json.dumps(attestation), encoding="utf-8"
    )

    with pytest.raises(AttestationError, match="non-empty array|exactly match"):
        verify_attestation(
            summary_path,
            public_key_pem(private_key.public_key()),
            now=now,
        )


def test_summary_byte_change_after_signing_is_rejected(tmp_path: Path) -> None:
    summary_path, _, private_key, _, now = write_fixture(tmp_path)
    summary_path.write_bytes(summary_path.read_bytes() + b"\n")

    with pytest.raises(AttestationError, match="summary_sha256"):
        verify_attestation(
            summary_path,
            public_key_pem(private_key.public_key()),
            now=now,
        )


def test_manifest_byte_change_after_signing_is_rejected(tmp_path: Path) -> None:
    summary_path, _, private_key, _, now = write_fixture(tmp_path)
    manifest_path = summary_path.parent / "validated-preview-manifest.json"
    manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")

    with pytest.raises(AttestationError, match="manifest hash|manifest_sha256"):
        verify_attestation(
            summary_path,
            public_key_pem(private_key.public_key()),
            now=now,
        )


def test_untrusted_public_key_cannot_replace_fingerprint_or_signature(tmp_path: Path) -> None:
    summary_path, _, _, _, now = write_fixture(tmp_path)
    attacker = Ed25519PrivateKey.generate()

    with pytest.raises(AttestationError, match="fingerprint"):
        verify_attestation(
            summary_path,
            public_key_pem(attacker.public_key()),
            now=now,
        )


def test_attestation_older_than_24_hours_is_rejected(tmp_path: Path) -> None:
    summary_path, artifact_root, private_key, _, now = write_fixture(tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    signed_at = now - timedelta(hours=25)
    summary["executed_at"] = (signed_at - timedelta(minutes=1)).isoformat().replace(
        "+00:00", "Z"
    )
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")
    attestation = build_attestation(
        summary_path,
        artifact_root,
        private_key,
        signed_at=signed_at,
    )
    (summary_path.parent / "attestation.json").write_text(
        json.dumps(attestation), encoding="utf-8"
    )

    with pytest.raises(AttestationError, match="older than 24 hours"):
        verify_attestation(
            summary_path,
            public_key_pem(private_key.public_key()),
            now=now,
        )


def test_issuer_cannot_refresh_qa_executed_more_than_24_hours_ago(tmp_path: Path) -> None:
    summary_path, artifact_root, private_key, _, now = write_fixture(tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["executed_at"] = (now - timedelta(hours=24, seconds=1)).isoformat().replace(
        "+00:00", "Z"
    )
    summary_path.write_text(json.dumps(summary, sort_keys=True), encoding="utf-8")

    with pytest.raises(AttestationError, match="within 24 hours"):
        build_attestation(summary_path, artifact_root, private_key, signed_at=now)


def test_private_key_file_must_be_owner_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("QA_EVIDENCE_OPERATOR_PRIVATE_KEY", raising=False)
    key_path = tmp_path / "operator-private-key.pem"
    private_key = Ed25519PrivateKey.generate()
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o644)

    with pytest.raises(AttestationError, match="permissions must be owner-only"):
        _private_key_from_sources(key_path)

    key_path.chmod(0o600)
    loaded = _private_key_from_sources(key_path)
    assert public_key_pem(loaded.public_key()) == public_key_pem(private_key.public_key())
