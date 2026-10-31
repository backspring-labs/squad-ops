-- 1792_memory_cycle_bindings.sql
-- SIP-0110 §5ad (#2179 T16; the owner's ruling of 2026-10-20): a campaign cycle's own bindings of
-- its campaign's pinned instructions. The campaign's snapshot fixes which instruction revisions are
-- in force; each cycle binds their @current references at its own pinned source commit, and every
-- dispatch of the cycle reads these rows. One row per cycle, record and revision, written once:
-- a launch, a re-binding and the sweep's fill each write without reading the others' rows, and a
-- row a dispatch may have been handed never changes. A re-binding writes its revision's rows
-- before its snapshot names that revision, so a dispatch reading either revision finds its own.
-- Additive: a cycle with no row reads its campaign's pin.

CREATE TABLE IF NOT EXISTS memory_cycle_bindings (
    cycle_id     TEXT NOT NULL,
    record_id    TEXT NOT NULL,
    revision     INTEGER NOT NULL,
    unit_kind    TEXT NOT NULL CHECK (unit_kind IN ('cycle', 'campaign')),
    unit_id      TEXT NOT NULL,
    bound_at     TIMESTAMPTZ NOT NULL,
    entry_body   JSON NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cycle_id, record_id, revision)
);
