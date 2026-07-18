#!/usr/bin/env python3
"""Work around Graphify portable-check treating API route labels as local paths.

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
PATTERN = re.compile(r'("label"\s*:\s*")([^"\\]*)(")')


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
    print(
        "Normalized "
        f"{count} API route label(s) and "
        f"{'one' if flow_normalized else 'zero'} flow artifact path(s) for portable Graphify artifacts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
