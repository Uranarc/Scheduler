# Media Scheduler

Python desktop app to manage media-team members, events, and automatic scheduling.

## Repository layout

```text
PythonProject1/
├─ media_scheduler/           # Main application package
│  ├─ main.py                 # App entry point
│  ├─ config.py               # Scheduling constants
│  ├─ db/                     # SQLite access layer
│  ├─ scheduler/              # Scheduling algorithm
│  ├─ gui/                    # CustomTkinter UI
│  ├─ utils/                  # Shared helpers/formatting
│  ├─ export.py               # CSV export
│  ├─ requirements.txt        # Runtime dependencies
│  └─ README.md               # Detailed app docs
├─ media_scheduler_legacy.py  # Legacy monolithic version (reference)
└─ .gitignore
```

## Quick start

```bash
cd media_scheduler
pip install -r requirements.txt
python main.py
```

## What is documented where

- `media_scheduler/README.md`: detailed usage, constants, availability and blackout formats.
- `CONTRIBUTING.md`: coding and PR guidelines.
- `CHANGELOG.md`: release notes.

## Notes for GitHub presentation

- Keep source code inside `media_scheduler/`.
- Keep generated/local files out of Git via `.gitignore`.
- Use issues + pull requests for changes so history stays clean.

## License

This repository is licensed under the MIT License. See `LICENSE`.

