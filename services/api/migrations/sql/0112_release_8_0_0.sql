-- =====================================================================================
-- 0112_release_8_0_0: version 8.0.0, Release 8 closed (the owner, 21 Nov 2026, 21:02: "accept release"; 22 Nov 2026,
--   07:40: "Let us publish release 8 first"; D839): SonarQube in the tests, code coverage measured and shown, the attack
--   test, the full test with its summary page, no test container left running, the website's Questions page.
--   Records the version only, so the API (version.toml 8.0.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('8.0.0', '0112_release_8_0_0', 'Release 8: code quality and testing')
ON CONFLICT (version) DO NOTHING;
