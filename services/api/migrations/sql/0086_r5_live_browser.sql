-- R5.20: watching the self-test's browsers live. One row per browser the runner drives in a running run: what it is on
-- (journey, step, address) and the newest frame only (a newer one replaces it: a slow viewer skips, never falls
-- behind); when a viewer last asked (the runner streams only while someone watches, at full rate only for the one shown
-- large); and per run the controls (paused, a step to take). Rows go when the run is collected. Tables only (D248).
CREATE TABLE IF NOT EXISTS tests.live_browsers (
    run_id        bigint NOT NULL,
    browser       text NOT NULL,                    -- the runner's own name for it (sweep, journey-<n>)
    label         text NOT NULL DEFAULT '',         -- what it is doing: the page sweep, a journey's name and role
    step          text NOT NULL DEFAULT '',
    url           text NOT NULL DEFAULT '',
    frame         bytea,                            -- the newest JPEG frame
    frame_seq     integer NOT NULL DEFAULT 0,
    frame_at      timestamptz,
    thumb         bytea,                            -- a small still for the tiles (every few seconds while watched)
    watched_until timestamptz,                      -- a viewer has the panel open (30 seconds after its last ask)
    large_until   timestamptz,                      -- a viewer shows this browser large (full rate)
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, browser)
);
CREATE TABLE IF NOT EXISTS tests.live_controls (
    run_id     bigint PRIMARY KEY,
    paused     boolean NOT NULL DEFAULT false,      -- pause after each step (a run started to be watched)
    steps      integer NOT NULL DEFAULT 0,          -- Step: how many steps to take while paused
    slow       boolean NOT NULL DEFAULT false,      -- slow motion was chosen when it started
    by_whom    text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE tests.live_browsers IS 'R5.20: the self-test''s browsers while a run is watched: the newest frame only, who watches';
COMMENT ON TABLE tests.live_controls IS 'R5.20: pause after each step, step and continue, slow motion, for a run started to be watched';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON tests.live_browsers, tests.live_controls TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON tests.live_browsers, tests.live_controls TO eax_migrator;
    END IF;
END;
$$;
