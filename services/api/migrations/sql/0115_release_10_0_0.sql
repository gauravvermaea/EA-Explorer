-- =====================================================================================
-- 0115_release_10_0_0: version 10.0.0, Release 10 accepted (the owner, 22 Nov 2026, 19:28: "R10 accepted"; D871):
--   scenario planning and game theory run by the person's AI through MCP, the project's read-only Scenario planning tab,
--   and every MCP tool tried in the full test with a card of its own. Records the version only, so the API
--   (version.toml 10.0.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('10.0.0', '0115_release_10_0_0', 'Release 10: scenario planning and game theory through the AI')
ON CONFLICT (version) DO NOTHING;
