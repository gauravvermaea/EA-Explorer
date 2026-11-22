-- =====================================================================================
-- 0113_r10_scenario_planning: Release 10, scenario planning and game theory (D788, D818, D857).
-- A project's scenario planning studies, each run kept as a dated version (D857 (7)): the question, the template, the
-- driving forces, the critical uncertainties, the futures and their signposts, the players and their games, the options
-- and their scores in each future, the working (results) and the recommendation; and the signposts marked seen or not at
-- each project review (D857 (6)). Rows only: who may read and change them, and every figure, are in
-- eax/scenario_planning.py and eax/game_theory.py (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS proj.sp_runs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid            uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    project_id      bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    version         integer NOT NULL,                     -- 1, 2, ...: each run of the wizard a dated version
    status          text NOT NULL DEFAULT 'draft',        -- draft | done
    question        text NOT NULL DEFAULT '',
    template        text NOT NULL DEFAULT '',
    organisation    text NOT NULL DEFAULT '',             -- the player that is the project's own organisation
    forces          jsonb NOT NULL DEFAULT '[]',
    uncertainties   jsonb NOT NULL DEFAULT '[]',
    futures         jsonb NOT NULL DEFAULT '[]',
    signposts       jsonb NOT NULL DEFAULT '[]',
    players         jsonb NOT NULL DEFAULT '[]',
    games           jsonb NOT NULL DEFAULT '[]',
    options         jsonb NOT NULL DEFAULT '[]',
    scores          jsonb NOT NULL DEFAULT '[]',
    results         jsonb NOT NULL DEFAULT '{}',          -- the working, as worked out when finished
    recommendation  text NOT NULL DEFAULT '',
    recommended     text NOT NULL DEFAULT '',
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    UNIQUE (project_id, version)
);
CREATE INDEX IF NOT EXISTS sp_runs_project ON proj.sp_runs (project_id, version DESC);

CREATE TABLE IF NOT EXISTS proj.sp_signpost_marks (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id      bigint NOT NULL REFERENCES proj.sp_runs (id) ON DELETE CASCADE,
    signpost    text NOT NULL,                            -- the signpost's ref in its run (SP-1, ...)
    seen        boolean NOT NULL,
    note        text NOT NULL DEFAULT '',
    marked_by   text NOT NULL,
    marked_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sp_signpost_marks_run ON proj.sp_signpost_marks (run_id, marked_at DESC);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA proj TO eax_migrator;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA proj TO eax_migrator;
    END IF;
END;
$$;
