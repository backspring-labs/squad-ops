-- 1950_scenario_evaluation_quality_seeded.sql
-- SIP-0113 §10j, §10n (#2562): Lighthouse and axe on a second, seeded instance of each evaluated
-- tree, beside §10f's reading of the empty one. NULL on a record written before it: never read as
-- measured, nor as not measured.

ALTER TABLE scenario_evaluations ADD COLUMN IF NOT EXISTS quality_seeded JSONB;
