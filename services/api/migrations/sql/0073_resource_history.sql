-- =====================================================================================
-- 0073_resource_history: the resource history (Release 3.5, R3.5-M8; owner, 14 Nov 2026, 17:14: "instrument memory
--   CPU disk cache etc every 15 min configurable from admin screen and have it available and can be deleted. We should
--   be able to run this while testing or working and keeping it"). One row per sample: each container's memory, CPU,
--   network and disk, the Docker host's memory and swap, the file systems, the database's cache, and what was happening
--   (a self-test, a backup, a restore, a start-up). Samples older than a setting become one row an hour (resolution
--   'hour'); older than another setting they are deleted (the job eax.resource_sample). The running of the
--   installation, so the operations schema (R2.27, D630; its own connection string). Tables and checks only (D248).
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS operations;

CREATE TABLE IF NOT EXISTS operations.resource_samples (
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at          timestamptz NOT NULL DEFAULT now(),
    resolution  text        NOT NULL DEFAULT 'sample' CHECK (resolution IN ('sample', 'hour')),
    samples     integer     NOT NULL DEFAULT 1 CHECK (samples >= 1),
    activity    text[]      NOT NULL DEFAULT '{}',
    containers  jsonb       NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(containers) = 'array'),
    host        jsonb       NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(host) = 'object'),
    disks       jsonb       NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(disks) = 'array'),
    database    jsonb       NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(database) = 'object')
);
CREATE INDEX IF NOT EXISTS resource_samples_at ON operations.resource_samples (at);
COMMENT ON TABLE operations.resource_samples IS 'R3.5-M8: the resource history, a sample every few minutes (System Admin > Footprint)';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON operations.resource_samples TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON operations.resource_samples TO eax_migrator;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA operations TO eax_migrator;
    END IF;
END;
$$;
