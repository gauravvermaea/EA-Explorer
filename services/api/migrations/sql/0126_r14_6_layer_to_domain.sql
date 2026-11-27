-- Release 14.6 (D959; owner, 26 Nov 2026, 17:54: "Add a next minor release to move layer to domain"; D941):
-- ArchiMate 4's "domain" inside the database too. Since D391 what people and tools see says domain; the internal names
-- were kept until now. One migration renames them, with no compatibility views:
--   core.layers and library_models.layers        -> domains (their sequences, keys, indexes and triggers too)
--   entity_types.layer_id (core, library_models)  -> domain_id
--   core.gap_items.layer, core.common_items.layer -> domain
--   core.copy_model, rpt.f_entities, rpt.f_catalogue and rpt.f_gap_items read the new names; the report functions'
--   result columns and the rpt views keep the names they have (domain, type_domain: D391), so no report changes.
-- history.row_versions is never changed (history.refuse_change): rows written before keep table_name 'layers' and
-- the key layer_id, and the change log reads them as domains (eax/change_log.py).
-- Views follow a renamed table or column by themselves; only the function bodies (stored as text) are written again.

ALTER TABLE core.layers RENAME TO domains;
ALTER SEQUENCE core.layers_id_seq RENAME TO domains_id_seq;
ALTER TABLE core.domains RENAME CONSTRAINT layers_pkey TO domains_pkey;
ALTER TABLE core.domains RENAME CONSTRAINT layers_guid_key TO domains_guid_key;
ALTER TABLE core.domains RENAME CONSTRAINT layers_model_id_code_key TO domains_model_id_code_key;
ALTER TABLE core.domains RENAME CONSTRAINT layers_model_id_fkey TO domains_model_id_fkey;
ALTER TABLE core.domains RENAME CONSTRAINT layers_status_code_fkey TO domains_status_code_fkey;
ALTER INDEX core.layers_model_id_idx RENAME TO domains_model_id_idx;
ALTER INDEX core.layers_status_code_fk RENAME TO domains_status_code_fk;
ALTER TRIGGER layers_00_access ON core.domains RENAME TO domains_00_access;
ALTER TRIGGER layers_0_lock ON core.domains RENAME TO domains_0_lock;
ALTER TRIGGER layers_0_no_truncate ON core.domains RENAME TO domains_0_no_truncate;
ALTER TRIGGER layers_1_model_lock ON core.domains RENAME TO domains_1_model_lock;
ALTER TRIGGER layers_history ON core.domains RENAME TO domains_history;
ALTER TRIGGER layers_stamp ON core.domains RENAME TO domains_stamp;
ALTER TABLE core.entity_types RENAME COLUMN layer_id TO domain_id;
ALTER TABLE core.entity_types RENAME CONSTRAINT entity_types_layer_id_fkey TO entity_types_domain_id_fkey;
ALTER INDEX core.entity_types_layer_id_idx RENAME TO entity_types_domain_id_idx;

ALTER TABLE library_models.layers RENAME TO domains;
ALTER SEQUENCE library_models.layers_id_seq RENAME TO domains_id_seq;
ALTER TABLE library_models.domains RENAME CONSTRAINT layers_pkey TO domains_pkey;
ALTER TABLE library_models.domains RENAME CONSTRAINT layers_guid_key TO domains_guid_key;
ALTER TABLE library_models.domains RENAME CONSTRAINT layers_model_id_code_key TO domains_model_id_code_key;
ALTER INDEX library_models.layers_model_id_idx RENAME TO domains_model_id_idx;
ALTER INDEX library_models.lib_layers_status_code_fk RENAME TO lib_domains_status_code_fk;
ALTER TABLE library_models.entity_types RENAME COLUMN layer_id TO domain_id;
ALTER INDEX library_models.entity_types_layer_id_idx RENAME TO entity_types_domain_id_idx;

COMMENT ON TABLE core.domains IS 'The domains of a model''s metamodel (Business, Application, Technology...)';

ALTER TABLE core.gap_items RENAME COLUMN layer TO domain;
ALTER TABLE core.common_items RENAME COLUMN layer TO domain;

