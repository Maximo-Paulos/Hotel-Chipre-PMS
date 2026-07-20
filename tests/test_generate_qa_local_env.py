from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from scripts.agent_ops import generate_qa_local_env
from scripts.agent_ops.generate_qa_local_env import (
    ALLOWED_KEYS,
    QALocalEnvError,
    build_values,
    write_env,
)


def _read(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines())


def test_generates_only_allowed_synthetic_values_with_private_permissions(tmp_path: Path) -> None:
    output = tmp_path / ".env.qa.local"
    values = build_values(run_id="qa-test-run-001")

    write_env(output, values)

    stored = _read(output)
    assert tuple(stored) == ALLOWED_KEYS
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stored["QA_EMAIL_DOMAIN"] == "qa.hotels-pms.com"
    assert stored["QA_EMAIL_DOMAIN_IS_DEDICATED"] == "true"
    assert len({stored[key] for key in stored if key.endswith("_EMAIL")}) == 5
    assert len({stored[key] for key in stored if key.endswith("_PASSWORD")}) == 5
    assert stored["QA_MASTER_ADMIN_PIN"].isdigit()
    assert len(stored["QA_MASTER_ADMIN_PIN"]) == 6
    assert not any(
        forbidden in stored
        for forbidden in ("DATABASE_URL", "TOKEN", "PRIVATE_KEY", "COOKIE", "OTP")
    )


def test_existing_file_requires_explicit_rotation_and_remains_unchanged(tmp_path: Path) -> None:
    output = tmp_path / ".env.qa.local"
    output.write_text("owned-by-user\n")
    before = output.read_bytes()

    with pytest.raises(QALocalEnvError, match="--rotate"):
        write_env(output, build_values())

    assert output.read_bytes() == before


def test_explicit_rotation_replaces_values_and_preserves_mode(tmp_path: Path) -> None:
    output = tmp_path / ".env.qa.local"
    first = build_values(run_id="qa-first-run")
    second = build_values(run_id="qa-second-run")
    write_env(output, first)

    write_env(output, second, rotate=True)

    assert _read(output)["QA_RUN_ID"] == "qa-second-run"
    assert _read(output)["QA_OWNER_PASSWORD"] != first["QA_OWNER_PASSWORD"]
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_refuses_symlink_destination_without_touching_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("do-not-touch")
    output = tmp_path / ".env.qa.local"
    output.symlink_to(target)

    with pytest.raises(QALocalEnvError, match="symlink"):
        write_env(output, build_values(), rotate=True)

    assert target.read_text() == "do-not-touch"


@pytest.mark.parametrize(
    "domain",
    ["hotels-pms.com", "example.test", "bad domain", "qa@hotels-pms.com"],
)
def test_requires_a_dedicated_qa_subdomain(domain: str) -> None:
    with pytest.raises(QALocalEnvError, match="domain"):
        build_values(domain=domain)


def test_render_rejects_extra_sensitive_keys(tmp_path: Path) -> None:
    values = build_values()
    values["DATABASE_URL"] = "postgresql://forbidden"

    with pytest.raises(QALocalEnvError, match="unexpected"):
        write_env(tmp_path / ".env.qa.local", values)


def test_cli_never_prints_generated_credentials(monkeypatch, capsys, tmp_path: Path) -> None:
    output = tmp_path / ".env.qa.local"
    values = build_values(run_id="qa-cli-run-001")
    secrets_to_hide = [
        value
        for key, value in values.items()
        if key.endswith("_EMAIL") or key.endswith("_PASSWORD") or key.endswith("_PIN")
    ]
    monkeypatch.setattr(generate_qa_local_env, "build_values", lambda **_: values)
    monkeypatch.setattr(
        os.sys,
        "argv",
        ["generate_qa_local_env.py", "--output", str(output)],
    )

    assert generate_qa_local_env.main() == 0

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "secrets redacted" in combined
    assert all(secret not in combined for secret in secrets_to_hide)
