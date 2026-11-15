-- R5.27 (owner, 15 Nov 2026, 19:17; D700): the service desk reworked. A group first, then the request; every request
-- to the Super Admins, who assign it; no approval step; Reports and Help are not asked for here ("Reports are not
-- needed. Those people will do themselvs"; "Help is not needed"); "Something else" is a group of its own.
-- Data only (D248): the request types are switched off, never deleted, so a request raised before keeps its type.
UPDATE core.service_types SET enabled = false, modified_by = 'R5.27', modified_at = now()
 WHERE area IN ('Reports', 'Help') AND key <> 'other';
UPDATE core.service_types
   SET area = 'Other', name = 'Something else', sort = 10,
       about = 'Anything that is not in the catalogue: describe what you need.',
       form = '[{"name": "what", "label": "What you need", "kind": "textarea", "required": true, "choices": [], "help": "As much as you can: what, for whom, by when."}]',
       modified_by = 'R5.27', modified_at = now()
 WHERE key = 'other';
UPDATE core.service_types SET team = 'super-admin', approval = '', modified_by = 'R5.27', modified_at = now()
 WHERE team <> 'super-admin' OR approval <> '';
-- open requests still waiting for a team are the Super Admins' now
UPDATE core.service_tickets SET team = 'super-admin' WHERE status IN ('new', 'waiting-approval', 'approved', 'in-progress', 'waiting-requester');
