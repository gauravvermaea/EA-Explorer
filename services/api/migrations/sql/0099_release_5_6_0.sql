-- =====================================================================================
-- 0099_release_5_6_0: version 5.6.0, Release 5.6 (the owner, 16 Nov 2026: "Build 5.6"): job priorities (R5.6-Q2,
--   migration 0098), updates and deployments from the published GitHub Releases only (R5.6-U1, U2), the synchronous
--   backup and restore test (R5.6-B1) and the restore drills as documents with a PDF. Records the version only, so the
--   API (version.toml 5.6.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('5.6.0', '0099_release_5_6_0', 'Release 5.6: job priorities, GitHub Releases, the backup and restore test')
ON CONFLICT (version) DO NOTHING;
