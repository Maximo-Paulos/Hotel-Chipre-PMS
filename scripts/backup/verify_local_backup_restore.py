#!/usr/bin/env python3
"""Run a disposable local backup -> restore drill.

The default safety boundary is local-only: PostgreSQL URLs must point to a
loopback host. The source is never modified and the restored database is
created under a temporary directory/database and removed on exit.

Examples:
    python scripts/backup/verify_local_backup_restore.py \
        --database-url sqlite:///./local-test.db
    python scripts/backup/verify_local_backup_restore.py \
        --database-url postgresql+psycopg2://pms@127.0.0.1:5432/hotel_pms
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
from typing import Iterable
from urllib.parse import unquote, urlsplit
import uuid


DEFAULT_TABLES = ("guests", "reservations", "payments", "audit_logs")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LOCAL_POSTGRES_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


class DrillError(RuntimeError):
    """Expected, safe failure for a local drill."""


def _validate_tables(tables: Iterable[str]) -> tuple[str, ...]:
    validated = tuple(tables)
    if not validated or any(not IDENTIFIER.fullmatch(table) for table in validated):
        raise DrillError("table names must be simple SQL identifiers")
    return validated


def _sqlite_path(database_url: str) -> Path:
    parsed = urlsplit(database_url)
    if not parsed.scheme.startswith("sqlite"):
        raise DrillError("expected a sqlite URL")
    raw_path = unquote(parsed.path)
    if raw_path in {"", "/", "/:memory:", ":memory:"}:
        raise DrillError("an on-disk SQLite source is required for a dump")
    # sqlite:///relative.db -> relative.db; sqlite:////tmp/db -> /tmp/db.
    path = raw_path[1:] if raw_path.startswith("//") else raw_path.lstrip("/")
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise DrillError(f"SQLite source does not exist: {source}")
    return source


def _sqlite_counts(connection: sqlite3.Connection, tables: tuple[str, ...]) -> dict[str, int]:
    available = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    missing = [table for table in tables if table not in available]
    if missing:
        raise DrillError(f"SQLite source is missing key tables: {', '.join(missing)}")
    return {
        table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in tables
    }


def _run_sqlite(source: Path, tables: tuple[str, ...]) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="hcp-backup-restore-") as temp_dir:
        dump_path = Path(temp_dir) / "database.dump.sql"
        restored_path = Path(temp_dir) / "restored.sqlite3"
        with sqlite3.connect(source) as source_db:
            source_counts = _sqlite_counts(source_db, tables)
            dump_sql = "\n".join(source_db.iterdump()) + "\n"
        dump_path.write_text(dump_sql, encoding="utf-8")

        with sqlite3.connect(restored_path) as restored_db:
            # SQLite's iterdump order can insert a child before its referenced
            # table. Load the dump without enforcement, then turn enforcement
            # on and validate every FK after the restore completes.
            restored_db.execute("PRAGMA foreign_keys = OFF")
            restored_db.executescript(dump_sql)
            restored_db.execute("PRAGMA foreign_keys = ON")
            integrity = restored_db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise DrillError(f"SQLite integrity_check failed: {integrity}")
            foreign_key_errors = restored_db.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_key_errors:
                raise DrillError("SQLite foreign_key_check found violations")
            restored_counts = _sqlite_counts(restored_db, tables)

        if source_counts != restored_counts:
            raise DrillError(
                f"row counts changed during restore: source={source_counts} restored={restored_counts}"
            )
        return {
            "backend": "sqlite",
            "dump_format": "sqlite SQL iterdump",
            "integrity_check": "ok",
            "foreign_key_check": "ok",
            "tables": source_counts,
            "dump_bytes": len(dump_sql.encode("utf-8")),
        }


def _postgres_parts(database_url: str) -> dict[str, str]:
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgresql", "postgres", "postgresql+psycopg2", "postgresql+psycopg"}:
        raise DrillError("expected a PostgreSQL URL")
    host = parsed.hostname or ""
    if host.lower() not in LOCAL_POSTGRES_HOSTS:
        raise DrillError("refusing PostgreSQL restore drill: host is not local")
    if not parsed.path or parsed.path == "/":
        raise DrillError("PostgreSQL URL must include a database name")
    return {
        "host": host,
        "port": str(parsed.port or 5432),
        "user": unquote(parsed.username or os.environ.get("PGUSER", "")),
        "password": unquote(parsed.password or os.environ.get("PGPASSWORD", "")),
        "database": unquote(parsed.path.lstrip("/")),
    }


def _pg_command(parts: dict[str, str], program: str, database: str | None = None) -> list[str]:
    command = [program, "--no-password", "--host", parts["host"] or "127.0.0.1", "--port", parts["port"]]
    if parts["user"]:
        command.extend(["--username", parts["user"]])
    command.append(database or parts["database"])
    return command


def _run_pg_command(parts: dict[str, str], command: list[str], *, input_text: str | None = None) -> str:
    child_env = os.environ.copy()
    if parts["password"]:
        child_env["PGPASSWORD"] = parts["password"]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            input=input_text,
            env=child_env,
        )
    except FileNotFoundError as exc:
        raise DrillError(f"required PostgreSQL tool is unavailable: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        # Do not echo stderr: provider errors can contain DSNs or credentials.
        raise DrillError(f"{command[0]} failed with exit code {exc.returncode}") from exc
    return result.stdout


def _pg_count(parts: dict[str, str], database: str, table: str) -> int:
    output = _run_pg_command(
        parts,
        _pg_command(parts, "psql", database)
        + ["--tuples-only", "--no-align", "--command", f'SELECT COUNT(*) FROM "{table}"'],
    )
    return int(output.strip())


def _run_postgres(database_url: str, tables: tuple[str, ...]) -> dict[str, object]:
    parts = _postgres_parts(database_url)
    required_tools = ("pg_dump", "pg_restore", "createdb", "dropdb", "psql")
    missing_tools = [tool for tool in required_tools if shutil.which(tool) is None]
    if missing_tools:
        raise DrillError(f"required PostgreSQL tools are unavailable: {', '.join(missing_tools)}")

    with tempfile.TemporaryDirectory(prefix="hcp-backup-restore-") as temp_dir:
        dump_path = Path(temp_dir) / "database.dump"
        temp_database = f"hcp_restore_{uuid.uuid4().hex[:16]}"
        _run_pg_command(parts, _pg_command(parts, "pg_dump")[:-1] + ["--format=custom", "--file", str(dump_path), parts["database"]])
        dump_bytes = dump_path.stat().st_size
        try:
            _run_pg_command(parts, _pg_command(parts, "createdb", "postgres")[:-1] + [temp_database])
            _run_pg_command(
                parts,
                _pg_command(parts, "pg_restore")[:-1]
                + ["--exit-on-error", "--no-owner", "--dbname", temp_database, str(dump_path)],
            )
            source_counts = {table: _pg_count(parts, parts["database"], table) for table in tables}
            restored_counts = {table: _pg_count(parts, temp_database, table) for table in tables}
        finally:
            _run_pg_command(parts, _pg_command(parts, "dropdb", "postgres")[:-1] + ["--if-exists", temp_database])

    if source_counts != restored_counts:
        raise DrillError(
            f"row counts changed during restore: source={source_counts} restored={restored_counts}"
        )
    return {
        "backend": "postgresql",
        "dump_format": "pg_dump custom",
        "tables": source_counts,
        "dump_bytes": dump_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="local SQLite/PostgreSQL URL; defaults to DATABASE_URL",
    )
    parser.add_argument(
        "--table",
        dest="tables",
        action="append",
        default=None,
        help="key table to compare; may be repeated (default: guests, reservations, payments, audit_logs)",
    )
    args = parser.parse_args()
    try:
        if not args.database_url:
            raise DrillError("provide --database-url or DATABASE_URL")
        tables = _validate_tables(args.tables or DEFAULT_TABLES)
        scheme = urlsplit(args.database_url).scheme
        if scheme.startswith("sqlite"):
            result = _run_sqlite(_sqlite_path(args.database_url), tables)
        elif scheme in {"postgresql", "postgres", "postgresql+psycopg2", "postgresql+psycopg"}:
            result = _run_postgres(args.database_url, tables)
        else:
            raise DrillError("database URL must use SQLite or PostgreSQL")
    except DrillError as exc:
        print(f"LOCAL_RESTORE_DRILL_FAILED: {exc}")
        return 1
    print(json.dumps({"status": "verified", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
