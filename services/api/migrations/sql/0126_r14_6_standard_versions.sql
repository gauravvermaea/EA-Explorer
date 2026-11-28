-- =====================================================================================
-- 0126_r14_6_standard_versions: which version of a standard each domain, element type, relationship type and allowed
-- relationship belongs to (Release 14.6, D965; owner, 28 Nov 2026, 07:43: "in both core domain and entity types we should
-- have a archimate_version_id_start and archimate_version_id_end ... The idea is when new versions of archimate come we
-- know what new items come in it, then what is removed goes in end and what lives on is in new version"; 07:47: the
-- relationship types and allowed relationships too, a "replaced by" link, the names standard_version_start_id and
-- standard_version_end_id, empty end while current).
--   core.standard_versions   a standard's versions in order: ArchiMate 4.0 to start with
--   ..._start_id             the version the item came in; empty for an item of no standard (a custom type, an extension)
--   ..._end_id               the last version it is in; empty while it is in the latest
--   replaced_by_id           what takes its place in a later version (renamed, merged), in the same model
-- library_models' copies get the same columns (no foreign keys: that schema may live in a database of its own).
-- Rows only, and core.copy_model carrying them to a copy; the rules (an end not before its start) are in the code (D248).
-- =====================================================================================

CREATE TABLE IF NOT EXISTS core.standard_versions (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guid        uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    standard    text NOT NULL,                       -- ArchiMate, TOGAF, ...
    version     text NOT NULL,                       -- 4.0, 4.1, ...
    released    date,
    sort_order  integer NOT NULL,                    -- the versions of a standard in order
    description text NOT NULL DEFAULT '',
    UNIQUE (standard, version),
    UNIQUE (standard, sort_order)
);
COMMENT ON TABLE core.standard_versions IS 'The versions of a standard (ArchiMate 4.0, ...) the metamodel''s items say they come from (D965)';
INSERT INTO core.standard_versions (standard, version, sort_order, description)
VALUES ('ArchiMate', '4.0', 40, 'The Open Group ArchiMate 4 Specification')
ON CONFLICT (standard, version) DO NOTHING;

