"""The API container's part of the backup and restore cases (eax test backup-cases, last but one in eax test full; owner,
28 Nov 2026, 09:05: "I need very very detailed test suite to test backups and restores are working from command line
using the commands including model and project zip backups with finger printing"; 09:08: "after a backup is done its
zip file should be checked ... try schedule backup test"; D971).

The host's side (eaxcli/backup_cases.py) runs the real eax commands, one after another, each waited for; between them it
asks this module, `docker compose exec -T api python -m eax.testing.backup_cases <command>` with the test's state as JSON
on standard input and one JSON line on standard output, to make the test's content, take fingerprints and make changes:

  start          the test's record (a self-test run, so its data is removed like any self-test's), a Super Admin account,
                 the models and project every self-test run makes (self_test_<id>_1 with entities, relationships, a drawn
                 view and a line attribute; _2 its child; _3 the project), then more: entities with descriptions, values
                 and tags, relationships, a model tag, a KPI, the child's own change, and in the project a step, a key
                 question, a stakeholder with a discussion, a Business Model Canvas with items and a document with its
                 file. The application backups' "keep" is raised for the test (so its backups never push out the owner's
                 own) and the schedules are noted, to be put back by finish.
  fingerprint    {models, projects}: each one's fingerprint (below)
  change_model   {model}: changes through the API as a person makes them (an entity added, one renamed with a new
                 description, one deleted, a relationship added), committed
  change_project {project}: a step added, a key question removed, the canvas renamed with an item added
  delete_model   {model}: the model deleted (as Model admin does)
  new_model      {name}: a model made after the backup
  forge          {sid, good}: files in the uploaded folder: not good backups (not a zip, a zip without backup.json, one
                 cut short, one from a newer release, one changed after it was made), and two that are (a copy of a
                 good one, as if brought from another installation, and one as made before fingerprints)
  find           {models: [names], projects: [names]}: their ids (or "")
  runs           {prefix}: the application backups whose tag starts with it, with their files and status
  others         every backup file that is not the test's, with its size (the same at the start and the end)
  register       {models, projects}: models and projects made by restores, recorded as the test's, to be removed
  schedule_next  the Backups page's application schedule set to run in the coming minute (the old one noted)
  schedule_reset the schedules put back as they were
  finish         the results recorded, the test's data removed, keep and the schedules put back, the record closed

A model's fingerprint holds no database id, so a model restored as a new model compares with the one it came from:
  metamodel   domains, element and relationship types, allowed relationships (with the standard version each belongs
              to and what replaces it, D965), attributes and where they apply, pick lists and rules, by code
  entities    type, name, description, status, parent, tags
  values      each attribute value by its entity (or relationship) and attribute
  relationships  type, both ends (type and name), name, description, status
  views       the drawn views by name, with how many elements each holds
  kpis        the model's own KPIs by name and kind
  icons       each entity icon's SHA-256 by its entity
and "keys" (guids and display IDs), compared only when a model is put back over itself (it keeps them).
A project's fingerprint: its steps, document classes, stakeholders, key questions, canvases and their items, documents
and the models it works on, by content (core), and every table of the project backup without ids or times (all,
compared when a project is put back over itself), and each document file's SHA-256 from Documents.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from . import fixtures, store
from .backup_restore import Api, _err, _ok, _upload_waiting, _why, say

ROLES = ["super-admin"]
KEEP_EXTRA = 25          # the application backups' keep raised by this for the test (D971)


def digest(rows: list) -> str:
    """A checksum over rows, in a fixed order (pure)."""
    h = hashlib.sha256()
    for r in sorted(json.dumps(x, default=str, sort_keys=True) for x in rows):
        h.update(r.encode("utf-8") + b"\x1e")
    return h.hexdigest()[:20]


# ---------------------------------------------------------------- fingerprints
def _all(conn, q: str, **p) -> list[list]:
    return [list(r) for r in conn.execute(text(q), p).all()]


MODEL_PARTS: dict[str, str] = {
    "domains": """SELECT d.code, d.name, d.colour, coalesce(d.description, ''), sv.standard || ' ' || sv.version,
                         ev.standard || ' ' || ev.version, rb.code
                    FROM core.domains d LEFT JOIN core.standard_versions sv ON sv.id = d.standard_version_start_id
                    LEFT JOIN core.standard_versions ev ON ev.id = d.standard_version_end_id
                    LEFT JOIN core.domains rb ON rb.id = d.replaced_by_id
                   WHERE d.model_id = :m AND NOT d.is_deleted""",
    "entity_types": """SELECT t.code, t.name, d.code, b.code, coalesce(t.aspect, ''), coalesce(t.description, ''), t.status_code,
                              coalesce(t.notation, ''), coalesce(t.fill_colour, ''), t.is_connector,
                              sv.standard || ' ' || sv.version, ev.standard || ' ' || ev.version, rb.code
                         FROM core.entity_types t JOIN core.domains d ON d.id = t.domain_id
                         LEFT JOIN core.entity_types b ON b.id = t.base_type_id
                         LEFT JOIN core.standard_versions sv ON sv.id = t.standard_version_start_id
                         LEFT JOIN core.standard_versions ev ON ev.id = t.standard_version_end_id
                         LEFT JOIN core.entity_types rb ON rb.id = t.replaced_by_id
                        WHERE t.model_id = :m AND NOT t.is_deleted""",
    "relationship_types": """SELECT r.code, r.name, coalesce(r.verb, ''), coalesce(r.category, ''), r.is_directed,
                                    coalesce(r.description, ''), r.status_code, sv.standard || ' ' || sv.version,
                                    ev.standard || ' ' || ev.version, rb.code
                               FROM core.relationship_types r
                               LEFT JOIN core.standard_versions sv ON sv.id = r.standard_version_start_id
                               LEFT JOIN core.standard_versions ev ON ev.id = r.standard_version_end_id
                               LEFT JOIN core.relationship_types rb ON rb.id = r.replaced_by_id
                              WHERE r.model_id = :m AND NOT r.is_deleted""",
    "allowed": """SELECT s.code, rt.code, t.code, coalesce(a.note, ''), a.source_multiplicity, a.target_multiplicity,
                         sv.standard || ' ' || sv.version, ev.standard || ' ' || ev.version, bs.code, br.code, bt.code
                    FROM core.allowed_relationships a
                    JOIN core.entity_types s ON s.id = a.source_type_id JOIN core.entity_types t ON t.id = a.target_type_id
                    JOIN core.relationship_types rt ON rt.id = a.relationship_type_id
                    LEFT JOIN core.standard_versions sv ON sv.id = a.standard_version_start_id
                    LEFT JOIN core.standard_versions ev ON ev.id = a.standard_version_end_id
                    LEFT JOIN core.allowed_relationships b ON b.id = a.replaced_by_id
                    LEFT JOIN core.entity_types bs ON bs.id = b.source_type_id
                    LEFT JOIN core.entity_types bt ON bt.id = b.target_type_id
                    LEFT JOIN core.relationship_types br ON br.id = b.relationship_type_id
                   WHERE a.model_id = :m AND NOT a.is_deleted""",
    "attributes": """SELECT a.code, a.name, a.data_type_code, pl.code, coalesce(a.unit, ''), coalesce(a.description, '')
                       FROM core.attribute_types a LEFT JOIN core.pick_lists pl ON pl.id = a.pick_list_id
                      WHERE a.model_id = :m AND NOT a.is_deleted""",
    "attributes_on_types": """SELECT coalesce(et.code, ''), coalesce(rt.code, ''), at.code, i.is_required, coalesce(i.section, ''),
                                     i.default_value
                                FROM core.item_attributes i JOIN core.attribute_types at ON at.id = i.attribute_type_id
                                LEFT JOIN core.entity_types et ON et.id = i.entity_type_id
                                LEFT JOIN core.relationship_types rt ON rt.id = i.relationship_type_id
                               WHERE i.model_id = :m AND NOT i.is_deleted""",
    "pick_lists": """SELECT pl.code, pl.name, v.value, v.status_code FROM core.pick_lists pl
                       LEFT JOIN core.pick_list_values v ON v.pick_list_id = pl.id AND NOT v.is_deleted
                      WHERE pl.model_id = :m AND NOT pl.is_deleted""",
    "rules": """SELECT et.code, at.code, vr.field_name, vr.rule_type_code, coalesce(vr.param1, ''), coalesce(vr.param2, ''),
                       vr.severity, vr.message
                  FROM core.validation_rules vr LEFT JOIN core.entity_types et ON et.id = vr.entity_type_id
                  LEFT JOIN core.attribute_types at ON at.id = vr.attribute_type_id
                 WHERE vr.model_id = :m AND NOT vr.is_deleted""",
    "entities": """SELECT t.code, e.name, coalesce(e.description, ''), e.status_code, p.name, e.tags
                     FROM core.entities e JOIN core.entity_types t ON t.id = e.entity_type_id
                     LEFT JOIN core.entities p ON p.id = e.parent_entity_id
                    WHERE e.model_id = :m AND NOT e.is_deleted""",
    "values": """SELECT coalesce(et.code || ':' || e.name, rt.code || ':' || rs.name || '>' || rtg.name), at.code,
                        v.value_text, v.value_number, v.value_date, v.value_bool
                   FROM core.attribute_values v JOIN core.attribute_types at ON at.id = v.attribute_type_id
                   LEFT JOIN core.entities e ON e.id = v.entity_id LEFT JOIN core.entity_types et ON et.id = e.entity_type_id
                   LEFT JOIN core.relationships r ON r.id = v.relationship_id
                   LEFT JOIN core.relationship_types rt ON rt.id = r.relationship_type_id
                   LEFT JOIN core.entities rs ON rs.id = r.source_entity_id LEFT JOIN core.entities rtg ON rtg.id = r.target_entity_id
                  WHERE v.model_id = :m AND NOT v.is_deleted""",
    "relationships": """SELECT rt.code, st.code || ':' || s.name, tt.code || ':' || t.name, coalesce(r.name, ''),
                               coalesce(r.description, ''), r.status_code
                          FROM core.relationships r JOIN core.relationship_types rt ON rt.id = r.relationship_type_id
                          JOIN core.entities s ON s.id = r.source_entity_id JOIN core.entity_types st ON st.id = s.entity_type_id
                          JOIN core.entities t ON t.id = r.target_entity_id JOIN core.entity_types tt ON tt.id = t.entity_type_id
                         WHERE r.model_id = :m AND NOT r.is_deleted""",
    "icons": """SELECT t.code || ':' || e.name, i.content_type, md5(i.content)
                  FROM core.entity_icons i JOIN core.entities e ON e.id = i.entity_id
                  JOIN core.entity_types t ON t.id = e.entity_type_id
                 WHERE e.model_id = :m AND NOT e.is_deleted""",
}
METAMODEL = ("domains", "entity_types", "relationship_types", "allowed", "attributes", "attributes_on_types", "pick_lists", "rules")
CONTENT = ("entities", "values", "relationships", "icons", "views", "kpis")
KEYS_SQL = """SELECT 'e', e.guid::text, e.display_id FROM core.entities e WHERE e.model_id = :m AND NOT e.is_deleted
              UNION ALL SELECT 'r', r.guid::text, '' FROM core.relationships r WHERE r.model_id = :m AND NOT r.is_deleted"""


def model_fingerprint(conn, guid: str) -> dict:
    """A model's fingerprint (see the module); {"missing": True} when there is no such model."""
    conn.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
    m = conn.execute(text("SELECT id, name, kind_code FROM core.models WHERE guid = CAST(:g AS uuid) AND NOT is_deleted"),
                     {"g": guid}).first()
    if not m:
        return {"missing": True}
    parts, counts = {}, {}
    for part, q in MODEL_PARTS.items():
        rows = _all(conn, q, m=m[0])
        parts[part], counts[part] = digest(rows), len(rows)
    try:
        from .. import views_client as vc
        views = (vc.export_model(guid, all_versions=False) or {}).get("drawn_views") or []
        rows = [[v.get("name"), *sorted(f"{k}:{len(x)}" for k, x in v.items() if isinstance(x, list))] for v in views]
        parts["views"], counts["views"] = digest(rows), len(rows)
    except Exception as exc:  # noqa: BLE001 - no views service: said, not compared
        parts["views"], counts["views"] = "unavailable", f"the views service did not answer ({str(exc)[:80]})"
    try:
        from .. import kpis
        rows = [[d.get("name"), d.get("kind"), d.get("entity_type_code"), d.get("attribute_code")] for d in kpis.definitions(conn, m[0])]
        parts["kpis"], counts["kpis"] = digest(rows), len(rows)
    except Exception as exc:  # noqa: BLE001
        parts["kpis"], counts["kpis"] = "unavailable", str(exc)[:80]
    keys = _all(conn, KEYS_SQL, m=m[0])
    commits = conn.execute(text("SELECT count(*) FROM core.commits WHERE model_id = :m"), {"m": m[0]}).scalar()
    tags = [r[0] for r in conn.execute(text("SELECT name FROM core.model_tags WHERE model_id = :m ORDER BY name"), {"m": m[0]})]
    return {"name": m[1], "kind": m[2], "parts": parts, "counts": counts, "keys": digest(keys),
            "info": {"commits": commits, "tags": tags}}


