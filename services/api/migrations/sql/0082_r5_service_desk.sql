-- =====================================================================================
-- 0082_r5_service_desk: R5.11 (D692): the service desk: the catalogue of what people can ask for, the requests
--   (tickets), their history and their files; and the catalogue's first types (Super Admins change them on System
--   Admin > Service catalogue). The workflow is in the API (eax/servicedesk.py); tables and rows only here (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS core.service_types (
    key           text PRIMARY KEY,
    area          text NOT NULL,
    name          text NOT NULL,
    about         text NOT NULL DEFAULT '',
    form          jsonb NOT NULL DEFAULT '[]',
    team          text NOT NULL,
    approval      text NOT NULL DEFAULT '',
    target_hours  integer NOT NULL DEFAULT 24,
    wizard        text NOT NULL DEFAULT '',
    enabled       boolean NOT NULL DEFAULT true,
    sort          integer NOT NULL DEFAULT 100,
    modified_by   text NOT NULL DEFAULT 'system:install',
    modified_at   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE core.service_types IS 'R5.11: what people can ask for: its form, its team, its approval and its target time';

CREATE TABLE IF NOT EXISTS core.service_tickets (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type_key      text NOT NULL REFERENCES core.service_types (key),
    title         text NOT NULL,
    fields        jsonb NOT NULL DEFAULT '{}',
    status        text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'waiting-approval', 'approved', 'in-progress',
                                                                'waiting-requester', 'done', 'declined', 'cancelled')),
    priority      text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    raised_by     text NOT NULL,
    assigned_to   text,
    team          text NOT NULL,
    approval      text NOT NULL DEFAULT '',
    approved_by   text,
    approved_at   timestamptz,
    model_guid    uuid,
    project_guid  uuid,
    due_at        timestamptz,
    overdue_told  boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    closed_at     timestamptz
);
CREATE INDEX IF NOT EXISTS service_tickets_status_idx ON core.service_tickets (status);
CREATE INDEX IF NOT EXISTS service_tickets_raised_idx ON core.service_tickets (raised_by);
COMMENT ON TABLE core.service_tickets IS 'R5.11: a request (REQ-<id>) from the service catalogue';

