"""Repository functions for assignments, coordinator cleanup, and dashboard summaries."""

from datetime import datetime, timezone

from media_scheduler.db.connection import get_conn
from media_scheduler.db.members import adjust_member_load_stress
from media_scheduler.scheduler.load import compute_load_increment


def list_assignments_db(start: str = None, end: str = None):
    q = '''SELECT a.id as aid, e.id as evid, e.date as evdate, e.name as evname, a.zone as zone,
                   a.member_id as mid, m.name as mname
            FROM assignments a
            JOIN events e ON a.event_id = e.id
            JOIN members m ON a.member_id = m.id'''
    params = ()
    if start and end:
        q += ' WHERE e.date BETWEEN ? AND ?'
        params = (start, end)
    q += ' ORDER BY e.date'
    with get_conn() as conn:
        return conn.execute(q, params).fetchall()


def list_coordinators_in_range(start: str, end: str) -> dict:
    """event_id -> coordinator name, for events in range that have one assigned."""
    with get_conn() as conn:
        rows = conn.execute('''
            SELECT ec.event_id AS event_id, m.name AS name
            FROM event_coordinators ec
            JOIN members m ON m.id = ec.member_id
            JOIN events e ON e.id = ec.event_id
            WHERE e.date BETWEEN ? AND ?
        ''', (start, end)).fetchall()
    return {r['event_id']: r['name'] for r in rows}


def update_assignment_member(assignment_id: int, member_id: int, stress_increase: float = 1.0):
    """
    Reassign an existing (event, zone) slot to a different member.

    Only the load contribution of THIS one assignment moves from the old
    member to the new one — the rest of each member's load_stress (built up
    over prior generations, with decay already applied) is left untouched.
    """
    with get_conn() as conn:
        row = conn.execute('''
            SELECT a.member_id AS old_member_id, a.zone AS zone, e.importance AS importance
            FROM assignments a
            JOIN events e ON a.event_id = e.id
            WHERE a.id = ?
        ''', (assignment_id,)).fetchone()

        if row is None:
            return

        old_member_id = row['old_member_id']
        conn.execute('UPDATE assignments SET member_id = ? WHERE id = ?', (member_id, assignment_id))
        conn.commit()

    if old_member_id == member_id:
        return  # no actual change

    load_inc = compute_load_increment(row['zone'], row['importance'], stress_increase)
    if old_member_id is not None:
        adjust_member_load_stress(old_member_id, -load_inc)
    adjust_member_load_stress(member_id, load_inc)


def add_assignment_manual(event_id: int, zone: str, member_id: int, stress_increase: float = 1.0):
    """
    Manually assign a member to an (event, zone) slot.

    If the slot already had a different member assigned (upsert case), that
    member's load contribution for this slot is removed and the new
    member's is added — previously only the new member's load was touched,
    leaving the replaced member's load permanently inflated.
    """
    with get_conn() as conn:
        importance_row = conn.execute('SELECT importance FROM events WHERE id = ?', (event_id,)).fetchone()
        importance = int(importance_row['importance']) if importance_row else 1

        existing = conn.execute(
            'SELECT member_id FROM assignments WHERE event_id = ? AND zone = ?',
            (event_id, zone)
        ).fetchone()
        old_member_id = existing['member_id'] if existing else None

        conn.execute('''
            INSERT INTO assignments (event_id, zone, member_id, assigned_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(event_id, zone) DO UPDATE SET
                member_id = excluded.member_id,
                assigned_at = excluded.assigned_at
        ''', (event_id, zone, member_id, datetime.now(timezone.utc).isoformat()))
        conn.commit()

    if old_member_id == member_id:
        return  # re-assigning the same person to the same slot: no load change

    load_inc = compute_load_increment(zone, importance, stress_increase)
    if old_member_id is not None:
        adjust_member_load_stress(old_member_id, -load_inc)
    adjust_member_load_stress(member_id, load_inc)


