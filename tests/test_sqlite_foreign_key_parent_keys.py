"""Every foreign key in a migrated SQLite database needs a unique parent key.

SQLite only checks this when a row in the parent table is written, so a bad
key ships silently and surfaces later as "foreign key mismatch" on an
unrelated write. That is how shift_handoffs' composite FK to
cash_close_reports(hotel_id, id) broke closing a cash session: the unique
constraint it relies on was only ever added by a PostgreSQL-only repair
migration. Models-based test databases (create_all) carry every constraint
inline, so only a real `alembic upgrade head` exposes the gap.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _migrate(db_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _unique_column_sets(conn: sqlite3.Connection, table: str) -> list[set[str]]:
    sets: list[set[str]] = []
    primary_key = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")') if row[5] > 0}
    if primary_key:
        sets.append(primary_key)
    for index in conn.execute(f'PRAGMA index_list("{table}")'):
        if index[2]:  # unique
            sets.append({row[2] for row in conn.execute(f'PRAGMA index_info("{index[1]}")')})
    return sets


def test_every_foreign_key_in_a_migrated_sqlite_database_has_a_unique_parent_key(tmp_path):
    db_path = tmp_path / "migrated.db"
    _migrate(db_path)
    conn = sqlite3.connect(db_path)
    tables = [row[0] for row in conn.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]

    broken: list[str] = []
    for table in tables:
        keys: dict[int, dict] = {}
        for row in conn.execute(f'PRAGMA foreign_key_list("{table}")'):
            key = keys.setdefault(row[0], {"parent": row[2], "from": [], "to": []})
            key["from"].append(row[3])
            key["to"].append(row[4])
        for key in keys.values():
            if None in key["to"]:
                continue  # references the parent's primary key implicitly
            if set(key["to"]) not in _unique_column_sets(conn, key["parent"]):
                broken.append(f'{table}({",".join(key["from"])}) -> {key["parent"]}({",".join(key["to"])})')

    assert not broken, "foreign keys whose parent key is not unique on SQLite: " + "; ".join(broken)


def test_cash_close_reports_accepts_writes_with_foreign_keys_enforced(tmp_path):
    db_path = tmp_path / "migrated.db"
    _migrate(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    # Raised "foreign key mismatch - shift_handoffs referencing
    # cash_close_reports" before 20260917_sqlite_cash_close_parent_key.
    conn.execute("DELETE FROM cash_close_reports WHERE id = -1")
