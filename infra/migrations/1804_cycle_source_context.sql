-- 1804_cycle_source_context.sql
-- SIP-0112 contract 1, §D.3, E.4.3 (#2410): an external Project's source, pinned on its Cycle
-- before dispatch. The shape the shared fixture records (project-source-context/v1): the
-- Project Record's version, the Development Configuration revision, the repository, and the
-- development baseline and integrated-upstream commits. NULL for a sample application, which
-- has no external source. Written once, at creation, and never changed for the Cycle.

ALTER TABLE cycle_registry ADD COLUMN IF NOT EXISTS source_context JSONB;
