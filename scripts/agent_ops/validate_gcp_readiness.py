#!/usr/bin/env python3
"""Static, non-mutating check for the future Google Cloud deployment shape."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    dockerfile = root / "Dockerfile.backend"
    render = root / "render.yaml"
    env_example = root / ".env.example"
    docs = root / "docs" / "runbooks" / "gcp-migration.md"
    for path in (dockerfile, render, env_example, docs):
        if not path.is_file():
            errors.append(f"missing required readiness file: {path.relative_to(root)}")
    if errors:
        return errors
    docker_text = dockerfile.read_text(encoding="utf-8")
    if not re.search(r"^USER appuser\s*$", docker_text, re.MULTILINE):
        errors.append("Dockerfile.backend must run as non-root appuser")
    if "timeout-graceful-shutdown" not in docker_text:
        errors.append("Dockerfile.backend must configure graceful shutdown")
    render_text = render.read_text(encoding="utf-8")
    if "preDeployCommand:" not in render_text or "alembic upgrade head" not in render_text:
        errors.append("render.yaml must keep Alembic as the pre-deploy schema job")
    if "maxInstances:" not in render_text or "DB_POOL_SIZE" not in env_example.read_text(encoding="utf-8"):
        errors.append("connection-budget inputs must be explicit before Cloud Run autoscaling")
    env_text = env_example.read_text(encoding="utf-8")
    for name in ("OBJECT_STORAGE_GCS_BUCKET", "OBJECT_STORAGE_GCS_PROJECT", "REDIS_NAMESPACE"):
        if f"{name}=" not in env_text:
            errors.append(f".env.example must document {name}")
    docs_text = docs.read_text(encoding="utf-8")
    for marker in ("Cloud Run", "Cloud SQL", "Secret Manager", "no provision"):
        if marker.lower() not in docs_text.lower():
            errors.append(f"gcp-migration.md must document {marker}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    errors = validate(args.root.resolve())
    result = {"status": "ready-for-provider-validation" if not errors else "blocked", "errors": errors}
    print(json.dumps(result, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
