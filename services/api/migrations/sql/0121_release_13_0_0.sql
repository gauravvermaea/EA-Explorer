-- =====================================================================================
-- 0121_release_13_0_0: version 13.0.0, Release 13 accepted (the owner, 23 Nov 2026, 21:28: "ok this release is
--   accepted"; 21:40: "lets close R13"; D900): System Admin in seven groups with multi-level tabs and sub-menus, every
--   sub-tab with its own address (D898), and every command-line option documented with a test that keeps it so
--   (D899). Records the version only, so the API (version.toml 13.0.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('13.0.0', '0121_release_13_0_0', 'Release 13: System Admin regrouped, every command-line option documented')
ON CONFLICT (version) DO NOTHING;
