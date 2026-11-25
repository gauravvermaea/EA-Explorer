-- =====================================================================================
-- 0123_release_14_0_0: version 14.0.0, Release 14 accepted (the owner, 25 Nov 2026, 08:42: "Close it"; "I think only
--   reports is the issue"; D922): stabilisation; every test of the full test passing after a clean restart except
--   "every report opens" (R14.5.19). Records the version only, so the API (version.toml 14.0.0) and the database
--   agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('14.0.0', '0123_release_14_0_0', 'Release 14: stabilisation, every test passing but the reports one (R14.5.19)')
ON CONFLICT (version) DO NOTHING;
