"""Compatibility entrypoint for the guarded local E2E database seed.

The former script dropped every table reachable through ``DATABASE_URL`` and
imported a removed application seed function. This entrypoint now delegates
to the E2E workflow, which accepts only the fixed repository ``_e2e.db`` file
or an explicitly isolated loopback PostgreSQL target.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.seed_e2e_backend import E2ESafetyError, main as seed_local_e2e_database  # noqa: E402


def main() -> None:
    try:
        seed_local_e2e_database()
    except E2ESafetyError as exc:
        raise SystemExit(f"reset.py stopped by the E2E safety check: {exc}") from exc


if __name__ == "__main__":
    main()
