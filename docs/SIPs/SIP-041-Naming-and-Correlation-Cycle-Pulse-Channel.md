# SIP-041 — SquadOps Naming & Correlation (cycle / pulse / channel)
*Status: Draft*  
*Created: 2025-10-18 23:58:58Z*  
*Owner: Nexa Squad (Jason as editor)*

> Goal: Replace `run_id`, `ecid`, and `pid` with a single, durable **`cycle_id`**, add **`pulse`** and **`channel`** concepts, and standardize headers/schemas/telemetry so the system can scale cleanly with tracing and parallel work.

---

## 1. Summary
This SIP defines canonical identifiers for the SquadOps runtime:
- **`process_id` (+ `process_rev`)** — the business process blueprint.
- **`cycle_id`** — the single correlator for one full SDLC run.
- **`pulse_id`** — a bounded time/context window (one **trace per pulse**).
- **`channel_id`** (+ optional `channel_seq`) — parallel paths within a pulse.
- **`trace_id`** — observability trace (per pulse).
- **`task_id`** — unit of work (orchestrator-native or ULID).
- **`context_id`** — content-addressed snapshot of prompt/RAG/tools.

Optional: **`warmboot_id`** (series), **`build_id`** (code snapshot), **`trigger_*`** (pulse trigger metadata).

## 2. Motivation
- `run_id` is orchestrator-specific; `pid`/`ecid` naming was ambiguous with “process.”  
- Long, multi-hour traces are slow, brittle, and hard to analyze.  
- Parallel agent execution inside the same window needs a first-class concept for grouping and ordering.  
- We want clean OpenTelemetry/W3C alignment without overloading `trace_id`.

## 3. Non-Goals
- Mandating a specific orchestrator or tracer vendor.
- Encoding channel/sequence inside `trace_id` (we won’t).

---

## 4. Canonical IDs & Semantics
| Concept | Field | Purpose | Scope | Minted | Format | Example |
|---|---|---|---|---|---|---|
| Business process (blueprint) | `process_id` (+ `process_rev`) | Which blueprint is running | One per blueprint rev | On publish | slug + int | `ONBOARD_CUSTOMER`, `3` |
| Full run (cycle) | `cycle_id` | Portable correlator for one SDLC run | 1 per cycle | At cycle start | ULID/UUIDv7 | `01JC3C6T6H6XKX6TS3YV0WQG1P` |
| Time/context window | `pulse_id` | Window for measurement & context | Many per cycle | On window entry | ULID/UUIDv7 | `01JC3C7B6Y5K1N2J3Q4R5S6T7U` |
| Parallel path | `channel_id` | Parallel execution path within a pulse | Many per pulse | On first use | free string (`CH1.neo`) | `CH1.neo` |
| (per-channel order) | `channel_seq` *(optional)* | Monotonic step idx within a channel | Int per channel | Increment per step | integer ≥ 0 | `128` |
| Observability | `trace_id` | Telemetry trace (per pulse) | 1 per pulse | At pulse start | 16-byte hex or derived | `d0b7f4…73cf` |
| Unit of work | `task_id` | Scheduled activity | Many per cycle | On schedule | native/ULID | `prefect-run-9d1f5` |
| Context snapshot | `context_id` | Content-addressed prompt/RAG/tools | New on change | At pulse start/swap | `ctx_` + hash | `ctx_b3_f5x9…` |
| Warm-boot series | `warmboot_id` | Group multiple cycles | Optional | Series start | ULID | `01JC3BPP2…` |
| Build snapshot | `build_id` | Code snapshot used | Optional | Build/deploy time | `git:{sha}`/ULID | `git:3c1d9f2` |

> **Tracing policy:** One **trace per pulse**. Carry `cycle_id`, `pulse_id`, `process_id`, `process_rev`, and `channel_*` as span attributes. Do **not** overload `trace_id`.

---

## 5. Transport Headers (HTTP / MQ)
- `X-SquadOps-Process-Id`, `X-SquadOps-Process-Rev`
- `X-SquadOps-Cycle-Id`
- `X-SquadOps-Pulse-Id`
- `X-SquadOps-Channel-Id`, `X-SquadOps-Channel-Seq` *(optional)*
- `X-SquadOps-Task-Id`, `X-SquadOps-Context-Id`
- Optional: `X-SquadOps-Run-Id`, `X-SquadOps-Build-Id`, `X-SquadOps-WarmBoot-Id`
- Optional (trigger metadata): `X-SquadOps-Trigger-Kind`, `X-SquadOps-Trigger-Ref`

