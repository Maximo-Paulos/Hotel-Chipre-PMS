from __future__ import annotations

import ast
import builtins
from pathlib import Path

import pytest

from scripts import seed_e2e_backend, serve_e2e_backend


def test_seed_guard_accepts_only_explicit_test_and_repository_e2e_database():
    env = {"APP_ENV": "test", "DATABASE_URL": seed_e2e_backend.E2E_DATABASE_URL}

    normalized = seed_e2e_backend.prepare_e2e_environment(env)

    assert env["APP_ENV"] == "test"
    assert env["DATABASE_URL"] == seed_e2e_backend.E2E_DATABASE_URL
    assert normalized == seed_e2e_backend.E2E_DATABASE_URL


def test_reset_e2e_database_only_removes_the_explicit_generated_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    db_path = tmp_path / "_e2e.db"
    db_path.write_bytes(b"isolated test data")
    (tmp_path / "_e2e.db-wal").write_bytes(b"wal")
    monkeypatch.setattr(seed_e2e_backend, "E2E_DATABASE_PATH", db_path)
    monkeypatch.setenv("E2E_RESET_DATABASE", "true")

    seed_e2e_backend.reset_e2e_database()

    assert not db_path.exists()
    assert not (tmp_path / "_e2e.db-wal").exists()


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"APP_ENV": "test"},
        {"DATABASE_URL": seed_e2e_backend.E2E_DATABASE_URL},
    ],
)
def test_seed_guard_rejects_missing_explicit_environment(env):
    with pytest.raises(seed_e2e_backend.E2ESafetyError):
        seed_e2e_backend.prepare_e2e_environment(env)


@pytest.mark.parametrize("app_env", ["production", "prod", "preview", "development", "TEST"])
def test_seed_guard_rejects_every_environment_except_exact_test(app_env):
    env = {"APP_ENV": app_env, "DATABASE_URL": seed_e2e_backend.E2E_DATABASE_URL}

    with pytest.raises(seed_e2e_backend.E2ESafetyError, match="APP_ENV=test"):
        seed_e2e_backend.prepare_e2e_environment(env)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg2://hotel_qa:secret@production.example.test/postgres",
        "postgresql://postgres:secret@db.ezkljznogqpmrjxyvklr.supabase.co/postgres",
        "sqlite:///:memory:",
        "sqlite:////tmp/_e2e.db",
        "sqlite:///./other-e2e.db",
        "sqlite:///./_e2e.db?mode=rw",
    ],
)
def test_seed_guard_rejects_inherited_or_ambiguous_database_targets(database_url):
    env = {"APP_ENV": "test", "DATABASE_URL": database_url}

    with pytest.raises(seed_e2e_backend.E2ESafetyError):
        seed_e2e_backend.prepare_e2e_environment(env)


def test_seed_main_refuses_postgres_before_migrations_or_seed(monkeypatch):
    called = {"migrations": False, "seed": False}
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:secret@db.ezkljznogqpmrjxyvklr.supabase.co/postgres",
    )
    monkeypatch.setattr(
        seed_e2e_backend,
        "run_migrations",
        lambda: called.__setitem__("migrations", True),
    )
    monkeypatch.setattr(
        seed_e2e_backend,
        "upsert_seed_data",
        lambda: called.__setitem__("seed", True),
    )

    with pytest.raises(seed_e2e_backend.E2ESafetyError):
        seed_e2e_backend.main()

    assert called == {"migrations": False, "seed": False}


def test_run_migrations_refuses_bad_target_before_importing_alembic(monkeypatch):
    imported: list[str] = []
    original_import = builtins.__import__

    def tracking_import(name, *args, **kwargs):
        imported.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", tracking_import)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:secret@production.invalid/postgres")

    with pytest.raises(seed_e2e_backend.E2ESafetyError):
        seed_e2e_backend.run_migrations()

    assert not any(name == "alembic" or name.startswith("alembic.") for name in imported)


def test_serve_wrapper_refuses_bad_target_before_seed_or_uvicorn(monkeypatch):
    seeded = False

    def record_seed():
        nonlocal seeded
        seeded = True

    monkeypatch.setattr(serve_e2e_backend, "seed_main", record_seed)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:secret@production.invalid/postgres")

    with pytest.raises(seed_e2e_backend.E2ESafetyError):
        serve_e2e_backend.main()

    assert seeded is False


@pytest.mark.parametrize("script_name", ["seed_e2e_backend.py", "serve_e2e_backend.py"])
def test_e2e_scripts_have_no_top_level_app_alembic_or_uvicorn_imports(script_name):
    path = Path(__file__).resolve().parents[1] / "scripts" / script_name
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top_level_imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.append(node.module)

    assert not any(
        name == "app"
        or name.startswith("app.")
        or name == "alembic"
        or name.startswith("alembic.")
        or name == "uvicorn"
        for name in top_level_imports
    )
