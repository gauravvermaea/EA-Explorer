-- =====================================================================================
-- 0077_release_4_0_0: version 4.0.0, Release 4 (owner, 15 Nov 2026, 06:56: "Release accepted"). Records the
--   version only, so the API (version.toml 4.0.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('4.0.0', '0077_release_4_0_0', 'Release 4')
ON CONFLICT (version) DO NOTHING;
