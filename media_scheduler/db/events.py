"""Repository functions for events and fixed monthly event generation."""

import calendar
from datetime import date

from media_scheduler.db.connection import get_conn


def add_event_db(name: str, date_str: str, importance: int = 1):
    with get_conn() as conn:
        conn.execute('INSERT INTO events (name, date, importance) VALUES (?, ?, ?)', (name, date_str, importance))
        conn.commit()


def list_events_db(start: str = None, end: str = None):
    q = 'SELECT * FROM events'
    params = ()
    if start and end:
        q += ' WHERE date BETWEEN ? AND ?'
        params = (start, end)
    q += ' ORDER BY date, importance DESC'
    with get_conn() as conn:
        return conn.execute(q, params).fetchall()


def delete_event_db(event_id: int):
    with get_conn() as conn:
        conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
        conn.commit()


def delete_all_events_db():
    with get_conn() as conn:
        conn.execute('DELETE FROM events')
        conn.commit()


def delete_events_for_month(year: int, month: int):
    start = date(int(year), int(month), 1).isoformat()
    if int(month) == 12:
        end = date(int(year) + 1, 1, 1).isoformat()
    else:
        end = date(int(year), int(month) + 1, 1).isoformat()

    with get_conn() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM events WHERE date >= ? AND date < ?', (start, end))
        deleted = c.rowcount
        conn.commit()
    return deleted


def generate_fixed_events_for_month(year: int, month: int):
    """
    Regras:
      - Todo domingo:
          * 1º domingo = Ceia (importância 10)
          * demais domingos = Culto da Família (importância 8)
      - Toda quarta:
          * 2ª quarta do mês = Quarta em Família (importância 8)
          * outras quartas = Culto da Palavra (importância 6)
      - Todo sábado:
          * 2º sábado = Culto de Mulheres (importância 7)
          * 3º sábado = Revolution (importância 7)
      - Evita duplicar por data.
    """
    _, ndays = calendar.monthrange(year, month)
    created = []

    sunday_count = 0
    wednesday_count = 0
    saturday_count = 0

    with get_conn() as conn:
        c = conn.cursor()

        for d in range(1, ndays + 1):
            dt = date(year, month, d)
            wd = dt.weekday()  # Mon=0 ... Sun=6
            ds = dt.isoformat()

            exists = c.execute('SELECT 1 FROM events WHERE date = ? LIMIT 1', (ds,)).fetchone()
            if exists:
                continue

            name = None
            imp = None

            if wd == 6:
                sunday_count += 1
                if sunday_count == 1:
                    name = f'Ceia - Domingo {ds}'
                    imp = 10
                else:
                    name = f'Culto da Família - Domingo {ds}'
                    imp = 8

            elif wd == 2:
                wednesday_count += 1
                if wednesday_count == 2:
                    name = f'Quarta em Família - Quarta {ds}'
                    imp = 8
                else:
                    name = f'Culto da Palavra - Quarta {ds}'
                    imp = 6

            elif wd == 5:
                saturday_count += 1
                if saturday_count == 2:
                    name = f'Culto de Mulheres - Sábado {ds}'
                    imp = 7
                elif saturday_count == 3:
                    name = f'Revolution - Sábado {ds}'
                    imp = 7

            if not name:
                continue

            c.execute(
                'INSERT INTO events (name, date, importance) VALUES (?, ?, ?)',
                (name, ds, int(imp))
            )
            created.append((ds, name, int(imp)))

        conn.commit()

    return created



