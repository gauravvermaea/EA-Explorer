-- =====================================================================================
-- 0101_r5_7_journeys: customer journey maps (R5.7-J1; owner, 16 Nov 2026, from 15:58, and 17 Nov 13:50): first-class
--   in a project beside the Business Model Canvas, in tables of their own in the projects schema as the canvas has.
--   A journey has stages (columns) and parts under each stage (steps with the emotion there, -2 to +2, touchpoints,
--   pain points, moments that matter, opportunities, and kinds a project adds itself, with fields of its own);
--   personas for the whole journey; links out to model elements (by guid, with the name kept: proj may live in its own
--   database, D266); the documents behind it and every change. Stages and parts keep a lineage across copies, so two
--   journeys compare. Tables only; the rules are in eax/journeys.py (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS proj.journeys (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid        uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    project_id  bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    name        text NOT NULL,
    kind        text NOT NULL DEFAULT 'current' CHECK (kind IN ('current', 'target', 'working', 'scenario')),
    status      text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'agreed')),
    description text NOT NULL DEFAULT '',
    persona     text NOT NULL DEFAULT '',                                    -- whose journey it is, in a few words
    source_id   bigint REFERENCES proj.journeys (id) ON DELETE SET NULL,     -- the journey it was made from
    source_note text NOT NULL DEFAULT '',
    created_by  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    changed_by  text NOT NULL DEFAULT '',
    changed_at  timestamptz
);
CREATE INDEX IF NOT EXISTS journeys_project ON proj.journeys (project_id);

CREATE TABLE IF NOT EXISTS proj.journey_stages (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid        uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    journey_id  bigint NOT NULL REFERENCES proj.journeys (id) ON DELETE CASCADE,
    sort_order  integer NOT NULL DEFAULT 0,
    name        text NOT NULL,
    note        text NOT NULL DEFAULT '',
    lineage     uuid NOT NULL DEFAULT gen_random_uuid()      -- the same stage in every copy
);
CREATE INDEX IF NOT EXISTS journey_stages_journey ON proj.journey_stages (journey_id, sort_order);

CREATE TABLE IF NOT EXISTS proj.journey_items (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid        uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    journey_id  bigint NOT NULL REFERENCES proj.journeys (id) ON DELETE CASCADE,
    stage_id    bigint REFERENCES proj.journey_stages (id) ON DELETE CASCADE,   -- none: for the whole journey (a persona)
    part        text NOT NULL CHECK (part ~ '^(step|touchpoint|pain_point|moment|opportunity|persona|x-[a-z0-9][a-z0-9-]{0,38})$'),
    sort_order  integer NOT NULL DEFAULT 0,
    text        text NOT NULL,
    note        text NOT NULL DEFAULT '',
    score       smallint CHECK (score BETWEEN -2 AND 2),     -- a step's emotion: -2 very unhappy to +2 very happy
    fields      jsonb NOT NULL DEFAULT '{}'::jsonb,          -- the values of the kind's own fields
    lineage     uuid NOT NULL DEFAULT gen_random_uuid(),     -- the same part in every copy
    changed_by  text NOT NULL DEFAULT '',
    changed_at  timestamptz
);
CREATE INDEX IF NOT EXISTS journey_items_journey ON proj.journey_items (journey_id, stage_id, part, sort_order);

CREATE TABLE IF NOT EXISTS proj.journey_links (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid        uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    journey_id  bigint NOT NULL REFERENCES proj.journeys (id) ON DELETE CASCADE,
    stage_id    bigint REFERENCES proj.journey_stages (id) ON DELETE CASCADE,
    item_id     bigint REFERENCES proj.journey_items (id) ON DELETE CASCADE,
    model_guid  uuid NOT NULL,                  -- no foreign key: proj may move to its own database (D266)
    entity_guid uuid NOT NULL,
    display_id  text NOT NULL DEFAULT '',
    name        text NOT NULL,                  -- kept, so the journey reads without the model
    entity_type text NOT NULL DEFAULT '',
    added_by    text NOT NULL,
    added_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS journey_links_journey ON proj.journey_links (journey_id);

-- the kinds of part a project adds itself, and extra fields on the standard ones
CREATE TABLE IF NOT EXISTS proj.journey_part_kinds (
    project_id  bigint NOT NULL REFERENCES proj.projects (id) ON DELETE CASCADE,
    code        text NOT NULL CHECK (code ~ '^(step|touchpoint|pain_point|moment|opportunity|x-[a-z0-9][a-z0-9-]{0,38})$'),
    label       text NOT NULL,
    fields      jsonb NOT NULL DEFAULT '[]'::jsonb,
    note        text NOT NULL DEFAULT '',
    sort_order  integer NOT NULL DEFAULT 0,
    added_by    text NOT NULL,
    added_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, code)
);

CREATE TABLE IF NOT EXISTS proj.journey_documents (
    journey_id  bigint NOT NULL REFERENCES proj.journeys (id) ON DELETE CASCADE,
    document_id bigint NOT NULL REFERENCES proj.documents (id) ON DELETE CASCADE,
    note        text NOT NULL DEFAULT '',
    added_by    text NOT NULL,
    added_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (journey_id, document_id)
);

CREATE TABLE IF NOT EXISTS proj.journey_events (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    journey_id  bigint NOT NULL REFERENCES proj.journeys (id) ON DELETE CASCADE,
    action      text NOT NULL,
    username    text NOT NULL,
    at          timestamptz NOT NULL DEFAULT now(),
    note        text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS journey_events_journey ON proj.journey_events (journey_id, at);

-- an index on every foreign key, as migration 0097 gave the others
CREATE INDEX IF NOT EXISTS journeys_source ON proj.journeys (source_id);
CREATE INDEX IF NOT EXISTS journey_items_stage ON proj.journey_items (stage_id);
CREATE INDEX IF NOT EXISTS journey_links_stage ON proj.journey_links (stage_id);
CREATE INDEX IF NOT EXISTS journey_links_item ON proj.journey_links (item_id);
CREATE INDEX IF NOT EXISTS journey_documents_document ON proj.journey_documents (document_id);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON proj.journeys, proj.journey_stages, proj.journey_items, proj.journey_links,
            proj.journey_part_kinds, proj.journey_documents, proj.journey_events TO eax_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA proj TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON proj.journeys, proj.journey_stages, proj.journey_items, proj.journey_links,
            proj.journey_part_kinds, proj.journey_documents, proj.journey_events TO eax_migrator;
    END IF;
END;
$$;
