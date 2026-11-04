-- 2101_goal_set_revision_change.sql
-- SIP-0115 §5.4, §5.5a, §6 (#2886, slice 3): the action that wrote a goal-set revision, when it was
-- one of slice 3's rather than a whole-document edit: a candidate added, promoted or dropped, or a
-- backlog item split. ``{"kind", "subject", "position"?, "split_into"?, "campaign_id"?}``
-- (``Change.to_document``): the kind, the candidate's or item's id, the position a promoted
-- candidate took, the ids a split's parts took the parent's place with, and the Campaign the crew
-- acted within (Q41). NULL on every revision written before this, and on every whole-document
-- write: additive, and read as "an edit".
--
-- The derived backlog view reads it to tell a split parent (``removed`` with its ``split_into``)
-- from an item the owner removed. Nothing else derived is stored (2100's rule stands).

ALTER TABLE project_goal_set_revisions
    ADD COLUMN IF NOT EXISTS change JSONB;
