"""Repository functions for members and member blackout dates."""

from media_scheduler.config import LOAD_CAP
from media_scheduler.db.connection import get_conn


def _zone_to_col(zone: str) -> str:
    if zone == 'live':
        return 'live_level'
    if zone == 'luzes':
        return 'luzes_level'
    return 'slide_level'


def set_member_coord_level(member_id: int, value: int):
    with get_conn() as conn:
        conn.execute('UPDATE members SET coord_level = ? WHERE id = ?', (int(value), member_id))
        conn.commit()


def set_member_max_days_per_month(member_id: int, value: int | None):
    with get_conn() as conn:
        conn.execute('UPDATE members SET max_days_per_month = ? WHERE id = ?', (value, member_id))
        conn.commit()


def add_blackout_db(member_id: int, date_str: str, note: str = ''):
    with get_conn() as conn:
        conn.execute('''
            INSERT INTO member_blackouts (member_id, date, note)
            VALUES (?, ?, ?)
            ON CONFLICT(member_id, date) DO UPDATE SET note = excluded.note
        ''', (member_id, date_str, note))
        conn.commit()


def delete_blackout_db(member_id: int, date_str: str):
    with get_conn() as conn:
        conn.execute('DELETE FROM member_blackouts WHERE member_id = ? AND date = ?', (member_id, date_str))
        conn.commit()


def list_blackouts_for_member_db(member_id: int):
    with get_conn() as conn:
        return conn.execute(
            'SELECT date, note FROM member_blackouts WHERE member_id = ? ORDER BY date',
            (member_id,)
        ).fetchall()


def add_member(name: str, live: int, luzes: int, slide: int, coord_level: int = 0,
               stress: float = 0.0, availability: str = '', phone: str = ''):
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO members (name, live_level, luzes_level, slide_level, coord_level, stress, load_stress, max_days_per_month, availability, phone) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (name, live, luzes, slide, coord_level, round(float(stress), 2), 0.0, None, availability, phone)
        )
        conn.commit()


def update_member_full(member_id: int, name: str, phone: str, live: int, luzes: int, slide: int,
                       coord: int, stress: float, max_days: int | None, availability: str):
    with get_conn() as conn:
        conn.execute('''
            UPDATE members
            SET name = ?, phone = ?, live_level = ?, luzes_level = ?, slide_level = ?,
                coord_level = ?, stress = ?, max_days_per_month = ?, availability = ?
            WHERE id = ?
        ''', (name, phone, live, luzes, slide, coord, round(float(stress), 2), max_days, availability, member_id))
        conn.commit()


def set_member_phone(member_id: int, phone: str):
    with get_conn() as conn:
        conn.execute('UPDATE members SET phone = ? WHERE id = ?', (phone.strip(), member_id))
        conn.commit()


def list_members_db():
    with get_conn() as conn:
        return conn.execute('SELECT * FROM members ORDER BY name').fetchall()


def delete_member_db(member_id: int):
    with get_conn() as conn:
        conn.execute('DELETE FROM members WHERE id = ?', (member_id,))
        conn.commit()


def delete_all_members_db():
    with get_conn() as conn:
        conn.execute('DELETE FROM members')
        conn.commit()


def update_member_level(member_id: int, zone: str, level: int):
    col = _zone_to_col(zone)
    with get_conn() as conn:
        conn.execute(f'UPDATE members SET {col} = ? WHERE id = ?', (level, member_id))
        conn.commit()


def set_member_stress(member_id: int, value: float):
    with get_conn() as conn:
        conn.execute('UPDATE members SET stress = ? WHERE id = ?', (round(float(value), 2), member_id))
        conn.commit()


def set_member_availability(member_id: int, availability_csv: str):
    with get_conn() as conn:
        conn.execute('UPDATE members SET availability = ? WHERE id = ?', (availability_csv, member_id))
        conn.commit()


def _clamp_load(value: float) -> float:
    return round(max(0.0, min(float(LOAD_CAP), float(value))), 2)


def adjust_member_load_stress(member_id: int, delta: float):
    """
    Nudge a member's dynamic load_stress by `delta` (positive or negative),
    clamped to [0, LOAD_CAP].
    """
    with get_conn() as conn:
        row = conn.execute('SELECT load_stress FROM members WHERE id = ?', (member_id,)).fetchone()
        if row is None:
            return
        new_val = _clamp_load(float(row['load_stress'] or 0.0) + delta)
        conn.execute('UPDATE members SET load_stress = ? WHERE id = ?', (new_val, member_id))
        conn.commit()
