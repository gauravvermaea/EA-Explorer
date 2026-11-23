-- =====================================================================================
-- 0118_r12_agile_dorp: Release 12, sprints as the TOGAF Series Guide G210 has them (R12.2, D883): the review is the
-- guide's Demo, Outcome, Retrospective and Planning (a demo note and a retrospective on each sprint, the outcome being
-- each item accepted or not); the first sprint may be Sprint zero, the strategic sprint; and the project's way of
-- prioritising its backlog (the guide's four: the most value first, the riskiest first, a slice through all the
-- phases, the easiest first). Rows only (D248).
-- =====================================================================================

ALTER TABLE proj.sprints ADD COLUMN IF NOT EXISTS zero boolean NOT NULL DEFAULT false;
ALTER TABLE proj.sprints ADD COLUMN IF NOT EXISTS demo_note text NOT NULL DEFAULT '';
ALTER TABLE proj.sprints ADD COLUMN IF NOT EXISTS retrospective text NOT NULL DEFAULT '';
ALTER TABLE proj.agile_settings ADD COLUMN IF NOT EXISTS priority_rule text NOT NULL DEFAULT 'value';
