-- =====================================================================================
-- 0106_r6_7_settings_copies: the safety copies kept before a settings import (Release 6.7, D755; the owner, 17 Nov
--   2026: "a safety copy of the current settings first, so it can be undone"). One row per import or undo: the settings
--   of the parts it changed, as they were (the same file Export settings makes; never a password, key or certificate).
--   A table only; the logic is in eax/settings_transfer.py (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS core.settings_copies (
    id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid       uuid        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    made_at    timestamptz NOT NULL DEFAULT now(),
    made_by    text        NOT NULL,
    why        text        NOT NULL DEFAULT 'import',      -- import or undo
    parts      text[]      NOT NULL DEFAULT '{}',          -- the parts the import changed
    body       jsonb       NOT NULL,                       -- the settings file of those parts, as they were
    undone_at  timestamptz,
    undone_by  text
);
CREATE INDEX IF NOT EXISTS settings_copies_made_at ON core.settings_copies (made_at DESC);
COMMENT ON TABLE core.settings_copies IS 'R6.7: the settings as they were before each import (undo puts them back)';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.settings_copies TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.settings_copies TO eax_migrator;
    END IF;
END;
$$;