CREATE OR REPLACE FUNCTION core.copy_model(p_src bigint, p_dst bigint, p_content boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    n jsonb := '{}'::jsonb;
    c integer;
BEGIN
    IF EXISTS (SELECT 1 FROM core.entity_types WHERE model_id = p_dst) THEN
        RAISE EXCEPTION 'The model to copy into already has a metamodel';
    END IF;
    PERFORM set_config('eax.copy_into', p_dst::text, true);

    INSERT INTO core.domains (model_id, code, name, description, colour, sort_order, origin_guid, status_code)
    SELECT p_dst, code, name, description, colour, sort_order, guid, status_code
      FROM core.domains WHERE model_id = p_src AND NOT is_deleted;
    GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('domains', c);

    INSERT INTO core.pick_lists (model_id, code, name, description, origin_guid, status_code)
    SELECT p_dst, code, name, description, guid, status_code FROM core.pick_lists WHERE model_id = p_src AND NOT is_deleted;
    GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('pick_lists', c);

    INSERT INTO core.pick_list_values (model_id, pick_list_id, value, description, sort_order, origin_guid, status_code)
    SELECT p_dst, d.id, v.value, v.description, v.sort_order, v.guid, v.status_code
      FROM core.pick_list_values v JOIN core.pick_lists d ON d.model_id = p_dst AND d.origin_guid =
           (SELECT guid FROM core.pick_lists WHERE id = v.pick_list_id)
     WHERE v.model_id = p_src AND NOT v.is_deleted;

    INSERT INTO core.entity_types (model_id, domain_id, code, name, description, aspect, id_prefix, table_name, sort_order,
                                   origin_guid, status_code)
    SELECT p_dst, dl.id, t.code, t.name, t.description, t.aspect, t.id_prefix, t.table_name, t.sort_order, t.guid, t.status_code
      FROM core.entity_types t JOIN core.domains sl ON sl.id = t.domain_id
      JOIN core.domains dl ON dl.model_id = p_dst AND dl.origin_guid = sl.guid
     WHERE t.model_id = p_src AND NOT t.is_deleted;
    GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('entity_types', c);

    INSERT INTO core.relationship_types (model_id, code, name, verb, category, is_directed, description, sort_order,
                                         origin_guid, status_code)
    SELECT p_dst, code, name, verb, category, is_directed, description, sort_order, guid, status_code
      FROM core.relationship_types WHERE model_id = p_src AND NOT is_deleted;
    GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('relationship_types', c);

    INSERT INTO core.attribute_types (model_id, code, name, description, data_type_code, pick_list_id, unit, column_name,
                                      origin_guid, status_code)
    SELECT p_dst, a.code, a.name, a.description, a.data_type_code, dp.id, a.unit, a.column_name, a.guid, a.status_code
      FROM core.attribute_types a
      LEFT JOIN core.pick_lists sp ON sp.id = a.pick_list_id
      LEFT JOIN core.pick_lists dp ON dp.model_id = p_dst AND dp.origin_guid = sp.guid
     WHERE a.model_id = p_src AND NOT a.is_deleted;
    GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('attribute_types', c);

    INSERT INTO core.item_attributes (model_id, attribute_type_id, entity_type_id, relationship_type_id, is_required,
                                      section, sort_order, default_value, help_text, origin_guid, status_code)
    SELECT p_dst, da.id, de.id, dr.id, i.is_required, i.section, i.sort_order, i.default_value, i.help_text, i.guid, i.status_code
      FROM core.item_attributes i
      JOIN core.attribute_types sa ON sa.id = i.attribute_type_id
      JOIN core.attribute_types da ON da.model_id = p_dst AND da.origin_guid = sa.guid
      LEFT JOIN core.entity_types se ON se.id = i.entity_type_id
      LEFT JOIN core.entity_types de ON de.model_id = p_dst AND de.origin_guid = se.guid
      LEFT JOIN core.relationship_types sr ON sr.id = i.relationship_type_id
      LEFT JOIN core.relationship_types dr ON dr.model_id = p_dst AND dr.origin_guid = sr.guid
     WHERE i.model_id = p_src AND NOT i.is_deleted
       AND (i.entity_type_id IS NULL OR de.id IS NOT NULL) AND (i.relationship_type_id IS NULL OR dr.id IS NOT NULL);

    INSERT INTO core.validation_rules (model_id, attribute_type_id, field_name, entity_type_id, rule_type_code, param1, param2,
                                       severity, message, sort_order, origin_guid, status_code)
    SELECT p_dst, da.id, r.field_name, de.id, r.rule_type_code, r.param1, r.param2, r.severity, r.message, r.sort_order,
           r.guid, r.status_code
      FROM core.validation_rules r
      LEFT JOIN core.attribute_types sa ON sa.id = r.attribute_type_id
      LEFT JOIN core.attribute_types da ON da.model_id = p_dst AND da.origin_guid = sa.guid
      LEFT JOIN core.entity_types se ON se.id = r.entity_type_id
      LEFT JOIN core.entity_types de ON de.model_id = p_dst AND de.origin_guid = se.guid
     WHERE r.model_id = p_src AND NOT r.is_deleted
       AND (r.attribute_type_id IS NULL OR da.id IS NOT NULL) AND (r.entity_type_id IS NULL OR de.id IS NOT NULL);
    GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('rules', c);

    INSERT INTO core.allowed_relationships (model_id, relationship_type_id, source_type_id, target_type_id, note,
                                            origin_guid, status_code)
    SELECT p_dst, dr.id, ds.id, dt.id, a.note, a.guid, a.status_code
      FROM core.allowed_relationships a
      JOIN core.relationship_types sr ON sr.id = a.relationship_type_id
      JOIN core.relationship_types dr ON dr.model_id = p_dst AND dr.origin_guid = sr.guid
      JOIN core.entity_types ss ON ss.id = a.source_type_id
      JOIN core.entity_types ds ON ds.model_id = p_dst AND ds.origin_guid = ss.guid
      JOIN core.entity_types st ON st.id = a.target_type_id
      JOIN core.entity_types dt ON dt.model_id = p_dst AND dt.origin_guid = st.guid
     WHERE a.model_id = p_src AND NOT a.is_deleted;
    GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('mappings', c);

    IF p_content THEN
        INSERT INTO core.entities (model_id, entity_type_id, display_id, name, description, origin_guid, status_code)
        SELECT p_dst, dt.id, e.display_id, e.name, e.description, e.guid, e.status_code
          FROM core.entities e JOIN core.entity_types st ON st.id = e.entity_type_id
          JOIN core.entity_types dt ON dt.model_id = p_dst AND dt.origin_guid = st.guid
         WHERE e.model_id = p_src AND NOT e.is_deleted;
        GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('entities', c);

        -- parents once every entity is there
        UPDATE core.entities d SET parent_entity_id = dp.id
          FROM core.entities s
          JOIN core.entities sp ON sp.id = s.parent_entity_id
          JOIN core.entities dp ON dp.model_id = p_dst AND dp.origin_guid = sp.guid
         WHERE d.model_id = p_dst AND d.origin_guid = s.guid AND s.model_id = p_src AND s.parent_entity_id IS NOT NULL;

        INSERT INTO core.display_id_counters (model_id, entity_type_id, last_number, origin_guid)
        SELECT p_dst, dt.id, k.last_number, k.guid
          FROM core.display_id_counters k JOIN core.entity_types st ON st.id = k.entity_type_id
          JOIN core.entity_types dt ON dt.model_id = p_dst AND dt.origin_guid = st.guid
         WHERE k.model_id = p_src
        ON CONFLICT (model_id, entity_type_id) DO UPDATE SET last_number = greatest(core.display_id_counters.last_number,
                                                                                    EXCLUDED.last_number);

        INSERT INTO core.relationships (model_id, relationship_type_id, source_entity_id, target_entity_id, name, description,
                                        origin_guid, status_code)
        SELECT p_dst, dr.id, ds.id, dt.id, r.name, r.description, r.guid, r.status_code
          FROM core.relationships r
          JOIN core.relationship_types sr ON sr.id = r.relationship_type_id
          JOIN core.relationship_types dr ON dr.model_id = p_dst AND dr.origin_guid = sr.guid
          JOIN core.entities se ON se.id = r.source_entity_id AND NOT se.is_deleted
          JOIN core.entities ds ON ds.model_id = p_dst AND ds.origin_guid = se.guid
          JOIN core.entities te ON te.id = r.target_entity_id AND NOT te.is_deleted
          JOIN core.entities dt ON dt.model_id = p_dst AND dt.origin_guid = te.guid
         WHERE r.model_id = p_src AND NOT r.is_deleted;
        GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('relationships', c);

        INSERT INTO core.attribute_values (model_id, attribute_type_id, entity_id, relationship_id, value_text, value_number,
                                           value_date, value_bool, value_ref, origin_guid, status_code)
        SELECT p_dst, da.id, de.id, dr.id, v.value_text, v.value_number, v.value_date, v.value_bool, dref.id, v.guid, v.status_code
          FROM core.attribute_values v
          JOIN core.attribute_types sa ON sa.id = v.attribute_type_id
          JOIN core.attribute_types da ON da.model_id = p_dst AND da.origin_guid = sa.guid
          LEFT JOIN core.entities se ON se.id = v.entity_id
          LEFT JOIN core.entities de ON de.model_id = p_dst AND de.origin_guid = se.guid
          LEFT JOIN core.relationships sr ON sr.id = v.relationship_id
          LEFT JOIN core.relationships dr ON dr.model_id = p_dst AND dr.origin_guid = sr.guid
          LEFT JOIN core.entities sref ON sref.id = v.value_ref
          LEFT JOIN core.entities dref ON dref.model_id = p_dst AND dref.origin_guid = sref.guid
         WHERE v.model_id = p_src AND NOT v.is_deleted
           AND (v.entity_id IS NULL OR de.id IS NOT NULL) AND (v.relationship_id IS NULL OR dr.id IS NOT NULL)
           AND (v.value_ref IS NULL OR dref.id IS NOT NULL);
        GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('values', c);
    END IF;

    PERFORM set_config('eax.copy_into', '', true);
    RETURN n;
END;
$function$;

CREATE OR REPLACE FUNCTION rpt.f_entities()
 RETURNS TABLE(model_id bigint, model_name text, entity_id bigint, entity_guid uuid, display_id text, name text, description text, entity_type_code text, entity_type text, layer_code text, layer text, parent_id bigint, parent_name text, status text, origin_guid uuid, created_at timestamp with time zone, created_by text, modified_at timestamp with time zone, modified_by text, link text)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'core'
AS $function$
BEGIN
    PERFORM set_config('eax.rls_bypass', 'on', true);
    RETURN QUERY
    SELECT e.model_id, m.name, e.id, e.guid, e.display_id, e.name, e.description, t.code, t.name, l.code, l.name,
           e.parent_entity_id, pe.name, e.status_code, e.origin_guid, e.created_at, e.created_by, e.modified_at, e.modified_by,
           '#/metamodel/' || m.guid || '/entity/' || e.guid
      FROM core.entities e JOIN core.models m ON m.id = e.model_id AND NOT m.is_deleted
      JOIN core.entity_types t ON t.id = e.entity_type_id JOIN core.domains l ON l.id = t.domain_id
      LEFT JOIN core.entities pe ON pe.id = e.parent_entity_id
     WHERE NOT e.is_deleted;
    PERFORM set_config('eax.rls_bypass', '', true);
END;
$function$;

CREATE OR REPLACE FUNCTION rpt.f_catalogue()
 RETURNS TABLE(model_id bigint, model_name text, layer text, entity_type_code text, entity_type text, report_view text, attribute_code text, attribute text, data_type text, pick_list text, pick_list_values text, required boolean, report_column text)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'core'
AS $function$
BEGIN
    PERFORM set_config('eax.rls_bypass', 'on', true);
    RETURN QUERY
    SELECT m.id, m.name, l.name, t.code, t.name, 'rpt.t_' || rpt.snake(t.code), a.code, a.name, a.data_type_code, pl.name,
           (SELECT string_agg(pv.value, ', ' ORDER BY pv.sort_order) FROM core.pick_list_values pv
             WHERE pv.pick_list_id = pl.id AND NOT pv.is_deleted),
           i.is_required, rpt.snake(a.code)
      FROM core.entity_types t JOIN core.models m ON m.id = t.model_id AND NOT m.is_deleted
      JOIN core.domains l ON l.id = t.domain_id
      LEFT JOIN core.item_attributes i ON i.entity_type_id = t.id AND NOT i.is_deleted
      LEFT JOIN core.attribute_types a ON a.id = i.attribute_type_id
      LEFT JOIN core.pick_lists pl ON pl.id = a.pick_list_id
     WHERE NOT t.is_deleted AND t.status_code <> 'retired';
    PERFORM set_config('eax.rls_bypass', '', true);
END;
$function$;

CREATE OR REPLACE FUNCTION rpt.f_gap_items()
 RETURNS TABLE(model_id bigint, model_name text, gap_analysis text, template text, baseline text, target text, compared_at timestamp with time zone, entity_type text, entity_type_name text, layer text, name text, status text, togaf_cell text, baseline_name text, target_name text, fields_changed integer, changed_fields text, note text, resolution text, work_packages text, work_package_count integer, has_gap_entity boolean, link text)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'core'
AS $function$
#variable_conflict use_column
BEGIN
    PERFORM set_config('eax.rls_bypass', 'on', true);
    RETURN QUERY
    SELECT a.model_id, m.name, a.name, a.template, a.baseline ->> 'label', a.target ->> 'label', a.compared_at,
           i.entity_type, i.entity_type_name, i.domain, i.name, i.status,
           CASE i.status WHEN 'kept' THEN 'Included' WHEN 'changed' THEN 'Changed' WHEN 'new' THEN 'New (gap: to build or buy)'
                         ELSE 'Eliminated (gap: to retire or replace)' END,
           i.baseline_name, i.target_name, jsonb_array_length(i.changes),
           (SELECT string_agg(c ->> 'label', ', ') FROM jsonb_array_elements(i.changes) c),
           i.note, nullif(i.resolution, ''),
           (SELECT string_agg(w.name, ', ' ORDER BY w.name) FROM core.entities w WHERE w.guid = ANY (i.work_packages) AND NOT w.is_deleted),
           cardinality(i.work_packages), i.gap_entity IS NOT NULL, '#/compare/gaps/' || a.guid
      FROM core.gap_items i JOIN core.gap_analyses a ON a.id = i.analysis_id
      JOIN core.models m ON m.id = a.model_id AND NOT m.is_deleted
     WHERE NOT i.gone;
    PERFORM set_config('eax.rls_bypass', '', true);
END;
$function$;
