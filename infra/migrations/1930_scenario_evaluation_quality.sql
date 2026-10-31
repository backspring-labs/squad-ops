-- 1930_scenario_evaluation_quality.sql
-- SIP-0113 §4.2 (#2416): each evaluation's Lighthouse and axe reading, measured on the instance the
-- scenarios read. NULL on a record written before the baselines existed: never read as measured,
-- nor as not measured.

ALTER TABLE scenario_evaluations ADD COLUMN IF NOT EXISTS quality JSONB;
