from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / ".pytest_cache" / "smoke"
REPORT_PATH = ARTIFACTS_DIR / "last_run.txt"
JUNIT_PATH = ARTIFACTS_DIR / "junit.xml"


def main() -> int:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/smoke",
        "-q",
        "-rA",
        "--junitxml",
        str(JUNIT_PATH),
    ]

    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)

    combined_output = []
    if result.stdout:
        combined_output.append(result.stdout.rstrip())
    if result.stderr:
        combined_output.append(result.stderr.rstrip())
    rendered_output = "\n\n".join(combined_output).strip()

    report_lines = [
        f"timestamp_utc={datetime.now(timezone.utc).isoformat()}",
        f"exit_code={result.returncode}",
        f"command={' '.join(command)}",
        f"junit_xml={JUNIT_PATH}",
        "",
        rendered_output or "(no output)",
    ]
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)

    print(f"\nSmoke report: {REPORT_PATH}")
    print(f"JUnit XML: {JUNIT_PATH}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
