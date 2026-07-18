#!/usr/bin/env python3
"""Synchronize Claude's skill discovery directory from the canonical library."""

from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".agents" / "skills"
TARGET = ROOT / ".claude" / "skills"


def _skill_dirs(root: Path) -> dict[str, Path]:
    return {path.name: path for path in root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()}


def _compare_dirs(source: Path, target: Path) -> list[str]:
    drift: list[str] = []
    source_files = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
    target_files = {path.relative_to(target) for path in target.rglob("*") if path.is_file()} if target.exists() else set()
    for relative in sorted(source_files | target_files):
        left, right = source / relative, target / relative
        if not left.is_file() or not right.is_file() or not filecmp.cmp(left, right, shallow=False):
            drift.append(str(relative))
    return drift


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when Claude's skill mirror drifts")
    parser.add_argument("--write", action="store_true", help="replace Claude's skill mirror")
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")

    if not SOURCE.is_dir():
        raise FileNotFoundError(f"Canonical skill directory does not exist: {SOURCE}")
    if args.check:
        drift = _compare_dirs(SOURCE, TARGET)
        if drift:
            print("Claude skill mirror drift:")
            print("\n".join(f".claude/skills/{path}" for path in drift))
            return 1
        return 0

    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    print(f"Synchronized {len(_skill_dirs(SOURCE))} skills to .claude/skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
