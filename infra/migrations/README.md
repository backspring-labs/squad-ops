# Postgres Migrations

Postgres DDL migrations applied at runtime-api startup.

All migrations are idempotent (`CREATE ... IF NOT EXISTS`) and apply in lexicographic filename order.

## Numbering ranges

Numeric ranges are reserved to keep parallel work streams from colliding. SIP-0089 plan binding decision **D11** establishes the scheme; the existing `001`–`006` migrations predate the range scheme and remain at their original three-digit prefixes.

| Range | Owner | Status |
|---|---|---|
| `001–006` | Pre-range-scheme (cycle registry, pulse, squad profiles, workload canon, run checkpoints, chat tables) | In place |
| `1000–1099` | 1.0.x hardening (Spark) | Reserved |
| `1100–1199` | SIP-0089 Agent Runtime State (v1.1) | In use — see `1100_agent_runtime_state.sql` |
| `1200–1299` | SIP-0090 Agent Embodiment Substrate (v1.2) | Reserved (tentative) |
| `1300–1399` | SIP-0091 Duty Durability via Temporal (v1.3) | Reserved (tentative) |

If your work doesn't fit a reserved range, pick the next free hundred and add a row here in the same PR.

## Authoring rules

- **Idempotent DDL only** — use `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, etc.
- **One concern per file** — don't bundle unrelated schema changes.
- **Header comment** — first line is the filename; second line names the SIP and section.
- **CHECK constraints** for enum-shaped columns must match the `Literal` types in the corresponding Python model (D3).
