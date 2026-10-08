-- 1701_authoring_envelopes_json.sql
-- SIP-0110 §0.11 (#2105): an envelope is stored as `json`, not `jsonb`. JSONB reorders an object's
-- keys, and a handler's prompt follows its inputs' order (the prior outputs a planning task is
-- shown render in the order they arrive), so an envelope read back from JSONB re-rendered a
-- different prompt. Found by the live reconstruction proof on dep_3005231a1e36: the calibration's
-- development.author_manifest differed at character 42,276, its prior outputs in the other order.
-- `json` keeps the text as written. Rows captured before this keep the order JSONB gave them.

ALTER TABLE authoring_envelopes ALTER COLUMN envelope TYPE json USING envelope::json;
