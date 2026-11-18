-- =====================================================================================
-- 0107_release_6_7_0: version 6.7.0, Release 6 closed (the owner, 18 Nov 2026, 12:41: "ok release 6 work is approved";
--   "lets close entire 6x line"): secrets and certificates (6.0), site pairings and sync (6.5), setup guided and
--   documented, the integrity checks, an external database server, your own certificates and Jenkins (6.6), the
--   settings exported and imported (6.7). Records the version only, so the API (version.toml 6.7.0) and the database
--   agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('6.7.0', '0107_release_6_7_0', 'Release 6: secrets and certificates, sync, setup, settings import and export')
ON CONFLICT (version) DO NOTHING;
