-- =====================================================================================
-- 0125_release_14_5_0: version 14.5.0, Release 14.5 accepted (the owner, 27 Nov 2026, 15:01: "ok lets accept this
--   release"; D955): the bugs of the full tests of 25 to 27 Nov fixed, code coverage over 85% (the API, the screens,
--   the jobs), the DR drill passed. Records the version only, so the API (version.toml 14.5.0) and the database
--   agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('14.5.0', '0125_release_14_5_0', 'Release 14.5: the full tests'' bugs fixed, coverage over 85%, the DR drill passed')
ON CONFLICT (version) DO NOTHING;
