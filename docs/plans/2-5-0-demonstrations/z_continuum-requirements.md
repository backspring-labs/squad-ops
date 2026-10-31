# Continuum: read one plugin, and one command, by its id

## Problem

An operator who wants one plugin's status, or one command's definition, has to fetch a whole list
(`/diagnostics` or `/api/registry`) and search it by hand. Scripts that check a single plugin do
the same, and break when the list's order changes.

## Feature 1: one plugin's status

`GET /api/plugins/{plugin_id}` answers one loaded plugin's status, with status 200.

- The body is the same object `/diagnostics` lists for that plugin in its `plugins` array, with
  the same fields and values: `id`, `name`, `version`, `status`, `discovery_index`, `required`,
  `error`, `contribution_count` and `load_time_ms`.
- A `plugin_id` that no installed plugin has answers 404, with FastAPI's error body
  (`{"detail": "..."}`).
- Plugin ids contain dots (`continuum.sample_nav`), and the route takes them as they are.

## Feature 2: one command's definition

`GET /api/commands/{command_id}` answers one registered command's definition, with status 200.

- The body is the same object `/api/registry` lists for that command in its `commands` array,
  with every field it has there (`id`, `label`, `danger_level` and `plugin_id` among them).
- A `command_id` that no plugin registered answers 404, with FastAPI's error body.
- `GET /api/commands/audit` keeps answering the audit log, as it does today.

## Constraints

- Every existing endpoint answers exactly as it does today.
- Each feature comes with tests under `tests/`, as `CLAUDE.md` asks: the exact status and body for
  a known id and for an unknown one.
- The two features are separate changes, one increment each.

## Out of scope

The web app under `web/`, the plugin UIs, authentication, and any change to how plugins are
discovered or loaded.
