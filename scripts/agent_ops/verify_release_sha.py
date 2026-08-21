#!/usr/bin/env python3
"""Validate that an observed release manifest is bound to one Git commit.

This validator is deliberately provider-neutral. A deploy adapter may write a
small JSON manifest from the provider's observed deployment state, then this
script proves that the release SHA, environment and artifact references agree.
It does not deploy, mutate cloud resources, or read secrets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SHA_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
REPOSITORY_RE = re.compile(r"[^/\s]+/[^/\s]+\Z")
ENVIRONMENTS = {"build", "staging", "production"}
IMMUTABLE_ARTIFACT_RE = re.compile(
    r"[^/@\s:]+(?:/[^/@\s:]+)*:(?P<tag>[0-9a-f]{40}|[0-9a-f]{64})"
    r"(?:@sha256:[0-9a-f]{64})?\Z"
)


def _non_empty(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def validate_manifest(
    manifest: object,
    *,
    expected_sha: str | None = None,
    expected_repository: str | None = None,
    expected_environment: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    repository = _non_empty(manifest.get("repository"), "repository", errors)
    if repository and not REPOSITORY_RE.fullmatch(repository):
        errors.append("repository must use the owner/repository form")
    if expected_repository and repository != expected_repository:
        errors.append("repository does not match expected repository")

    environment = _non_empty(manifest.get("environment"), "environment", errors)
    if environment and environment not in ENVIRONMENTS:
        errors.append("environment must be build, staging, or production")
    if expected_environment and environment != expected_environment:
        errors.append("environment does not match expected environment")

    code_sha = _non_empty(manifest.get("code_sha"), "code_sha", errors)
    if code_sha and not SHA_RE.fullmatch(code_sha):
        errors.append("code_sha must be a full 40- or 64-character lowercase Git SHA")
    if expected_sha and code_sha != expected_sha:
        errors.append("code_sha does not match expected SHA")

    artifact_refs = manifest.get("artifact_refs")
    if not isinstance(artifact_refs, dict) or not artifact_refs:
        errors.append("artifact_refs must be a non-empty object")
    else:
        for name, reference in sorted(artifact_refs.items()):
            if not isinstance(name, str) or not name.strip():
                errors.append("artifact_refs names must be non-empty strings")
                continue
            if not isinstance(reference, str) or not reference.strip():
                errors.append(f"artifact_refs.{name} must be a non-empty string")
                continue
            normalized = reference.strip()
            if any(character.isspace() for character in normalized):
                errors.append(f"artifact_refs.{name} must not contain whitespace")
                continue
            match = IMMUTABLE_ARTIFACT_RE.fullmatch(normalized)
            if not match:
                errors.append(
                    f"artifact_refs.{name} must use an immutable SHA tag and optional sha256 digest"
                )
            elif code_sha and match.group("tag") != code_sha:
                errors.append(f"artifact_refs.{name} must include the exact code_sha tag")

    migration_revision = manifest.get("migration_revision")
    if migration_revision is not None:
        _non_empty(migration_revision, "migration_revision", errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-repository")
    parser.add_argument("--expected-environment", choices=sorted(ENVIRONMENTS))
    args = parser.parse_args()

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"Release manifest rejected: {error}")
        return 1

    errors = validate_manifest(
        manifest,
        expected_sha=args.expected_sha,
        expected_repository=args.expected_repository,
        expected_environment=args.expected_environment,
    )
    if errors:
        print("Release manifest rejected:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Release manifest is bound to {args.expected_sha}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
