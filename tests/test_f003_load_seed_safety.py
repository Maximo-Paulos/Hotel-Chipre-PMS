from __future__ import annotations

import pytest

from scripts import seed_e2e_backend, seed_f003_load_scenario


DATABASE_NAME = "hotel_chipre_e2e_f003_load_20260930"
APP_URL = (
    "postgresql+psycopg2://hotel_chipre_e2e_f003_load_20260930_app_runner:test-only-password"
    f"@127.0.0.1:5432/{DATABASE_NAME}"
)
SEED_URL = (
    "postgresql+psycopg2://hotel_chipre_e2e_f003_load_20260930_seed_runner:test-only-seed-password"
    f"@127.0.0.1:5432/{DATABASE_NAME}"
)


def _f003_environment() -> dict[str, str]:
    return {
        "APP_ENV": "test",
        "E2E_F003_LOAD": "true",
        "DATABASE_URL": APP_URL,
        seed_e2e_backend.E2E_POSTGRES_ISOLATED: "true",
        seed_e2e_backend.E2E_POSTGRES_DATABASE_URL_EXPLICIT: APP_URL,
        "E2E_POSTGRES_SEED_DATABASE_URL": SEED_URL,
        seed_e2e_backend.E2E_POSTGRES_SEED_DATABASE_URL_EXPLICIT: SEED_URL,
    }


def test_f003_seed_accepts_only_dedicated_local_fixture_target():
    target = _f003_environment()

    database_url, app_parameters, seed_url, seed_parameters = seed_f003_load_scenario._validated_target(target)

    assert database_url == APP_URL
    assert app_parameters["dbname"] == DATABASE_NAME
    assert app_parameters["user"].endswith("_app_runner")
    assert seed_url == SEED_URL
    assert seed_parameters["user"].endswith("_seed_runner")


def test_f003_seed_requires_explicit_opt_in():
    target = _f003_environment()
    target["E2E_F003_LOAD"] = "false"

    with pytest.raises(seed_e2e_backend.E2ESafetyError, match="E2E_F003_LOAD=true"):
        seed_f003_load_scenario._validated_target(target)


def test_f003_seed_rejects_sqlite_even_with_opt_in():
    target = _f003_environment()
    target["DATABASE_URL"] = seed_e2e_backend.E2E_DATABASE_URL
    target.pop(seed_e2e_backend.E2E_POSTGRES_DATABASE_URL_EXPLICIT)
    target.pop("E2E_POSTGRES_SEED_DATABASE_URL")
    target.pop(seed_e2e_backend.E2E_POSTGRES_SEED_DATABASE_URL_EXPLICIT)
    target.pop(seed_e2e_backend.E2E_POSTGRES_ISOLATED)

    with pytest.raises(seed_e2e_backend.E2ESafetyError, match="local PostgreSQL 16"):
        seed_f003_load_scenario._validated_target(target)


def test_f003_seed_rejects_database_outside_its_dedicated_namespace():
    target = _f003_environment()
    wrong_database = "hotel_chipre_e2e_unrelated"
    target["DATABASE_URL"] = APP_URL.replace(DATABASE_NAME, wrong_database)
    target[seed_e2e_backend.E2E_POSTGRES_DATABASE_URL_EXPLICIT] = target["DATABASE_URL"]
    target["E2E_POSTGRES_SEED_DATABASE_URL"] = SEED_URL.replace(DATABASE_NAME, wrong_database)
    target[seed_e2e_backend.E2E_POSTGRES_SEED_DATABASE_URL_EXPLICIT] = target["E2E_POSTGRES_SEED_DATABASE_URL"]

    with pytest.raises(seed_e2e_backend.E2ESafetyError, match="dedicated disposable database name"):
        seed_f003_load_scenario._validated_target(target)
