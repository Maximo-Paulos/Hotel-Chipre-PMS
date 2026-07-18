#!/usr/bin/env python3
"""Validate the portable vault structure, context metadata, and local links."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "knowledge"
REQUIRED_CONTEXT_FIELDS = {"scope", "owner", "last_verified_commit", "canonical_sources", "graphify_minimum", "required_validation"}
REQUIRED_FILES = {
    "README.md", "00-control/TASK_ROUTER.md", "00-control/STATUS-TODAY.md", "00-control/SOURCE-OF-TRUTH.md",
    "00-control/DECISION-LOG.md", "00-control/tooling-patterns.md", "30-operations/cloud-regression-catalog.md",
    "40-delivery/release-gates.md", "40-delivery/qa-evidence-template.md", "40-delivery/task-handoff-template.md",
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    errors: list[str] = []
    for relative in sorted(REQUIRED_FILES):
        if not (KNOWLEDGE / relative).is_file():
            errors.append(f"missing vault file: knowledge/{relative}")
    for path in sorted((KNOWLEDGE / "10-context").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            errors.append(f"missing frontmatter: {path.relative_to(ROOT)}")
            continue
        try:
            frontmatter = text.split("---\n", 2)[1]
        except IndexError:
            errors.append(f"malformed frontmatter: {path.relative_to(ROOT)}")
            continue
        fields = {line.split(":", 1)[0].strip() for line in frontmatter.splitlines() if ":" in line}
        missing = REQUIRED_CONTEXT_FIELDS - fields
        if missing:
            errors.append(f"{path.relative_to(ROOT)} missing frontmatter fields: {', '.join(sorted(missing))}")
    for path in KNOWLEDGE.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / target).resolve().is_file():
                errors.append(f"broken local link in {path.relative_to(ROOT)}: {raw_target}")
    if errors:
        print("Knowledge validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Knowledge vault structure, frontmatter, and local links are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
