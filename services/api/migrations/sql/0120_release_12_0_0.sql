-- =====================================================================================
-- 0120_release_12_0_0: version 12.0.0, Release 12 closed as an unstable release (the owner, 23 Nov 2026, 20:45: "I am
--   ready to close the release as an unstable release"; "We will fix everything in R14"; D897): project and model
--   templates from TOGAF and its Series Guides. Records the version only, so the API (version.toml 12.0.0) and the
--   database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('12.0.0', '0120_release_12_0_0', 'Release 12: templates from TOGAF and its Series Guides (unstable)')
ON CONFLICT (version) DO NOTHING;
