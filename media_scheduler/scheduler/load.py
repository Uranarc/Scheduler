"""Shared formula for a single assignment's contribution to dynamic load (load_stress).

Used both when generating a schedule automatically (scheduler/algorithm.py) and
when adjusting load_stress after a manual assignment edit (db/assignments.py),
so the two code paths can never drift apart again.
"""

from media_scheduler.config import ZONE_WEIGHTS


def compute_load_increment(zone: str, importance: int, stress_increase: float = 1.0) -> float:
    """
    Higher-importance events and higher-weighted zones (see config.ZONE_WEIGHTS)
    increase load more. This is the per-assignment increment; callers are
    responsible for decay and capping (see config.LOAD_DECAY / config.LOAD_CAP).
    """
    zw = float(ZONE_WEIGHTS.get(zone, 1.0))
    return round(float(stress_increase) * (1 + 0.3 * (float(importance) - 1)) * (1 + 0.2 * (zw - 1)), 2)
