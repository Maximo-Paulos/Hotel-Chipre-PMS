#!/usr/bin/env python3
"""Run deterministic local checks for the agent/vault operating system."""

from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(*args: str) -> int:
    print("+", " ".join(args))
    return subprocess.run(args, cwd=ROOT).returncode


def validate_json(path: str) -> int:
    print("+ JSON", path)
    try:
        json.loads((ROOT / path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Invalid JSON {path}: {error}")
        return 1
    return 0


def main() -> int:
    commands = [
        (sys.executable, "scripts/agent_ops/render_agents.py", "--check"),
        (sys.executable, "scripts/agent_ops/sync_skills.py", "--check"),
        (sys.executable, "scripts/agent_ops/check_knowledge.py"),
    ]
    failed = any(run(*command) for command in commands)
    failed = validate_json("qa/regression-catalog.json") or failed
    failed = validate_json("qa/preview-manifest.example.json") or failed
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
