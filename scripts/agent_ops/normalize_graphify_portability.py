#!/usr/bin/env python3
"""Normalize Graphify artifacts that embed local worktree paths.

Graphify stores route literals as JSON node labels.  Its portable checker
rightly rejects machine paths such as /Users/... but currently also rejects
four API route labels beginning with /api. Prefixing them preserves the route
meaning while making the labels unambiguously human text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / ".graphify" / "graph.json"
FLOWS = ROOT / ".graphify" / "flows.json"
INSTRUCTION_DIR_NAMES = (
    "description-instructions",
    "label-instructions",
)
PATTERN = re.compile(r'("(?:label|message_summary)"\s*:\s*")([^"\\]*)(")')


def normalize_instruction_paths() -> int:
    """Replace this repository's absolute root in generated instructions only."""
    root_prefix = f"{ROOT.resolve()}/"
    resolved_root = ROOT.resolve()
    count = 0
    for name in INSTRUCTION_DIR_NAMES:
        directory = ROOT / ".graphify" / name
        if not directory.is_dir():
            continue
        resolved_directory = directory.resolve()
        if not resolved_directory.is_relative_to(resolved_root):
            continue
        for instruction in directory.rglob("*.md"):
            if not instruction.resolve().is_relative_to(resolved_directory):
                continue
            text = instruction.read_text(encoding="utf-8")
            normalized = text.replace(root_prefix, "")
            if normalized != text:
                instruction.write_text(normalized, encoding="utf-8")
                count += 1
    return count


def main() -> int:
    text = GRAPH.read_text(encoding="utf-8")
    count = 0

    def normalize_label(match: re.Match[str]) -> str:
        nonlocal count
        label = match.group(2)
        if "/api/" not in label:
            return match.group(0)
        count += 1
        return f"{match.group(1)}{label.replace('/api/', 'api/')}{match.group(3)}"

    normalized = PATTERN.sub(normalize_label, text)
    if count:
        GRAPH.write_text(normalized, encoding="utf-8")
    flow_normalized = False
    if FLOWS.is_file():
        flows = json.loads(FLOWS.read_text(encoding="utf-8"))
        if flows.get("graphPath") != ".graphify/graph.json":
            flows["graphPath"] = ".graphify/graph.json"
            FLOWS.write_text(json.dumps(flows, indent=2) + "\n", encoding="utf-8")
            flow_normalized = True
    instructions_normalized = normalize_instruction_paths()
    print(
        "Normalized "
        f"{count} API route label(s) and "
        f"{'one' if flow_normalized else 'zero'} flow artifact path(s) and "
        f"{instructions_normalized} generated instruction file(s) for portable Graphify artifacts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
