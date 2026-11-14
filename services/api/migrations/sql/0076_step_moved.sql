-- =====================================================================================
-- 0076_step_moved: a step's history may say it was moved (R4.21; owner, 14 Nov 2026: "ADM Steps in each phase while
--   creating a new project or while working on a project can change order"). The check of proj.step_events.action only;
--   no version change; no logic (D248).
-- =====================================================================================

ALTER TABLE IF EXISTS proj.step_events DROP CONSTRAINT IF EXISTS step_events_action_check;
ALTER TABLE IF EXISTS proj.step_events ADD CONSTRAINT step_events_action_check
    CHECK (action IN ('opened', 'closed', 'reopened', 'moved'));
