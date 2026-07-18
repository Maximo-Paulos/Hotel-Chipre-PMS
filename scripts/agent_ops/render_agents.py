#!/usr/bin/env python3
"""Render shared agent definitions for Claude Code and Codex."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROLE_DIR = ROOT / "agent-ops" / "roles"
ROLE_SKILL_MAP = ROOT / "agent-ops" / "role-skill-map.json"
CLAUDE_DIR = ROOT / ".claude" / "agents"
CODEX_DIR = ROOT / ".codex" / "agents"


def _roles() -> list[dict[str, str]]:
    roles = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(ROLE_DIR.glob("*.json"))]
    names = [role["name"] for role in roles]
    if len(names) != len(set(names)):
        raise ValueError("Agent names must be unique")
    skill_map = json.loads(ROLE_SKILL_MAP.read_text(encoding="utf-8"))
    if set(names) != set(skill_map):
        raise ValueError("Role skill map must cover exactly the canonical roles")
    for role in roles:
        role["skills"] = skill_map[role["name"]]
    return roles


def _instructions(role: dict[str, str]) -> str:
    return f"""You are the {role['title']} for Hotel Chipre PMS.

Read `{role['context_pack']}` before exploring raw code. If Graphify is fresh, use its smallest relevant command before broad searching.

Scope: {role['focus']}

Validation: {role['validation']}

Required skills: {", ".join(role['skills'])}.

Never expose secrets, session data, credentials, PII, webhook secrets, or payment data. Respect the existing working tree and do not revert other agents' changes. Do not claim a task is complete until the applicable tests, documentation updates, Graphify freshness, and release evidence are verified. For cloud work, the required QA evidence must come from isolated preview data and QA personas only."""


def _claude(role: dict[str, str]) -> str:
    skills = "\n".join(f"  - {skill}" for skill in role["skills"])
    return f'''---
name: {role['name']}
description: {role['description']}
tools: Read, Grep, Glob, Edit, Write, Bash
model: inherit
skills:
{skills}
---

{_instructions(role)}
'''


def _toml_string(value: str) -> str:
    return value.replace("'''", "\\\\'\\\\'\\\\'")


def _codex(role: dict[str, str]) -> str:
    return "\n".join(
        [
            f'name = "{role["name"]}"',
            f'description = "{role["description"]}"',
            "developer_instructions = '''",
            _toml_string(_instructions(role)),
            "'''",
            "",
        ]
    )


def _expected() -> dict[Path, str]:
    expected: dict[Path, str] = {}
    for role in _roles():
        expected[CLAUDE_DIR / f"{role['name']}.md"] = _claude(role)
        expected[CODEX_DIR / f"{role['name']}.toml"] = _codex(role)
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when generated files drift")
    parser.add_argument("--write", action="store_true", help="write generated files")
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")

    expected = _expected()
    drift = [path for path, content in expected.items() if not path.is_file() or path.read_text(encoding="utf-8") != content]
    if args.check:
        if drift:
            print("Agent configuration drift:")
            print("\n".join(str(path.relative_to(ROOT)) for path in drift))
            return 1
        return 0

    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"Rendered {len(expected)} agent configuration files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
