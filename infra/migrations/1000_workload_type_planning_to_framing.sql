-- 1000_workload_type_planning_to_framing.sql
-- Rename workload_type='planning' to 'framing' (SIP-0092 vocabulary discipline).
-- Two columns store the value:
--   1. cycle_runs.workload_type (TEXT) — the run's workload type (since 004)
--   2. cycle_registry.applied_defaults (JSONB) — workload_sequence entries
-- Idempotent: re-running is a no-op once 'planning' values are gone.

-- 1) Run-level workload_type
UPDATE cycle_runs
SET workload_type = 'framing'
WHERE workload_type = 'planning';

-- 2) Cycle-level applied_defaults.workload_sequence[*].type
UPDATE cycle_registry
SET applied_defaults = jsonb_set(
    applied_defaults,
    '{workload_sequence}',
    (
        SELECT jsonb_agg(
            CASE
                WHEN elem->>'type' = 'planning'
                    THEN jsonb_set(elem, '{type}', '"framing"'::jsonb)
                ELSE elem
            END
        )
        FROM jsonb_array_elements(applied_defaults->'workload_sequence') AS elem
    )
)
WHERE applied_defaults ? 'workload_sequence'
  AND EXISTS (
      SELECT 1
      FROM jsonb_array_elements(applied_defaults->'workload_sequence') AS elem
      WHERE elem->>'type' = 'planning'
  );

-- 3) Cycle-level execution_overrides.workload_sequence[*].type (defensive — same shape)
UPDATE cycle_registry
SET execution_overrides = jsonb_set(
    execution_overrides,
    '{workload_sequence}',
    (
        SELECT jsonb_agg(
            CASE
                WHEN elem->>'type' = 'planning'
                    THEN jsonb_set(elem, '{type}', '"framing"'::jsonb)
                ELSE elem
            END
        )
        FROM jsonb_array_elements(execution_overrides->'workload_sequence') AS elem
    )
)
WHERE execution_overrides ? 'workload_sequence'
  AND EXISTS (
      SELECT 1
      FROM jsonb_array_elements(execution_overrides->'workload_sequence') AS elem
      WHERE elem->>'type' = 'planning'
  );