def compare_models(before: dict, after: dict, keys: bool = False, parts: tuple[str, ...] = METAMODEL + CONTENT) -> list[str]:
    """What differs between two model fingerprints, in words (empty: the same) (pure)."""
    if after.get("missing"):
        return ["the model is missing"]
    if before.get("missing"):
        return ["the model to compare with is missing"]
    out = []
    for p in parts:
        b, a = before["parts"].get(p), after["parts"].get(p)
        if "unavailable" in (a, b):
            continue
        if a != b:
            cb, ca = before["counts"].get(p), after["counts"].get(p)
            out.append(f"{p}: {cb} before, {ca} after" if cb != ca else f"{p}: the same count ({ca}), different content")
    if before.get("kind") != after.get("kind"):
        out.append(f"kind: {before.get('kind')} before, {after.get('kind')} after")
    if keys and before.get("keys") != after.get("keys"):
        out.append("the entities' and relationships' ids or display IDs changed")
    return out


PROJECT_CORE: dict[str, str] = {
    "steps": "SELECT phase, seq, name, removed, coalesce(done_note, ''), due_date FROM proj.steps WHERE project_id = :p",
    "items": "SELECT phase, name, kind, type, chosen, folder, placeholder, coalesce(note, '') FROM proj.items WHERE project_id = :p",
    "stakeholders": """SELECT name, coalesce(organisation, ''), coalesce(role_title, ''), coalesce(category, ''),
                              coalesce(concerns, ''), power, interest FROM proj.stakeholders WHERE project_id = :p""",
    "key_questions": """SELECT question, coalesce(asked_by, ''), coalesce(approach, ''), status, coalesce(answer, '')
                          FROM proj.key_questions WHERE project_id = :p""",
    "canvases": "SELECT name, kind, status, coalesce(description, '') FROM proj.canvases WHERE project_id = :p",
    "canvas_items": """SELECT c.name, i.block, i.sort_order, i.text, coalesce(i.note, ''), coalesce(i.mark, ''), coalesce(i.was_text, '')
                         FROM proj.canvas_items i JOIN proj.canvases c ON c.id = i.canvas_id WHERE c.project_id = :p""",
    "documents": """SELECT coalesce(folder, ''), file_name, coalesce(kind, ''), coalesce(state, ''), coalesce(title, ''),
                           coalesce(description, '') FROM proj.documents WHERE project_id = :p AND deleted_at IS NULL""",
    "models": "SELECT how, coalesce(role, ''), model_guid::text FROM proj.project_models WHERE project_id = :p",
}
VOLATILE = re.compile(r"^(id|guid|origin_guid|project_id|row_version|versions|file_size|sort_order)$|_id$|_at$|_by$|^mayan_|^repo_|"
                      r"_tries$|^is_test_data$|_guid$")
