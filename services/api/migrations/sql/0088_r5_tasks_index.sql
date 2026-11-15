-- R5.28 (owner, 15 Nov 2026, 19:19, Database maintenance's finding "core.tasks has duplicate indexes"): the same index
-- was made twice, by 0016 (tasks_by_idx) and 0023 (tasks_requested_by_idx). The later one goes.
DROP INDEX IF EXISTS core.tasks_requested_by_idx;
