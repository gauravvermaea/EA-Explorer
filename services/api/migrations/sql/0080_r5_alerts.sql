-- =====================================================================================
-- 0080_r5_alerts: R5.9 (D689): the alerts system's tables. The checks, their states and the telling are in the API
--   (eax/alerts.py, the job eax.alerts_run every minute); here only where they are kept (D248: no logic here).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS core.alert_checks (
    check_key        text PRIMARY KEY,
    what             text NOT NULL DEFAULT '',
    state            text NOT NULL DEFAULT 'OK' CHECK (state IN ('OK', 'WARNING', 'CRITICAL', 'UNKNOWN')),
    pending          text NOT NULL DEFAULT 'OK',
    streak           integer NOT NULL DEFAULT 0,
    changes          jsonb NOT NULL DEFAULT '[]',
    since            timestamptz NOT NULL DEFAULT now(),
    value            double precision,
    message          text NOT NULL DEFAULT '',
    acked_by         text,
    acked_at         timestamptz,
    ack_note         text,
    last_notified_at timestamptz,
    escalated        boolean NOT NULL DEFAULT false,
    flapping         boolean NOT NULL DEFAULT false,
    checked_at       timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE core.alert_checks IS 'R5.9: each check''s state now, since when, acknowledged by whom';

CREATE TABLE IF NOT EXISTS core.alert_history (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    check_key  text NOT NULL,
    state      text NOT NULL,
    value      double precision,
    message    text NOT NULL DEFAULT '',
    at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS alert_history_at_idx ON core.alert_history (at);
COMMENT ON TABLE core.alert_history IS 'R5.9: every change of state, kept 90 days';

CREATE TABLE IF NOT EXISTS core.alert_silences (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    check_key   text NOT NULL DEFAULT '*',
    until       timestamptz NOT NULL,
    reason      text NOT NULL DEFAULT '',
    created_by  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE core.alert_silences IS 'R5.9: a check (or * for all) silenced, or a planned downtime, until a time';

CREATE TABLE IF NOT EXISTS core.alert_config (
    key       text PRIMARY KEY,
    warning   double precision,
    critical  double precision,
    enabled   boolean NOT NULL DEFAULT true,
    hold      integer
);
COMMENT ON TABLE core.alert_config IS 'R5.9: a built-in check''s levels as set on System Admin > Alerts (none: the defaults)';

CREATE TABLE IF NOT EXISTS core.alert_custom (
    key         text PRIMARY KEY,
    name        text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('url', 'sql')),
    target      text NOT NULL,
    warning     double precision NOT NULL,
    critical    double precision NOT NULL,
    enabled     boolean NOT NULL DEFAULT true,
    hold        integer,
    created_by  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE core.alert_custom IS 'R5.9: checks a person adds: an address that answers, or a read-only query that returns a number';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.alert_checks, core.alert_history, core.alert_silences, core.alert_config,
              core.alert_custom TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.alert_checks, core.alert_history, core.alert_silences, core.alert_config,
              core.alert_custom TO eax_migrator;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO eax_migrator;
    END IF;
END;
$$;
