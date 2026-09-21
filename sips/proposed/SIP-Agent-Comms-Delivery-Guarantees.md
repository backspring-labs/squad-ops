---
sip_uid: '17883224960377942'
title: Agent Comms Delivery Guarantees
status: proposed
author: jladd
created_at: '2026-07-08T00:00:00Z'
---
# SIP: Agent Comms Delivery Guarantees

## Status
Proposed

**Targets:** gate for Campaign (v1.6), alongside SIP-0096 + #288 + #316. Implementation window: the 1.5 stabilization minor, or riding 1.4 as hardening (parity gates features, not hardening — #281). The gate is: **implemented before any squad does paid external duty/Campaign work over this transport.**
**Builds on:** SIP-0094 (per-agent reply queues + `subscribe()` primitive, implemented) and #323 (agent comms poll→push migration). SIP-0094 §4 explicitly deferred the agent-side loop as "a follow-up"; #323 was that follow-up. This SIP is the next rung: the transport loop is now correct — the *delivery guarantees around failure* are not.
**Amends:** SIP-0094 D12 ack policy — scoped per-direction, not revoked (see §5.1).

## 1. Abstract

The agent comms transport (`{agent_id}_comms` dispatch, `{agent_id}_replies` reply) is structurally sound after SIP-0094 and #323: durable queues, robust connections, persistent push consumers with resubscribe-on-drop, QoS prefetch=1, publish retry (#245). But its failure-path guarantees sit below what paid external work requires: a message whose handler fails is **acked and discarded** (no redelivery, no dead-letter queue), publishes carry no explicit broker confirmation, redelivered tasks are reprocessed with no idempotency check, and the `delay_seconds` publish path sets a TTL without a dead-letter exchange — which *expires* messages rather than deferring them. Today the orchestration layer compensates (dispatch retry, task timeouts, the correction protocol, honest run reporting), so a lost comms message degrades to a retried-or-failed task rather than silent data loss. That net is adequate for internal cycles and inadequate for Campaign-era duty work, where "the orchestrator will notice eventually" is not a delivery guarantee. This SIP adds bounded redelivery + a dead-letter queue, explicit publisher confirms with mandatory routing, completed-task idempotency at the consumer, real deferred redelivery, and DLQ observability.

## 2. Problem Statement

Four gaps, all in shipped code:

**Gap A — Failed processing silently discards the message.** The subscription layer acks every delivery whether the callback succeeded or failed (`RabbitMQAdapter._dispatch_subscription_delivery`, and the `QueuePort.subscribe` default), and the agent callback `_process_comms_message` (`src/squadops/agents/entrypoint.py`) swallows all exceptions by contract. This ack-always policy was carried forward deliberately in #323 to preserve semantics ("acknowledge anyway to avoid infinite retries" — the poison-loop concern is real), but the outcome is at-most-once processing: a transient handler failure (LLM adapter hiccup, reply-publish failure after work completed) discards the task envelope with only a log line. There is no bounded retry, no quarantine, no operator-visible dead-letter.

