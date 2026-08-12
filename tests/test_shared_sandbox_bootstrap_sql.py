from __future__ import annotations

from pathlib import Path

import pytest

from scripts.agent_ops.build_shared_sandbox_bootstrap_sql import (
    BASE_ID,
    SharedSandboxBootstrapError,
    build_sql,
    load_env,
)


def _values() -> dict[str, str]:
    return {
        "QA_RUN_ID": "shared-sandbox-base-v1",
        "QA_EMAIL_DOMAIN": "qa.hotels-pms.com",
        "QA_EMAIL_DOMAIN_IS_DEDICATED": "true",
        "QA_OWNER_EMAIL": "owner-base@qa.hotels-pms.com",
        "QA_OWNER_PASSWORD": "OwnerPlaintext9!ShouldNeverAppear",
        "QA_ISOLATION_OWNER_EMAIL": "isolation-base@qa.hotels-pms.com",
        "QA_ISOLATION_OWNER_PASSWORD": "IsolationPlaintext9!ShouldNeverAppear",
    }


def test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords() -> None:
    values = _values()

    sql = build_sql(values)

    assert "pg_advisory_xact_lock" in sql
    assert BASE_ID in sql
    assert "unmarked existing hotel" in sql
    assert "unmarked existing identity" in sql
    assert "enable_mercado_pago" in sql
    assert "false, false, false" in sql
    assert values["QA_OWNER_PASSWORD"] not in sql
    assert values["QA_ISOLATION_OWNER_PASSWORD"] not in sql


def test_sql_creates_primary_switch_membership_and_isolated_owner() -> None:
    sql = build_sql(_values())

    assert sql.count("insert into hotel_configuration") == 2
    assert sql.count("insert into hotel_memberships") == 3
    assert "Hotel QA Compartido" in sql
    assert "Hotel QA Aislamiento" in sql
    assert "insert into hotel_configuration select" not in sql


def test_env_file_requires_owner_only_permissions(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.qa.local"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in _values().items()) + "\n",
        encoding="utf-8",
    )
    env_file.chmod(0o644)

    with pytest.raises(SharedSandboxBootstrapError, match="readable only by its owner"):
        load_env(env_file)


def test_env_file_refuses_symlink(tmp_path: Path) -> None:
    real_file = tmp_path / "personas"
    real_file.write_text("not-used\n", encoding="utf-8")
    real_file.chmod(0o600)
    linked_file = tmp_path / ".env.qa.local"
    linked_file.symlink_to(real_file)

    with pytest.raises(SharedSandboxBootstrapError, match="cannot be a symlink"):
        load_env(linked_file)
