-- =====================================================================================
-- 0097_discovery_fk_indexes: the two foreign keys of Release 5.5's discovery tables that had no index (the self-test's
-- database check, 16 Nov 2026, 15:02: "foreign keys have an index (speed): core.discovery_found_in(resource_id);
-- core.discovery_not_found(run_id)"): removing a source, and deleting a run or a project, no longer read the whole
-- table. Indexes only; no logic (D248).
-- =====================================================================================

CREATE INDEX IF NOT EXISTS discovery_found_in_resource ON core.discovery_found_in (resource_id);
CREATE INDEX IF NOT EXISTS discovery_not_found_run ON core.discovery_not_found (run_id);