EVENT_TABLES = re.compile(r"_events$|^gov_history$|^members$|^signoff$")


def project_fingerprint(pc, guid: str, files: bool = True) -> dict:
    """A project's fingerprint (see the module); {"missing": True} when there is no such project."""
    from .. import project_backup as pb
    p = pc.execute(text("SELECT * FROM proj.projects WHERE guid = CAST(:g AS uuid)"), {"g": guid}).mappings().first()
    if not p:
        return {"missing": True}
    pid = p["id"]
    core, counts = {}, {}
    for part, q in PROJECT_CORE.items():
        rows = _all(pc, q, p=pid)
        core[part], counts[part] = digest(rows), len(rows)
    whole = {}
    for table, where, _m in pb.TABLES:
        if EVENT_TABLES.search(table):
            continue
        try:
            rows = [dict(r) for r in pc.execute(text(f"SELECT * FROM proj.{table} WHERE {where}"), {"p": pid}).mappings()]
        except Exception:  # noqa: BLE001 - a table this installation does not have yet
            continue
        whole[table] = digest([{k: v for k, v in r.items() if not VOLATILE.search(k)} for r in rows])
    proj_row = {k: v for k, v in dict(p).items() if not VOLATILE.search(k) and k != "name"}
    whole["projects"] = digest([proj_row])
    file_rows, note = [], ""
    if files:
        from .. import mayan
        for d in pc.execute(text("""SELECT folder, file_name, mayan_document_id FROM proj.documents
                                     WHERE project_id = :p AND deleted_at IS NULL AND mayan_document_id IS NOT NULL"""),
                            {"p": pid}).mappings():
            try:
                content, _ct, _n = mayan.download(d["mayan_document_id"])
                file_rows.append([d["folder"] or "", d["file_name"], hashlib.sha256(content).hexdigest()])
            except Exception as exc:  # noqa: BLE001 - Documents down: said, the files not compared
                note = f"Documents did not give the files ({str(exc)[:80]})"
                file_rows = []
                break
    return {"name": p["name"], "core": core, "counts": counts, "all": whole, "repo_state": p.get("repo_state"),
            "files": "unavailable" if note else digest(file_rows), "file_count": len(file_rows), "note": note}


