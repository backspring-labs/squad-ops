---
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

Redis (already in the stack) as the dedup store: `SETNX comms:done:{task_id}` with a TTL (~24h, config) written **after** the reply publish succeeds. On delivery, a hit → ack + structured log (`duplicate_of_completed_task`), no reprocess. Semantics chosen deliberately: dedup on *completed*, not on *seen* — a crash mid-processing leaves no marker, so the redelivery reprocesses (at-least-once preserved). Redis loss shrinks the dedup window to zero until it refills; the failure mode is duplicate work, never lost work — acceptable degradation, noted in Open Questions.

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
2. Kill an agent mid-task: the redelivered envelope is reprocessed exactly once end-to-end. Complete a task, then force redelivery of the same envelope: it is deduped (acked, logged, not reprocessed, no duplicate reply).
3. A publish to a nonexistent routing key surfaces as `QueueError` after retries — never silence.
4. `publish(delay_seconds=30)` delivers the message *after* ~30s, not before; nothing expires undelivered.
5. Reply-queue behavior is byte-identical to pre-SIP (ack-always, no redelivery) — regression-pinned.
6. `squadops doctor` fails if the DLX policy is absent on any `*_comms` queue.
7. **Live-validated on the deployed stack**: induced handler failure → DLQ; agent kill/restart → idempotent redelivery; lite cycle green throughout.

## 8. Open Questions (design review)

1. **Duplicate handling on dedup hit:** drop+log (proposed — the executor's timeout/retry already covers a lost reply) vs re-publish a cached reply (requires storing replies; more machinery, faster recovery). Start with drop+log?
2. **Dedup store durability:** is a redis-restart-sized dedup gap acceptable (duplicate work, bounded by task timeout), or does Campaign require a Postgres-backed marker on the run ledger instead?
3. **DLQ topology:** one shared `comms.dlq` (proposed — one place to alert on and replay from) vs per-agent `{agent_id}_comms.dlq` (isolates blast radius, 7× the surface)?
4. **Port shape:** is the ack policy a `subscribe()` option (proposed) or a separate port method? Non-Rabbit adapters inherit the default `ack_always` either way; does the port `capabilities()` map need a `dead_letter` flag?
5. **Replay authz:** DLQ replay is a mutating op — `cycles:write` scope, or a new `comms:admin`?
