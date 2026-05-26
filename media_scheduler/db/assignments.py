"""Repository functions for assignments, coordinator cleanup, and dashboard summaries."""

from datetime import UTC, datetime

from media_scheduler.db.connection import get_conn
from media_scheduler.db.members import recalculate_member_load_stress


def list_assignments_db(start: str = None, end: str = None):
    q = '''SELECT a.id as aid, e.date as evdate, e.name as evname, a.zone as zone,
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


def update_assignment_member(assignment_id: int, member_id: int):
    with get_conn() as conn:
        # Get old member id first
        old_mid = conn.execute('SELECT member_id FROM assignments WHERE id = ?', (assignment_id,)).fetchone()
        if old_mid:
            old_mid = old_mid['member_id']

        conn.execute('UPDATE assignments SET member_id = ? WHERE id = ?', (member_id, assignment_id))
        conn.commit()

    # Recalculate both old and new member's loads
    if old_mid and old_mid != member_id:
        recalculate_member_load_stress(old_mid)
    recalculate_member_load_stress(member_id)


def add_assignment_manual(event_id: int, zone: str, member_id: int):
    with get_conn() as conn:
        conn.execute('''
            INSERT INTO assignments (event_id, zone, member_id, assigned_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(event_id, zone) DO UPDATE SET
                member_id = excluded.member_id,
                assigned_at = excluded.assigned_at
        ''', (event_id, zone, member_id, datetime.now(UTC).isoformat()))
        conn.commit()

    recalculate_member_load_stress(member_id)


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
            'load_stress': float(r['load_stress'] or 0.0),
            'manual_stress': float(r['manual_stress'] or 0.0),
            'max_days': (None if max_days is None else int(max_days)),
            'days_remaining': days_remaining,
            'over_limit': (max_days is not None and total_days > int(max_days)),
        })
    return out


def delete_assignment_db(assignment_id: int):
    with get_conn() as conn:
        # Get member id before deletion
        row = conn.execute('SELECT member_id FROM assignments WHERE id = ?', (assignment_id,)).fetchone()
        member_id = int(row['member_id']) if row else None

        conn.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))
        conn.commit()

    if member_id is not None:
        recalculate_member_load_stress(member_id)


def delete_all_assignments_db():
    with get_conn() as conn:
        # Get all member ids
        member_ids = conn.execute('SELECT DISTINCT member_id FROM assignments').fetchall()
        conn.execute('DELETE FROM assignments')
        conn.commit()

    # Recalculate all members
    for r in member_ids:
        recalculate_member_load_stress(r['member_id'])


def delete_assignments_in_range(start: str, end: str):
    with get_conn() as conn:
        # Get all member ids affected
        member_ids = conn.execute('''
            SELECT DISTINCT a.member_id
            FROM assignments a
            JOIN events e ON a.event_id = e.id
            WHERE e.date BETWEEN ? AND ?
        ''', (start, end)).fetchall()

        conn.execute('''
            DELETE FROM assignments
            WHERE event_id IN (SELECT id FROM events WHERE date BETWEEN ? AND ?)
        ''', (start, end))
        conn.commit()

    # Recalculate affected members
    for r in member_ids:
        recalculate_member_load_stress(r['member_id'])


def delete_coordinators_in_range(start: str, end: str):
    with get_conn() as conn:
        conn.execute('''
            DELETE FROM event_coordinators
            WHERE event_id IN (SELECT id FROM events WHERE date BETWEEN ? AND ?)
        ''', (start, end))
        conn.commit()

