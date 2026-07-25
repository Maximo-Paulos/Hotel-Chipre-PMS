"""B3.2: migration adding guests.birth_place/birth_country/marital_status/occupation
must be reversible and clean on SQLite (upgrade -> downgrade -1 -> upgrade)."""
import os
import subprocess
import sys
import tempfile


def _run(args, env, cwd):
    return subprocess.run(args, capture_output=True, text=True, env=env, cwd=cwd)


def test_guest_checkin_profile_migration_up_down_up_on_sqlite():
    cwd = os.path.dirname(os.path.dirname(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        dsn = f"sqlite:///{tmp}/mig.db"
        env = {**os.environ, "DATABASE_URL": dsn}

        up1 = _run([sys.executable, "-m", "alembic", "upgrade", "head"], env, cwd)
        assert up1.returncode == 0, f"upgrade head failed:\n{up1.stderr}"

        down = _run([sys.executable, "-m", "alembic", "downgrade", "-1"], env, cwd)
        assert down.returncode == 0, f"downgrade -1 failed:\n{down.stderr}"

        up2 = _run([sys.executable, "-m", "alembic", "upgrade", "head"], env, cwd)
        assert up2.returncode == 0, f"re-upgrade head failed:\n{up2.stderr}"

        import sqlite3
        conn = sqlite3.connect(f"{tmp}/mig.db")
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(guests)")}
        finally:
            conn.close()
        for field in ("birth_place", "birth_country", "marital_status", "occupation"):
            assert field in columns