**Gap B — No publisher-side delivery confirmation.** `publish()` retries on channel failure (#245) but does not explicitly enable publisher confirms or set `mandatory` routing. An unroutable publish (routing key with no queue — possible during queue-migration windows) or a broker-side failure after channel accept can lose a message invisibly. aio_pika enables confirms on channels by default, but the guarantee is implicit and untested — nothing pins it, and `mandatory` is unset, so unroutable returns don't surface.

**Gap C — Redelivery is not idempotent.** An agent killed mid-processing leaves the delivery unacked; the broker redelivers on reconnect (correct at-least-once mechanics, live-verified in #323's validation). But the consumer has no dedup: a task that *completed* (reply published) just before a crash-before-ack is fully reprocessed — duplicate LLM spend and a duplicate reply into the results queue. `TaskEnvelope.task_id` is the natural idempotency key; nothing uses it at this layer.

**Gap D — The delay mechanism is fake.** `publish(delay_seconds=…)` sets per-message `expiration` (TTL) with no dead-letter exchange. The code comment itself calls this simplified. TTL without DLX means the message is *available immediately and deleted after the delay* — the inverse of the intended semantics. `retry(message, delay_seconds)` builds on it, so its "retry with delay" is actually "retry now, expire if not consumed in time." Latent, not currently bleeding (the comms path doesn't call `retry()`), but it is an API whose contract is the opposite of its behavior.

## 3. Why Now (and why not before)

Resilience in SquadOps deliberately lives above the transport: `TaskDispatcher.dispatch_with_retry`, per-task timeouts, the correction protocol (SIP-0086), and honest terminal reporting via `RunCompletion` all convert a lost message into a visible task failure. Hardening the transport earlier would have violated the defer-infra-completeness principle — the orchestration net was the right net for internal cycles.

The Campaign arc changes the threat model. Duty work (1.4) and Campaign orchestration (1.6) put paid, externally-visible work on this transport. At that point a discarded envelope is not "a task the executor will retry" — it may be a customer deliverable, and the failure evidence must be operator-facing (a DLQ with alerting), not a log line evicted from a container buffer. SIP-0096 makes verification evidence trustworthy; this SIP makes the *message layer under it* trustworthy. Same arc, one layer down.

## 4. Goals

1. **Bounded redelivery, then dead-letter.** A comms delivery whose handler fails is redelivered up to N times (default 3, config `SQUADOPS__COMMS__MAX_DELIVERY_ATTEMPTS`), then routed to a durable dead-letter queue with its `x-death` history intact. The consumer keeps running throughout. Nothing is silently discarded.
2. **Explicit publisher guarantees.** Publisher confirms pinned on (explicit, tested — not inherited from library defaults), `mandatory=True` on comms/reply publishes, unroutable returns surfaced as failures into the existing #245 retry loop.
3. **Idempotent consumption keyed on `task_id`.** A completed task (reply published) records its `task_id` in a dedup store; a redelivered envelope whose `task_id` is marked complete is acked with a log instead of reprocessed. Redelivery of an *incomplete* task reprocesses normally — at-least-once delivery with idempotent effect.
4. **Real deferred redelivery.** Replace TTL-as-expiration with the wait-queue pattern (TTL + DLX routing back to the target queue), fixing `retry()`'s contract to mean what it says.
5. **DLQ observability.** DLQ depth, redelivery count, and confirm-failure metrics exposed through the existing telemetry port; a non-empty DLQ is an alertable condition, and `squadops` gains a minimal DLQ inspect/replay surface.

## 5. Approach Sketch

### 5.1 Bounded redelivery + DLQ (amends SIP-0094 D12, per-direction)

SIP-0094 D12's ack-always rationale is *reply-direction specific*: a failing reply callback is a waiter-side logic error, and requeuing a reply would poison-loop. That stays. The **dispatch direction** (`{agent_id}_comms`) is different — handler failure there is real work lost — so the ack policy becomes per-subscription:

- `subscribe()` gains an ack-policy option (`ack_always` — default, current behavior — vs `redeliver_then_dlq`). Reply-queue subscriptions keep `ack_always`. Agent comms subscriptions opt into `redeliver_then_dlq`.
- Under `redeliver_then_dlq`, a raising callback triggers `nack(requeue=True)` while the broker-maintained `x-death` count is below N, then `reject(requeue=False)` — the DLX routes the message to `comms.dlq`. The callback contract changes for this policy only: `_process_comms_message` re-raises instead of swallowing (its logging stays).
- **DLX via broker policy, not declare-args.** Durable queues reject redeclaration with changed arguments (`PRECONDITION_FAILED` — the SIP-0094 D3 gotcha). A RabbitMQ policy (`rabbitmqctl set_policy`) attaches the DLX to existing `*_comms` queues with no declare-args drift and no queue migration. The policy is applied by the deploy pipeline (rebuild_and_deploy step, same pattern as the #327 prompt re-sync) and asserted by `squadops doctor`.
- Poison-message safety (the original reason for ack-always) is *strictly better*: a poison message burns N attempts and lands in quarantine instead of either looping forever or vanishing.

### 5.2 Publisher confirms + mandatory routing

Pin `publisher_confirms=True` at channel creation (explicit even if it matches the library default), set `mandatory=True` on comms/reply publishes, and map `DeliveryError`/basic.return into the existing publish-retry-then-`QueueError` path. One new failure mode becomes visible: publishing to a queue that doesn't exist yet fails fast instead of silently dropping — which is correct, and D9 (declare-before-consume/publish) already makes it rare.

### 5.3 Consumer idempotency

Redis (already in the stack) as the dedup store: `SETNX comms:done:{task_id}` with a TTL (~24h, config) written **after** the reply publish succeeds. On delivery, a hit → ack + structured log (`duplicate_of_completed_task`), no reprocess. Semantics chosen deliberately: dedup on *completed*, not on *seen* — a crash mid-processing leaves no marker, so the redelivery reprocesses (at-least-once preserved). Redis loss shrinks the dedup window to zero until it refills; the failure mode is duplicate work, never lost work — acceptable degradation, noted in Open Questions. **That holds only where the work terminates: see §5.3a, where reprocessing a crash mid-processing was neither duplicate work nor lost work but an unbounded crash loop (#1626).**

### 5.3a The death path — an incident rule, and a gap in §5.1 (added 2026-09-20, #1626)

**The incident.** The qa agent took a SIGSEGV inside a repair handler (a corrupt
`tree_sitter` node, #1626). Docker restarted it, the broker redelivered the unacked
message, and it died again — **37 times over ~90 minutes**. Stated as provable: no record was
written; **no handler result reached the correction, deadlock (#1221) or
repeated-signature machinery**, each of which consumes a handler RESULT; the run stayed
`running`; and every restarted agent took the poisoned delivery again. Not every
termination mechanism depends on a handler returning — `TaskDispatcher._publish_and_await`
carries a task timeout that does not — and the incident record does not claim otherwise.
`cycle_runs.status` staying `running` with nothing running is what, by the verification
driver's contract, makes every later preflight refuse. One message bricked the deploy.

**§5.3's reasoning does not cover it.** §5.3 chooses dedup on *completed* rather than
*seen*, so "a crash mid-processing leaves no marker, so the redelivery reprocesses", on the
stated grounds that "the failure mode is duplicate work, never lost work". That is true when
the work *terminates*. #1626 is a third mode the sentence does not admit: **reprocessing can
be fatal and unbounded.** The observed fact, stated as observed: in the affected agent
runtime state the delivery crashed on every one of 37 attempts. **Input alone is not
sufficient to reproduce it** — the same content parses cleanly in a fresh process on
identical versions and architecture (#1626), which points at memory-state-dependent
corruption. The interim rule does not depend on input-only determinism, and must not be
justified by it.

**§5.1's bound does not cover it either, and this is the gap worth fixing here.** §5.1 bounds
poison messages with the broker-maintained `x-death` count, advanced by a **raising
callback** — `nack(requeue=True)` while the count is below N, then `reject(requeue=False)`
to the DLX. A process that **dies** raises nothing. The channel drops and the broker requeues
the unacked message, and **a requeue after consumer death is not a dead-lettering: it carries
no `x-death` entry.** So the count never advances and §5.1's N-attempt bound never trips.
§5.1's claim that "a poison message burns N attempts and lands in quarantine instead of
either looping forever or vanishing" holds for a *failing* handler and not for a *dying*
one. **MEASURED on this deployment, 2026-09-20**, through the project's own adapter
(`create_queue_adapter`) against the running broker: publish one message, consume it
without acking, close the connection — the consumer-death case — and re-consume.

```
FIRST delivery : redelivered=False  x-death=None
AFTER requeue  : redelivered=True   x-death=None
```

The redelivery carries `redelivered=True` and **no `x-death` entry**. An automatic requeue
after consumer death is not a dead-lettering, so the count §5.1 bounds on never advances.
This was recorded here as asserted-not-measured; it is now measured, and §5.1's death-path
gap is a fact rather than an inference.

**The interim rule, in force now.** Until completed-task deduplication (§5.3) exists:

> A redelivered **`comms.task`** is converted to a typed `FAILED` result for the original
> task id and acknowledged. Only the cycle's recorded correction machinery may retry it.

**Scope: task dispatch only.** `comms.chat` deliveries are untouched by this rule, and it
must not be described as bounding consumer poison loops in general — only task dispatch is
guarded.

**What `redelivered` does and does not prove.** It proves a prior delivery was **not
acknowledged**. It does *not* prove the work did not happen. The subscription awaits the
callback and acks only afterwards, so the connection can close before the callback runs,
during the work, or **after the work and its reply succeeded but before the ack** — and the
broker may mark a message redelivered that never reached the prior consumer at all. The
honest statement is therefore: **the prior delivery's completion is unknown.**

**The ack-gap case, and the assumption that makes it safe.** The uncomfortable ordering is:
a task completes, publishes `SUCCEEDED`, loses its connection before the ack, is
redelivered, and this rule then publishes `FAILED` for the same task id. In today's
topology the success is queued first and `ReplyRouter` **pops** the future when it resolves
(`adapters/cycles/reply_router.py:127`), so the later `FAILED` finds no registered future
and is dropped — the successful result stands.

That safety is **conditional on one active consumer per `{agent_id}_comms` queue.** With
overlapping consumers — a rolling restart, a second agent process on the same queue — the
two results can race and a successful task can be recorded as failed. **Preserving
single-active-consumer per dispatch queue is therefore an acceptance condition of this
interim rule**, and it lapses only when completed-task dedup (§5.3) makes the ordering
irrelevant.

The rule follows from that, not from a cause: with completion unknown, the broker layer is
the wrong place to decide. Re-executing risks unbudgeted duplicate work and, as #1626 shows,
can be fatal and unbounded; discarding risks losing work. Emitting a typed `FAILED` for the
original task id records the uncertainty where it can be reasoned about, and hands the retry
decision to the only layer with a budget and a record. Implemented in #1627.

**What §5.1 and §5.3 must add when they land — and an acceptance condition.** The rule
above narrows rather than disappears. `redeliver_then_dlq` needs a **death-path bound that
does not rely on `x-death`** — an attempt marker written *before* the handler runs (§5.3's
Redis store can carry `seen` beside `completed`), or a redelivery treated as terminal for a
task with no completion marker. Without one, §5.1 ships believing it has bounded poison
messages while the fatal case remains unbounded.

**The two mechanisms cannot coexist, and this is an acceptance condition on §5.1.** Under
`redeliver_then_dlq` an explicit `nack(requeue=True)` also produces a delivery with
`redelivered=True`. If the interim flag-only test is still in place then, attempt 2 is
converted to `FAILED` and acked: **the configured N-attempt budget collapses to one and the
message never reaches the DLQ.** §5.1 must therefore land with the death-path marker
**replacing** the flag-only test in the same change, not beside it.

### 5.4 Deferred redelivery (fixes Gap D)

A shared `comms.wait` queue declared with DLX → default exchange, no consumers. `publish(delay_seconds=…)` routes the message to `comms.wait` with per-message TTL and `x-dead-letter-routing-key` = target queue; on expiry the broker delivers it to the real queue. `retry()` inherits correct semantics unchanged.

### 5.5 Observability

- Gauges/counters via the telemetry port: `comms_dlq_depth`, `comms_redeliveries_total`, `comms_publish_confirm_failures_total`, `comms_duplicate_drops_total`.
- Prometheus alert on `comms_dlq_depth > 0` sustained.
- CLI: `squadops comms dlq list` / `squadops comms dlq replay <message-id>` (replay = re-publish to origin queue, delete from DLQ). Minimal, read-mostly; full tooling is out of scope.

## 6. Non-Goals

- **Exactly-once delivery.** At-least-once with idempotent effect is the ceiling; exactly-once over AMQP is a mirage.
- **Replacing RabbitMQ** or adopting quorum queues, TLS, per-agent credentials, vhost isolation. Those are deployment-tier concerns → `SIP-Edge-Deployment-Profile` (with #352).
- **Changing the agent concurrency model.** One-at-a-time, in-order, prefetch=1 stays — an agent is a serial actor by design.
- **The ACI workload runner's poll-based `consume()`** (`adapters/capabilities/aci_executor.py`) — different surface, different lifecycle; migrate separately if it earns it.
- **Reply-direction redelivery.** SIP-0094 D12 stands for replies (see §5.1).

## 7. Acceptance Criteria

1. A comms handler that fails N times for the same delivery lands the message in `comms.dlq` with `x-death` history; the agent's consumer keeps processing subsequent messages; the DLQ depth metric and alert fire. No code path acks-and-discards a failed dispatch delivery.
2. Kill an agent mid-task. **Until completed-task dedup (§5.3) ships, the interim rule of §5.3a governs**: the redelivered envelope is NOT reprocessed — it yields a typed `FAILED` for the original task id, is acked, the queue drains, and any retry comes from recorded cycle governance. **Once §5.3 ships and §5.1 replaces the flag-only test with a death-path marker**, this criterion becomes its original form: the redelivered envelope is reprocessed exactly once end-to-end. In both eras: complete a task, then force redelivery of the same envelope — it is deduped (acked, logged, not reprocessed, no duplicate reply).
3. A publish to a nonexistent routing key surfaces as `QueueError` after retries — never silence.
4. `publish(delay_seconds=30)` delivers the message *after* ~30s, not before; nothing expires undelivered.
5. Reply-queue behavior is byte-identical to pre-SIP (ack-always, no redelivery) — regression-pinned.
6. `squadops doctor` fails if the DLX policy is absent on any `*_comms` queue.
7. **Live-validated on the deployed stack**: induced handler failure → DLQ; agent kill/restart → the behaviour §7.2 requires *for the era in force* (interim: typed `FAILED`, acked, no broker rerun; post-§5.3: idempotent redelivery); **whether `x-death` is absent on an automatic requeue after consumer death — **measured absent** in §5.3a, to be reconfirmed on the accepted deploy**; lite cycle green throughout.

## 8. Open Questions (design review)

1. **Duplicate handling on dedup hit:** drop+log (proposed — the executor's timeout/retry already covers a lost reply) vs re-publish a cached reply (requires storing replies; more machinery, faster recovery). Start with drop+log?
2. **Dedup store durability:** is a redis-restart-sized dedup gap acceptable (duplicate work, bounded by task timeout), or does Campaign require a Postgres-backed marker on the run ledger instead?
3. **DLQ topology:** one shared `comms.dlq` (proposed — one place to alert on and replay from) vs per-agent `{agent_id}_comms.dlq` (isolates blast radius, 7× the surface)?
4. **Port shape:** is the ack policy a `subscribe()` option (proposed) or a separate port method? Non-Rabbit adapters inherit the default `ack_always` either way; does the port `capabilities()` map need a `dead_letter` flag?
5. **Replay authz:** DLQ replay is a mutating op — `cycles:write` scope, or a new `comms:admin`?