def compare_projects(before: dict, after: dict, whole: bool = False, files: bool = True) -> list[str]:
    """What differs between two project fingerprints, in words (empty: the same) (pure)."""
    if after.get("missing"):
        return ["the project is missing"]
    out = []
    for p, b in before["core"].items():
        if after["core"].get(p) != b:
            cb, ca = before["counts"].get(p), after["counts"].get(p)
            out.append(f"{p}: {cb} before, {ca} after" if cb != ca else f"{p}: the same count ({ca}), different content")
    if whole:
        for t, b in before["all"].items():
            if t in PROJECT_CORE or t in ("project_models", "key_questions", "canvases", "canvas_items", "documents"):
                continue
            if after["all"].get(t) != b:
                out.append(f"{t} differs")
    if files and "unavailable" not in (before.get("files"), after.get("files")) and before.get("files") != after.get("files"):
        out.append(f"the document files differ ({before.get('file_count')} before, {after.get('file_count')} after)")
    return out


def fingerprint(state: dict) -> dict:
    """{models: [guid], projects: [guid]} -> their fingerprints."""
    from .. import projects as pj
    from ..db import get_engine
    out: dict[str, Any] = {"models": {}, "projects": {}}
    with get_engine().begin() as conn:
        for g in state.get("models") or []:
            out["models"][g] = model_fingerprint(conn, g) if g else {"missing": True}
    if state.get("projects"):
        with pj.connections() as pc:
            for g in state["projects"]:
                out["projects"][g] = project_fingerprint(pc, g, files=state.get("files", True)) if g else {"missing": True}
    return out


def compare(state: dict) -> dict:
    """{kind: model|project, before, after, keys|whole}: the differences (for the host, which has no database)."""
    if state.get("kind") == "project":
        return {"differences": compare_projects(state["before"], state["after"], bool(state.get("whole")), state.get("files", True))}
    parts = METAMODEL if state.get("only") == "metamodel" else METAMODEL + CONTENT
    return {"differences": compare_models(state["before"], state["after"], bool(state.get("keys")), parts)}


