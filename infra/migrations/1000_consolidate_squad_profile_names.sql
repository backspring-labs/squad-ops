-- 1000: #173 — consolidate squad-profile names (Spark migration range 1000–1099).
--
-- Renames the 27b builder profile `spark-squad-with-builder` → `full`, drops the
-- redundant no-builder 27b `full-squad` (its work moves to `full`, which now carries
-- the builder — the A/B-confirmed quality lever), and repoints the active profile to
-- the always-runnable `smoke` (fixes the full-squad-on-a-non-Spark-box footgun).
--
-- Idempotent and safe on both fresh and existing databases, and safe to re-run: the
-- runtime applies migrations at startup and there is no migration-tracking table yet
-- (#158). Every statement no-ops on a second pass.

BEGIN;

-- Drop the retired no-builder 27b profile.
DELETE FROM squad_profiles WHERE profile_id = 'full-squad';

-- Rename the builder 27b profile to the new tier name and align its metadata with YAML.
UPDATE squad_profiles
   SET profile_id  = 'full',
       name        = 'Full Squad',
       description = 'All 6 roles incl. builder on qwen3.6:27b — uniform single-loaded '
                     'model on Spark (no swap overhead), max reasoning depth at the ~16 '
                     'tps ceiling. The quality squad. (Consolidates the former full-squad '
                     '+ spark-squad-with-builder; #173.)',
       updated_at  = NOW()
 WHERE profile_id = 'spark-squad-with-builder';

-- Seed-log hygiene: drop the retired ids so the log mirrors the YAML. Mark `full`
-- seeded ONLY if it now exists (existing DB, post-rename); on a FRESH DB `full` does
-- not exist yet, so it stays unseeded and is seeded normally from YAML at startup.
DELETE FROM squad_profiles_seed_log WHERE profile_id IN ('full-squad', 'spark-squad-with-builder');
INSERT INTO squad_profiles_seed_log (profile_id)
     SELECT 'full' WHERE EXISTS (SELECT 1 FROM squad_profiles WHERE profile_id = 'full')
ON CONFLICT DO NOTHING;

-- Footgun fix: repoint the active profile to the always-runnable `smoke`, but only if
-- dropping `full-squad` left no active profile. One-time + re-run safe, and never
-- clobbers an operator's later `set_active_profile` choice (e.g. they pick `full`).
UPDATE squad_profiles
   SET is_active = TRUE
 WHERE profile_id = 'smoke'
   AND NOT EXISTS (SELECT 1 FROM squad_profiles WHERE is_active = TRUE);

COMMIT;
