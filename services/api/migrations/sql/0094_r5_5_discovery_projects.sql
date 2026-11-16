-- =====================================================================================
-- 0094_r5_5_discovery_projects: R5.5, enterprise discovery (the owner's design, 15 Nov 2026, 20:11 to 20:28: "EA explorer
--   will only be source and sink of information. Let MCP and LLm run this one"). EA Explorer keeps:
--   * discovery projects: a name, a target model, the sources (resources) it covers, the defaults of a run (read only
--     what is new, or everything; mark or delete what is gone) and its schedule, a marker of when a run is due (the
--     people's own AI runs and schedules it; EA Explorer runs nothing);
--   * each source's kind, where it is, what to include, whether attachments are read, how it signs in (the method
--     only: a sign-in is tested, then forgotten) and where the last run got to;
--   * runs: who ran them ("AI agent on behalf of" the person who set up the project), the tags before and after;
--   * where each element was found (Found in), what was skipped as NOT FOR AI USE (titles only), what may be the same
--     as an element already there, and what was no longer found;
--   * the Discovery Admin, a global role (eax-discovery-admin) that sets up discovery projects for any model.
--   Tables and rows only: no logic in the database (D248).
-- =====================================================================================

INSERT INTO core.app_roles (code, name, scope, description, sort_order) VALUES
    ('discovery-admin', 'Discovery Admin', 'global',
     'Sets up discovery projects and their sources for any model; the people''s own AI runs them through MCP', 7)
ON CONFLICT (code) DO NOTHING;
INSERT INTO core.role_mappings (keycloak_role, app_role, created_by)
VALUES ('eax-discovery-admin', 'discovery-admin', 'system:migration')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS core.discovery_projects (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid          uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    name          text NOT NULL,
    purpose       text NOT NULL DEFAULT '',
    target_model  uuid NOT NULL,                     -- the model the AI commits into (a child to review first, or the main one)
    set_up_by     text NOT NULL,                     -- the AI works "on behalf of" this person
    read_default  text NOT NULL DEFAULT 'new' CHECK (read_default IN ('new', 'all')),
    gone_default  text NOT NULL DEFAULT 'mark' CHECK (gone_default IN ('mark', 'delete')),
    schedule      text NOT NULL DEFAULT 'none' CHECK (schedule IN ('none', 'daily', 'weekly', 'monthly')),
    schedule_day  integer NOT NULL DEFAULT 1,        -- weekly: 1 Monday to 7 Sunday; monthly: 1 to 28
    schedule_time text NOT NULL DEFAULT '02:00',     -- HH:MM, the installation's time zone (UTC)
    next_due_at   timestamptz,                       -- when the next run is due (none without a schedule)
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    updated_by    text NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS discovery_projects_name ON core.discovery_projects (lower(name));
CREATE INDEX IF NOT EXISTS discovery_projects_due ON core.discovery_projects (next_due_at) WHERE next_due_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS core.discovery_resources (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id   bigint NOT NULL REFERENCES core.discovery_projects (id) ON DELETE CASCADE,
    kind         text NOT NULL,                      -- mailbox, folder, ftp, sftp, sharepoint, git, wiki, tickets, ...
    name         text NOT NULL,
    location     text NOT NULL DEFAULT '',           -- where it is: an address, a path, a site, a repository
    include      text NOT NULL DEFAULT '',           -- what to read (folders, labels, file kinds); empty: everything shared
    attachments  boolean NOT NULL DEFAULT true,      -- attachments are read (owner, 20:24)
    sign_in      text NOT NULL DEFAULT 'none' CHECK (sign_in IN ('none', 'key', 'basic', 'certificate', 'sso')),
    tested_at    timestamptz,                        -- the last Test the link: when, whether it answered, what it said
    test_ok      boolean,
    test_note    text NOT NULL DEFAULT '',
    position     text NOT NULL DEFAULT '',           -- where the last run got to (for "only what is new")
    position_at  timestamptz,
    enabled      boolean NOT NULL DEFAULT true,
    created_by   text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS discovery_resources_project ON core.discovery_resources (project_id);

CREATE TABLE IF NOT EXISTS core.discovery_runs (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid          uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    project_id    bigint NOT NULL REFERENCES core.discovery_projects (id) ON DELETE CASCADE,
    number        integer NOT NULL,
    status        text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'finished', 'abandoned')),
    run_by        text NOT NULL,                     -- the AI's own sign-in (its MCP token or machine credential)
    on_behalf_of  text NOT NULL,                     -- the person who set up the project
    ai_client     text NOT NULL DEFAULT '',          -- the AI client that ran it, as it says
    read_mode     text NOT NULL CHECK (read_mode IN ('new', 'all')),
    gone_mode     text NOT NULL CHECK (gone_mode IN ('mark', 'delete')),
    start_tag     uuid,                              -- the target model's tag before the run
    end_tag       uuid,                              -- and after it: comparing the two shows what the run changed
    summary       text NOT NULL DEFAULT '',
    counts        jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    UNIQUE (project_id, number)
);

CREATE TABLE IF NOT EXISTS core.discovery_found_in (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        bigint NOT NULL REFERENCES core.discovery_runs (id) ON DELETE CASCADE,
    model_guid    uuid NOT NULL,
    element_kind  text NOT NULL DEFAULT 'entity' CHECK (element_kind IN ('entity', 'relationship')),
    element_ref   text NOT NULL,                     -- as the AI named it (name, display ID or guid)
    element_guid  uuid,                              -- resolved once the run's changes are part of the model
    element_name  text NOT NULL DEFAULT '',
    resource_id   bigint REFERENCES core.discovery_resources (id) ON DELETE SET NULL,
    resource_name text NOT NULL DEFAULT '',
    item          text NOT NULL DEFAULT '',          -- the mail, file, page, ticket or commit
    place         text NOT NULL DEFAULT '',          -- where in it: page, line, slide, moment in a recording
    link          text NOT NULL DEFAULT '',          -- to open the item where the person may
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS discovery_found_in_element ON core.discovery_found_in (model_guid, element_guid);
CREATE INDEX IF NOT EXISTS discovery_found_in_run ON core.discovery_found_in (run_id);

CREATE TABLE IF NOT EXISTS core.discovery_skipped (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        bigint NOT NULL REFERENCES core.discovery_runs (id) ON DELETE CASCADE,
    resource_name text NOT NULL DEFAULT '',
    title         text NOT NULL,                     -- the title, place and date only: never what it holds
    place         text NOT NULL DEFAULT '',
    item_date     text NOT NULL DEFAULT '',
    reason        text NOT NULL DEFAULT 'Marked NOT FOR AI USE OR AUTOMATED PROCESSING'
);
CREATE INDEX IF NOT EXISTS discovery_skipped_run ON core.discovery_skipped (run_id);

CREATE TABLE IF NOT EXISTS core.discovery_maybe_same (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        bigint NOT NULL REFERENCES core.discovery_runs (id) ON DELETE CASCADE,
    model_guid    uuid NOT NULL,
    element_ref   text NOT NULL,
    element_guid  uuid,
    other_ref     text NOT NULL,
    other_guid    uuid,
    note          text NOT NULL DEFAULT '',
    resolved_by   text NOT NULL DEFAULT '',
    resolved_at   timestamptz
);
CREATE INDEX IF NOT EXISTS discovery_maybe_same_run ON core.discovery_maybe_same (run_id);

CREATE TABLE IF NOT EXISTS core.discovery_not_found (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        bigint NOT NULL REFERENCES core.discovery_runs (id) ON DELETE CASCADE,
    model_guid    uuid NOT NULL,
    element_guid  uuid,
    element_name  text NOT NULL DEFAULT '',
    resource_name text NOT NULL DEFAULT '',
    action        text NOT NULL CHECK (action IN ('marked', 'deleted'))
);
CREATE INDEX IF NOT EXISTS discovery_not_found_element ON core.discovery_not_found (model_guid, element_guid);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.discovery_projects, core.discovery_resources, core.discovery_runs,
              core.discovery_found_in, core.discovery_skipped, core.discovery_maybe_same, core.discovery_not_found TO eax_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.discovery_projects, core.discovery_resources, core.discovery_runs,
              core.discovery_found_in, core.discovery_skipped, core.discovery_maybe_same, core.discovery_not_found TO eax_migrator;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO eax_migrator;
    END IF;
END;
$$;
