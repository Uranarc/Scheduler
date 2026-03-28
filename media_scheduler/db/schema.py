"""Database schema creation, migrations, indexes, and initial seed data."""

from media_scheduler.config import SEED_MEMBERS
from media_scheduler.db.connection import get_conn


def init_db():
    """
    Creates schema + indexes.
    - Seeds initial members if table is empty
    - Migrates missing columns safely:
        * members.load_stress
        * members.max_days_per_month
        * members.coord_level
    - Creates member_blackouts table for per-date unavailability
    - Creates event_coordinators table (coordinator always among assigned members)
    """
    with get_conn() as conn:
        c = conn.cursor()

        # --- base tables ---
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
            availability TEXT DEFAULT ''
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

        # --- migrations for existing DBs ---
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(members)").fetchall()]

        if "load_stress" not in cols:
            conn.execute('ALTER TABLE members ADD COLUMN load_stress REAL DEFAULT 0')

        if "max_days_per_month" not in cols:
            conn.execute('ALTER TABLE members ADD COLUMN max_days_per_month INTEGER')

        if "coord_level" not in cols:
            conn.execute('ALTER TABLE members ADD COLUMN coord_level INTEGER DEFAULT 0')

        # --- per-date unavailability ---
        c.execute('''CREATE TABLE IF NOT EXISTS member_blackouts (
            id INTEGER PRIMARY KEY,
            member_id INTEGER NOT NULL,
            date TEXT NOT NULL,          -- yyyy-mm-dd
            note TEXT DEFAULT '',
            FOREIGN KEY(member_id) REFERENCES members(id) ON DELETE CASCADE
        )''')

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
                rows.append((nm, live, luz, sl, coord, 0.0, 0.0, None, avail))
            conn.executemany(
                "INSERT INTO members (name, live_level, luzes_level, slide_level, coord_level, stress, load_stress, max_days_per_month, availability) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows
            )

        conn.commit()


