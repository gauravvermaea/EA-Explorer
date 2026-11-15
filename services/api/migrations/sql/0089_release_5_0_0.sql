-- =====================================================================================
-- 0089_release_5_0_0: version 5.0.0, Release 5 (owner, 15 Nov 2026, 19:31: Release 5 accepted). Records the
--   version only, so the API (version.toml 5.0.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('5.0.0', '0089_release_5_0_0', 'Release 5')
ON CONFLICT (version) DO NOTHING;
