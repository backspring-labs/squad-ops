# CLI reference

`squadops` talks to the runtime API over HTTP, so it works the same against a
local stack or a remote one — set `SQUADOPS__API__URL` and authenticate.

For a task-oriented walkthrough see [operate a cycle](operate-a-cycle.md).

## Command groups

| Group | Commands |
|---|---|
| `projects` | `list` · `show` |
| `cycles` | `create` · `list` · `show` · `cancel` |
| `runs` | `list` · `show` · `retry` · `cancel` · `gate` · `resume` · `checkpoints` · `assemble` |
| `artifacts` | `ingest` · `get` · `download` · `list` |
| `baseline` | `set` · `get` · `list` |
| `squad-profiles` | `list` · `show` · `active` · `set-active` · `create` · `clone` · `activate` · `delete` |
| `request-profiles` | `list` · `show` |
| `models` | `list` · `pulled` · `pull` · `remove` |
| `agent` | `state` · `activity` |
| `assignment` | `show` · `create` |
| `auth` | `login` · `logout` · `status` |
| `bootstrap` | provision an environment from a profile |
| `doctor` | validate an environment against a profile contract |

## Conventions

- Most read commands have a short alias — `ls` for `list`, `cat` for `show`.
- `--json` returns machine-readable output on read commands.
- Authentication is a cached token at `~/.config/squadops/token.json`.
- Commands that address a run take `<project> <cycle-id> <run-id>` in that order.
