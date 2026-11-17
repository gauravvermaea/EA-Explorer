-- =====================================================================================
-- 0102_release_5_7_0: version 5.7.0, Release 5.7 (the owner, 17 Nov 2026: "build 5.7"): the views' ArchiMate icons
--   (R5.7-V1), logo and branding (R5.7-B1, migration 0100), customer journey maps (R5.7-J1, migration 0101), a
--   presentation deck with the person's own AI through MCP (R5.7-P1) and the backup and restore test on all of it
--   (R5.7-T1). Records the version only, so the API (version.toml 5.7.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('5.7.0', '0102_release_5_7_0', 'Release 5.7: view icons, branding, customer journeys, the deck tools')
ON CONFLICT (version) DO NOTHING;
