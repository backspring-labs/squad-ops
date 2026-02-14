# Hello Squad: CLI Greeting Script

**Project:** hello_squad
**Version:** 0.1.0
**Status:** Draft

---

## Overview

A minimal CLI script that prints a greeting from SquadOps with the current timestamp and a randomly selected motivational quote. This project serves as the simplest possible build-capable SquadOps example — one source file, one test file.

---

## Requirements

### Output

When run, the script prints three lines to stdout:

1. **Greeting:** `Hello from SquadOps!`
2. **Timestamp:** Current date and time in ISO 8601 format (e.g., `2026-01-15T12:00:00`)
3. **Quote:** A randomly selected motivational quote from a built-in list of at least 5 quotes

Example output:
```
Hello from SquadOps!
2026-01-15T12:00:00
"The best way to predict the future is to invent it." — Alan Kay
```

### Quotes

Include at least 5 motivational quotes with attribution. The selection must be random (using `random.choice`).

### Entry Point

The script runs via:
```bash
python hello_squad.py
```

---

## Technical Constraints

- **Language:** Python 3.11+
- **Dependencies:** Standard library only (`datetime`, `random`)
- **Single file:** `hello_squad.py`
- **Testable:** The greeting and quote selection logic must be in importable functions (not just top-level script code)

---

## File Structure

```
hello_squad.py      # Main script with greeting, timestamp, and quote functions
test_hello_squad.py # Unit tests for all functions
```

---

## Acceptance Criteria

1. Running `python hello_squad.py` prints the greeting, timestamp, and a quote
2. The greeting is always `Hello from SquadOps!`
3. The timestamp reflects the current time
4. The quote is randomly selected from the built-in list
5. Unit tests cover: greeting text, timestamp format, quote list contents, and main output
