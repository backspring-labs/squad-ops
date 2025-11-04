# SIP-041 — Naming & Correlation (Cycle / Pulse + Optional Channel)
*Status: Draft*  
*Revised: 2025-10-19 00:12:34Z*  
*Owner: Nexa Squad (Jason as editor)*

## 1) Decisions
- **Adopt `cycle_id`** as the single correlator for one full SDLC run (replaces `pid`/`ecid`/`run_id` as correlator).
- **Trace per pulse:** keep **one `trace_id` per `pulse_id`** (bounded time/context window).
- **Make `channel` optional:** use `channel_id` (and optional `channel_seq`) only when there is parallel work inside a pulse.
- **Drop series/warmboot for now:** no `series_id`/`warmboot_id` in the baseline.
- **Blueprint ID format:** use **`process_id` in `BP-001` style** (+ **`process_rev`**). The `process_id` is stable across versions; `process_rev` is the integer revision.

---

## 2) Canonical IDs & Semantics
| Concept | Field | Purpose | Scope | Minted | Format | Example |
|---|---|---|---|---|---|---|
| Business process (blueprint) | `process_id` + `process_rev` | Which blueprint/revision is being executed | One per blueprint rev | At publish | `process_id`: `^BP-\d{{3,}}$`; `process_rev`: int ≥1 | `BP-001`, `3` |
| Full run (cycle) | `cycle_id` | Portable correlator for a full SDLC run | 1 per cycle | At cycle start | ULID/UUIDv7 | `01JC3C6T6H6XKX6TS3YV0WQG1P` |
| Time/context window | `pulse_id` | Window for measurement & context (unit of tracing) | Many per cycle | On window entry | ULID/UUIDv7 | `01JC3C7B6Y5K1N2J3Q4R5S6T7U` |
| Observability | `trace_id` | Telemetry trace id (per pulse) | 1 per pulse | At pulse start | 16-byte hex or derived | `d0b7f4…73cf` |
| Parallel path *(optional)* | `channel_id` | Parallel execution path within a pulse | Many per pulse | On first use | free string; recommend `CH<n>.<actor>` | `CH1.neo` |
| Per-channel order *(optional)* | `channel_seq` | Monotonic step index per channel | Int per channel | Increment per step | integer ≥0 | `128` |
| Unit of work | `task_id` | Scheduled activity | Many per cycle | On schedule | native/ULID | `prefect-run-9d1f5` |
| Context snapshot | `context_id` | Content-addressed prompt/RAG/tools state | New on change | At pulse start/swap | `ctx_` + short hash | `ctx_b3_f5x9…` |

**Note:** If you prefer a human label for the process, add `process_name` (e.g., `"ONBOARD_CUSTOMER"`), but **do not** use it as an identifier.

---

## 3) Transport Headers (HTTP / MQ)
- `X-SquadOps-Process-Id`  (e.g., `BP-001`)
- `X-SquadOps-Process-Rev` (e.g., `3`)
- `X-SquadOps-Cycle-Id`
- `X-SquadOps-Pulse-Id`
- `X-SquadOps-Channel-Id` *(optional)*, `X-SquadOps-Channel-Seq` *(optional)*
- `X-SquadOps-Task-Id`, `X-SquadOps-Context-Id`

**Deprecations accepted for 60–90 days (ingest shim writes canonical fields):**
- `X-SquadOps-PID`, `X-SquadOps-ECID`, `X-Run-Id` ⇒ `X-SquadOps-Cycle-Id`
- `X-SquadOps-Process-Key` ⇒ `X-SquadOps-Process-Id`
- `X-SquadOps-Process-Version` ⇒ `X-SquadOps-Process-Rev`
- `X-SquadOps-Context-Ref` ⇒ `X-SquadOps-Context-Id`

---

