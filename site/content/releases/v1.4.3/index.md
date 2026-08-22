---
title: v1.4.3
---

# v1.4.3

**Released 2026-08-04** · [tag `v1.4.3`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.4.3)

**Lifecycle Hygiene** — a cycle can neither strand the next one nor fail silently. Seven
hash-stable fixes, five planned plus two found *by the deploy window itself*: **#373+#529**
focus-lease reaper across cancel routes, executor finalize, and startup sweep; **#561**
activity self-heal; **#498** interpreter resolution (bare `python` resolves to
`sys.executable`, strictly after the safelist gate); **#572** queue capability honesty;
**#573** a redaction char-class overrun that swallowed adjacent log fields; **#710**
stranded-mode sweep; **#712** owner-checked lease release.

**Found by the window, not the tests:** #710 — pre-deploy capture showed six agents in
`cycle` mode holding zero leases, so focus arbitration had been silently inert for 64
cycles over two weeks. #712 — a cancelled run's late finalize would have stripped the
*relaunched* run's focus, unreachable before this patch only because #529's leak was an
accidental guard.

Confirmation **shk-4 green**; 9/9 leases released, zero residue, no restart.

## Merged pull requests (8)

| PR | Title | Closes |
|---|---|---|
| [#714](https://github.com/backspring-labs/squad-ops/pull/714) | chore(release): cut v1.4.3 — lifecycle hygiene (version bump + marker sync + as-built record) | — |
| [#713](https://github.com/backspring-labs/squad-ops/pull/713) | fix(runtime): owner-check the lease release on ambient entry (#712) | [#712](https://github.com/backspring-labs/squad-ops/issues/712) |
| [#711](https://github.com/backspring-labs/squad-ops/pull/711) | fix(runtime): reap agents stranded in cycle mode with no lease at startup (#710) | [#710](https://github.com/backspring-labs/squad-ops/issues/710) |
| [#709](https://github.com/backspring-labs/squad-ops/pull/709) | fix(telemetry): a literal `|` in the email TLD class swallowed the next log field (#573) | [#573](https://github.com/backspring-labs/squad-ops/issues/573) |
| [#708](https://github.com/backspring-labs/squad-ops/pull/708) | fix(comms): report the delay and priority capabilities the queue actually has (#572) | [#572](https://github.com/backspring-labs/squad-ops/issues/572) |
| [#706](https://github.com/backspring-labs/squad-ops/pull/706) | fix(checks): resolve a bare `python` at spawn instead of through PATH (#498) | [#498](https://github.com/backspring-labs/squad-ops/issues/498) |
| [#705](https://github.com/backspring-labs/squad-ops/pull/705) | fix(runtime): self-heal stale activity rows and end them at cancel and startup (#561) | [#561](https://github.com/backspring-labs/squad-ops/issues/561) |
| [#704](https://github.com/backspring-labs/squad-ops/pull/704) | fix(runtime): reclaim stranded focus leases at cancel, finalize, and startup (#373, #529) | [#373](https://github.com/backspring-labs/squad-ops/issues/373) [#529](https://github.com/backspring-labs/squad-ops/issues/529) |