# ---------------------------------------------------------------- the test's content
def start(state: dict) -> dict:
    """The test's record, account, models, project and content (see the module)."""
    from ..db import get_engine
    engine, repo = store.engine(), get_engine()
    by = state.get("by") or "eax test backup-cases"
    with engine.begin() as conn:
        run_id = store.create_run(conn, by, "eax", ["backup"], state.get("folder", ""), state.get("version", ""), "detailed")
        store.set_state(conn, run_id, state="running", step="backup and restore cases")
        run = dict(conn.execute(text("SELECT id, run_guid::text AS run_guid, started_by FROM tests.test_runs WHERE id = :id"),
                                {"id": run_id}).mappings().first())
    sid = store.short(run["run_guid"])
    say(f"the test's record: self-test run {run_id} ({sid})")
    with repo.begin() as conn:
        tokens = fixtures.accounts(conn, run, by, ROLES, say)
    ids = fixtures.models_and_project(repo, run, by, ROLES, say)
    with engine.begin() as conn:
        store.set_fixture_ids(conn, run_id, ids)
    a = Api(tokens["super-admin"])
    made: list[dict] = []
    m1, m2, proj = ids.get("model", ""), ids.get("other_model", ""), ids.get("project", "")
    rows = [{"name": f"BRC application {i} {sid}", "description": f"Backup case application {i}, with a description"}
            for i in (1, 2, 3)]
    s, out = a.tool("add_entities", {"model": m1, "entity_type": "ApplicationComponent", "rows": rows})
    _ok(made, "three more applications with descriptions", s == 200 and not _err(out), _why(out))
    s, out = a.tool("add_relationships", {"model": m1, "rows": [
        {"relationship_type": "Association", "source": f"BRC application 1 {sid}", "target": "Self-test capability 3",
         "name": "supports"},
        {"relationship_type": "Association", "source": f"BRC application 2 {sid}", "target": "Self-test capability 3"}]})
    _ok(made, "two more relationships, one named", s == 200 and not _err(out), _why(out))
    s, out = a.tool("update_entity", {"model": m1, "entity": f"BRC application 3 {sid}", "tags": ["backup-case", "kept"]})
    _ok(made, "an entity with tags", s == 200 and not _err(out), _why(out))
    s, out = a.tool("commit_my_changes", {"model": m1, "message": f"self_test_{sid} backup cases"})
    _ok(made, "the changes committed", s == 200 and not _err(out), _why(out))
    s, out = a.tool("tag_model", {"model": m1, "name": f"self_test_{sid} before the backups", "description": "backup cases"})
    _ok(made, "a model tag", s == 200 and not _err(out), _why(out))
    s, out = a.tool_confirmed("add_own_kpi", {"model": m1, "name": f"BRC applications {sid}", "kind": "count",
                                              "entity_type": "ApplicationComponent"})
    _ok(made, "a KPI of the model's own", s == 200 and not _err(out), _why(out))
    s, out = a.tool("add_entities", {"model": m2, "entity_type": "Capability", "rows": [{"name": f"BRC child capability {sid}"}]})
    s2, out2 = a.tool("commit_my_changes", {"model": m2, "message": f"self_test_{sid} child"})
    _ok(made, "the child model's own change", s == 200 and not _err(out) and not _err(out2), _err(out) or _why(out2))
    extra: dict[str, Any] = {}
    if proj:
        s, out = a.tool("add_project_step", {"project": proj, "phase": "A", "name": f"BRC step {sid}"})
        _ok(made, "a project step", s == 200 and not _err(out), _why(out))
        s, out = a.tool("save_key_question", {"project": proj, "question": f"BRC key question {sid}?", "asked_by": "Backup cases"})
        if _ok(made, "a key question", s == 200 and not _err(out), _why(out)):
            extra["question"] = str((out or {}).get("id") or (out or {}).get("guid") or "")
        s, out = a.tool("save_stakeholder", {"project": proj, "name": f"BRC stakeholder {sid}"})
        sh = (out or {}).get("id") if isinstance(out, dict) else None
        s2, out2 = a.tool("note_stakeholder_discussion", {"project": proj, "stakeholder": sh or "",
                                                           "html": "<p>Backup cases discussion.</p>", "title": "BRC"})
        _ok(made, "a stakeholder and a discussion", s == 200 and bool(sh) and s2 == 200 and not _err(out2), _why(out2))
        s, out = a.tool("change_business_model_canvas", {"project": proj, "action": "new", "name": f"BRC canvas {sid}"})
        canvas = str((out or {}).get("id") or (out or {}).get("guid") or "") if isinstance(out, dict) else ""
        if _ok(made, "a Business Model Canvas", s == 200 and bool(canvas), _why(out)):
            extra["canvas"] = canvas
            for block, words in (("value_propositions", "Claims settled in a day"), ("customer_segments", "Brokers")):
                s, out = a.tool("change_business_model_canvas", {"project": proj, "action": "add", "canvas": canvas,
                                                                 "block": block, "text": f"{words} {sid}"})
                _ok(made, f"a canvas item in {block}", s == 200 and not _err(out), _why(out))
        s, out = a.tool("add_document_class", {"project": proj, "phase": "A", "name": f"BRC documents {sid}"})
        item = (out or {}).get("id") or (out or {}).get("item") if isinstance(out, dict) else None
        if _ok(made, "a document class", s == 200 and bool(item), _why(out)):
            content = f"Backup cases {sid}: a document whose file is compared by its SHA-256 after each restore.\n".encode()
            s, d = _upload_waiting(a, f"/api/v1/projects/{proj}/items/{item}/documents", f"brc_{sid}.txt", content,
                                   seconds=900, item=item)
            doc = (d or {}).get("id") if isinstance(d, dict) else None
            if _ok(made, "a document with its file", s in (200, 201) and bool(doc), _why(d)):
                extra.update(document=str(doc), document_sha=hashlib.sha256(content).hexdigest())
    saved = _keep_for_the_test()
    return {"run_id": run_id, "sid": sid, "token": tokens["super-admin"], "ids": {**ids, **extra}, "made": made,
            "calls": a.calls, "schedules_saved": saved}


