"""SQLite connection helper used by database modules."""

import sqlite3

from media_scheduler.config import DB_FILENAME


def get_conn():
    conn = sqlite3.connect(DB_FILENAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


