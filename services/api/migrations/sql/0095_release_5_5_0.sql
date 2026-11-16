-- =====================================================================================
-- 0095_release_5_5_0: version 5.5.0, Release 5.5 (the owner, 16 Nov 2026: "Build this release"): enterprise discovery
--   (R5.5, migration 0094), architecture decision records and dispensations (R5.5.1, migration 0093) and the Live browser
--   full screen (R5.5.2). Records the version only, so the API (version.toml 5.5.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('5.5.0', '0095_release_5_5_0', 'Release 5.5: enterprise discovery, decision records and dispensations')
ON CONFLICT (version) DO NOTHING;
