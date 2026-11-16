-- =====================================================================================
-- 0098_r5_6_job_priorities: job priorities (R5.6-Q2; owner, 15 Nov 2026, 22:47; agreed 16 Nov 2026, 15:46): the levels
--   changed on System Admin › Jobs (a kind not listed keeps the level it ships with, eax/job_priorities.py), and each
--   kind's skips when the queue was too full (in a row, in all, the last). Tables only; no logic (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS core.job_priorities (
    task_name  text PRIMARY KEY,
    level      text NOT NULL CHECK (level IN ('high', 'normal', 'low')),
    set_by     text NOT NULL,
    set_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.job_skips (
    task_name  text PRIMARY KEY,
    in_row     integer NOT NULL DEFAULT 0,
    total      integer NOT NULL DEFAULT 0,
    last_at    timestamptz
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.job_priorities, core.job_skips TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.job_priorities, core.job_skips TO eax_migrator;
    END IF;
END;
$$;
