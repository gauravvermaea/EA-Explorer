-- =====================================================================================
-- 0111_test_summaries: the test summaries kept, the detailed files deletable (D825; owner, 21 Nov 2026: "Please add
-- them in one summary page for anyone to check. We also need the ability to only keep summary in a DB table or
-- something and delete detailed result files form UI or command line")
--   * a self-test run keeps its summary in its row (summary: the counts, the health, the coverage, the security gate's
--     and the attack test's counts) and when its detailed files were deleted (files_deleted_at and _by: the report,
--     the log, the videos, the scanners' reports and the screenshots), the summary and the results staying
--   * a full test (eax test full: the dev check, the self-test with the attack test, the backup and restore test and
--     SonarQube) is one row of tests.full_tests: each step's outcome and its summary, the folders of its detailed files
--     and its summary page (work/tests/full-<time>/index.html)
-- Tables, columns and constraints only; no version change; no logic (D248).
-- =====================================================================================

ALTER TABLE IF EXISTS tests.test_runs
    ADD COLUMN IF NOT EXISTS summary          jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS files_deleted_at timestamptz,
    ADD COLUMN IF NOT EXISTS files_deleted_by text;

CREATE TABLE IF NOT EXISTS tests.full_tests (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    folder           text NOT NULL UNIQUE CHECK (folder ~ '^full-[A-Za-z0-9._-]{1,70}$'),   -- work/tests/<folder>/index.html
    started_by       text NOT NULL DEFAULT '' CHECK (length(started_by) <= 200),
    version          text NOT NULL DEFAULT '' CHECK (length(version) <= 40),
    passed           boolean NOT NULL DEFAULT false,
    run_id           bigint,                                         -- its self-test run (tests.test_runs), when it had one
    summary          jsonb NOT NULL DEFAULT '{}'::jsonb,             -- each step and its figures: what the page shows
    started_at       timestamptz,
    finished_at      timestamptz NOT NULL DEFAULT now(),
    files_deleted_at timestamptz,                                    -- its steps' detailed files deleted (the page stays)
    files_deleted_by text
);
CREATE INDEX IF NOT EXISTS full_tests_recent_idx ON tests.full_tests (finished_at DESC);

COMMENT ON TABLE tests.full_tests IS 'Each eax test full: its steps and their summary, kept after the detailed files go (D825)';
