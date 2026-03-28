"""Availability parsing helpers for weekday-based member constraints."""

_WEEKDAY_ALIASES = {
    # EN
    'monday': 0, 'mon': 0,
    'tuesday': 1, 'tue': 1, 'tues': 1,
    'wednesday': 2, 'wed': 2,
    'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
    'friday': 4, 'fri': 4,
    'saturday': 5, 'sat': 5,
    'sunday': 6, 'sun': 6,
    # PT
    'segunda': 0, 'segunda-feira': 0, 'seg': 0,
    'terca': 1, 'terça': 1, 'terça-feira': 1, 'terca-feira': 1, 'ter': 1,
    'quarta': 2, 'quarta-feira': 2, 'qua': 2,
    'quinta': 3, 'quinta-feira': 3, 'qui': 3,
    'sexta': 4, 'sexta-feira': 4, 'sex': 4,
    'sabado': 5, 'sábado': 5, 'sábado-feira': 5, 'sab': 5, 'sáb': 5,
    'domingo': 6, 'dom': 6,
    # numbers
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
}


def _parse_availability_csv(s: str):
    if not s:
        return set()
    toks = [t.strip().lower() for t in s.split(',') if t.strip()]
    out = set()
    for t in toks:
        if t in _WEEKDAY_ALIASES:
            out.add(_WEEKDAY_ALIASES[t])
    return out

