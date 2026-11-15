-- =====================================================================================
-- 0079_r5_auditor: R5.22 (D693): the Auditor, a global role that sees everything a Super Admin sees and changes
--   nothing. The API answers an Auditor's reads as a Super Admin's and judges their changes by their other roles
--   (eax/permissions.py auditor_roles), so the database sees no new rule for the screens. Here: the role and its
--   default mapping (Keycloak role eax-audit), and the reports' model access (rpt.f_model_access, phase 5, D138)
--   giving the Auditor every model, as the Super Admin.
-- =====================================================================================

INSERT INTO core.app_roles (code, name, scope, description, sort_order) VALUES
    ('auditor', 'Auditor', 'global', 'Sees everything a Super Admin sees (secrets only as set or not set), every report and all data; changes nothing', 5)
ON CONFLICT (code) DO NOTHING;

INSERT INTO core.role_mappings (keycloak_role, app_role, created_by)
VALUES ('eax-audit', 'auditor', 'system:migration')
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION rpt.f_model_access() RETURNS TABLE (username text, model_id bigint)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, core AS $$
BEGIN
    PERFORM set_config('eax.rls_bypass', 'on', true);
    RETURN QUERY
    SELECT lower(k.username), m.id FROM core.known_users k CROSS JOIN core.models m
     WHERE NOT m.is_deleted AND k.roles && ARRAY['super-admin', 'auditor']
    UNION
    SELECT lower(k.username), m.id FROM core.known_users k CROSS JOIN core.models m
     WHERE NOT m.is_deleted AND m.kind_code IN ('template', 'reference') AND NOT m.is_draft
    UNION
    SELECT lower(u.username), u.model_id FROM core.model_users u
    UNION
    SELECT lower(u.username), a.ancestor_id FROM core.model_users u JOIN core.model_ancestors a ON a.model_id = u.model_id;
    PERFORM set_config('eax.rls_bypass', '', true);
END;
$$;
