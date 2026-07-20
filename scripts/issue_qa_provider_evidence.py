#!/usr/bin/env python3
"""Issue a short-lived Render-consumable token from provider evidence.

Run this only after the preview manifest has passed the repository provider
validator. The Ed25519 private key is read only from the trusted producer's
secret environment. The resulting capability is written with mode 0600 and is
never printed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.bootstrap_cloud_qa import (  # noqa: E402
    QABootstrapError,
    build_provider_evidence_payload,
    canonical_provider_evidence_json,
    encode_provider_evidence_segment,
)


def _required(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise QABootstrapError(f"{name} is required")
    return value


def load_provider_evidence_private_key(value: str) -> Ed25519PrivateKey:
    """Load the producer-only signer from PEM or base64 raw seed bytes."""

    normalized = value.replace("\\n", "\n").strip()
    encoded = normalized.encode("utf-8")
    if not normalized.startswith("-----BEGIN"):
        try:
            raw_key = base64.b64decode(encoded, validate=True)
            return Ed25519PrivateKey.from_private_bytes(raw_key)
        except (TypeError, ValueError) as exc:
            raise QABootstrapError(
                "QA_PROVIDER_EVIDENCE_PRIVATE_KEY is not valid Ed25519 base64"
            ) from exc
    try:
        key = serialization.load_pem_private_key(encoded, password=None)
    except (TypeError, ValueError) as exc:
        raise QABootstrapError("QA_PROVIDER_EVIDENCE_PRIVATE_KEY is not valid PEM") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise QABootstrapError("QA_PROVIDER_EVIDENCE_PRIVATE_KEY must be an Ed25519 private key")
    return key


def issue_provider_evidence_token(
    manifest: Mapping[str, Any],
    *,
    private_key: str,
    now: int | None = None,
    ttl_seconds: int = 900,
    nonce: str | None = None,
) -> str:
    """Create a provider-bound capability using the producer-only signer."""

    issued_at = int(time.time()) if now is None else int(now)
    payload = build_provider_evidence_payload(
        manifest,
        now=issued_at,
        ttl_seconds=ttl_seconds,
        nonce=nonce,
    )
    encoded_payload = encode_provider_evidence_segment(
        canonical_provider_evidence_json(payload)
    )
    signature = load_provider_evidence_private_key(private_key).sign(
        encoded_payload.encode("ascii")
    )
    return f"{encoded_payload}.{encode_provider_evidence_segment(signature)}"


def _safe_output_path(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    repository = ROOT_DIR.resolve()
    ignored_artifacts = (ROOT_DIR / "artifacts" / "qa").resolve()
    try:
        inside_repository = resolved.is_relative_to(repository)
    except AttributeError:  # pragma: no cover - Python < 3.9 compatibility
        inside_repository = repository in resolved.parents
    if inside_repository and not resolved.is_relative_to(ignored_artifacts):
        raise QABootstrapError("evidence token output inside the repository must use artifacts/qa")
    return resolved


def write_private_token(path: Path, token: str) -> None:
    output = _safe_output_path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise QABootstrapError("evidence token output already exists; refusing to overwrite") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token)
            handle.write("\n")
    except Exception:
        output.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise QABootstrapError("provider manifest must contain a JSON object")
        ttl_raw = os.environ.get("QA_PROVIDER_EVIDENCE_TTL_SECONDS", "900")
        try:
            ttl_seconds = int(ttl_raw)
        except ValueError as exc:
            raise QABootstrapError("QA_PROVIDER_EVIDENCE_TTL_SECONDS must be an integer") from exc
        token = issue_provider_evidence_token(
            manifest,
            private_key=_required("QA_PROVIDER_EVIDENCE_PRIVATE_KEY"),
            ttl_seconds=ttl_seconds,
        )
        write_private_token(args.output, token)
    except (OSError, json.JSONDecodeError, QABootstrapError) as exc:
        message = str(exc) if isinstance(exc, QABootstrapError) else "manifest could not be read"
        print(f"Provider evidence token refused: {message}", file=sys.stderr)
        return 2
    print("Provider evidence token written to a restricted file", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