def _keep_for_the_test() -> list[dict]:
    """The schedules as they are (to put back), with the application backups' keep raised for the test."""
    from .. import backup_schedule as bs
    from ..db import get_engine
    with get_engine().begin() as conn:
        rows = [{k: r.get(k) for k in ("kind", "enabled", "cron", "tag", "keep", "warn_after_hours")} for r in bs.get_all(conn)]
        app = next((r for r in rows if r["kind"] == "application"), None)
        if app:
            bs.update(conn, "application", {"keep": min(365, int(app["keep"]) + KEEP_EXTRA)}, "eax test backup-cases")
    return rows


def schedule_reset(state: dict) -> dict:
    """The schedules put back as they were when the test started."""
    from .. import backup_schedule as bs
    from ..db import get_engine
    done = []
    with get_engine().begin() as conn:
        for r in state.get("schedules_saved") or []:
            bs.update(conn, r["kind"], {k: r[k] for k in ("enabled", "cron", "tag", "keep", "warn_after_hours")},
                      "eax test backup-cases")
            done.append(r["kind"])
    return {"reset": done}


def schedule_next(state: dict) -> dict:
    """The application schedule set to run in the coming minute (two minutes when this one is nearly over)."""
    from .. import backup_schedule as bs
    from ..db import get_engine
    with get_engine().begin() as conn:
        tz = bs.zone(conn)
        now = datetime.now(tz)
        at = (now + timedelta(minutes=2 if now.second >= 40 else 1)).replace(second=0, microsecond=0)
        cron = f"{at.minute} {at.hour} {at.day} {at.month} *"
        cur = bs.get(conn, "application")
        bs.update(conn, "application", {"enabled": True, "cron": cron, "tag": state["tag"],
                                        "keep": max(int(cur["keep"]), 1)}, "eax test backup-cases")
    return {"cron": cron, "at": at.isoformat(timespec="minutes"), "zone": str(tz)}


def change_model(state: dict) -> dict:
    """Changes to a model as a person makes them, committed: added, renamed, deleted, related."""
    a, m, sid = Api(state["token"]), state["model"], state["sid"]
    made: list[dict] = []
    s, out = a.tool("add_entities", {"model": m, "entity_type": "ApplicationComponent",
                                     "rows": [{"name": f"BRC added after the backup {sid}"}]})
    _ok(made, "an entity added", s == 200 and not _err(out), _why(out))
    s, out = a.tool("update_entity", {"model": m, "entity": f"BRC application 1 {sid}", "name": f"BRC renamed {sid}",
                                      "description": "changed after the backup"})
    _ok(made, "an entity renamed with a new description", s == 200 and not _err(out), _why(out))
    gone = _entity_guid(m, f"BRC application 2 {sid}")
    s, out = a.rest("delete", f"/api/v1/models/{m}/content/entities/{gone}") if gone else (0, {"error": "not found"})
    _ok(made, "an entity deleted with its relationship", s == 200, _why(out))
    s, out = a.tool("add_relationships", {"model": m, "rows": [
        {"relationship_type": "Association", "source": f"BRC application 3 {sid}", "target": "Self-test capability 1"}]})
    _ok(made, "a relationship added", s == 200 and not _err(out), _why(out))
    s, out = a.tool("commit_my_changes", {"model": m, "message": f"self_test_{sid} changed after the backup"})
    _ok(made, "the changes committed", s == 200, _why(out))
    return {"made": made, "ok": all(x["ok"] for x in made[:-1])}


def _entity_guid(model: str, name: str) -> str:
    from ..db import get_engine
    with get_engine().begin() as conn:
        conn.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
        return str(conn.execute(text("""SELECT e.guid FROM core.entities e JOIN core.models m ON m.id = e.model_id
                                        WHERE m.guid = CAST(:m AS uuid) AND e.name = :n AND NOT e.is_deleted LIMIT 1"""),
                                {"m": model, "n": name}).scalar() or "")


def change_project(state: dict) -> dict:
    """Changes to a project: a step added, the key question removed, a canvas item added."""
    a, p, sid = Api(state["token"]), state["project"], state["sid"]
    made: list[dict] = []
    s, out = a.tool("add_project_step", {"project": p, "phase": "B", "name": f"BRC step added after the backup {sid}"})
    _ok(made, "a step added", s == 200 and not _err(out), _why(out))
    if state.get("canvas"):
        s, out = a.tool("change_business_model_canvas", {"project": p, "action": "add", "canvas": state["canvas"],
                                                         "block": "channels", "text": f"Added after the backup {sid}"})
        _ok(made, "a canvas item added", s == 200 and not _err(out), _why(out))
    s, out = a.tool("save_stakeholder", {"project": p, "name": f"BRC stakeholder added after the backup {sid}"})
    _ok(made, "a stakeholder added", s == 200 and not _err(out), _why(out))
    return {"made": made, "ok": all(x["ok"] for x in made)}


def delete_model(state: dict) -> dict:
    """A model deleted, as on Model admin (its name typed to confirm)."""
    from .. import model_ops as mo
    from ..db import get_engine
    with get_engine().begin() as conn:
        conn.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
        name = conn.execute(text("SELECT name FROM core.models WHERE guid = CAST(:g AS uuid)"), {"g": state["model"]}).scalar()
        mo.delete_model(conn, state["model"], name, state.get("by") or "eax test backup-cases", None)
    return {"deleted": name}


