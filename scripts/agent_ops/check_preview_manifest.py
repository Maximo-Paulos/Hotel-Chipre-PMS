#!/usr/bin/env python3
"""Reject preview manifests that can accidentally test a shared deployment."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse


PRODUCTION_HOSTS = {"app.hotels-pms.com", "hotels-pms.com", "api.hotels-pms.com"}
REQUIRED = {
    "schema_version", "task_id", "code_sha", "app_url", "api_url", "health_url", "supabase_branch_ref",
    "database_isolated", "frontend_vite_api_url", "cors_frontend_url", "qa_secrets_isolated",
}


def valid_https(value: object) -> bool:
    parsed = urlparse(str(value))
    return parsed.scheme == "https" and bool(parsed.hostname) and parsed.hostname not in PRODUCTION_HOSTS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-sha")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Invalid preview manifest: {error}")
        return 1
    errors: list[str] = []
    missing = REQUIRED - set(manifest)
    if missing:
        errors.append("missing: " + ", ".join(sorted(missing)))
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    sha = str(manifest.get("code_sha", ""))
    if not re.fullmatch(r"[0-9a-f]{7,64}", sha):
        errors.append("code_sha must be a Git SHA")
    if args.expected_sha and sha != args.expected_sha:
        errors.append("code_sha does not match expected SHA")
    for field in ("app_url", "api_url", "health_url", "cors_frontend_url"):
        if not valid_https(manifest.get(field)):
            errors.append(f"{field} must be a non-production HTTPS preview URL")
    if manifest.get("frontend_vite_api_url") != manifest.get("api_url"):
        errors.append("frontend_vite_api_url must exactly equal api_url")
    if manifest.get("cors_frontend_url") != manifest.get("app_url"):
        errors.append("cors_frontend_url must exactly equal app_url")
    if manifest.get("database_isolated") is not True:
        errors.append("database_isolated must be true")
    if manifest.get("qa_secrets_isolated") is not True:
        errors.append("qa_secrets_isolated must be true")
    if not str(manifest.get("supabase_branch_ref", "")).strip():
        errors.append("supabase_branch_ref is required")
    if errors:
        print("Preview manifest rejected:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Preview manifest is isolated and internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
