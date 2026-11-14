-- =====================================================================================
-- 0075_selftest_reports_suite: the self-test's reports suite (R4.1; owner, 14 Nov 2026: "add more test cases for
--   reports", "Browser with test users"). A run's suites and a result's suite may now be 'reports' too. Constraints only;
--   no version change; no logic (D248).
-- =====================================================================================

ALTER TABLE IF EXISTS tests.test_runs DROP CONSTRAINT IF EXISTS test_runs_suites_check;
ALTER TABLE IF EXISTS tests.test_runs ADD CONSTRAINT test_runs_suites_check
    CHECK (suites <@ ARRAY['api', 'ui', 'db', 'security', 'reports', 'backup', 'restore']::text[] AND cardinality(suites) > 0);

ALTER TABLE IF EXISTS tests.test_results DROP CONSTRAINT IF EXISTS test_results_suite_check;
ALTER TABLE IF EXISTS tests.test_results ADD CONSTRAINT test_results_suite_check
    CHECK (suite IN ('smoke', 'api', 'ui', 'db', 'security', 'reports', 'backup', 'restore'));
