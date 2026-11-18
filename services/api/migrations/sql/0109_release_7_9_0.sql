-- =====================================================================================
-- 0109_release_7_9_0: version 7.9.0, Release 7.9 closed (the owner, 19 Nov 2026, 00:01: "ok lets release 7.9"): error
--   codes (EAX-AREA-NNN, one list, services/api/eax/errors.json) in the API's answers, the logs, System Admin's health
--   and alerts, eax status and eax errors, Jenkins' Status and error codes, and the error code guide (the website and
--   printed guide 25). Records the version only, so the API (version.toml 7.9.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('7.9.0', '0109_release_7_9_0', 'Release 7.9: error codes and the error code guide')
ON CONFLICT (version) DO NOTHING;