## 4) Minimal Event Envelope (YAML)
```yaml
process_id: "BP-001"
process_rev: 3
cycle_id: "01JC3C6T6H6XKX6TS3YV0WQG1P"
pulse_id: "01JC3C7B6Y5K1N2J3Q4R5S6T7U"
trace_id: "d0b7f4a5e3fd41b6a0e5c1bb9d2a73cf"   # 1 per pulse
# channel_id: "CH1.neo"          # optional
# channel_seq: 128                # optional
task_id: "prefect-run-9d1f5"
context_id: "ctx_b3_7n7a2k1m…"
ts: "2025-10-18T22:15:03Z"
agent: "neo"
```

---

## 5) Storage Schema (events table)
```sql
CREATE TABLE so_events (
  process_id   TEXT NOT NULL,      -- e.g., BP-001
  process_rev  INT  NOT NULL,      -- e.g., 3
  cycle_id     CHAR(26) NOT NULL,  -- ULID
  pulse_id     CHAR(26) NOT NULL,
  trace_id     TEXT,
  channel_id   TEXT,               -- optional
  channel_seq  INT,                -- optional
  task_id      TEXT,
  context_id   TEXT,
  ts           TIMESTAMPTZ NOT NULL,
  agent        TEXT,
  payload      JSONB NOT NULL,
  PRIMARY KEY (cycle_id, ts, COALESCE(channel_seq, 0))
);
CREATE INDEX idx_so_proc   ON so_events(process_id, process_rev, ts DESC);
CREATE INDEX idx_so_pulse  ON so_events(cycle_id, pulse_id, ts DESC);
CREATE INDEX idx_so_chan   ON so_events(cycle_id, pulse_id, channel_id, channel_seq);
CREATE INDEX idx_so_task   ON so_events(task_id);
```

---

## 6) OpenTelemetry / W3C Mapping
- **One trace per pulse.** Tag spans with: `cycle_id`, `pulse_id`, `process_id`, `process_rev`, and, if used, `channel_id`, `channel_seq`.
- **Deterministic trace ids (optional):** `trace_id = HASH128(cycle_id + ":" + pulse_id)`; otherwise let tracer mint.
- **Span links:** link pulse *N* root → pulse *N-1* root for continuity across a cycle.
- **Do not** encode channel/seq into `trace_id` (use span attributes).

---

## 7) Migration
### Old → New
| Old | New | Action |
|---|---|---|
| `pid`, `ecid`, `run_id` (as correlator) | `cycle_id` | Replace; keep aliases 60–90 days. |
| `process_key`, `process_version` | `process_id`, `process_rev` | Rename; adopt `BP-001` convention. |
| `context_ref` | `context_id` | Rename. |
| `series_id`, `warmboot_id` | *(none)* | Remove from baseline. |

### Ingest shim (pseudo-TS)
```ts
function normalizeHeaders(h: Record<string,string>) {
  const out = { ...h };
  out["X-SquadOps-Cycle-Id"]   ||= h["X-SquadOps-ECID"] || h["X-SquadOps-PID"] || h["X-Run-Id"];
  out["X-SquadOps-Process-Id"] ||= h["X-SquadOps-Process-Key"];
  out["X-SquadOps-Process-Rev"]||= h["X-SquadOps-Process-Version"];
  out["X-SquadOps-Context-Id"] ||= h["X-SquadOps-Context-Ref"];
  return out;
}
```

---

## 8) Validation Rules
- `process_id`: must match `^BP-\d{{3,}}$` (e.g., BP-001, BP-042, BP-1024)
- `process_rev`: integer ≥ 1
- `cycle_id`, `pulse_id`: ULID/UUIDv7 strings
- `channel_id`: free string; recommended pattern `^CH\d+(\.[A-Za-z0-9_-]+)?$`
- `channel_seq`: integer ≥ 0

---

## 9) Acceptance Criteria
- All services emit `X-SquadOps-Cycle-Id` and include `cycle_id` in logs.  
- Tracer shows **one trace per pulse** with spans tagged by `cycle_id` and (if used) `channel_id`.  
- Events table queries/dashboards operate on `process_id/process_rev`, `cycle_id`, and optionally `channel_id`.
