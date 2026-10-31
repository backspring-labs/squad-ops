-- 1808_project_derived_profiles.sql
-- SIP-0112 H.4, contract 8 (H.6), #2619.
--
-- A repository-backed product's derived development profile: what the squad's roles depend on in
-- it, and each gap, read from its tree, its Development Configuration revision and the inherited
-- baseline captured there. It is derived at each capture and recorded beside it, so one profile
-- belongs to one capture. A capture recorded before 2.5 has none (NULL), and a unit that pinned
-- it reads the profile as absent (H.6).

ALTER TABLE project_inherited_baselines ADD COLUMN IF NOT EXISTS derived_profile JSONB;
