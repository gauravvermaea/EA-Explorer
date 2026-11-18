-- =====================================================================================
-- 0108_release_7_0_0: version 7.0.0, Release 7 closed (the owner, 18 Nov 2026, 21:00: "Then lets accept this release
--   and we can move on"): the documentation release: the EA Explorer website inside the application and on its own
--   (role guides, 281 How do I pages each with its screen's picture, Guides, Concepts, Integrate, Platform, a page for
--   every report), the AI page as tiles, and the 24 printed guides as PDF. Records the version only, so the API
--   (version.toml 7.0.0) and the database agree. Rows only (D248).
-- =====================================================================================

INSERT INTO core.schema_versions (version, migration, description) VALUES
    ('7.0.0', '0108_release_7_0_0', 'Release 7: the website, How do I with pictures, the 24 printed guides')
ON CONFLICT (version) DO NOTHING;
