-- R5.19: the server sizing estimates people save (their inputs, the assumptions used and the answer), to compare and
-- to hand to an infrastructure team. Tables only (D248).
CREATE TABLE IF NOT EXISTS core.sizing_estimates (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at       timestamptz NOT NULL DEFAULT now(),
    by_whom  text NOT NULL,
    name     text NOT NULL CHECK (btrim(name) <> ''),
    result   jsonb NOT NULL                          -- eax/sizing.py's answer: inputs, assumptions, containers, server, disk
);
CREATE INDEX IF NOT EXISTS sizing_estimates_at_idx ON core.sizing_estimates (at);
COMMENT ON TABLE core.sizing_estimates IS 'R5.19: saved server sizing estimates (a best estimate, with the assumptions used)';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.sizing_estimates TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.sizing_estimates TO eax_migrator;
    END IF;
END;
$$;
