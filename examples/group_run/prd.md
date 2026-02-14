# Group Run: Running Activity Logger

**Project:** group_run
**Version:** 0.1.0
**Status:** Draft

---

## Overview

A CLI application for logging running activities. Users can record runs with distance, time, and date, view their running history, and see summary statistics. This project serves as a multi-module SquadOps build example targeting a realistic application structure.

---

## Requirements

### Commands

The application provides four commands:

| Command | Description |
|---------|-------------|
| `log` | Record a new running activity |
| `history` | Display all logged runs in chronological order |
| `stats` | Show summary statistics (total distance, average pace, etc.) |
| `delete` | Remove a run by its ID |

### Log Command

```bash
python -m group_run log --distance 5.0 --time 25:30 --date 2026-01-15
```

- `--distance` (required): Distance in kilometers (float)
- `--time` (required): Duration in `MM:SS` or `HH:MM:SS` format
- `--date` (optional): Date of the run, defaults to today (ISO 8601 format)

Each logged run is assigned a sequential integer ID.

### History Command

```bash
python -m group_run history
```

Prints a table of all runs:
```
ID  Date        Distance  Time     Pace
1   2026-01-15  5.00 km   25:30    5:06/km
2   2026-01-16  10.00 km  52:00    5:12/km
```

### Stats Command

```bash
python -m group_run stats
```

Prints summary statistics:
- Total runs
- Total distance (km)
- Total time
- Average pace (min/km)
- Longest run (by distance)
- Fastest pace

### Data Storage

- Runs are stored in a JSON file (`runs.json`) in the current directory
- The file is created automatically on first `log` command
- File format: JSON array of run objects

---

## Technical Constraints

- **Language:** Python 3.11+
- **Dependencies:** Standard library only (`argparse`, `json`, `datetime`, `pathlib`)
- **Entry point:** `python -m group_run`
- **No global mutable state** — pass data store path explicitly

---

## File Structure

```
group_run/
    __init__.py
    __main__.py     # Entry point, argument parsing
    models.py       # RunRecord dataclass
    store.py        # JSON file read/write operations
    stats.py        # Statistics computation
    display.py      # Table formatting and output
```

---

## Acceptance Criteria

1. `log` command creates a run entry with correct distance, time, and date
2. `history` command displays all runs in a formatted table
3. `stats` command shows correct aggregate statistics
4. `delete` command removes a run by ID
5. Data persists across command invocations via `runs.json`
6. Invalid inputs (negative distance, malformed time) produce clear error messages
7. All modules have corresponding unit tests
