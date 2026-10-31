-- 1698_campaign_accepted_commit.sql
-- SIP-0109 §24bv point 2, §24cd point 2: on a repository-backed Project the accepted tree is the
-- head of the campaign's branch in the managed clone, so it carries that commit beside its
-- identity (AcceptedTree.commit): the calibration record's commit, or an increment's captured one.
-- A sample application's tree is the vault's and names none. The row is the authority and the
-- clone's ref its projection. A commit is held only with an identity, by name, so re-applying is a
-- no-op.

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS accepted_commit TEXT;

ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS ck_campaigns_accepted_commit;
ALTER TABLE campaigns ADD CONSTRAINT ck_campaigns_accepted_commit
    CHECK (accepted_commit IS NULL
        OR (accepted_identity IS NOT NULL AND accepted_commit ~ '^[0-9a-f]{40}$'));
