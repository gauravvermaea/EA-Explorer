-- =====================================================================================
-- 0096_selftest_mcp_suite: the self-test's MCP suite (R5.5.5; owner, 16 Nov 2026, 12:45: "add a story for MCP test, where
-- MCP api is tested"). A run's suites and a result's suite may now be 'mcp' too: without it a run asking for it was
-- refused (IntegrityError, 14:11). Constraints only; no logic (D248).
-- =====================================================================================

ALTER TABLE IF EXISTS tests.test_runs DROP CONSTRAINT IF EXISTS test_runs_suites_check;
ALTER TABLE IF EXISTS tests.test_runs ADD CONSTRAINT test_runs_suites_check
    CHECK (suites <@ ARRAY['api', 'ui', 'db', 'jobs', 'mcp', 'security', 'reports', 'performance', 'backup', 'restore']::text[]
           AND cardinality(suites) > 0);

ALTER TABLE IF EXISTS tests.test_results DROP CONSTRAINT IF EXISTS test_results_suite_check;
ALTER TABLE IF EXISTS tests.test_results ADD CONSTRAINT test_results_suite_check
    CHECK (suite IN ('smoke', 'api', 'ui', 'db', 'jobs', 'mcp', 'security', 'reports', 'performance', 'backup', 'restore'));
