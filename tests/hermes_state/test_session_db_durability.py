"""NS-506: session DB durability pragmas.

On memory/disk-constrained hosts an interrupted write (OOM kill, SIGTERM
mid-write, full disk) can tear the SQLite session DB. These tests pin the
durability settings the connection must apply so a regression that drops
them is caught.
"""

import sqlite3

import pytest

from hermes_state import SessionDB


@pytest.fixture
def db(tmp_path):
    database = SessionDB(tmp_path / "state.db")
    try:
        yield database
    finally:
        database.close()


def _pragma(conn: sqlite3.Connection, name: str):
    return conn.execute(f"PRAGMA {name}").fetchone()[0]


def test_wal_mode_uses_synchronous_normal(db):
    """On a normal local filesystem the DB runs WAL + synchronous=NORMAL.

    NORMAL is the SQLite-recommended WAL setting: crash-safe against OS
    crash / power loss / process kill (the DB file is never corrupted, only
    the last un-checkpointed txn can be lost), without the per-write fsync
    cost of FULL.
    """
    conn = db._conn
    assert _pragma(conn, "journal_mode").lower() == "wal"
    # 0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA
    assert _pragma(conn, "synchronous") == 1


def test_busy_timeout_is_set(db):
    """An explicit busy_timeout keeps a checkpoint/contention spike from
    surfacing as an immediate 'database is locked'."""
    assert _pragma(db._conn, "busy_timeout") == 2000


def test_synchronous_is_never_off(db):
    """The corruption-prone setting (synchronous=OFF) must never be in
    effect for the session store, regardless of journal mode."""
    assert _pragma(db._conn, "synchronous") >= 1


def test_foreign_keys_still_enabled(db):
    """Regression guard: the durability pragmas must not displace the
    existing foreign_keys=ON."""
    assert _pragma(db._conn, "foreign_keys") == 1
