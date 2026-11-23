-- =====================================================================================
-- 0116_release_11_0_0: version 11.0.0, Release 11 accepted (the owner, 22 Nov 2026, 20:50: "R11 accepted"; D878):
--   certificate mode working and tested: every service can read its own key, eax certs check, the switch between
--   passwords and certificates from System Admin > Secrets and remembered for the next clean restart, the clean
--   restart's --certificate and --password, and the Secrets page showing what applies to the mode. Records the
--   version only, so the API (version.toml 11.0.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('11.0.0', '0116_release_11_0_0', 'Release 11: certificate mode, working and tested')
ON CONFLICT (version) DO NOTHING;