ALTER TABLE core.domains
    ADD COLUMN IF NOT EXISTS standard_version_start_id bigint REFERENCES core.standard_versions (id),
    ADD COLUMN IF NOT EXISTS standard_version_end_id bigint REFERENCES core.standard_versions (id),
    ADD COLUMN IF NOT EXISTS replaced_by_id bigint REFERENCES core.domains (id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS domains_standard_version_start_id_idx ON core.domains (standard_version_start_id);
CREATE INDEX IF NOT EXISTS domains_standard_version_end_id_idx ON core.domains (standard_version_end_id);
CREATE INDEX IF NOT EXISTS domains_replaced_by_id_idx ON core.domains (replaced_by_id);
ALTER TABLE library_models.domains
    ADD COLUMN IF NOT EXISTS standard_version_start_id bigint,
    ADD COLUMN IF NOT EXISTS standard_version_end_id bigint,
    ADD COLUMN IF NOT EXISTS replaced_by_id bigint;

ALTER TABLE core.entity_types
    ADD COLUMN IF NOT EXISTS standard_version_start_id bigint REFERENCES core.standard_versions (id),
    ADD COLUMN IF NOT EXISTS standard_version_end_id bigint REFERENCES core.standard_versions (id),
    ADD COLUMN IF NOT EXISTS replaced_by_id bigint REFERENCES core.entity_types (id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS entity_types_standard_version_start_id_idx ON core.entity_types (standard_version_start_id);
CREATE INDEX IF NOT EXISTS entity_types_standard_version_end_id_idx ON core.entity_types (standard_version_end_id);
CREATE INDEX IF NOT EXISTS entity_types_replaced_by_id_idx ON core.entity_types (replaced_by_id);
ALTER TABLE library_models.entity_types
    ADD COLUMN IF NOT EXISTS standard_version_start_id bigint,
    ADD COLUMN IF NOT EXISTS standard_version_end_id bigint,
    ADD COLUMN IF NOT EXISTS replaced_by_id bigint;

ALTER TABLE core.relationship_types
    ADD COLUMN IF NOT EXISTS standard_version_start_id bigint REFERENCES core.standard_versions (id),
    ADD COLUMN IF NOT EXISTS standard_version_end_id bigint REFERENCES core.standard_versions (id),
    ADD COLUMN IF NOT EXISTS replaced_by_id bigint REFERENCES core.relationship_types (id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS relationship_types_standard_version_start_id_idx ON core.relationship_types (standard_version_start_id);
CREATE INDEX IF NOT EXISTS relationship_types_standard_version_end_id_idx ON core.relationship_types (standard_version_end_id);
CREATE INDEX IF NOT EXISTS relationship_types_replaced_by_id_idx ON core.relationship_types (replaced_by_id);
ALTER TABLE library_models.relationship_types
    ADD COLUMN IF NOT EXISTS standard_version_start_id bigint,
    ADD COLUMN IF NOT EXISTS standard_version_end_id bigint,
    ADD COLUMN IF NOT EXISTS replaced_by_id bigint;

ALTER TABLE core.allowed_relationships
    ADD COLUMN IF NOT EXISTS standard_version_start_id bigint REFERENCES core.standard_versions (id),
    ADD COLUMN IF NOT EXISTS standard_version_end_id bigint REFERENCES core.standard_versions (id),
    ADD COLUMN IF NOT EXISTS replaced_by_id bigint REFERENCES core.allowed_relationships (id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS allowed_relationships_standard_version_start_id_idx ON core.allowed_relationships (standard_version_start_id);
CREATE INDEX IF NOT EXISTS allowed_relationships_standard_version_end_id_idx ON core.allowed_relationships (standard_version_end_id);
CREATE INDEX IF NOT EXISTS allowed_relationships_replaced_by_id_idx ON core.allowed_relationships (replaced_by_id);
ALTER TABLE library_models.allowed_relationships
    ADD COLUMN IF NOT EXISTS standard_version_start_id bigint,
    ADD COLUMN IF NOT EXISTS standard_version_end_id bigint,
    ADD COLUMN IF NOT EXISTS replaced_by_id bigint;

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

    INSERT INTO core.domains (model_id, code, name, description, colour, sort_order, origin_guid, status_code, standard_version_start_id, standard_version_end_id)
    SELECT p_dst, code, name, description, colour, sort_order, guid, status_code, standard_version_start_id, standard_version_end_id
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
                                   origin_guid, status_code, standard_version_start_id, standard_version_end_id)
    SELECT p_dst, dl.id, t.code, t.name, t.description, t.aspect, t.id_prefix, t.table_name, t.sort_order, t.guid, t.status_code,
           t.standard_version_start_id, t.standard_version_end_id
      FROM core.entity_types t JOIN core.domains sl ON sl.id = t.domain_id
      JOIN core.domains dl ON dl.model_id = p_dst AND dl.origin_guid = sl.guid
     WHERE t.model_id = p_src AND NOT t.is_deleted;
    GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('entity_types', c);

    INSERT INTO core.relationship_types (model_id, code, name, verb, category, is_directed, description, sort_order,
                                         origin_guid, status_code, standard_version_start_id, standard_version_end_id)
    SELECT p_dst, code, name, verb, category, is_directed, description, sort_order, guid, status_code, standard_version_start_id, standard_version_end_id
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
                                            origin_guid, status_code, standard_version_start_id, standard_version_end_id)
    SELECT p_dst, dr.id, ds.id, dt.id, a.note, a.guid, a.status_code, a.standard_version_start_id, a.standard_version_end_id
      FROM core.allowed_relationships a
      JOIN core.relationship_types sr ON sr.id = a.relationship_type_id
      JOIN core.relationship_types dr ON dr.model_id = p_dst AND dr.origin_guid = sr.guid
      JOIN core.entity_types ss ON ss.id = a.source_type_id
      JOIN core.entity_types ds ON ds.model_id = p_dst AND ds.origin_guid = ss.guid
      JOIN core.entity_types st ON st.id = a.target_type_id
      JOIN core.entity_types dt ON dt.model_id = p_dst AND dt.origin_guid = st.guid
     WHERE a.model_id = p_src AND NOT a.is_deleted;
    GET DIAGNOSTICS c = ROW_COUNT; n := n || jsonb_build_object('mappings', c);

    -- what replaces what, within the copy (D965)
    UPDATE core.domains d SET replaced_by_id = dn.id
      FROM core.domains s JOIN core.domains sn ON sn.id = s.replaced_by_id
      JOIN core.domains dn ON dn.model_id = p_dst AND dn.origin_guid = sn.guid
     WHERE s.model_id = p_src AND d.model_id = p_dst AND d.origin_guid = s.guid;
    UPDATE core.entity_types d SET replaced_by_id = dn.id
      FROM core.entity_types s JOIN core.entity_types sn ON sn.id = s.replaced_by_id
      JOIN core.entity_types dn ON dn.model_id = p_dst AND dn.origin_guid = sn.guid
     WHERE s.model_id = p_src AND d.model_id = p_dst AND d.origin_guid = s.guid;
    UPDATE core.relationship_types d SET replaced_by_id = dn.id
      FROM core.relationship_types s JOIN core.relationship_types sn ON sn.id = s.replaced_by_id
      JOIN core.relationship_types dn ON dn.model_id = p_dst AND dn.origin_guid = sn.guid
     WHERE s.model_id = p_src AND d.model_id = p_dst AND d.origin_guid = s.guid;
    UPDATE core.allowed_relationships d SET replaced_by_id = dn.id
      FROM core.allowed_relationships s JOIN core.allowed_relationships sn ON sn.id = s.replaced_by_id
      JOIN core.allowed_relationships dn ON dn.model_id = p_dst AND dn.origin_guid = sn.guid
     WHERE s.model_id = p_src AND d.model_id = p_dst AND d.origin_guid = s.guid;

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

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_report') THEN
        GRANT SELECT ON core.standard_versions TO eax_report;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_migrator') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON core.standard_versions TO eax_migrator;
    END IF;
END;
$$;

