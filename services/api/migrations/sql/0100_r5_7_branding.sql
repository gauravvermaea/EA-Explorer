-- =====================================================================================
-- 0100_r5_7_branding: logo and branding (R5.7-B1; owner, 16 Nov 2026, 09:44, agreed 16:14 and 17 Nov 13:49): the
--   logo and the browser tab's icon, and the themes Super Admins add (CSS of looks only, checked by the API before it
--   is kept, eax/branding.py). The choice itself (the theme, the switch for each person's own, the product name) is a
--   row of core.settings under the key branding. In the database, so a backup, a restore and a site copy carry them.
--   Tables only; no logic (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS core.branding_files (
    key          text PRIMARY KEY CHECK (key IN ('logo', 'favicon')),
    content_type text NOT NULL,
    data         bytea NOT NULL,
    set_by       text NOT NULL,
    set_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.branding_themes (
    slug    text PRIMARY KEY CHECK (slug ~ '^[a-z0-9][a-z0-9-]{0,39}$'),
    name    text NOT NULL,
    css     text NOT NULL,
    set_by  text NOT NULL,
    set_at  timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.branding_files, core.branding_themes TO eax_app;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.branding_files, core.branding_themes TO eax_migrator;
    END IF;
END;
$$;
