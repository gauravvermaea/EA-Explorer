-- =====================================================================================
-- 0093_r5_5_1_decisions: R5.5.1, architecture decision records and dispensations (owner, 15 Nov 2026, 18:20; agreed
--   20:31 to 20:34). Tables, columns, indexes and rows only; no logic (D248).
--   * a record of the organisation's own Governance Log has no project (project_id empty);
--   * a record's ADM phase, record type, sponsor, its template's fields, and when its end was warned of and reached;
--   * where a record was found (R5.5: the discovery AI may write records too);
--   * links both ways: to elements of a model, principles, standards, requirements and other records;
--   * a dispensation's statuses in the new lifecycle (Requested -> Proposed, Granted -> Accepted, Refused -> Rejected);
--   * the Architecture Board, a global role (eax-architecture-board) that accepts the organisation's records;
--   * the governance report's rows (copied from the projects' database by the governance job, test data left out)
--     and its view rpt.v_governance_decisions for the report login.
-- =====================================================================================

ALTER TABLE proj.gov_records ALTER COLUMN project_id DROP NOT NULL;
ALTER TABLE proj.gov_records ADD COLUMN IF NOT EXISTS phase text NOT NULL DEFAULT '';
ALTER TABLE proj.gov_records ADD COLUMN IF NOT EXISTS record_type text NOT NULL DEFAULT '';
ALTER TABLE proj.gov_records ADD COLUMN IF NOT EXISTS sponsor text NOT NULL DEFAULT '';
ALTER TABLE proj.gov_records ADD COLUMN IF NOT EXISTS fields jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE proj.gov_records ADD COLUMN IF NOT EXISTS warned_on date;          -- the notice before the end was sent
ALTER TABLE proj.gov_records ADD COLUMN IF NOT EXISTS ended_on date;           -- it was found ended (Expired) and told
ALTER TABLE proj.gov_records ADD COLUMN IF NOT EXISTS found_in jsonb;          -- R5.5: where the discovery AI found it
CREATE UNIQUE INDEX IF NOT EXISTS gov_records_yearly_ref ON proj.gov_records (ref) WHERE ref ~ '^(ADR|DISP)-[0-9]{4}-[0-9]+$';
CREATE INDEX IF NOT EXISTS gov_records_ending ON proj.gov_records (expires_on) WHERE kind = 'Dispensation';
CREATE INDEX IF NOT EXISTS gov_records_org ON proj.gov_records (kind, raised_on DESC) WHERE project_id IS NULL;

UPDATE proj.gov_records SET status = CASE status WHEN 'Requested' THEN 'Proposed' WHEN 'Granted' THEN 'Accepted'
                                                 WHEN 'Refused' THEN 'Rejected' ELSE status END
 WHERE kind = 'Dispensation' AND status IN ('Requested', 'Granted', 'Refused');

CREATE TABLE IF NOT EXISTS proj.gov_links (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    record_id   bigint NOT NULL REFERENCES proj.gov_records (id) ON DELETE CASCADE,
    link_kind   text NOT NULL CHECK (link_kind IN ('element', 'principle', 'standard', 'requirement', 'record')),
    relation    text NOT NULL DEFAULT 'affects'
                CHECK (relation IN ('affects', 'governed-by', 'meets', 'supersedes', 'depends-on')),
    target      text NOT NULL,                 -- an element's, principle's, standard's, requirement's or record's guid
    model_guid  uuid,                          -- the model an element is in
    label       text NOT NULL DEFAULT '',      -- its name when linked (shown when the target is gone)
    created_by  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (record_id, link_kind, relation, target)
);
CREATE INDEX IF NOT EXISTS gov_links_target ON proj.gov_links (link_kind, target);

INSERT INTO core.app_roles (code, name, scope, description, sort_order) VALUES
    ('architecture-board', 'Architecture Board', 'global',
     'Accepts or rejects the organisation''s architecture decision records and dispensations (in a project, its sign-off people do)', 6)
ON CONFLICT (code) DO NOTHING;
INSERT INTO core.role_mappings (keycloak_role, app_role, created_by)
VALUES ('eax-architecture-board', 'architecture-board', 'system:migration')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS core.governance_report (
    record_guid  uuid PRIMARY KEY,
    ref          text NOT NULL,
    kind         text NOT NULL,
    title        text NOT NULL,
    status       text NOT NULL,
    approval     text NOT NULL DEFAULT '',
    project_guid uuid,
    project_name text NOT NULL DEFAULT '',     -- empty: the organisation's own Governance Log
    phase        text NOT NULL DEFAULT '',
    owner        text NOT NULL DEFAULT '',
    sponsor      text NOT NULL DEFAULT '',
    raised_on    date,
    expires_on   date,
    days_left    integer,                      -- a dispensation's days to its end on the day it was copied
    ending_soon  boolean NOT NULL DEFAULT false,
    linked_elements integer NOT NULL DEFAULT 0,
    copied_at    timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW rpt.v_governance_decisions AS
SELECT record_guid, ref, kind, title, status, approval, project_guid,
       CASE WHEN project_name = '' THEN 'Organisation' ELSE project_name END AS project_name,
       phase, owner, sponsor, raised_on, expires_on, days_left, ending_soon, linked_elements, copied_at
  FROM core.governance_report;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.governance_report TO eax_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON proj.gov_links TO eax_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA proj TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.governance_report TO eax_migrator;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA proj TO eax_migrator;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA proj TO eax_migrator;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_report') THEN
        GRANT SELECT ON rpt.v_governance_decisions TO eax_report;
    END IF;
END;
$$;
