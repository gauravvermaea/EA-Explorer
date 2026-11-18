-- =====================================================================================
-- 0105_r6_6_db_integrity: the database maintenance runs keep the integrity checks and their repairs too (Release 6.6,
--   R6.6.1, D750): kinds integrity (the weekly and after-restore check with its safe fixes) and repair (orphan rows
--   removed on an admin's yes). A constraint only; no logic (D248).
-- =====================================================================================

ALTER TABLE core.db_maintenance_runs DROP CONSTRAINT IF EXISTS db_maintenance_runs_kind_check;
ALTER TABLE core.db_maintenance_runs ADD CONSTRAINT db_maintenance_runs_kind_check
    CHECK (kind IN ('check', 'tidy', 'compact', 'clear', 'locks', 'integrity', 'repair'));
