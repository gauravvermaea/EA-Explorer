-- =====================================================================================
-- 0092_release_5_1_0: version 5.1.0, Release 5.1, the stabilisation release (owner, 16 Nov 2026, 09:24: "Lets do clean
--   build test everything and release this as a stabalization release before we do any more work"; 09:24: "I think make it 5.1"). Records the
--   version only, so the API (version.toml 5.1.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('5.1.0', '0092_release_5_1_0', 'Release 5.1: stabilisation')
ON CONFLICT (version) DO NOTHING;
