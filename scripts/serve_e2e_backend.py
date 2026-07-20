"""
Seed and serve the E2E backend on 127.0.0.1:8040.

This wrapper avoids shell-specific environment syntax when Playwright or a
developer wants to boot the backend as a single command.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.seed_e2e_backend import main as seed_main, prepare_e2e_environment  # noqa: E402


def main() -> None:
    prepare_e2e_environment()
    seed_main()

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8040)


if __name__ == "__main__":
    main()
