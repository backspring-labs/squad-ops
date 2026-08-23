---
title: v1.1.1
---

# v1.1.1

**Released 2026-06-29** · [tag `v1.1.1`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.1.1)

Hardening patch on the 1.1.0 runtime line. The runtime lane (SIP-0089) was
live-validated end-to-end after 1.1.0, surfacing two regressions the unit
suites couldn't catch (#270, #272); both are fixed here alongside the resume
and reliability work from the 1.1.x hardening plan. No new SIPs — the additive
items are backward-compatible and the one rename (#79) is internal.

### Added
- Per-role Prefect task names: tasks render as `{role} [{n}/{total}]: {title}`
  so a role appearing multiple times in a plan is distinguishable in the
  Prefect UI (#94).
- Agent **`mode`** and **`runtime_status`** are now surfaced on the agent-list
  API and the console agent view, alongside the heartbeat fields — health is
  `runtime_status`, posture is `mode` (see
  `docs/agent-runtime-status-model.md`) (#230, #231).

### Fixed
- **Auth:** cycle API routes returned 403 for every authenticated user — #150
  applied `cycles:read`/`cycles:write` scope checks, but the role-centric
  Keycloak realm issues *roles*, not those scopes. Bridge realm roles to their
  implied scopes in `resolve_identity` so role-bearing tokens authorize as
  intended (#270).
- **Duty scheduler:** duty windows never auto-opened under the default
  `missed_window_policy="skip"` — the poll-cadence lag before the first
  observing tick was misread as a missed window. A just-active window is now
  treated as on-time within one poll interval (plus jitter margin) (#272).
- **Resume:** a duty-deferred run is now re-attempted *and* actually
  re-executed on resume — the resume route never re-invoked the executor
  before (#222).
- **Resume:** mid-sequence runs resume at the correct workload index instead of
  re-running from workload 0 (#257).
- **Comms:** `publish()` now retries with bounded backoff across the RabbitMQ
  reconnect window instead of failing the first send after a drop (#245).
- **Capabilities:** strip `<think>` blocks before fenced-code parsing, and log
  the raw output on zero extraction so empty parses are diagnosable (#130).
- **CLI/API:** `runs retry` now actually executes the run (it previously
  no-op'd); corrected stale docstrings (#133, #205).
- **Telemetry:** the `BrokenExporter` test no longer leaks a global OTel
  provider into sibling tests (#239).

### Changed
- Renamed the `governance.establish_contract` capability → **`governance.define_done`**
  and its `run_contract.json` artifact → **`definition_of_done.json`** (the fields
  are a standard Definition of Done, not a "contract"). Internal rename, no
  behaviour change; historical artifacts on disk are left as-is (#79).

### Internal / tooling
- Regression suite runs in parallel via `pytest-xdist -n auto` (#216).
- `update_sip_status.py` now rewrites the body `**Status:**` line on promotion,
  not just the frontmatter (#253).
- Deduplicated three copies of the JSONB-parsing helper into one (#156); routed
  the dispatched-flow factory through `create_workflow_tracker` (#250); corrected
  stale flow-executor references in the control-plane context doc (#168).

## Merged pull requests (17)

| PR | Title | Closes |
|---|---|---|
| [#275](https://github.com/backspring-labs/squad-ops/pull/275) | chore(release): cut 1.1.1 — post-1.1.0 runtime-lane hardening | [#274](https://github.com/backspring-labs/squad-ops/issues/274) |
| [#273](https://github.com/backspring-labs/squad-ops/pull/273) | fix(runtime): open duty windows on-time within the poll cadence (#272) | [#272](https://github.com/backspring-labs/squad-ops/issues/272) |
| [#271](https://github.com/backspring-labs/squad-ops/pull/271) | fix(auth): bridge realm roles to implied scopes so cycle routes work (#270) | [#270](https://github.com/backspring-labs/squad-ops/issues/270) |
| [#269](https://github.com/backspring-labs/squad-ops/pull/269) | feat(observability): per-role n/total Prefect task names + framing titles (#94) | [#94](https://github.com/backspring-labs/squad-ops/issues/94) |
| [#268](https://github.com/backspring-labs/squad-ops/pull/268) | ci: parallelize the regression suite with pytest-xdist -n auto (#216) | [#216](https://github.com/backspring-labs/squad-ops/issues/216) |
| [#264](https://github.com/backspring-labs/squad-ops/pull/264) | fix(cli,api): make `runs retry` actually execute; correct stale execution docstrings (#133, #205) | — |
| [#267](https://github.com/backspring-labs/squad-ops/pull/267) | refactor(governance): rename establish_contract → define_done (#79) | [#79](https://github.com/backspring-labs/squad-ops/issues/79) |
| [#266](https://github.com/backspring-labs/squad-ops/pull/266) | fix(capabilities): strip <think> before fenced parsing + log zero-extraction raw (#130) | [#1](https://github.com/backspring-labs/squad-ops/issues/1) [#130](https://github.com/backspring-labs/squad-ops/issues/130) |
| [#265](https://github.com/backspring-labs/squad-ops/pull/265) | docs: correct stale flow-executor refs in control-plane context doc (#168) | [#168](https://github.com/backspring-labs/squad-ops/issues/168) |
| [#263](https://github.com/backspring-labs/squad-ops/pull/263) | feat(console): surface agent mode + runtime_status on the agent list (#230, #231) | [#230](https://github.com/backspring-labs/squad-ops/issues/230) |
| [#262](https://github.com/backspring-labs/squad-ops/pull/262) | refactor(adapters): extract one parse_jsonb helper, dedup 3 copies (#156) | [#156](https://github.com/backspring-labs/squad-ops/issues/156) |
| [#261](https://github.com/backspring-labs/squad-ops/pull/261) | refactor(cycles): route dispatched factory through create_workflow_tracker (#250) | [#250](https://github.com/backspring-labs/squad-ops/issues/250) |
| [#260](https://github.com/backspring-labs/squad-ops/pull/260) | fix(cycles): resume mid-sequence runs at the right workload index (#257) | [#257](https://github.com/backspring-labs/squad-ops/issues/257) |
| [#259](https://github.com/backspring-labs/squad-ops/pull/259) | fix(telemetry): stop BrokenExporter test leaking a global OTel provider → atexit traceback (#239) | [#239](https://github.com/backspring-labs/squad-ops/issues/239) |
| [#256](https://github.com/backspring-labs/squad-ops/pull/256) | fix(cycles): resume re-attempts duty-deferred runs + actually re-executes (#222) | [#222](https://github.com/backspring-labs/squad-ops/issues/222) |
| [#255](https://github.com/backspring-labs/squad-ops/pull/255) | fix(comms): bounded retry/backoff for RabbitMQ publish() across reconnect window (#245) | [#245](https://github.com/backspring-labs/squad-ops/issues/245) |
| [#254](https://github.com/backspring-labs/squad-ops/pull/254) | fix(maintainer): rewrite body **Status:** line on SIP promotion (#253) | [#253](https://github.com/backspring-labs/squad-ops/issues/253) |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0079-Implementation-Run-Contract-Correction](../../design/sips/SIP-0079-Implementation-Run-Contract-Correction.md) | new | implemented |
