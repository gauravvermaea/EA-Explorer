-- =====================================================================================
-- 0103_r5_7_branding_fonts: fonts Super Admins upload for the themes (owner, 17 Nov 2026, 15:48: "In themes also give
--   ability to upload a custom fonts file"; D736). The file (WOFF2, WOFF, TrueType or OpenType, checked by the API) and
--   the family name the themes use for it. The screens load it from the API themselves; a theme only names it (a theme
--   still loads nothing from elsewhere, D729). In the database, so backups, restores and site copies carry it.
--   Tables only; no logic (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS core.branding_fonts (
    slug         text PRIMARY KEY CHECK (slug ~ '^[a-z0-9][a-z0-9-]{0,39}$'),
    family       text NOT NULL,
    weight       text NOT NULL DEFAULT 'normal' CHECK (weight IN ('normal', 'bold')),
    style        text NOT NULL DEFAULT 'normal' CHECK (style IN ('normal', 'italic')),
    content_type text NOT NULL,
    data         bytea NOT NULL,
    set_by       text NOT NULL,
    set_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (family, weight, style)              -- a family's regular, bold, italic and bold italic files
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.branding_fonts TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.branding_fonts TO eax_migrator;
    END IF;
END;
$$;