**Note:** If you previously emitted `X-SquadOps-PID` or `X-SquadOps-ECID`, accept them as aliases for 60–90 days; write both during the window and log a deprecation warning.

---

## 6. Event Envelope (YAML)
```yaml
process_id: "ONBOARD_CUSTOMER"
process_rev: 3
cycle_id: "01JC3C6T6H6XKX6TS3YV0WQG1P"
pulse_id: "01JC3C7B6Y5K1N2J3Q4R5S6T7U"
trace_id: "d0b7f4a5e3fd41b6a0e5c1bb9d2a73cf" # one per pulse
channel_id: "CH1.neo"
# channel_seq: 128                         # optional
task_id: "prefect-run-9d1f5"
context_id: "ctx_b3_7n7a2k1m…"
warmboot_id: "01JC3BPP2J2M7F4P7K2N6R8X1A"
build_id: "git:3c1d9f2"
ts: "2025-10-18T22:15:03Z"
agent: "neo"
```

---

## 7. Storage Schema (minimal events table)
```sql
CREATE TABLE so_events (
  process_id   TEXT NOT NULL,
  process_rev  INT  NOT NULL,
  cycle_id     CHAR(26) NOT NULL,   -- ULID
  pulse_id     CHAR(26),
  trace_id     TEXT,
  channel_id   TEXT,
  channel_seq  INT,
  task_id      TEXT,
  context_id   TEXT,
  warmboot_id  TEXT,
  build_id     TEXT,
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

## 8. OpenTelemetry / W3C Mapping
- **Root trace**: start **one trace per pulse**; tag spans with `cycle_id`, `pulse_id`, `process_id`, `process_rev`, `channel_id`, `channel_seq`.
- **Deterministic trace ids (optional):** `trace_id = HASH128(cycle_id + ":" + pulse_id)`; otherwise let the tracer mint.
- **Span links:** link pulse *N* root → pulse *N-1* root for continuity across a cycle.
- **Logs:** include `cycle_id` and `channel_id` in every structured log line; `trace_id`/`span_id` if available.
- **Do not** encode channel/seq into `trace_id`. If necessary, add to `tracestate` *and* span attributes.

---

## 9. Backward Compatibility & Migration
### Old → New
| Old | New | Action |
|---|---|---|
| `pid`, `ecid`, `run_id` (as correlator) | **`cycle_id`** | Replace. Keep aliases for 60–90 days; emit both fields during window. |
| `process_key`, `process_version` | **`process_id`, `process_rev`** | Rename. |
| `context_ref` | **`context_id`** | Rename. |
| `pulse_seq` | **`channel_seq`** *(if you used it as global order)* | Prefer per-channel `channel_seq`; you may compute a merged order at ingest. |

### Example ingest shim (pseudo-TS)
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

## 10. Reference Helpers (pseudo)
### ULID / UUIDv7 mint
```python
def mint_cycle_id():  # ULID preferred for sortable IDs
    import ulid
    return str(ulid.new())
```
### Per-pulse tracing
```python
def start_pulse_trace(cycle_id, pulse_id, tracer):
    # Optionally derive deterministic trace_id from (cycle_id, pulse_id)
    # Otherwise, let tracer mint; always tag attributes below.
    span = tracer.start_as_current_span("pulse_root", attributes={
        "cycle_id": cycle_id,
        "pulse_id": pulse_id,
    })
    return span
```
### Per-channel sequencing (optional)
```python
def next_channel_seq(cycle_id, pulse_id, channel_id, store):
    # store is a KV or DB; returns monotonic int per (cycle,pulse,channel)
    return store.incr(f"{cycle_id}:{pulse_id}:{channel_id}")
```

---

## 11. Rollout Plan
1. **Week 0–1:** Ship header/attr support; begin dual-write (old+new).  
2. **Week 2–3:** Migrate storage schema; add ingest shim; dashboards read new fields.  
3. **Week 4–6:** Turn on warnings when old fields are seen.  
4. **Week 7+:** Remove old fields; finalize dashboards on `cycle_id`/`pulse_id`/`channel_id`.

## 12. Acceptance Criteria
- All services emit `X-SquadOps-Cycle-Id` and include `cycle_id` in structured logs.  
- Tracer shows **one trace per pulse**, with spans tagged by `cycle_id`/`channel_id`.  
- Events table populated with `cycle_id`, `pulse_id`, `channel_id` and queries/dashboards function.  
- Ingest shim translates legacy fields without data loss.

## 13. Glossary
- **Cycle:** one full SDLC run (formerly ecid/pid/run).  
- **Pulse:** a time/context window; the unit of tracing.  
- **Channel:** a parallel execution path within a pulse.

---

*End of SIP-041*
