"""General helper utilities for parsing values, dates, and formatting Portuguese dates."""

from datetime import date, datetime
from media_scheduler.scheduler.availability import _parse_availability_csv

PT_WEEKDAYS_FULL = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sábado",
    6: "Domingo",
}

PT_WEEKDAYS_SHORT = {
    0: "Seg",
    1: "Ter",
    2: "Qua",
    3: "Qui",
    4: "Sex",
    5: "Sáb",
    6: "Dom",
}

PT_WEEKDAYS_MEDIUM = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
}

PT_MONTHS = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def parse_date_input(val: str | None) -> date | None:
    """Parse flexible date input formats into a date object.
    
    Accepts dd-mm-yyyy, dd/mm/yyyy, dd.mm.yyyy, yyyy-mm-dd, yyyy/mm/dd.
    """
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None

    formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%y",
        "%d/%m/%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def to_db_date(val: str | date | None) -> str:
    """Convert any supported date input or date object to DB ISO format (yyyy-mm-dd)."""
    if val is None:
        return ""
    if isinstance(val, date):
        return val.isoformat()
    parsed = parse_date_input(val)
    if parsed:
        return parsed.isoformat()
    return str(val).strip()


def to_display_date(val: str | date | None) -> str:
    """Convert any date input or DB ISO date to standard Portuguese display format (dd-mm-yyyy)."""
    if val is None:
        return ""
    if isinstance(val, date):
        return val.strftime("%d-%m-%Y")
    parsed = parse_date_input(val)
    if parsed:
        return parsed.strftime("%d-%m-%Y")
    return str(val).strip()


def _next_month_reference(reference_date: date | None = None) -> tuple[int, int]:
    base = reference_date or date.today()
    year = base.year
    month = base.month + 1
    if month == 13:
        month = 1
        year += 1
    return year, month


def _next_month_reference_date(reference_date: date | None = None) -> date:
    year, month = _next_month_reference(reference_date)
    return date(year, month, 1)


def _safe_int(s: str, default=0):
    s = (s or '').strip()
    if s == '':
        return default
    return int(s)


def _safe_float(s: str, default=0.0):
    s = (s or '').strip()
    if s == '':
        return round(float(default), 2)
    return round(float(s), 2)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _pt_weekday_name(d: date) -> str:
    return PT_WEEKDAYS_FULL.get(d.weekday(), "")


def _format_pt_date(d: date) -> str:
    return d.strftime("%d/%m")


def normalize_availability_display(avail_str: str) -> str:
    """Convert raw availability string into standardized Portuguese weekday names."""
    if not avail_str:
        return "Sempre"
    days = _parse_availability_csv(avail_str)
    if not days:
        return avail_str
    if len(days) == 7:
        return "Sempre"
    return ", ".join(PT_WEEKDAYS_MEDIUM[d] for d in sorted(days))
