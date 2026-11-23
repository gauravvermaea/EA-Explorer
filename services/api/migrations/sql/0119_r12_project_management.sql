-- =====================================================================================
-- 0119_r12_project_management: Release 12, the base improvements (R12.4, D879, D884, D889).
--   * project management (TOGAF Series Guide: Project Management and the ADM, G188): each project's settings (how it
--     records RACI: none, per phase, per deliverable or per step, chosen at setup; the phases whose end is an approval
--     gate, chosen by the architect; the roadmap's period, free), a plan of its phases, its milestones, its RACI and
--     its status reports;
--   * the risk register: a Risk record of the Governance log describes the risk Assessment in a model (R12.5, D887);
--   * TOGAF roles and skill levels beside each person's skills (R12.8);
--   * maps always live: a library item, and the project item made from it, may name the view that shows it live from
--     the project's primary working model (the Organization Map, the Information Map, the Business Capability Map,
--     the business scenarios and the building blocks).
-- Every existing project is brought up to date by the seed at start (D884); rows only (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS proj.pm_settings (
    project_id    bigint PRIMARY KEY REFERENCES proj.projects (id) ON DELETE CASCADE,
    raci          text NOT NULL DEFAULT 'none' CHECK (raci IN ('none', 'phase', 'deliverable', 'step')),
    gates         text[] NOT NULL DEFAULT '{}',        -- phases whose end needs their chosen deliverables approved
    roadmap_from  date,                                 -- the roadmap's period: free, both empty for all of it
    roadmap_to    date,
    roadmap_marks text NOT NULL DEFAULT 'year' CHECK (roadmap_marks IN ('month', 'quarter', 'year')),
    modified_by   text,
    modified_at   timestamptz,
    CHECK (roadmap_from IS NULL OR roadmap_to IS NULL OR roadmap_to > roadmap_from)
);

CREATE TABLE IF NOT EXISTS proj.phase_plans (
    project_id    bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    cycle         integer NOT NULL DEFAULT 1,
    phase         text NOT NULL,
    starts_on     date NOT NULL,
    ends_on       date NOT NULL,
    PRIMARY KEY (project_id, cycle, phase),
    CHECK (ends_on >= starts_on)
);

CREATE TABLE IF NOT EXISTS proj.milestones (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid          uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    project_id    bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    name          text NOT NULL,
    due_on        date NOT NULL,
    phase         text NOT NULL DEFAULT '',
    note          text NOT NULL DEFAULT '',
    done_at       timestamptz,
    done_by       text,
    created_by    text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS milestones_project ON proj.milestones (project_id, due_on);

-- who is Responsible, Accountable, Consulted or Informed: for a phase, a deliverable or a step, as the project's setting
-- says (one of phase, item_id, step_id is set: kept by reference so a project's backup and restore keep them)
CREATE TABLE IF NOT EXISTS proj.raci (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id    bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    scope         text NOT NULL CHECK (scope IN ('phase', 'deliverable', 'step')),
    phase         text,
    item_id       bigint REFERENCES proj.items (id) ON DELETE CASCADE,
    step_id       bigint REFERENCES proj.steps (id) ON DELETE CASCADE,
    username      text NOT NULL,
    letter        text NOT NULL CHECK (letter IN ('R', 'A', 'C', 'I')),
    CHECK ((scope = 'phase' AND phase IS NOT NULL AND item_id IS NULL AND step_id IS NULL)
        OR (scope = 'deliverable' AND item_id IS NOT NULL AND phase IS NULL AND step_id IS NULL)
        OR (scope = 'step' AND step_id IS NOT NULL AND phase IS NULL AND item_id IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS raci_one ON proj.raci (project_id, scope, coalesce(phase, ''), coalesce(item_id, 0),
                                                       coalesce(step_id, 0), username, letter);

CREATE TABLE IF NOT EXISTS proj.status_reports (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id    bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    at            timestamptz NOT NULL DEFAULT now(),
    by_user       text NOT NULL,
    rag           text NOT NULL CHECK (rag IN ('green', 'amber', 'red')),
    summary       text NOT NULL,
    next_steps    text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS status_reports_project ON proj.status_reports (project_id, at DESC);

-- the risk register (R12.5, D887): a Risk record of the Governance log "describes" the risk Assessment in a model
ALTER TABLE proj.gov_links DROP CONSTRAINT IF EXISTS gov_links_relation_check;
ALTER TABLE proj.gov_links ADD CONSTRAINT gov_links_relation_check
    CHECK (relation IN ('affects', 'governed-by', 'meets', 'supersedes', 'depends-on', 'describes'));

-- TOGAF roles and skill levels beside each person's own skills (R12.8, D879): the roles they hold and a level 1 to 4 for
-- each category of architecture skill (TOGAF Series Guides G198, G249)
ALTER TABLE personal.user_skills ADD COLUMN IF NOT EXISTS togaf_roles text[] NOT NULL DEFAULT '{}';
ALTER TABLE personal.user_skills ADD COLUMN IF NOT EXISTS togaf_levels jsonb NOT NULL DEFAULT '{}';

ALTER TABLE proj.lib_items ADD COLUMN IF NOT EXISTS live_view text NOT NULL DEFAULT '';
ALTER TABLE proj.items ADD COLUMN IF NOT EXISTS live_view text NOT NULL DEFAULT '';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA proj TO eax_migrator;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA proj TO eax_migrator;
    END IF;
END;
$$;
