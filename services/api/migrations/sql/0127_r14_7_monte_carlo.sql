-- =====================================================================================
-- 0127_r14_7_monte_carlo: Release 14.7, Monte Carlo simulation (D957, D962).
-- A project's Monte Carlo studies (kept in the project, the model never changed, D957 (3)): what each answers (roadmap
-- confidence, an option's business case, risk exposure, scenario planning with chances), its inputs (ranges and
-- events, drafted by the person's AI or typed on the screen, D957 (2)), its "move together" groups (D957 (5)), its
-- currency (D957 (6)); and each run kept with the inputs it used, its seed and its results. The organisation's risk
-- scale (what Likelihood and Impact 1 to 5 mean as a chance and a loss, D957 (6)) is one row for the installation.
-- Rows only: who may read and change them, and every figure, are in eax/monte_carlo_studies.py and
-- eax/monte_carlo.py (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS proj.mc_studies (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid        uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    project_id  bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    name        text NOT NULL,
    kind        text NOT NULL,                       -- roadmap | business_case | risk | scenarios
    question    text NOT NULL DEFAULT '',
    currency    text NOT NULL DEFAULT '',            -- one per study (D957 (6)); the installation's when empty
    unit        text NOT NULL DEFAULT '',            -- a roadmap's durations: days | weeks | months
    runs        integer NOT NULL DEFAULT 10000,
    seed        integer NOT NULL DEFAULT 1,
    inputs      jsonb NOT NULL DEFAULT '[]',         -- the ranges and events, each with who set it and where it came from
    groups      jsonb NOT NULL DEFAULT '[]',         -- [{name, members, strength}]
    settings    jsonb NOT NULL DEFAULT '{}',         -- targets, amounts, the futures' weights
    created_by  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text NOT NULL DEFAULT '',
    updated_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, name)
);
CREATE INDEX IF NOT EXISTS mc_studies_project ON proj.mc_studies (project_id);

CREATE TABLE IF NOT EXISTS proj.mc_runs (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid        uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    study_id    bigint NOT NULL REFERENCES proj.mc_studies (id) ON DELETE CASCADE,
    number      integer NOT NULL,                    -- 1, 2, ... in its study
    inputs      jsonb NOT NULL,                      -- what it ran: the inputs, groups and settings as they were
    runs        integer NOT NULL,
    seed        integer NOT NULL,
    digest      text NOT NULL,
    result      jsonb NOT NULL,
    run_by      text NOT NULL,
    run_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (study_id, number)
);
CREATE INDEX IF NOT EXISTS mc_runs_study ON proj.mc_runs (study_id, number DESC);

CREATE TABLE IF NOT EXISTS proj.mc_risk_scale (
    id          integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    likelihood  jsonb NOT NULL,                      -- {"1": 0.05, ...}: the chance in a year
    impact      jsonb NOT NULL,                      -- {"1": [low, likely, high], ...}: a loss
    currency    text NOT NULL DEFAULT '',
    set_by      text NOT NULL,
    set_at      timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA proj TO eax_migrator;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA proj TO eax_migrator;
    END IF;
END;
$$;
