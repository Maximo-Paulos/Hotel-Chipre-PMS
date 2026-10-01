from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_legacy_reset_entrypoint_fails_closed_without_explicit_test_runtime():
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"APP_ENV", "ENVIRONMENT", "DATABASE_URL", "E2E_RESET_DATABASE"}
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, str(ROOT_DIR / "reset.py")],
        cwd=ROOT_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "local E2E requires APP_ENV=test" in result.stderr
