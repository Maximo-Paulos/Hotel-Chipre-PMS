#!/usr/bin/env python3
"""Emit a short, read-only context reminder for Claude/Codex hooks."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def graphify_state() -> str:
    graphify = shutil.which("graphify")
    if not graphify:
        return "unknown (graphify no está en PATH)"
    result = subprocess.run([graphify, "check-update", "."], cwd=ROOT, capture_output=True, text=True, check=False, timeout=10)
    output = (result.stdout or result.stderr).strip().replace("\n", " ")
    if result.returncode:
        return f"stale/unknown: {output[:180]}"
    if "Pending semantic updates" in output:
        return "AST current; descriptions/labels intentionally pending"
    return "fresh"


def main() -> None:
    router = "knowledge/00-control/TASK_ROUTER.md"
    state = graphify_state()
    context = (
        f"context: consulta {router}; abre sólo el pack del rol. "
        f"Graphify: {state}. Para cambios de código, actualiza sólo al final con "
        "`graphify update . --scope all --no-description --no-label`."
    )
    print(json.dumps({"hookSpecificOutput": {"additionalContext": context}}))


if __name__ == "__main__":
    main()
