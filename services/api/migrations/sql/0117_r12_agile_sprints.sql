-- =====================================================================================
-- 0117_r12_agile_sprints: Release 12, architecture in sprints for a project of the Agile type (R12.2, D858, D879;
-- TOGAF Series Guide: Applying the TOGAF ADM using Agile Sprints, G210).
-- The project's backlog (drawn from the requirements in its models, and deliverables sent back), its sprints (each
-- with its goal, dates, the ADM phases, steps and deliverables agreed for it, and who accepts them) and each item's
-- decision at the sprint review (accepted, or back to the backlog). The project's default sprint length.
-- Rows only: who may read and change them, and every rule, are in eax/agile.py (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS proj.agile_settings (
    project_id   bigint PRIMARY KEY REFERENCES proj.projects (id) ON DELETE CASCADE,
    sprint_days  integer NOT NULL DEFAULT 14,
    changed_by   text NOT NULL,
    changed_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS proj.sprints (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid          uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    project_id    bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    seq           integer NOT NULL,                        -- Sprint 1, 2, ...
    name          text NOT NULL DEFAULT '',
    goal          text NOT NULL DEFAULT '',
    starts_on     date NOT NULL,
    ends_on       date NOT NULL,
    phases        text[] NOT NULL DEFAULT '{}',            -- the ADM phases the sprint runs (P, A, B, ...)
    steps         text[] NOT NULL DEFAULT '{}',            -- the project's steps agreed for it, as "B: name" (kept by a restore)
    accepter      text NOT NULL DEFAULT '',                -- who accepts its deliverables: a member's username or a name
    status        text NOT NULL DEFAULT 'planned',         -- planned | open | reviewed
    review_note   text NOT NULL DEFAULT '',
    created_by    text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    reviewed_by   text,
    reviewed_at   timestamptz,
    UNIQUE (project_id, seq)
);
CREATE INDEX IF NOT EXISTS sprints_project ON proj.sprints (project_id, seq);

CREATE TABLE IF NOT EXISTS proj.backlog_items (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid          uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    project_id    bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    kind          text NOT NULL,                           -- requirement | deliverable | item
    model_guid    uuid,                                    -- a requirement: the model and entity it is
    entity_guid   uuid,
    item_id       bigint REFERENCES proj.items (id) ON DELETE SET NULL,   -- a deliverable: the project's deliverable
    title         text NOT NULL,
    priority      integer NOT NULL DEFAULT 0,              -- higher first
    status        text NOT NULL DEFAULT 'backlog',         -- backlog | planned | accepted
    sprint_id     bigint REFERENCES proj.sprints (id) ON DELETE SET NULL,
    returned      integer NOT NULL DEFAULT 0,              -- times it came back from a sprint not accepted
    added_by      text NOT NULL,
    added_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS backlog_items_project ON proj.backlog_items (project_id, status, priority DESC);
CREATE UNIQUE INDEX IF NOT EXISTS backlog_items_entity ON proj.backlog_items (project_id, entity_guid) WHERE entity_guid IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS backlog_items_deliverable ON proj.backlog_items (project_id, item_id) WHERE item_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS proj.sprint_decisions (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sprint_id     bigint NOT NULL REFERENCES proj.sprints (id) ON DELETE CASCADE,
    backlog_id    bigint NOT NULL REFERENCES proj.backlog_items (id) ON DELETE CASCADE,
    accepted      boolean NOT NULL,
    note          text NOT NULL DEFAULT '',
    accepted_by   text NOT NULL DEFAULT '',                -- the sprint's accepter, as recorded
    decided_by    text NOT NULL,
    decided_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sprint_id, backlog_id)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA proj TO eax_migrator;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA proj TO eax_migrator;
    END IF;
END;
$$;
