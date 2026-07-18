#!/usr/bin/env python3
"""Validate redacted cloud QA evidence against the regression catalog."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "qa" / "regression-catalog.json"
REQUIRED_RESULT_FIELDS = {"persona", "case_id", "status", "preview_url", "precondition", "human_action", "expected", "observed", "evidence", "code_sha"}
PRODUCTION_HOSTS = {"app.hotels-pms.com", "hotels-pms.com", "api.hotels-pms.com"}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("--expected-sha", help="require evidence for this exact Git SHA")
    args = parser.parse_args()
    errors: list[str] = []
    try:
        summary = json.loads(args.summary.read_text(encoding="utf-8"))
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Invalid QA evidence input: {error}")
        return 1

    for field in ("task_id", "code_sha", "preview", "executed_at", "results", "external_exclusions", "blocked"):
        if field not in summary:
            fail(errors, f"missing top-level field: {field}")
    code_sha = str(summary.get("code_sha", ""))
    if not re.fullmatch(r"[0-9a-f]{7,64}", code_sha):
        fail(errors, "code_sha must be a Git SHA")
    if args.expected_sha and code_sha != args.expected_sha:
        fail(errors, f"evidence SHA {code_sha} does not match expected {args.expected_sha}")
    try:
        datetime.fromisoformat(str(summary.get("executed_at", "")).replace("Z", "+00:00"))
    except ValueError:
        fail(errors, "executed_at must be ISO-8601")

    preview = summary.get("preview", {})
    for key in ("app_url", "api_url"):
        url = str(preview.get(key, ""))
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            fail(errors, f"preview.{key} must be an HTTPS URL")
        elif parsed.hostname in PRODUCTION_HOSTS:
            fail(errors, f"preview.{key} must not point at shared production host {parsed.hostname}")

    expected_pairs = {(case["id"], persona) for case in catalog["cases"] for persona in case["personas"]}
    observed_pairs: set[tuple[str, str]] = set()
    for index, result in enumerate(summary.get("results", [])):
        missing = REQUIRED_RESULT_FIELDS - set(result)
        if missing:
            fail(errors, f"result {index} missing: {', '.join(sorted(missing))}")
            continue
        pair = (result["case_id"], result["persona"])
        observed_pairs.add(pair)
        if result["status"] != "passed":
            fail(errors, f"{pair[0]} for {pair[1]} is not passed: {result['status']}")
        if result["code_sha"] != code_sha:
            fail(errors, f"{pair[0]} has mismatched result SHA")
        if not str(result["evidence"]).strip():
            fail(errors, f"{pair[0]} lacks non-sensitive evidence reference")
    missing_pairs = expected_pairs - observed_pairs
    if missing_pairs:
        fail(errors, "missing catalog coverage: " + ", ".join(f"{case}/{persona}" for case, persona in sorted(missing_pairs)))

    exclusions = set(summary.get("external_exclusions", []))
    mandated = set(catalog["policy"]["external_exclusions"])
    if not mandated.issubset(exclusions):
        fail(errors, "external exclusions are incomplete")
    if summary.get("blocked") is not False:
        fail(errors, "blocked must be false for passing QA evidence")

    if errors:
        print("QA evidence rejected:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"QA evidence valid for {len(expected_pairs)} persona/case rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