def new_model(state: dict) -> dict:
    """A model made after the backup (it must stay as it is when the backup is restored)."""
    from .. import mcp_build as mb
    from .. import mcp_server  # noqa: F401 - the MCP tools in their order
    from . import fixtures as fx
    me = fx._principal(f"svc-self-test-{state['sid']}-super-admin", (fx.perms.SUPER_ADMIN,))
    m = fx._as(me, mb.create_model(state["name"], start="empty", source="ArchiMate 4", description="backup cases"))
    fx._as(me, mb.add_entities(m["model"], "Capability", [{"name": f"Made after the backup {state['sid']}"}]))
    with store.engine().begin() as tc:
        store.add_fixture(tc, int(state["run_id"]), "model", m["model"], m["name"])
    return {"model": m["model"]}


def forge(state: dict) -> dict:
    """Files that are not good backups, in the uploaded folder, named for the test (see the module)."""
    from .. import backups as bk
    sid = state["sid"]
    folder = bk.app_dir() / "uploaded"
    folder.mkdir(parents=True, exist_ok=True)
    good = (bk.app_dir() / state["good"]).read_bytes() if state.get("good") else b""
    files: dict[str, bytes] = {"not-a-zip": b"this is not a zip file\n" * 20}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("README.txt", "a zip, but not an EA Explorer backup")
    files["no-backup-json"] = buf.getvalue()
    if good:
        files["cut-short"] = good[: len(good) // 2]
        src = zipfile.ZipFile(io.BytesIO(good))
        files["copy"] = good                                  # the same file, brought from elsewhere: it restores
        for case in ("newer", "changed", "old"):
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
                for n in src.namelist():
                    b = src.read(n)
                    if n == "backup.json" and case == "newer":
                        info = json.loads(b)
                        info["version"] = "999.0.0"
                        b = json.dumps(info).encode()
                    if n == "README.txt" and case == "changed":
                        b = b + b"changed after the backup was made\n"
                    if n == "backup.json" and case == "old":             # as made before 14.6: no fingerprint
                        info = json.loads(b)
                        info.pop("files", None)
                        b = json.dumps(info).encode()
                    z.writestr(n, b)
            files[case] = out.getvalue()
    names = {}
    for case, data in files.items():
        name = f"brc-{sid}-{case}{bk.SUFFIX}"
        (folder / name).write_bytes(data)
        names[case] = name
    return {"files": names}


def find(state: dict) -> dict:
    """Models and projects by name: their ids ("" when there is none)."""
    from .. import projects as pj
    from ..db import get_engine
    out: dict[str, dict] = {"models": {}, "projects": {}}
    with get_engine().begin() as conn:
        conn.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
        for n in state.get("models") or []:
            out["models"][n] = str(conn.execute(text("""SELECT guid FROM core.models WHERE lower(name) = lower(:n) AND NOT is_deleted
                                                        ORDER BY id DESC LIMIT 1"""), {"n": n}).scalar() or "")
    with pj.connections() as pc:
        for n in state.get("projects") or []:
            out["projects"][n] = str(pc.execute(text("SELECT guid FROM proj.projects WHERE lower(name) = lower(:n) ORDER BY id DESC LIMIT 1"),
                                                {"n": n}).scalar() or "")
    return out


def register(state: dict) -> dict:
    """Models and projects made by the test's restores, recorded as the test's own (removed by finish); a model restored
    as a root of its own ("<name> metamodel", when its metamodel matches no root here) brings that root with it."""
    from ..db import get_engine
    models = dict(state.get("models") or {})
    if models:
        with get_engine().begin() as conn:
            conn.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
            for r in conn.execute(text("""SELECT s.guid::text AS g, s.name FROM core.models m JOIN core.models s ON s.id = m.source_model_id
                                           WHERE m.guid::text = ANY(:g) AND s.kind_code = 'template' AND s.name LIKE :n"""),
                                  {"g": [g for g in models if g], "n": f"self\\_test\\_{state['sid']}\\_%"}).mappings():
                models[r["g"]] = r["name"]
    state = {**state, "models": models}
    with store.engine().begin() as tc:
        for kind in ("model", "project"):
            for ident, name in (state.get(kind + "s") or {}).items():
                if ident:
                    store.add_fixture(tc, int(state["run_id"]), kind, ident, name)
                    if kind == "project":
                        from .. import projects as pj
                        with pj.connections() as pc:
                            pc.execute(text("UPDATE proj.projects SET is_test_data = true WHERE guid::text = :g"), {"g": ident})
    return {"registered": True}


GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def files_of(state: dict) -> dict:
    """The test's own backups, and nothing else (to remove at the end): the application backups whose tag starts with
    the test's prefix; the backup folders of the test's own models and projects (by guid, never an empty or other name);
    of a model it shares with everyone (the root metamodel) only the files whose name holds the prefix; the forged files."""
    from .. import backups as bk
    from .. import project_backup as pb
    prefix = str(state.get("prefix") or "")
    if not re.fullmatch(r"brc-[A-Za-z0-9]{4,}", prefix):
        raise ValueError("files_of needs the test's prefix (brc-<id>)")
    own = [str(g) for g in state.get("models") or [] if GUID.match(str(g))]
    shared = [str(g) for g in state.get("shared_models") or [] if GUID.match(str(g))]
    projects = [str(g) for g in state.get("projects") or [] if GUID.match(str(g))]
    up = bk.app_dir() / "uploaded"
    shared_files = []
    for g in shared:
        d = bk.app_dir() / "models" / g
        if d.is_dir():
            shared_files += [f"{g}/{f.name}" for f in d.iterdir() if f.is_file() and prefix in f.name]
    return {"runs": [r["name"] for r in bk.list_application()["runs"] if str(r.get("tag") or "").startswith(prefix)],
            "models": [g for g in own if (bk.app_dir() / "models" / g).is_dir()],
            "shared": shared_files,
            "projects": [g for g in projects if (pb.folder() / g).is_dir()],
            "uploaded": sorted(f.name for f in up.glob(f"{prefix}-*")) if up.is_dir() else []}


def remove_files(state: dict) -> dict:
    """The test's own backups removed: only what files_of names."""
    import shutil

    from .. import backups as bk
    from .. import project_backup as pb
    found = files_of(state)
    for r in found["runs"]:
        shutil.rmtree(bk.app_dir() / r, ignore_errors=True)
    for g in found["models"]:
        shutil.rmtree(bk.app_dir() / "models" / g, ignore_errors=True)
    for f in found["shared"]:
        (bk.app_dir() / "models" / f).unlink(missing_ok=True)
    for g in found["projects"]:
        shutil.rmtree(pb.folder() / g, ignore_errors=True)
    for n in found["uploaded"]:
        (bk.app_dir() / "uploaded" / n).unlink(missing_ok=True)
    return {"removed": found}


def others(state: dict) -> dict:
    """Every backup file that is not the test's (not under its prefix, not of its models or projects), with its size:
    taken at the start and the end, the two must be the same (the test touches no one else's backups, D971)."""
    from .. import backups as bk
    prefix = str(state.get("prefix") or "")
    mine = [str(g) for g in (state.get("models") or []) + (state.get("projects") or []) if GUID.match(str(g))]
    out = []
    root = bk.root()
    if root.is_dir():
        for f in sorted(root.rglob("*")):
            rel = f.relative_to(root).as_posix()
            if not f.is_file() or rel.startswith("restores/") or (prefix and prefix in rel) or any(g in rel for g in mine):
                continue
            out.append(f"{rel}:{f.stat().st_size}")
    return {"files": out}


def runs(state: dict) -> dict:
    """The application backups whose tag starts with the prefix: name, tag, status and when made (newest first)."""
    from .. import backups as bk
    return {"runs": [{"name": r["name"], "tag": r.get("tag"), "status": r.get("status"), "created": r.get("created"),
                      "checked": (r.get("checked") or {}).get("ok"),
                      "models": [{"id": m.get("id"), "file": m.get("file"), "status": m.get("status")} for m in r.get("models") or []],
                      "projects": [{"id": x.get("id"), "file": x.get("file"), "status": x.get("status")} for x in r.get("projects") or []]}
                     for r in bk.list_application()["runs"] if str(r.get("tag") or "").startswith(state["prefix"])]}


def finish(state: dict) -> dict:
    """The results on the test's record, the schedules put back, the test's data removed, the record closed."""
    from ..db import get_engine
    out: dict[str, Any] = {}
    try:
        out["schedules"] = schedule_reset(state)
    except Exception as exc:  # noqa: BLE001 - said in the report
        out["schedules_error"] = str(exc)[:300]
    run_id = int(state["run_id"])
    with store.engine().begin() as conn:
        for r in state.get("results") or []:
            store.add_result(conn, run_id, "backup", f"backup cases: {r['name']}",
                             "passed" if r.get("ok") else "skipped" if r.get("ok") is None else "failed", r.get("detail", ""),
                             int(r.get("ms") or 0))
        store.finish(conn, run_id, error=state.get("error", ""))
    if state.get("keep"):
        return {**out, "kept": True}
    try:
        out["files"] = remove_files(state)
    except Exception as exc:  # noqa: BLE001
        out["files_error"] = str(exc)[:300]
    try:
        with get_engine().begin() as conn:
            res = fixtures.purge(conn, run_id, "eax test backup-cases")
        out["removed"] = {k: v for k, v in res.items() if isinstance(v, int)}
    except Exception as exc:  # noqa: BLE001 - the next self-test run removes what is left
        out["purge_error"] = str(exc)[:300]
    return out


COMMANDS = {"start": start, "fingerprint": fingerprint, "compare": compare, "change_model": change_model,
            "change_project": change_project, "delete_model": delete_model, "new_model": new_model, "forge": forge,
            "find": find, "register": register, "schedule_next": schedule_next, "schedule_reset": schedule_reset,
            "files_of": files_of, "runs": runs, "others": others, "finish": finish}


def main(argv: list[str]) -> int:
    """python -m eax.testing.backup_cases <command> (the state as JSON on standard input)."""
    cmd = argv[0] if argv else ""
    if cmd not in COMMANDS:
        print(json.dumps({"error": f"one of {', '.join(COMMANDS)}"}))
        return 2
    try:
        raw = sys.stdin.read() if not sys.stdin.isatty() else ""
        out = COMMANDS[cmd](json.loads(raw) if raw.strip() else {})
    except Exception as exc:  # noqa: BLE001 - said to the test, which records it and goes on
        out = {"error": f"{type(exc).__name__}: {exc}"[:1000]}
    out["at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(json.dumps(out, default=str), flush=True)
    return 1 if out.get("error") else 0


if __name__ == "__main__":
    t0 = time.time()
    sys.exit(main(sys.argv[1:]))
