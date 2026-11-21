-- =====================================================================================
-- 0110_selftest_attack_suite: the self-test's attack suite (R8.2, D817; owner, 21 Nov 2026, 10:15: "Build what is
-- needed for R 8.2 so that we can run it"). A run's suites and a result's suite may now be 'attack' too: without it
-- `eax test attack` would be refused when its run is recorded. Constraints only; no logic (D248).
-- =====================================================================================

ALTER TABLE IF EXISTS tests.test_runs DROP CONSTRAINT IF EXISTS test_runs_suites_check;
ALTER TABLE IF EXISTS tests.test_runs ADD CONSTRAINT test_runs_suites_check
    CHECK (suites <@ ARRAY['api', 'ui', 'db', 'jobs', 'mcp', 'security', 'reports', 'performance', 'attack', 'backup', 'restore']::text[]
           AND cardinality(suites) > 0);

ALTER TABLE IF EXISTS tests.test_results DROP CONSTRAINT IF EXISTS test_results_suite_check;
ALTER TABLE IF EXISTS tests.test_results ADD CONSTRAINT test_results_suite_check
    CHECK (suite IN ('smoke', 'api', 'ui', 'db', 'jobs', 'mcp', 'security', 'reports', 'performance', 'attack', 'backup', 'restore'));
