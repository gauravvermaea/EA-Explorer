-- =====================================================================================
-- 0084_selftest_performance_suite: the self-test's performance suite (R5.18, D695: "automated performance test (bench
-- marking)"). A run's suites and a result's suite may now be 'performance' too. Constraints only; no logic (D248).
-- =====================================================================================

ALTER TABLE IF EXISTS tests.test_runs DROP CONSTRAINT IF EXISTS test_runs_suites_check;
ALTER TABLE IF EXISTS tests.test_runs ADD CONSTRAINT test_runs_suites_check
    CHECK (suites <@ ARRAY['api', 'ui', 'db', 'security', 'reports', 'performance', 'backup', 'restore']::text[] AND cardinality(suites) > 0);

ALTER TABLE IF EXISTS tests.test_results DROP CONSTRAINT IF EXISTS test_results_suite_check;
ALTER TABLE IF EXISTS tests.test_results ADD CONSTRAINT test_results_suite_check
    CHECK (suite IN ('smoke', 'api', 'ui', 'db', 'security', 'reports', 'performance', 'backup', 'restore'));
