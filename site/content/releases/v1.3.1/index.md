---
title: v1.3.1
---

# v1.3.1

**Released 2026-07-08** · [tag `v1.3.1`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.3.1)

Hardening patch on the 1.3.0 stabilization line — the post-1.3.0 batch surfaced by
the 2026-07-04 independent health assessment, reassigned to the Macbook lane while
Spark was offline. All fixes; no feature SIPs (patches land on either lane anytime,
independent of the even/odd feature parity — #281). Every runtime-affecting change
was live-validated on the deployed stack before merge.

### Security
- **Agent-status writes moved off the unauthenticated `/health` lane (#326).**
  `POST/PUT /health/agents/status` were writable by any anonymous network client
  (the auth middleware allowlists the whole `/health` prefix). They now live at
  `POST/PUT /api/v1/agents/status` behind the `agents:write` scope; `/health/*`
  keeps only GET probes. The middleware allowlist is now **method-scoped**
  (GET/HEAD), so a future write route under `/health` fails closed instead of
  riding the no-auth lane. Agents authenticate their heartbeats via a new
  `squadops-agent` service identity (client credentials, `agent` realm role ⇒
  `agents:write` only); a half-configured identity raises at startup rather than
  silently sending anonymous heartbeats.

### Fixed
- **Concurrent same-agent cycles no longer bypass FocusLease arbitration (#288).**
  `RuntimeCoordinator.request_transition` short-circuited every same-mode request
  to `idempotent_skip` before arbitration, so a second cycle recruiting an
  already-recruited agent free-rode the first run's lease and lost the agent when
  the first finalized. A same-mode request from a *different* lease owner now
  rejects with `focus_lease_conflict` (admission defers the run); a same-owner
  replay still skips.
- **QA agent image now has Node.js so the frontend build check runs (#306).** The
  `qa.test` frontend build check (#290) and vitest shelled out to `npm`/`npx` in an
  image with no Node — every frontend check silently skipped, so a non-building
  frontend shipped green. Node ships in the qa image only (the sole Node consumer),
  declared via a config-driven per-role `system-packages.txt` (the apt analog of the
  existing per-role `requirements.txt` — no role name hardcoded in the Dockerfile).

### Added
- **Broker-hygiene check in `squadops doctor` (#328).** A new `broker` category
  flags queues on the retired pre-SIP-0094 `cycle_results_*` naming scheme and any
  queue holding messages with no consumer (an undrained backlog). Reads queue stats
  via `rabbitmqctl` inside the container (resolved from the compose service name, no
  credentials); an unqueryable broker warns rather than fails. The orphaned
  `cycle_results_*` queues left by the SIP-0094 migration (one with 48 undrained
  messages) were swept.

### Docs & SIP lifecycle
- Filed the **Externalized Build Sandbox** proposal (`sips/proposed/`) — the
  principled long-term home for build/test execution (a `BuildSandboxPort` so agents
  carry no toolchain), with #306 as its interim. Stays `proposed`.

## Merged pull requests (6)

| PR | Title | Closes |
|---|---|---|
| [#364](https://github.com/backspring-labs/squad-ops/pull/364) | release: 1.3.1 — hardening patch (#326, #288, #306, #328) | — |
| [#363](https://github.com/backspring-labs/squad-ops/pull/363) | fix(#288): arbitrate FocusLease on same-mode request from a different owner | [#288](https://github.com/backspring-labs/squad-ops/issues/288) |
| [#362](https://github.com/backspring-labs/squad-ops/pull/362) | fix(#328): broker-hygiene doctor check + sweep orphaned pre-SIP-0094 queues | [#328](https://github.com/backspring-labs/squad-ops/issues/328) |
| [#361](https://github.com/backspring-labs/squad-ops/pull/361) | fix(#306): install Node.js in the qa agent image so the frontend build check runs | [#306](https://github.com/backspring-labs/squad-ops/issues/306) |
| [#360](https://github.com/backspring-labs/squad-ops/pull/360) | docs(sip): propose Externalized Build Sandbox (proposed draft) | — |
| [#359](https://github.com/backspring-labs/squad-ops/pull/359) | fix(#326): move agent-status writes off the unauthenticated /health lane | [#326](https://github.com/backspring-labs/squad-ops/issues/326) |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| SIP-Externalized-Build-Sandbox | new | proposed |
