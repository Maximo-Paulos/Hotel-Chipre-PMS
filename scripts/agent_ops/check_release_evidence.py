#!/usr/bin/env python3
"""Ensure cloud evidence is complete and no functional code changed after it."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FUNCTIONAL_PREFIXES = ("app/", "frontend/src/", "alembic/")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path, help="qa/evidence/<task>/summary.json")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    checker = ROOT / "scripts" / "agent_ops" / "check_qa_evidence.py"
    basic = subprocess.run([sys.executable, str(checker), str(args.evidence)], cwd=ROOT, text=True)
    if basic.returncode:
        return basic.returncode
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    sha = evidence["code_sha"]
    try:
        git("merge-base", "--is-ancestor", sha, args.head)
    except subprocess.CalledProcessError:
        print(f"Evidence SHA {sha} is not an ancestor of {args.head}")
        return 1
    changed = git("diff", "--name-only", f"{sha}..{args.head}").splitlines()
    functional = [path for path in changed if path.startswith(FUNCTIONAL_PREFIXES)]
    if functional:
        print("Functional files changed after the latest QA evidence:")
        print("\n".join(f"- {path}" for path in functional))
        return 1
    print(f"Release evidence remains valid through {args.head}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
