"""Configuration constants used across scheduling, DB, and GUI modules."""

DB_FILENAME = 'media_scheduler.db'

ZONES = ['slide', 'luzes', 'live']
ZONE_WEIGHTS = {'slide': 3.0, 'luzes': 2.0, 'live': 1.0}

# Stress model (manual has slightly higher weight)
MANUAL_STRESS_WEIGHT = 1.1
LOAD_STRESS_WEIGHT = 0.9

# Dynamic load behavior (carry-over with decay, no infinite growth)
LOAD_DECAY = 0.6     # keeps 60% of last load each new generation
LOAD_CAP = 20.0      # hard cap to avoid runaway values

# --- Fairness / Variety knobs (ajustaveis) ---
MIN_SKILL = 1                 # skill 0 NAO entra naquela zona (evita "0 na live indo pra live")
LAST_EVENTS_WINDOW = 3        # quantos ultimos eventos contam como "recente" (variedade)
EVENT_REPEAT_PENALTY = 4.0    # penaliza membro repetido em eventos recentes
ZONE_REPEAT_PENALTY = 3.0     # penaliza repetir mesma zona do ultimo servico
SAME_DAY_TEAM_PENALTY = 8.0   # penaliza estar no time do evento anterior (forca trocar alguem)
RANDOM_JITTER = 0.25          # aleatoriedade pequena p/ desempate (0..0.5)

# Seed members: name, live, luzes, slide, availability, coord_level
SEED_MEMBERS = [
    ("Daniel", 8, 6, 10, "sunday", 5),
    ("Isaac", 9, 8, 7, "", 7),
    ("Ivan", 0, 5, 0, "", 4),
    ("Joyce", 7, 0, 7, "sunday", 6),
    ("Kaciane", 7, 0, 8, "wednesday,saturday", 6),
    ("Luis Gustavo", 7, 3, 9, "", 6),
    ("Mirian", 7, 0, 7, "", 7),
    ("Nayara", 8, 7, 7, "", 7),
    ("Oriana", 6, 0, 0, "sunday", 6),
    ("Raama", 7, 0, 8, "sunday", 6),
    ("Samuel", 0, 9, 0, "sunday", 7),
]

