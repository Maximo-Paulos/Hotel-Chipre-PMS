#!/usr/bin/env python3
"""Refuse provider drift between human-surface probes and final evidence."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


MAX_MANIFEST_BYTES = 2 * 1024 * 1024


class ManifestContinuityError(RuntimeError):
    """Safe error that never prints provider values."""


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ManifestContinuityError(f"{label} generated_at is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ManifestContinuityError(f"{label} generated_at is invalid") from None
    if parsed.tzinfo is None:
        raise ManifestContinuityError(f"{label} generated_at must include a timezone")
    return parsed


def _provider_subject(manifest: dict[str, Any]) -> dict[str, Any]:
    subject = dict(manifest)
    subject.pop("generated_at", None)
    return subject


def verify_manifest_continuity(
    probed_manifest: dict[str, Any],
    final_manifest: dict[str, Any],
) -> None:
    """Allow only a newer observation timestamp between provider snapshots."""

    probed_at = _timestamp(probed_manifest.get("generated_at"), "probed manifest")
    final_at = _timestamp(final_manifest.get("generated_at"), "final manifest")
    if final_at < probed_at:
        raise ManifestContinuityError("final manifest predates the probed manifest")
    if _provider_subject(probed_manifest) != _provider_subject(final_manifest):
        raise ManifestContinuityError(
            "provider identity, surface, deployment, database, lease, or configuration drifted "
            "after health/CORS/bundle probes"
        )


def _load_manifest(path: Path, label: str) -> dict[str, Any]:
    try:
        stat = path.lstat()
    except OSError:
        raise ManifestContinuityError(f"{label} cannot be read") from None
    if path.is_symlink() or not path.is_file() or stat.st_size > MAX_MANIFEST_BYTES:
        raise ManifestContinuityError(f"{label} is not a safe regular JSON file")
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ManifestContinuityError(f"{label} is not valid JSON") from None
    if not isinstance(value, dict):
        raise ManifestContinuityError(f"{label} must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("probed_manifest", type=Path)
    parser.add_argument("final_manifest", type=Path)
    args = parser.parse_args()
    try:
        probed = _load_manifest(args.probed_manifest, "probed manifest")
        final = _load_manifest(args.final_manifest, "final manifest")
        verify_manifest_continuity(probed, final)
    except ManifestContinuityError as error:
        parser.exit(2, f"preview manifest continuity failed: {error}{os.linesep}")
    print("Preview provider subject remained byte-equivalent after surface probes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
