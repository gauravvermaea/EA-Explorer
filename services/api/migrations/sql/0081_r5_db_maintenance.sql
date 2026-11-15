-- =====================================================================================
-- 0081_r5_db_maintenance: R5.12 (D691): the record of database maintenance: each check, tidy, compact, clear and lock
--   action, with what was found and what was done. The work is in the API (eax/dbmaint.py); a table only here (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS core.db_maintenance_runs (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at        timestamptz NOT NULL DEFAULT now(),
    kind      text NOT NULL CHECK (kind IN ('check', 'tidy', 'compact', 'clear', 'locks')),
    by_whom   text NOT NULL,
    findings  jsonb NOT NULL DEFAULT '[]',
    actions   jsonb NOT NULL DEFAULT '[]',
    status    text NOT NULL DEFAULT 'ok',
    note      text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS db_maintenance_runs_at_idx ON core.db_maintenance_runs (at);
COMMENT ON TABLE core.db_maintenance_runs IS 'R5.12: every database check and maintenance run: found, done, by whom';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.db_maintenance_runs TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.db_maintenance_runs TO eax_migrator;
    END IF;
END;
$$;
