# Media Scheduler

A CustomTkinter + SQLite app for managing media-team members, events, and automated assignment generation.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## UI stack

- `customtkinter`: modern dark-themed desktop UI components
- `matplotlib`: dashboard bar chart rendering

## Constants in `config.py`

- `DB_FILENAME`: SQLite database filename used by the app.
- `ZONES`: Assignment zones generated for each event (`slide`, `luzes`, `live`).
- `ZONE_WEIGHTS`: Relative weighting per zone in scoring.
- `MANUAL_STRESS_WEIGHT`: Weight applied to `members.stress` (manual/base stress) in score penalty.
- `LOAD_STRESS_WEIGHT`: Weight applied to `members.load_stress` (dynamic load stress) in score penalty.
- `LOAD_DECAY`: Multiplier applied to dynamic load at generation start.
- `LOAD_CAP`: Maximum allowed dynamic load value per member.
- `MIN_SKILL`: Minimum skill needed to be eligible for a zone.
- `LAST_EVENTS_WINDOW`: Number of prior events considered for repeat penalties.
- `EVENT_REPEAT_PENALTY`: Penalty when a member appears repeatedly in recent events.
- `ZONE_REPEAT_PENALTY`: Penalty when a member repeats the same zone as last assignment.
- `SAME_DAY_TEAM_PENALTY`: Penalty when member was part of previous event's team.
- `RANDOM_JITTER`: Small random score jitter to break ties.
- `SEED_MEMBERS`: Initial member tuples inserted when the members table is empty.

## Availability field format

The `availability` value is a comma-separated list of allowed weekdays.
If empty, the member is considered available every day.

Accepted inputs:
- English names/abbreviations: `sunday`, `wednesday,sunday`, `mon,thu`
- Portuguese names/abbreviations: `quarta,domingo`, `seg,qui`
- Numeric weekdays (Mon=0 ... Sun=6): `2,6`

Examples:
- `sunday`
- `quarta,domingo`
- `2,6`
- `` (empty string means always available)

## Blackout dates format

Blackout dates are explicit unavailable calendar dates per member.

Format:
- `yyyy-mm-dd`
- Multiple dates separated by commas

Examples:
- `2026-02-01`
- `2026-02-01, 2026-02-15`
- Empty input clears all blackout dates for that member

