-- =====================================================================================
-- 0114_release_9_0_0: version 9.0.0, Release 9 accepted (the owner, 22 Nov 2026, 19:22: "R9 is accepted"; D870):
--   the AI reads EA Explorer's own documentation, themes offered and people's own themes, the authenticator reset from
--   the user list, the restore drill in the full test, the image check every three months, eax test jenkins and
--   eax test commands. Also in the code, not yet accepted: Release 10 (scenario planning, migration 0113).
--   Records the version only, so the API (version.toml 9.0.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('9.0.0', '0114_release_9_0_0', 'Release 9: documentation for the AI, themes, the restore drill in the full test')
ON CONFLICT (version) DO NOTHING;