CREATE TABLE IF NOT EXISTS core.service_ticket_events (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id  bigint NOT NULL REFERENCES core.service_tickets (id),
    at         timestamptz NOT NULL DEFAULT now(),
    by_whom    text NOT NULL,
    kind       text NOT NULL,
    body       text NOT NULL DEFAULT '',
    data       jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS service_ticket_events_ticket_idx ON core.service_ticket_events (ticket_id);
COMMENT ON TABLE core.service_ticket_events IS 'R5.11: a request''s history: raised, comments, status, assignment, approval';

CREATE TABLE IF NOT EXISTS core.service_ticket_files (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id  bigint NOT NULL REFERENCES core.service_tickets (id),
    name       text NOT NULL,
    mime       text NOT NULL DEFAULT '',
    size       integer NOT NULL,
    content    bytea NOT NULL,
    added_by   text NOT NULL,
    added_at   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE core.service_ticket_files IS 'R5.11: small files attached to a request (10 MB each at most)';

INSERT INTO core.service_types (key, area, name, about, form, team, approval, target_hours, wizard, sort) VALUES
    ('new-model', 'Models', 'A new model', 'A model for a domain, a project or a reference, from a blank metamodel or a library model.', '[{"name": "name", "label": "Name of the model", "kind": "text", "required": true, "choices": [], "help": ""}, {"name": "start", "label": "Start from", "kind": "choice", "required": true, "choices": ["blank", "a library model", "a copy of a model"], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'model-creator', '', 24, '#/model-admin/wizards?wizard=new', 10),
    ('copy-model', 'Models', 'A copy of a model', 'A copy, with or without its link to the original.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "name", "label": "Name of the copy", "kind": "text", "required": true, "choices": [], "help": ""}, {"name": "linked", "label": "Keep the parent-child link", "kind": "choice", "required": true, "choices": ["yes", "no"], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'model-admins', '', 24, '#/model-admin/wizards?wizard=copy', 20),
    ('model-access', 'Models', 'Access to a model', 'A role on a model for you or someone else.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "person", "label": "Who (empty: me)", "kind": "person", "required": false, "choices": [], "help": ""}, {"name": "role", "label": "Role", "kind": "model-role", "required": true, "choices": [], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'model-admins', 'model-admins', 8, 'model-access', 30),
    ('metamodel-change', 'Models', 'A change to a metamodel', 'A new type, field, relationship or rule.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "change", "label": "What should change", "kind": "textarea", "required": true, "choices": [], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'model-admins', '', 72, '#/model-admin/wizards?wizard=extend', 40),
    ('data-load', 'Models', 'Data loaded into a model', 'Applications, capabilities or other content from a spreadsheet or a system.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "source", "label": "Where the data is", "kind": "textarea", "required": true, "choices": [], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'model-admins', '', 72, '#/model-admin/wizards?wizard=load', 50),
    ('data-correction', 'Models', 'A correction to a model''s content', 'Something wrong or missing in a model.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "what", "label": "What is wrong and what it should be", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'model-admins', '', 48, '', 55),
    ('restore-model', 'Models', 'A model restored', 'A model brought back from a backup or a tag.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "when", "label": "From when", "kind": "text", "required": true, "choices": [], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'it-admin', 'super-admin', 24, '#/model-admin/wizards?wizard=restore', 60),
    ('archive-model', 'Models', 'A model archived or brought back', 'Move a model to the archive, or back.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "direction", "label": "Archive or bring back", "kind": "choice", "required": true, "choices": ["archive", "bring back"], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'model-admins', '', 48, '#/model-admin/wizards?wizard=archive', 70),
    ('library-model', 'Models', 'A model in the library', 'A model published to (or withdrawn from) the library for others to start from.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'library-admin', '', 72, '#/model-admin/wizards?wizard=promote', 80),
    ('new-project', 'Projects', 'A new architecture project', 'A project following the ADM, from a template.', '[{"name": "name", "label": "Name of the project", "kind": "text", "required": true, "choices": [], "help": ""}, {"name": "template", "label": "Template (if you know it)", "kind": "text", "required": false, "choices": [], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'super-admin', '', 24, '#/project-admin', 10),
    ('project-access', 'Projects', 'Access to a project', 'A role on a project for you or someone else.', '[{"name": "project", "label": "Project", "kind": "project", "required": true, "choices": [], "help": ""}, {"name": "person", "label": "Who (empty: me)", "kind": "person", "required": false, "choices": [], "help": ""}, {"name": "role", "label": "Role", "kind": "project-role", "required": true, "choices": [], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'project-admins', '', 8, '#/project-admin?wizard=give', 20),
    ('project-template', 'Projects', 'A new project template', 'A template for a kind of project the organisation runs.', '[{"name": "what", "label": "What kind of project", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'super-admin', '', 120, '#/project-admin/templates', 30),
    ('restore-project', 'Projects', 'A project restored', 'A project brought back from a backup.', '[{"name": "project", "label": "Project", "kind": "project", "required": true, "choices": [], "help": ""}, {"name": "when", "label": "From when", "kind": "text", "required": true, "choices": [], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'it-admin', 'super-admin', 24, '#/project-admin?wizard=restore-file', 40),
    ('new-report', 'Reports', 'A new report or dashboard', 'A report on a model''s content.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "what", "label": "What it should show", "kind": "textarea", "required": true, "choices": [], "help": ""}, {"name": "who", "label": "Who reads it", "kind": "text", "required": false, "choices": [], "help": ""}]', 'super-admin', '', 120, '', 10),
    ('report-change', 'Reports', 'A change to a report', 'A report that should show something else.', '[{"name": "report", "label": "Which report", "kind": "text", "required": true, "choices": [], "help": ""}, {"name": "change", "label": "What should change", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'super-admin', '', 72, '', 20),
    ('survey', 'Reports', 'A survey to collect data', 'Questions sent to people, their answers into a model.', '[{"name": "model", "label": "Model", "kind": "model", "required": true, "choices": [], "help": ""}, {"name": "what", "label": "What to ask and of whom", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'model-creator', '', 72, '#/surveys', 30),
    ('new-user', 'Access', 'A new person', 'Someone who should sign in to EA Explorer.', '[{"name": "person", "label": "Their name and email", "kind": "text", "required": true, "choices": [], "help": ""}, {"name": "roles", "label": "What they will do", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'user-admin', '', 24, '#/admin/users', 10),
    ('global-role', 'Access', 'A global role', 'Super Admin, IT Admin, User Admin, Auditor, Model Creator, Library Admin.', '[{"name": "person", "label": "Who (empty: me)", "kind": "person", "required": false, "choices": [], "help": ""}, {"name": "role", "label": "Role", "kind": "global-role", "required": true, "choices": [], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'user-admin', 'super-admin', 24, '#/admin/users/mapping', 20),
    ('machine-credential', 'Access', 'A token or API key for a system', 'For another system to call EA Explorer.', '[{"name": "system", "label": "Which system and what it does", "kind": "textarea", "required": true, "choices": [], "help": ""}, {"name": "access", "label": "Read or read-write, which areas", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'it-admin', 'super-admin', 24, '#/admin/machine-access', 30),
    ('ip-allow', 'Access', 'An address allowed in', 'An address or range added to the allow lists.', '[{"name": "address", "label": "Address or range", "kind": "text", "required": true, "choices": [], "help": ""}, {"name": "place", "label": "Where", "kind": "choice", "required": true, "choices": ["site", "signin", "admin", "mcp", "machine"], "help": ""}, {"name": "why", "label": "Why it is needed", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'super-admin', '', 24, '#/admin/security', 40),
    ('question', 'Help', 'A question', 'How do I…? Where is…?', '[{"name": "question", "label": "Your question", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'it-admin', '', 24, '', 10),
    ('problem', 'Help', 'Something is not working', 'An error, something slow, something missing.', '[{"name": "what", "label": "What happened, where, and when", "kind": "textarea", "required": true, "choices": [], "help": ""}, {"name": "impact", "label": "How much it stops you", "kind": "choice", "required": true, "choices": ["a little", "a lot", "I cannot work"], "help": ""}]', 'it-admin', '', 8, '', 20),
    ('training', 'Help', 'Training', 'A walk-through for you or your team.', '[{"name": "topic", "label": "On what", "kind": "textarea", "required": true, "choices": [], "help": ""}, {"name": "people", "label": "For whom", "kind": "text", "required": false, "choices": [], "help": ""}]', 'super-admin', '', 120, '', 30),
    ('other', 'Help', 'Something else', 'Anything not in this list.', '[{"name": "what", "label": "What you need", "kind": "textarea", "required": true, "choices": [], "help": ""}]', 'super-admin', '', 72, '', 90)
ON CONFLICT (key) DO NOTHING;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.service_types, core.service_tickets, core.service_ticket_events,
              core.service_ticket_files TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.service_types, core.service_tickets, core.service_ticket_events,
              core.service_ticket_files TO eax_migrator;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO eax_migrator;
    END IF;
END;
$$;
