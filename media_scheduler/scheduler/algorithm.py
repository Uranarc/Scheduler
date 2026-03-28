"""Core scheduling algorithm and helper functions for assignment generation."""

import random
from datetime import UTC, date, datetime, timedelta

from media_scheduler.config import (
    EVENT_REPEAT_PENALTY,
    LAST_EVENTS_WINDOW,
    LOAD_CAP,
    LOAD_DECAY,
    LOAD_STRESS_WEIGHT,
    MANUAL_STRESS_WEIGHT,
    MIN_SKILL,
    RANDOM_JITTER,
    SAME_DAY_TEAM_PENALTY,
    ZONES,
    ZONE_REPEAT_PENALTY,
    ZONE_WEIGHTS,
)
from media_scheduler.db.assignments import delete_assignments_in_range, delete_coordinators_in_range
from media_scheduler.db.connection import get_conn
from media_scheduler.db.events import list_events_db
from media_scheduler.db.members import list_members_db
from media_scheduler.scheduler.availability import _parse_availability_csv
from media_scheduler.scheduler.coordinators import choose_coordinator


def _load_helpers(sdate: date, edate: date):
    """
    Returns:
      member_map, skills, avail, recent_map, blackout_map, limits_map,
      last_zone_by_member, event_members_by_date
    """
    members = list_members_db()
    member_map = {m['id']: dict(m) for m in members}

    skills = {
        m['id']: {'live': m['live_level'], 'luzes': m['luzes_level'], 'slide': m['slide_level']}
        for m in members
    }
    avail = {m['id']: _parse_availability_csv(m['availability'] or '') for m in members}

    # Pegamos histórico maior pra variedade
    hist_start = (sdate - timedelta(days=90)).isoformat()
    hist_end = (edate + timedelta(days=1)).isoformat()

    with get_conn() as conn:
        rows = conn.execute('''
            SELECT a.member_id as mid, a.zone as zone, e.date as ed
            FROM assignments a
            JOIN events e ON a.event_id = e.id
            WHERE e.date BETWEEN ? AND ?
            ORDER BY e.date
        ''', (hist_start, hist_end)).fetchall()

        b = conn.execute('''
            SELECT member_id as mid, date as d
            FROM member_blackouts
            WHERE date BETWEEN ? AND ?
        ''', (sdate.isoformat(), edate.isoformat())).fetchall()

    recent_map = {}
    last_zone_by_member = {}
    event_members_by_date = {}

    for r in rows:
        mid = r['mid']
        d = datetime.strptime(r['ed'], '%Y-%m-%d').date()
        recent_map.setdefault(mid, []).append(d)
        last_zone_by_member[mid] = r['zone']
        event_members_by_date.setdefault(d, set()).add(mid)

    blackout_map = {}
    for r in b:
        blackout_map.setdefault(r['mid'], set()).add(datetime.strptime(r['d'], '%Y-%m-%d').date())

    limits = {m['id']: (m['max_days_per_month'] if m['max_days_per_month'] is not None else None) for m in members}

    return member_map, skills, avail, recent_map, blackout_map, limits, last_zone_by_member, event_members_by_date


def _is_available_cached(mid: int, ev_date: date, avail_map) -> bool:
    allowed = avail_map.get(mid, set())
    if not allowed:
        return True
    return ev_date.weekday() in allowed


