-- 1792_memory_cycle_bindings.sql
-- SIP-0110 §5ad (#2179 T16; the owner's ruling of 2026-10-20): a campaign cycle's own bindings of
-- its campaign's pinned instructions. The campaign's snapshot fixes which instruction revisions are
-- in force; each cycle binds their @current references at its own pinned source commit when the
-- campaign launches it, and every dispatch of the cycle reads this row. A re-binding of the
-- campaign replaces a running cycle's row. Additive: a cycle with no row reads its campaign's pin.

CREATE TABLE IF NOT EXISTS memory_cycle_bindings (
    cycle_id      TEXT PRIMARY KEY,
    unit_kind     TEXT NOT NULL CHECK (unit_kind IN ('cycle', 'campaign')),
    unit_id       TEXT NOT NULL,
    bound_at      TIMESTAMPTZ NOT NULL,
    binding_body  JSON NOT NULL,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_cycle_bindings_unit ON memory_cycle_bindings (unit_kind, unit_id);
