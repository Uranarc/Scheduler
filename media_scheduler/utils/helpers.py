"""General helper utilities for parsing values and formatting Portuguese dates."""

from datetime import date


def _safe_int(s: str, default=0):
    s = (s or '').strip()
    if s == '':
        return default
    return int(s)


def _safe_float(s: str, default=0.0):
    s = (s or '').strip()
    if s == '':
        return default
    return float(s)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _pt_weekday_name(d: date) -> str:
    return {
        0: "Segunda-feira",
        1: "Terça-feira",
        2: "Quarta-feira",
        3: "Quinta-feira",
        4: "Sexta-feira",
        5: "Sábado",
        6: "Domingo",
    }[d.weekday()]


def _format_pt_date(d: date) -> str:
    return d.strftime("%d/%m")

