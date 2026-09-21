"""Database schema creation, migrations, indexes, and initial seed data.

Migrations
----------
Schema changes to an EXISTING table (new columns, etc.) go in MIGRATIONS
below as a new numbered function appended to the list — never edit an
already-shipped migration, only add new ones after it.

A brand new database is created directly with the full current schema (see
the CREATE TABLE statements in init_db()) and never runs the migrations at
all — they only exist to bring a database created by an OLDER version of
this app up to date. Applied migrations are tracked with SQLite's
PRAGMA user_version, so a normal startup on an already-current database
costs a single integer read instead of re-checking every column on every
launch.

To add a new column in the future: add it to the relevant CREATE TABLE
below (so fresh installs get it directly), write a small
`_migration_00N_<description>(conn)` function that adds it with
ALTER TABLE (guarded by a column-existence check, so it's safe to run
even if it somehow already applied), and append it to MIGRATIONS.
"""

from media_scheduler.config import SEED_MEMBERS
from media_scheduler.db.connection import get_conn


def _migration_001_add_load_and_max_days_columns(conn):
    """members.load_stress (dynamic load) and members.max_days_per_month."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(members)").fetchall()]
    if "load_stress" not in cols:
        conn.execute('ALTER TABLE members ADD COLUMN load_stress REAL DEFAULT 0')
    if "max_days_per_month" not in cols:
        conn.execute('ALTER TABLE members ADD COLUMN max_days_per_month INTEGER')


def _migration_002_add_coord_level_column(conn):
    """members.coord_level (used to pick a coordinator among assigned members)."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(members)").fetchall()]
    if "coord_level" not in cols:
        conn.execute('ALTER TABLE members ADD COLUMN coord_level INTEGER DEFAULT 0')


def _migration_003_add_phone_column(conn):
    """members.phone (WhatsApp number, used by the notifications service)."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(members)").fetchall()]
    if "phone" not in cols:
        conn.execute("ALTER TABLE members ADD COLUMN phone TEXT DEFAULT ''")


# Ordered oldest -> newest, 1-indexed by position. Append new migrations
# here; never reorder or remove existing ones. len(MIGRATIONS) is the
# current schema version.
MIGRATIONS = [
    _migration_001_add_load_and_max_days_columns,
    _migration_002_add_coord_level_column,
    _migration_003_add_phone_column,
]

CURRENT_SCHEMA_VERSION = len(MIGRATIONS)


def _run_migrations(conn):
    applied = conn.execute('PRAGMA user_version').fetchone()[0]
    if applied < CURRENT_SCHEMA_VERSION:
        for version, migration in enumerate(MIGRATIONS, start=1):
            if version > applied:
                migration(conn)
        # PRAGMA doesn't support `?` parameter binding; CURRENT_SCHEMA_VERSION
        # is a fixed int computed from len(MIGRATIONS) above, not user input.
        conn.execute(f'PRAGMA user_version = {CURRENT_SCHEMA_VERSION}')


def init_db():
    """
    Creates schema + indexes.
    - Brand new databases are created directly with the full current schema
      and start at CURRENT_SCHEMA_VERSION (see module docstring).
    - Existing databases from an older version of the app are brought up to
      date by _run_migrations() / MIGRATIONS above.
    - Seeds initial members if the table is empty.
    """
    with get_conn() as conn:
        c = conn.cursor()

        # --- base tables (current full schema) ---
        c.execute('''CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            live_level INTEGER DEFAULT 0,
            luzes_level INTEGER DEFAULT 0,
            slide_level INTEGER DEFAULT 0,
            coord_level INTEGER DEFAULT 0,
            stress REAL DEFAULT 0,              -- manual/base (you set)
            load_stress REAL DEFAULT 0,         -- dynamic load (system)
            max_days_per_month INTEGER,         -- NULL = no limit
            availability TEXT DEFAULT '',
            phone TEXT DEFAULT ''                -- WhatsApp number, e.g. 351912345678
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            name TEXT,
            date TEXT NOT NULL,
            importance INTEGER DEFAULT 1
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY,
            event_id INTEGER NOT NULL,
            zone TEXT NOT NULL,
            member_id INTEGER NOT NULL,
            assigned_at TEXT,
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
        )''')

        # Coordinator per event
        c.execute('''CREATE TABLE IF NOT EXISTS event_coordinators (
            event_id INTEGER PRIMARY KEY,
            member_id INTEGER NOT NULL,
            assigned_at TEXT,
            FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
        )''')

        # Per-date unavailability
        c.execute('''CREATE TABLE IF NOT EXISTS member_blackouts (
            id INTEGER PRIMARY KEY,
            member_id INTEGER NOT NULL,
            date TEXT NOT NULL,          -- yyyy-mm-dd
            note TEXT DEFAULT '',
            FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
        )''')

        # --- bring pre-existing databases up to the current schema ---
        _run_migrations(conn)

        # --- indexes/constraints ---
        conn.execute('CREATE INDEX IF NOT EXISTS idx_events_date ON events(date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_assignments_event ON assignments(event_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_assignments_member ON assignments(member_id)')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_assign_event_zone ON assignments(event_id, zone)')

        conn.execute('CREATE INDEX IF NOT EXISTS idx_blackouts_member_date ON member_blackouts(member_id, date)')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_blackouts_member_date ON member_blackouts(member_id, date)')

        conn.execute('CREATE INDEX IF NOT EXISTS idx_coord_member ON event_coordinators(member_id)')

        # --- seed members if empty ---
        n = conn.execute("SELECT COUNT(1) AS cnt FROM members").fetchone()["cnt"]
        if n == 0:
            rows = []
            for (nm, live, luz, sl, avail, coord) in SEED_MEMBERS:
                rows.append((nm, live, luz, sl, coord, 0.0, 0.0, None, avail, ''))
            conn.executemany(
                "INSERT INTO members (name, live_level, luzes_level, slide_level, coord_level, stress, load_stress, max_days_per_month, availability, phone) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows
            )

        conn.commit()