#!/usr/bin/env python3
"""Validate the portable vault structure, context metadata, and local links."""

from __future__ import annotations

import re
import json
import shlex
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "knowledge"
REQUIRED_CONTEXT_FIELDS = {"scope", "owner", "last_verified_commit", "canonical_sources", "graphify_minimum", "required_validation"}
REQUIRED_FILES = {
    "README.md", "00-control/TASK_ROUTER.md", "00-control/STATUS-TODAY.md", "00-control/SOURCE-OF-TRUTH.md",
    "00-control/DECISION-LOG.md", "00-control/tooling-patterns.md", "30-operations/cloud-regression-catalog.md",
    "40-delivery/release-gates.md", "40-delivery/qa-evidence-template.md", "40-delivery/task-handoff-template.md",
}
REQUIRED_OBSIDIAN_CONFIG = {"app.json", "appearance.json", "core-plugins.json"}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def inline_list(value: str) -> list[str]:
    """Parse the simple unquoted frontmatter lists used by context packs."""
    value = value.strip()
    if not value.startswith("[") or not value.endswith("]"):
        return []
    return [item.strip() for item in value[1:-1].split(",") if item.strip()]


def graphify_command_error(command: str) -> str | None:
    """Reject context commands that the installed Graphify CLI cannot route."""
    try:
        tokens = shlex.split(command)
    except ValueError as error:
        return f"invalid graphify_minimum quoting: {error}"
    if len(tokens) < 2 or tokens[0] != "graphify":
        return "graphify_minimum must start with graphify"
    subcommand = tokens[1]
    if subcommand in {"minimal-context", "affected-flows"} and "--files" not in tokens:
        return f"graphify {subcommand} must pass a concrete --files target"
    if subcommand == "summary" and tokens[2:] != [".graphify/graph.json"]:
        return "graphify summary must target .graphify/graph.json"
    if subcommand == "check-update" and tokens[2:] != ["."]:
        return "graphify check-update must target the repository root"
    return None


def main() -> int:
    errors: list[str] = []
    context_meta: dict[str, dict[str, str]] = {}
    for relative in sorted(REQUIRED_FILES):
        if not (KNOWLEDGE / relative).is_file():
            errors.append(f"missing vault file: knowledge/{relative}")
    obsidian_dir = KNOWLEDGE / ".obsidian"
    for filename in sorted(REQUIRED_OBSIDIAN_CONFIG):
        path = obsidian_dir / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"invalid portable Obsidian config knowledge/.obsidian/{filename}: {error}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"portable Obsidian config knowledge/.obsidian/{filename} must be an object")
    # A repository-root `.obsidian/` can be a user's local workspace for opening
    # this repository. It is intentionally ignored and must not invalidate the
    # portable vault. Only `knowledge/.obsidian/` is part of the checked-in
    # memory contract above.
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
        values = {
            key.strip(): value.strip()
            for line in frontmatter.splitlines()
            if ":" in line
            for key, value in [line.split(":", 1)]
        }
        missing = REQUIRED_CONTEXT_FIELDS - set(values)
        if missing:
            errors.append(f"{path.relative_to(ROOT)} missing frontmatter fields: {', '.join(sorted(missing))}")
            continue
        for source in inline_list(values["canonical_sources"]):
            if not (ROOT / source).exists():
                errors.append(f"{path.relative_to(ROOT)} missing canonical source: {source}")
        graph_error = graphify_command_error(values["graphify_minimum"])
        if graph_error:
            errors.append(f"{path.relative_to(ROOT)} {graph_error}")
        context_meta[str(path.relative_to(ROOT))] = values
    for path in KNOWLEDGE.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / target).resolve().is_file():
                errors.append(f"broken local link in {path.relative_to(ROOT)}: {raw_target}")
    for role_path in sorted((ROOT / "agent-ops" / "roles").glob("*.json")):
        try:
            role = json.loads(role_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            errors.append(f"invalid role JSON {role_path.relative_to(ROOT)}: {error}")
            continue
        pack = role.get("context_pack", "")
        metadata = context_meta.get(pack)
        if metadata is None:
            errors.append(f"{role.get('name', role_path.stem)} points to invalid context pack: {pack}")
            continue
        consumers = {metadata.get("owner", ""), *inline_list(metadata.get("consumers", "[]"))}
        if role.get("name") not in consumers:
            errors.append(
                f"{role.get('name', role_path.stem)} is not declared as owner/consumer of {pack}"
            )
    if errors:
        print("Knowledge validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Knowledge vault structure, frontmatter, and local links are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
