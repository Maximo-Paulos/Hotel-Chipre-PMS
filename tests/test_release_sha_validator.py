from __future__ import annotations

from scripts.agent_ops.verify_release_sha import validate_manifest


SHA = "a" * 40


def manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "repository": "owner/repository",
        "environment": "build",
        "code_sha": SHA,
        "artifact_refs": {
            "backend": f"ghcr.io/owner/repository-backend:{SHA}",
            "frontend": f"ghcr.io/owner/repository-frontend:{SHA}@sha256:{'b' * 64}",
        },
        "migration_revision": "20260821_release",
    }


def test_release_manifest_accepts_exact_sha_bound_artifacts() -> None:
    assert validate_manifest(
        manifest(),
        expected_sha=SHA,
        expected_repository="owner/repository",
        expected_environment="build",
    ) == []


def test_release_manifest_rejects_mismatched_sha_and_mutable_tag() -> None:
    value = manifest()
    value["code_sha"] = "c" * 40
    value["artifact_refs"] = {"backend": "ghcr.io/owner/repository-backend:latest"}

    errors = validate_manifest(value, expected_sha=SHA)

    assert "code_sha does not match expected SHA" in errors
    assert (
        "artifact_refs.backend must use an immutable SHA tag and optional sha256 digest"
        in errors
    )


def test_release_manifest_rejects_wrong_environment_and_digest() -> None:
    value = manifest()
    value["environment"] = "production"
    value["artifact_refs"] = {"backend": f"ghcr.io/owner/repository-backend:{SHA}@sha256:not-a-digest"}

    errors = validate_manifest(value, expected_environment="staging")

    assert "environment does not match expected environment" in errors
    assert (
        "artifact_refs.backend must use an immutable SHA tag and optional sha256 digest"
        in errors
    )
