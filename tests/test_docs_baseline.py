from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    REPO_ROOT / "docs" / "product-definition.md",
    REPO_ROOT / "docs" / "architecture-audit.md",
    REPO_ROOT / "docs" / "roadmap.md",
    REPO_ROOT / "docs" / "multi-agent-workflow.md",
    REPO_ROOT / "docs" / "security-baseline.md",
    REPO_ROOT / "docs" / "tooling-stack.md",
    REPO_ROOT / "app" / "AGENTS.md",
    REPO_ROOT / "frontend" / "AGENTS.md",
    REPO_ROOT / "tests" / "AGENTS.md",
]

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
IGNORED_TARGET_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")


def test_docs_baseline_files_exist() -> None:
    missing = [path.relative_to(REPO_ROOT).as_posix() for path in REQUIRED_FILES if not path.exists()]
    assert not missing, f"Missing required docs baseline files: {missing}"


def test_docs_baseline_local_links_exist() -> None:
    checked = []
    broken = []

    for source in REQUIRED_FILES:
        text = source.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK_RE.findall(text):
            cleaned = target.strip()
            if not cleaned or cleaned.startswith(IGNORED_TARGET_PREFIXES):
                continue
            link_target = cleaned.split("#", 1)[0].split("?", 1)[0]
            if not link_target:
                continue

            resolved = (source.parent / link_target).resolve()
            if REPO_ROOT not in resolved.parents and resolved != REPO_ROOT:
                broken.append(f"{source.relative_to(REPO_ROOT).as_posix()} -> {target} (escapes repo)")
                continue
            checked.append((source, target, resolved))
            if not resolved.exists():
                broken.append(f"{source.relative_to(REPO_ROOT).as_posix()} -> {target}")

    assert not broken, "Broken repo-relative markdown links:\n" + "\n".join(broken)
    assert checked, "No repo-relative markdown links were found to validate."
