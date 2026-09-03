from __future__ import annotations

import hashlib
import sqlite3

import pytest

from scripts.backup.verify_local_backup_restore import DrillError, _verify_local_objects


def test_verify_local_objects_checks_size_and_sha(tmp_path):
    storage = tmp_path / "objects"
    storage.mkdir()
    data = b"synthetic backup object"
    key = "exports/1/report.xlsx"
    path = storage / key
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE stored_objects (object_key TEXT, byte_size INTEGER, sha256_hex TEXT, status TEXT)"
    )
    connection.execute(
        "INSERT INTO stored_objects VALUES (?, ?, ?, 'ready')",
        (key, len(data), hashlib.sha256(data).hexdigest()),
    )
    assert _verify_local_objects(connection, storage) == {"ready": 1, "verified": 1}
    path.write_bytes(b"corrupt")
    with pytest.raises(DrillError, match="checksum/size mismatch"):
        _verify_local_objects(connection, storage)
    connection.close()
