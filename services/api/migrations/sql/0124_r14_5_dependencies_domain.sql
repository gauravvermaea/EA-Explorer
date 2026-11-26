-- D939: DR-01's dependencies function read rpt.entities.layer, renamed type_domain when ArchiMate 4 said domain, not layer
-- (0032, D391). A SQL function's body is not checked when a column it reads is renamed, so it failed only when run: the
-- DR-01, IT operations and Change manager dashboards answered "column x.layer does not exist" (self-test 18, 26 Nov
-- 2026). The same function, reading type_domain, and its own column named domain too (owner, 17:49: "ensure there is no
-- layer and only domain"): a function's columns cannot change in place, so it is dropped, made again and granted again.
-- The DR-01 dataset reads domain (eax/setup/superset_reports.py).
DROP FUNCTION IF EXISTS rpt.f_dependencies(text, integer);
CREATE FUNCTION rpt.f_dependencies(p_label text, p_steps integer DEFAULT 4) RETURNS TABLE (
    model_id bigint, model_name text, chosen_entity text, direction text, depth integer, entity text, entity_type text,
    domain text, lifecycle text, criticality numeric, last_relationship text, path text, link text)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE root AS (
        SELECT c.model_id, e.entity_id, e.name FROM rpt.dr_entity_choices c
          JOIN rpt.entities e ON e.model_id = c.model_id
           AND c.entity_label = e.name || ' (' || e.entity_type || ', ' || e.display_id || ')'
         WHERE c.entity_label = p_label
    ), edges AS (SELECT * FROM rpt.dependency_edges WHERE model_id IN (SELECT r.model_id FROM root r)),
    walk AS (
        SELECT r.model_id, r.entity_id AS root_id, 'Downstream: depends on it' AS dir, ed.dependant AS id, 1 AS depth,
               ARRAY[r.entity_id, ed.dependant] AS path, ed.relationship_type AS via
          FROM root r JOIN edges ed ON ed.provider = r.entity_id
        UNION ALL
        SELECT r.model_id, r.entity_id, 'Upstream: it depends on', ed.provider, 1, ARRAY[r.entity_id, ed.provider], ed.relationship_type
          FROM root r JOIN edges ed ON ed.dependant = r.entity_id
        UNION ALL
        SELECT w.model_id, w.root_id, w.dir, CASE WHEN w.dir LIKE 'Down%' THEN ed.dependant ELSE ed.provider END, w.depth + 1,
               w.path || CASE WHEN w.dir LIKE 'Down%' THEN ed.dependant ELSE ed.provider END, ed.relationship_type
          FROM walk w JOIN edges ed ON (w.dir LIKE 'Down%' AND ed.provider = w.id) OR (w.dir LIKE 'Up%' AND ed.dependant = w.id)
         WHERE w.depth < least(greatest(coalesce(p_steps, 4), 1), 6)
           AND NOT (CASE WHEN w.dir LIKE 'Down%' THEN ed.dependant ELSE ed.provider END) = ANY (w.path)
    ), best AS (
        SELECT DISTINCT ON (w.root_id, w.dir, w.id) w.* FROM walk w ORDER BY w.root_id, w.dir, w.id, w.depth
    )
    SELECT b.model_id, m.model_name, r.name, b.dir, b.depth, x.name, x.entity_type, x.type_domain, s.lifecycle, s.criticality, b.via,
           (SELECT string_agg(n.name, CASE WHEN b.dir LIKE 'Down%' THEN ' → ' ELSE ' ← ' END ORDER BY o)
              FROM unnest(b.path) WITH ORDINALITY AS u(eid, o) JOIN rpt.entities n ON n.entity_id = u.eid),
           x.link
      FROM best b JOIN root r ON r.entity_id = b.root_id JOIN rpt.models m ON m.model_id = b.model_id
      JOIN rpt.entities x ON x.entity_id = b.id LEFT JOIN rpt.entity_std s ON s.entity_id = b.id
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_report') THEN
        GRANT EXECUTE ON FUNCTION rpt.f_dependencies(text, integer) TO eax_report;
    END IF;
END;
$$;
