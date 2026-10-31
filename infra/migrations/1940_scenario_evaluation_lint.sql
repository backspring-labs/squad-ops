-- 1940_scenario_evaluation_lint.sql
-- SIP-0113 §4.2 (#2416): each evaluation's lint by #1937's rule sets, over the evaluated tree as
-- delivered. NULL on a record written before it: never read as measured, nor as not measured.

ALTER TABLE scenario_evaluations ADD COLUMN IF NOT EXISTS lint JSONB;
