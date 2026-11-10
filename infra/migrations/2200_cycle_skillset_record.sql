-- 2200_cycle_skillset_record.sql
-- SIP-0116 §10, phase 1 (#3011): what a Cycle's work required and what its squad's agents
-- supplied, recorded on the Cycle beside squad_profile_snapshot_ref (Q57). The shape is
-- squadops.skillset-record/v1: the base set, the squad and its roster hash, the development
-- profile and its requirements, the assignment, the content digests, and the record's own
-- digest. NULL for a Cycle created before the record existed. Written once, at creation.

ALTER TABLE cycle_registry ADD COLUMN IF NOT EXISTS skillset_record JSONB;
