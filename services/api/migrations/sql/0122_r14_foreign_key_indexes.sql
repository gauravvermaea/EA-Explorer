-- =====================================================================================
-- 0122_r14_foreign_key_indexes: Release 14 (R14.38). The full test of 24 Nov 2026 found five foreign keys of the
--   Release 12 project tables without an index (db check "foreign keys have an index"): each one is looked up when
--   its parent row is read or deleted, so each gets one. Indexes only (D248).
-- =====================================================================================

CREATE INDEX IF NOT EXISTS backlog_items_item_idx     ON proj.backlog_items (item_id);
CREATE INDEX IF NOT EXISTS backlog_items_sprint_idx   ON proj.backlog_items (sprint_id);
CREATE INDEX IF NOT EXISTS sprint_decisions_backlog_idx ON proj.sprint_decisions (backlog_id);
CREATE INDEX IF NOT EXISTS raci_item_idx              ON proj.raci (item_id);
CREATE INDEX IF NOT EXISTS raci_step_idx              ON proj.raci (step_id);
