-- =====================================================================================
-- 0074_release_3_5_0: version 3.5.0, Release 3.5 (owner, 14 Nov 2026, 17:49: "looks good lets close"). Records the
--   version only, so the API (version.toml 3.5.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('3.5.0', '0074_release_3_5_0', 'Release 3.5')
ON CONFLICT (version) DO NOTHING;