def generate_schedule_db(
    start: str,
    end: str,
    stress_increase: float = 1.0,
    stress_penalty: float = 1.0,
    recent_penalty: float = 0.3,
    cooldown_days: int = 0,
    *,
    clear_existing_in_range: bool = True,
):
    """
    Stress model:
      - members.stress      : manual/base (you set)
      - members.load_stress : dynamic carry-over across months with decay
      - scoring uses: stress_total = 1.1*manual + 0.9*load
      - at generation start: load *= LOAD_DECAY
      - during generation: load += computed load per assignment
      - load is capped at LOAD_CAP and persisted
      - manual stress is never overwritten

    Plus:
      - Blackout per date (member_blackouts)
      - Max days per month (members.max_days_per_month)
      - Coordinator per event (event_coordinators) chosen among assigned members only

    Variety fixes:
      - skill 0 is not allowed (MIN_SKILL)
      - penalties for repeating members in last N events
      - penalty for repeating same zone
      - penalty for being in previous event team (forces variation)
      - small random jitter for tie-breaking
    """
    sdate = datetime.strptime(start, '%Y-%m-%d').date()
    edate = datetime.strptime(end, '%Y-%m-%d').date()

    if clear_existing_in_range:
        delete_assignments_in_range(start, end)
        delete_coordinators_in_range(start, end)

    events = list_events_db(start, end)
    if not events:
        return {'assignments': [], 'coordinators': {}, 'final_stresses': {}, 'missing': []}

    (
        member_map, skills, avail_map, recent_map,
        blackout_map, limits_map, last_zone_by_member, event_members_by_date
    ) = _load_helpers(sdate, edate)

    max_importance = max(ev['importance'] for ev in events) if events else 1

    # normalize member fields
    for mid, m in member_map.items():
        m['stress'] = float(m.get('stress', 0.0) or 0.0)
        m['load_stress'] = float(m.get('load_stress', 0.0) or 0.0)
        m['coord_level'] = int(m.get('coord_level', 0) or 0)

    # Event dates within this generation range (for variety penalties)
    event_dates_sorted = sorted({datetime.strptime(ev['date'], '%Y-%m-%d').date() for ev in events})

    def recent_count(mid: int, ref_date: date, days: int = 30) -> int:
        dates = recent_map.get(mid, [])
        cutoff = ref_date - timedelta(days=days)
        return sum(1 for d in dates if cutoff <= d < ref_date)

    def has_nearby_past(mid: int, ev_date: date, days: int) -> bool:
        for d in recent_map.get(mid, []):
            if d < ev_date and (ev_date - d).days <= days:
                return True
        return False

    def is_blackout(mid: int, ev_date: date) -> bool:
        return ev_date in blackout_map.get(mid, set())

    # Track per-month distinct dates served (days, not zones)
    served_days = {mid: {} for mid in member_map.keys()}  # mid -> {(year,month): set(dates)}

    assignments = []
    missing = []
    coordinators = {}  # event_id -> member_name

    with get_conn() as conn:
        c = conn.cursor()

        # 1) decay load only for members that can appear in at least one event in this range
        candidate_member_ids = set()
        for ev in events:
            ev_date = datetime.strptime(ev['date'], '%Y-%m-%d').date()
            for mid in member_map.keys():
                if not _is_available_cached(mid, ev_date, avail_map):
                    continue
                if is_blackout(mid, ev_date):
                    continue
                if any(float(skills.get(mid, {}).get(zone, 0.0)) >= MIN_SKILL for zone in ZONES):
                    candidate_member_ids.add(mid)

        if candidate_member_ids:
            mids = sorted(candidate_member_ids)
            placeholders = ','.join('?' for _ in mids)
            c.execute(
                f'UPDATE members SET load_stress = load_stress * ? WHERE id IN ({placeholders})',
                (float(LOAD_DECAY), *mids)
            )
            conn.commit()

        # reload manual/load after decay
        rows = conn.execute('SELECT id, stress, load_stress, coord_level FROM members').fetchall()
        for r in rows:
            mid = r['id']
            if mid in member_map:
                member_map[mid]['stress'] = float(r['stress'] or 0.0)
                member_map[mid]['load_stress'] = float(r['load_stress'] or 0.0)
                member_map[mid]['coord_level'] = int(r['coord_level'] or 0)

        # Preload served days from DB for the window (range)
        pre = conn.execute('''
            SELECT a.member_id as mid, e.date as d
            FROM assignments a
            JOIN events e ON a.event_id = e.id
            WHERE e.date BETWEEN ? AND ?
        ''', (sdate.isoformat(), edate.isoformat())).fetchall()
        for r in pre:
            mid = r['mid']
            d = datetime.strptime(r['d'], '%Y-%m-%d').date()
            key = (d.year, d.month)
            served_days.setdefault(mid, {}).setdefault(key, set()).add(d)

        for ev in events:
            ev_date = datetime.strptime(ev['date'], '%Y-%m-%d').date()

            assigned_today = set(event_members_by_date.get(ev_date, set()))
            assigned_this_event = set()
            assigned_members_for_event: list[int] = []

            for zone in ZONES:
                best = None
                best_score = float('-inf')

                # dates anteriores dentro do range (pra penalidade de time)
                prev_dates = [d for d in event_dates_sorted if d < ev_date]
                last_window = prev_dates[-LAST_EVENTS_WINDOW:] if prev_dates else []
                last_date = prev_dates[-1] if prev_dates else None
                last_team = event_members_by_date.get(last_date, set()) if last_date else set()

                for mid, m in member_map.items():
                    if mid in assigned_this_event:
                        continue
                    if mid in assigned_today:
                        continue
                    if not _is_available_cached(mid, ev_date, avail_map):
                        continue
                    if cooldown_days > 0 and has_nearby_past(mid, ev_date, cooldown_days):
                        continue
                    if is_blackout(mid, ev_date):
                        continue

                    # monthly max days
                    limit = limits_map.get(mid, None)
                    if limit is not None and limit >= 0:
                        key = (ev_date.year, ev_date.month)
                        days_set = served_days.get(mid, {}).get(key, set())
                        would_be = len(days_set) + (0 if ev_date in days_set else 1)
                        if would_be > limit:
                            continue

                    skill = float(skills.get(mid, {}).get(zone, 0.0))

                    # HARD rule: nao escala skill 0
                    if skill < MIN_SKILL:
                        continue

                    manual = float(m.get('stress', 0.0))
                    load = float(m.get('load_stress', 0.0))
                    stress_total = (MANUAL_STRESS_WEIGHT * manual) + (LOAD_STRESS_WEIGHT * load)

                    recent = recent_count(mid, ev_date, 30)
                    zw = float(ZONE_WEIGHTS.get(zone, 1.0))

                    base = zw * skill * (1 + 0.1 * (ev['importance'] - 1))
                    stress_penalty_effective = stress_penalty * (1 + max(0, (max_importance - ev['importance'])) * 0.5)

                    # Variety penalties
                    repeat_in_last_events = sum(1 for d in last_window if mid in event_members_by_date.get(d, set()))
                    repeat_pen = repeat_in_last_events * EVENT_REPEAT_PENALTY

                    zone_pen = ZONE_REPEAT_PENALTY if (last_zone_by_member.get(mid) == zone) else 0.0

                    same_team_pen = SAME_DAY_TEAM_PENALTY if (mid in last_team) else 0.0

                    score = (
                        base
                        - (stress_total * stress_penalty_effective)
                        - (recent * recent_penalty)
                        - repeat_pen
                        - zone_pen
                        - same_team_pen
                    )

                    score += random.uniform(-RANDOM_JITTER, RANDOM_JITTER)

                    if score > best_score:
                        best_score = score
                        best = mid

                if best is None:
                    missing.append((ev['id'], ev['date'], ev['name'], zone))
                    continue

                c.execute('''
                    INSERT INTO assignments (event_id, zone, member_id, assigned_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(event_id, zone) DO UPDATE SET
                        member_id = excluded.member_id,
                        assigned_at = excluded.assigned_at
                ''', (ev['id'], zone, best, datetime.now(UTC).isoformat()))

                mname = member_map[best]['name']
                assignments.append((ev['id'], ev['date'], ev['name'], zone, best, mname))

                assigned_this_event.add(best)
                assigned_today.add(best)
                assigned_members_for_event.append(best)

                # update caches for next decisions
                last_zone_by_member[best] = zone
                event_members_by_date.setdefault(ev_date, set()).add(best)

                key = (ev_date.year, ev_date.month)
                served_days.setdefault(best, {}).setdefault(key, set()).add(ev_date)

                # add dynamic load
                zw = float(ZONE_WEIGHTS.get(zone, 1.0))
                load_inc = float(stress_increase) * (1 + 0.3 * (ev['importance'] - 1)) * (1 + 0.2 * (zw - 1))
                current_load = float(member_map[best].get('load_stress', 0.0))
                member_map[best]['load_stress'] = min(float(LOAD_CAP), current_load + load_inc)

                recent_map.setdefault(best, []).append(ev_date)

            # --- coordinator: MUST be among assigned members for this event ---
            coord_mid = choose_coordinator(assigned_members_for_event, member_map)
            if coord_mid is not None:
                c.execute('''
                    INSERT INTO event_coordinators (event_id, member_id, assigned_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(event_id) DO UPDATE SET
                        member_id = excluded.member_id,
                        assigned_at = excluded.assigned_at
                ''', (ev['id'], coord_mid, datetime.now(UTC).isoformat()))
                coordinators[ev['id']] = member_map[coord_mid]['name']

        conn.commit()

        # persist load stress capped
        for mid in member_map.keys():
            new_val = min(float(LOAD_CAP), float(member_map[mid].get('load_stress', 0.0)))
            member_map[mid]['load_stress'] = new_val
            c.execute('UPDATE members SET load_stress = ? WHERE id = ?', (new_val, mid))

        conn.commit()

    final_stresses = {
        mid: {
            "manual": float(member_map[mid].get('stress', 0.0)),
            "load": float(member_map[mid].get('load_stress', 0.0)),
            "total": (MANUAL_STRESS_WEIGHT * float(member_map[mid].get('stress', 0.0))) +
                     (LOAD_STRESS_WEIGHT * float(member_map[mid].get('load_stress', 0.0))),
        }
        for mid in member_map.keys()
    }

    return {
        'assignments': assignments,
        'coordinators': coordinators,
        'final_stresses': final_stresses,
        'missing': missing
    }


