-- R5.1 (D697): the optimisation reports, kept and compared; what of each was applied, by whom (tables only, D248).
CREATE TABLE IF NOT EXISTS core.optimisation_reports (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at       timestamptz NOT NULL DEFAULT now(),
    by_whom  text NOT NULL,
    report   jsonb NOT NULL,                       -- {at, unused_days, suggestions: [{area, key, title, evidence, ...}]}
    applied  jsonb NOT NULL DEFAULT '{}'           -- {suggestion key: {by, at, choice}}
);
CREATE INDEX IF NOT EXISTS optimisation_reports_at_idx ON core.optimisation_reports (at);
COMMENT ON TABLE core.optimisation_reports IS 'R5.1: the optimisation reports: suggestions with evidence, and what was applied (a person''s yes)';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.optimisation_reports TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.optimisation_reports TO eax_migrator;
    END IF;
END;
$$;
