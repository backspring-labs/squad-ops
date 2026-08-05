# ADR — Defended-Bespoke Architecture Decisions

**Status:** Accepted · **Established:** 2026-08-05 (1.5 Gate 1, #583) · **Source:**
the 2026-07-24 bespoke-inventions sweep (Tier 3), whose most repeated outcome was
*justified-LEAVE* — bespoke code a naive review (human or LLM) would flag as
reinventing a library or framework feature, that is deliberately correct here.

**Purpose:** pin these decisions once so they stop being re-litigated. Each entry is
the answer to "why doesn't this use X?" — settled, with the reasoning. A review that
wants to overturn one of these argues against the *why*, with new evidence; it does
not get to treat the bespoke shape itself as the defect. If a decision below stops
being true (a dependency gains the missing property, a constraint disappears), amend
this ADR in the same PR that changes the code.

---

## 1. Prefect is a passive UI tracker, not the orchestrator

Agents are distributed RabbitMQ request/reply workers. `@task`-wrapping queue
dispatch is not Prefect's execution model, and pretending otherwise would put a
second orchestrator in the loop. Deterministic task IDs and DB-backed resume
(SIP-0079) live outside Prefect on purpose; Prefect renders per-task progress
(SIP-0087) and nothing depends on it for correctness. The lane split is standing:
Console = cycle glue, Prefect = per-task visibility, LangFuse = LLM.

## 2. Reply router over `aio_pika.patterns.RPC`

SIP-0094's durable **shared per-agent reply queue** with `task_id` correlation
deliberately contradicts RPC's per-call exclusive queues. Per-call queues are exactly
the leaky pattern SIP-0094 retired: consumer-tag churn lost replies and leaked one
orphan queue per run. The router holds one long-lived subscription per agent and
resolves replies by `task_id`.

## 3. Hand-rolled publish-retry / resubscribe atop aio-pika

Each retry/resubscribe loop carries an issue-cited edge (`#245`-class) that
`RobustChannel` does not cover — recovery surfaces in `health()` instead of being
silently swallowed. Swapping to the library's recovery would reintroduce the failure
modes these loops were written against.

## 4. No tenacity / backoff library

Retry loops here are **domain classifications**, not exception predicates:
`outcome_class` routing, aimed re-rolls, correction decisions. A generic
retry-on-exception decorator collapses precisely the distinction the correction
protocol exists to make (transient vs product vs plan failure).

## 5. Run lifecycle FSM as transition tuples

The state machine validates `(current, target)` **values against persistence**, not
live objects — persistence-first, because the row is the truth and multiple processes
write it. FSM libraries bind transitions to live in-memory objects, which is the
wrong model for a lifecycle that must survive process death and be re-validated on
load.

## 6. `TaskEnvelope` frozen dataclasses + manual `to`/`from_dict`

A deliberate migration OFF pydantic. `from_dict` **drops unknown keys** by design —
that is rolling-deploy forward compatibility (an old agent reading a new envelope
keeps working, proven in v1.0.6). Frozen dataclasses + explicit codecs keep the A2A
message format (SIP-0031) a stable wire contract rather than a validation framework's
moving target.

## 7. Prompt renderer's minimal `{{var}}` substitution

`render_hash` provenance (#327 / SIP-0084) makes **byte-stable output load-bearing**:
prompt bytes are hashed for drift detection and fragment migrations are accepted only
on byte-equivalence (#452's standard). A real template engine (jinja2 filters,
whitespace control, autoescape) makes byte stability an accident instead of a
property.

## 8. Canonical-JSON sha256 idiom

Sorted-keys canonical serialization before hashing is what makes artifact/plan hashes
comparable across processes and releases (contract and manifest hash stability is a
release gate). A generic "hash the object" helper without the canonical form would
make every hash an implementation detail of dict ordering.

## 9. Checkpoint codec (SIP-0079)

Checkpoints are explicitly versioned payloads with their own codec rather than
pickled state: they must be readable by a *different, newer* process after a crash —
same forward-compat reasoning as entry 6, applied to resume.

## 10. Gate waits are DB polls

Human gate approval is a **crash-survivable wait**: the decision is a row, the waiter
polls it, and an orchestrator restart changes nothing. Event-driven gate delivery
would be faster and strictly less durable — the wait can outlive any process,
connection, or broker state.

## 11. Subprocess handling in test/probe runners

The runners manage spawn/timeout/kill directly (no plugin harness) because the
subject process is **untrusted squad output**: hard timeouts, exit-code semantics,
and output capture are the contract, and #498 added interpreter resolution strictly
after the safelist gate. A test-framework plugin would run untrusted code inside the
trusted process.

## 12. Secrets providers (SIP-0052)

`env` / `file` / `docker_secret` behind `SecretProvider` instead of a vault SDK: the
port is the abstraction, providers are deliberately dumb, and deployment profiles
choose. A vault dependency would invert that into infrastructure the smallest
profiles don't have.

## 13. Handler registry as a table

Capability handlers register in an explicit table rather than via decorators or
entry-point discovery: the registry is diffable, testable for drift (registry/event
parity tests), and load order is not import order. Implicit discovery is exactly how
handlers go silently missing in a container image.

## 14. Token file over keyring

The CLI stores its auth token in a file, not the OS keyring: agents and CI run
headless in containers where no keyring exists, and one code path that works
everywhere beats two paths where the privileged one is untestable in the environment
that matters.

## 15. `jose` over `PyJWT`

The auth boundary (SIP-0062) validates Keycloak JWTs via `jose` for its JWK-set
handling; the choice is pinned so dependency-hygiene passes don't "simplify" the auth
path into a subtly different validator.
