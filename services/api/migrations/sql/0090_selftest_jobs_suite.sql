-- =====================================================================================
-- 0090_selftest_jobs_suite: the self-test's jobs suite (R5.46; owner, 16 Nov 2026: "in self test dasboard have another
-- item for job tests"). A run's suites and a result's suite may now be 'jobs' too. Constraints only; no logic (D248).
-- =====================================================================================

ALTER TABLE IF EXISTS tests.test_runs DROP CONSTRAINT IF EXISTS test_runs_suites_check;
ALTER TABLE IF EXISTS tests.test_runs ADD CONSTRAINT test_runs_suites_check
    CHECK (suites <@ ARRAY['api', 'ui', 'db', 'jobs', 'security', 'reports', 'performance', 'backup', 'restore']::text[]
           AND cardinality(suites) > 0);

ALTER TABLE IF EXISTS tests.test_results DROP CONSTRAINT IF EXISTS test_results_suite_check;
ALTER TABLE IF EXISTS tests.test_results ADD CONSTRAINT test_results_suite_check
    CHECK (suite IN ('smoke', 'api', 'ui', 'db', 'jobs', 'security', 'reports', 'performance', 'backup', 'restore'));
