"""Coordinator selection logic among already assigned event members."""

import random


def choose_coordinator(assigned_member_ids: list[int], member_map: dict) -> int | None:
    """
    Coordinator must be one of the already assigned members for that event.
    Picks the highest coord_level; ties are randomized.
    """
    ids = [mid for mid in assigned_member_ids if mid is not None]
    if not ids:
        return None
    best_level = None
    best_ids: list[int] = []
    for mid in ids:
        lvl = int(member_map.get(mid, {}).get("coord_level", 0) or 0)
        if best_level is None or lvl > best_level:
            best_level = lvl
            best_ids = [mid]
        elif lvl == best_level:
            best_ids.append(mid)
    return random.choice(best_ids) if best_ids else None

