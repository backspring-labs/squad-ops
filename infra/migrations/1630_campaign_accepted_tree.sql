-- 1630_campaign_accepted_tree.sql
-- SIP-0109 §7.1, §12a (#1801): the campaign's accepted tree — its verified identity and the
-- cycle whose candidate it is. Every increment is proposed against it and every ruling binds to
-- it. Written only by a promotion's control-log transition, in that transaction; NULL until the
-- calibration cycle's tree is promoted. The two columns are set together or not at all.

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS accepted_identity TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS accepted_cycle_id TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_campaigns_accepted_together'
    ) THEN
        ALTER TABLE campaigns ADD CONSTRAINT ck_campaigns_accepted_together
            CHECK ((accepted_identity IS NULL) = (accepted_cycle_id IS NULL));
    END IF;
END $$;