def get_load_summary(year: int, month: int) -> list[dict]:
    start = f'{int(year):04d}-{int(month):02d}-01'
    if int(month) == 12:
        end = f'{int(year) + 1:04d}-01-01'
    else:
        end = f'{int(year):04d}-{int(month) + 1:02d}-01'

    with get_conn() as conn:
        rows = conn.execute('''
            SELECT
                m.id AS member_id,
                m.name AS name,
                m.load_stress AS load_stress,
                m.stress AS manual_stress,
                m.max_days_per_month AS max_days,
                COALESCE(x.slide_count, 0) AS slide_count,
                COALESCE(x.luzes_count, 0) AS luzes_count,
                COALESCE(x.live_count, 0) AS live_count,
                COALESCE(x.total_days, 0) AS total_days
            FROM members m
            LEFT JOIN (
                SELECT
                    a.member_id AS member_id,
                    SUM(CASE WHEN a.zone = 'slide' THEN 1 ELSE 0 END) AS slide_count,
                    SUM(CASE WHEN a.zone = 'luzes' THEN 1 ELSE 0 END) AS luzes_count,
                    SUM(CASE WHEN a.zone = 'live' THEN 1 ELSE 0 END) AS live_count,
                    COUNT(DISTINCT e.date) AS total_days
                FROM assignments a
                JOIN events e ON e.id = a.event_id
                WHERE e.date >= ? AND e.date < ?
                GROUP BY a.member_id
            ) x ON x.member_id = m.id
            ORDER BY m.name
        ''', (start, end)).fetchall()

    out = []
    for r in rows:
        max_days = r['max_days']
        total_days = int(r['total_days'] or 0)
        days_remaining = None if max_days is None else int(max_days) - total_days
        out.append({
            'member_id': r['member_id'],
            'name': r['name'],
            'slide_count': int(r['slide_count'] or 0),
            'luzes_count': int(r['luzes_count'] or 0),
            'live_count': int(r['live_count'] or 0),
            'total_days': total_days,
            'load_stress': round(float(r['load_stress'] or 0.0), 2),
            'manual_stress': round(float(r['manual_stress'] or 0.0), 2),
            'max_days': (None if max_days is None else int(max_days)),
            'days_remaining': days_remaining,
            'over_limit': (max_days is not None and total_days > int(max_days)),
        })
    return out


def delete_assignment_db(assignment_id: int, stress_increase: float = 1.0):
    with get_conn() as conn:
        row = conn.execute('''
            SELECT a.member_id AS member_id, a.zone AS zone, e.importance AS importance
            FROM assignments a
            JOIN events e ON a.event_id = e.id
            WHERE a.id = ?
        ''', (assignment_id,)).fetchone()

        conn.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))
        conn.commit()

    if row is not None:
        load_inc = compute_load_increment(row['zone'], row['importance'], stress_increase)
        adjust_member_load_stress(row['member_id'], -load_inc)


def delete_all_assignments_db(stress_increase: float = 1.0):
    with get_conn() as conn:
        rows = conn.execute('''
            SELECT a.member_id AS member_id, a.zone AS zone, e.importance AS importance
            FROM assignments a
            JOIN events e ON a.event_id = e.id
        ''').fetchall()
        conn.execute('DELETE FROM assignments')
        conn.commit()

    _reverse_load_by_member(rows, stress_increase)


def delete_assignments_in_range(start: str, end: str, stress_increase: float = 1.0):
    with get_conn() as conn:
        rows = conn.execute('''
            SELECT a.member_id AS member_id, a.zone AS zone, e.importance AS importance
            FROM assignments a
            JOIN events e ON a.event_id = e.id
            WHERE e.date BETWEEN ? AND ?
        ''', (start, end)).fetchall()

        conn.execute('''
            DELETE FROM assignments
            WHERE event_id IN (SELECT id FROM events WHERE date BETWEEN ? AND ?)
        ''', (start, end))
        conn.commit()

    _reverse_load_by_member(rows, stress_increase)


def _reverse_load_by_member(removed_assignment_rows, stress_increase: float = 1.0):
    """Subtract the load contribution of each removed assignment from its member.

    Batches per member so each member's load_stress is only written once,
    even if several of their assignments were removed together.
    """
    totals = {}
    for r in removed_assignment_rows:
        load_inc = compute_load_increment(r['zone'], r['importance'], stress_increase)
        totals[r['member_id']] = totals.get(r['member_id'], 0.0) + load_inc

    for member_id, total in totals.items():
        adjust_member_load_stress(member_id, -round(total, 2))


def delete_coordinators_in_range(start: str, end: str):
    with get_conn() as conn:
        conn.execute('''
            DELETE FROM event_coordinators
            WHERE event_id IN (SELECT id FROM events WHERE date BETWEEN ? AND ?)
        ''', (start, end))
        conn.commit()
