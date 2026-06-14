"""
Seed and serve the E2E backend on 127.0.0.1:8040.

This wrapper avoids shell-specific environment syntax when Playwright or a
developer wants to boot the backend as a single command.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(ROOT_DIR / '_e2e.db').resolve().as_posix()}")
os.environ.setdefault("JWT_SECRET", "e2e-local-jwt-secret-change-me-32chars")

from scripts.seed_e2e_backend import main as seed_main  # noqa: E402


def main() -> None:
    seed_main()

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8040)


if __name__ == "__main__":
    main()
