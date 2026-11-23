"""A project's risk register (Release 12, R12.5; D879, D887; TOGAF Series Guide: Integrating Risk and Security within a
TOGAF Enterprise Architecture, G152).

No new type and no new table for risks (D887: "Risk register = governance log Risk records linked to Assessments"):
* the **risk in the architecture** is an Assessment in one of the project's models, its Assessment Kind "Risk", with
  its likelihood, impact, inherent risk, treatment and residual risk (attributes on the existing type), the controls
  that reduce it (Control elements that influence it) and the elements it bears on (its other relationships);
* the **risk in the project's governance** is a Risk record of its Governance log, with its status, owner, review date
  and approval, linked to the Assessment it describes (a link of the existing kind "element", relation "describes")
  and to the elements it affects.

The register reads both: each Risk record with the Assessments it describes, and each risk Assessment in the
project's models that no record describes yet ("not in the log"), which can be logged in one step. Rules here (D248).
"""

from __future__ import annotations

from typing import Any

from . import decisions as dec
from . import governance as gv
from . import projects as pj
from .metamodel_edit import EditError

RISK = "Risk"
DESCRIBES = "describes"
VALUES = ("AssessmentKind", "Likelihood", "Impact", "InherentRisk", "RiskTreatment", "ResidualRisk", "Owner")
LEVELS = {"High": 3, "Medium": 2, "Low": 1}

_rows, _one = pj._rows, pj._one


def _models(pc, p: dict) -> list[str]:
    return [r["g"] for r in _rows(pc, "SELECT model_guid::text AS g FROM proj.project_models WHERE project_id = :p", p=p["id"])]


def assessments(cc, models: list[str]) -> list[dict]:
    """The risk Assessments in the models (Assessment Kind Risk), each with its values, its controls and what it bears on."""
    if not models:
        return []
    rows = _rows(cc, f"""
        SELECT e.id AS _id, e.guid::text AS id, e.name, e.display_id, m.guid::text AS model, m.name AS model_name,
               {", ".join(f"max(coalesce(v.value_text, v.value_number::text)) FILTER (WHERE a.code = '{c}') AS \"{c}\"" for c in VALUES)}
          FROM core.entities e JOIN core.entity_types t ON t.id = e.entity_type_id AND t.code = 'Assessment'
          JOIN core.models m ON m.id = e.model_id AND NOT m.is_deleted
          LEFT JOIN core.attribute_values v ON v.entity_id = e.id AND NOT v.is_deleted
          LEFT JOIN core.attribute_types a ON a.id = v.attribute_type_id
         WHERE NOT e.is_deleted AND m.guid = ANY (CAST(:ms AS uuid[]))
         GROUP BY e.id, e.guid, e.name, e.display_id, m.guid, m.name
         ORDER BY m.name, e.name""", ms=models)
    rows = [r for r in rows if (r.get("AssessmentKind") or "") == RISK]
    if not rows:
        return []
    near = _rows(cc, """
        SELECT CASE WHEN r.target_entity_id = ANY (CAST(:ids AS bigint[])) THEN r.target_entity_id ELSE r.source_entity_id END AS a,
               o.guid::text AS id, o.name, ot.code AS type, rt.code AS rel,
               (r.target_entity_id = ANY (CAST(:ids AS bigint[]))) AS incoming
          FROM core.relationships r JOIN core.relationship_types rt ON rt.id = r.relationship_type_id
          JOIN core.entities o ON o.id = CASE WHEN r.target_entity_id = ANY (CAST(:ids AS bigint[])) THEN r.source_entity_id ELSE r.target_entity_id END
          JOIN core.entity_types ot ON ot.id = o.entity_type_id
         WHERE NOT r.is_deleted AND NOT o.is_deleted
           AND (r.target_entity_id = ANY (CAST(:ids AS bigint[])) OR r.source_entity_id = ANY (CAST(:ids AS bigint[])))""",
                 ids=[r["_id"] for r in rows])
    for r in rows:
        mine = [n for n in near if n["a"] == r["_id"]]
        r["controls"] = [{"id": n["id"], "name": n["name"]} for n in mine if n["type"] == "Control"]
        r["bears_on"] = [{"id": n["id"], "name": n["name"], "type": n["type"]} for n in mine if n["type"] not in ("Control", "Assessment")]
        r.pop("_id")
        for k in ("Likelihood", "Impact"):
            try:
                r[k] = int(float(r[k])) if r.get(k) not in (None, "") else None
            except (TypeError, ValueError):
                r[k] = None
        r["score"] = r["Likelihood"] * r["Impact"] if r["Likelihood"] and r["Impact"] else None
    return rows


def register(pc, project: Any, user) -> dict:
    """The project's risk register: its Risk records with the Assessments they describe, and the risk Assessments of its
    models not in the log yet. Ordered by the residual risk, then the score."""
    p = pj.project_row(pc, project)
    pj._need(pc, p, user, "read")
    found = {a["id"]: a for a in assessments(pj.core(pc), _models(pc, p))}
    recs = _rows(pc, """SELECT g.id AS _id, g.guid::text AS id, g.ref, g.title, g.status, g.owner, g.expires_on, g.approval
                          FROM proj.gov_records g WHERE g.project_id = :p AND g.kind = :k ORDER BY g.ref""", p=p["id"], k=RISK)
    links = _rows(pc, """SELECT l.record_id, l.relation, l.target, l.label FROM proj.gov_links l
                          JOIN proj.gov_records g ON g.id = l.record_id
                         WHERE g.project_id = :p AND g.kind = :k AND l.link_kind = 'element'""", p=p["id"], k=RISK)
    described = set()
    entries = []
    for r in recs:
        mine = [x for x in links if x["record_id"] == r["_id"]]
        about = [found[x["target"]] for x in mine if x["relation"] == DESCRIBES and x["target"] in found]
        gone = [x["label"] for x in mine if x["relation"] == DESCRIBES and x["target"] not in found]
        described.update(a["id"] for a in about)
        r.pop("_id")
        r["expires_on"] = str(r["expires_on"])[:10] if r.get("expires_on") else ""
        entries.append({"record": r, "assessments": about, "missing": gone,
                        "affects": [x["label"] for x in mine if x["relation"] != DESCRIBES]})
    loose = [a for a in found.values() if a["id"] not in described]

    def rank(e: dict) -> tuple:
        a = (e.get("assessments") or [e.get("assessment") or {}])
        worst = max((LEVELS.get((x or {}).get("ResidualRisk") or "", 0) for x in a), default=0)
        score = max(((x or {}).get("score") or 0 for x in a), default=0)
        return (-worst, -score)
    entries.sort(key=rank)
    loose.sort(key=lambda a: rank({"assessment": a}))
    return {"entries": entries, "not_logged": loose, "models": len(_models(pc, p)),
            "high": sum(1 for a in found.values() if a.get("ResidualRisk") == "High"),
            "no_control": sum(1 for a in found.values() if not a["controls"]),
            "may_log": gv._may(pc, p, user)}


def log(pc, project: Any, user, d: dict) -> dict:
    """Logs a risk Assessment of the project's models in the Governance log: a Risk record with its name and owner,
    linked to it ("describes"). Refused when a record describes it already."""
    p = pj.project_row(pc, project)
    pj._need(pc, p, user, "contribute")
    model, element = str(d.get("model") or ""), str(d.get("element") or "")
    if model not in _models(pc, p):
        raise EditError("That model is not one of the project's.", 404)
    a = {x["id"]: x for x in assessments(pj.core(pc), [model])}.get(element)
    if not a:
        raise EditError("No such risk in that model: an Assessment whose Assessment Kind is Risk.", 404)
    if _one(pc, """SELECT 1 AS x FROM proj.gov_links l JOIN proj.gov_records g ON g.id = l.record_id
                    WHERE g.project_id = :p AND g.kind = :k AND l.link_kind = 'element' AND l.relation = :rel AND l.target = :t""",
            p=p["id"], k=RISK, rel=DESCRIBES, t=element):
        raise EditError(f"{a['name']} is in the Governance log already.", 409)
    made = gv.add(pc, project, user, {"kind": RISK, "title": a["name"], "owner": a.get("Owner") or "",
                                       "related": f"{a['model_name']}: {a['name']}"})
    dec.add_link(pc, user, made["id"], {"kind": "element", "relation": DESCRIBES, "target": element, "model": model})
    return {"id": made["id"], "ref": made["ref"], "message": f"{made['ref']} {a['name']} is in the Governance log, a draft."}


def describe(pc, project: Any, user, rid: str, d: dict) -> dict:
    """Links an existing Risk record to the Assessment it describes."""
    r, p = dec.record(pc, user, rid, write=True)
    if r["kind"] != RISK:
        raise EditError("Only a Risk record describes a risk in the architecture.", 409)
    if str(p.get("guid")) != str(pj.project_row(pc, project)["guid"]):
        raise EditError("That record is not this project's.", 404)
    model, element = str(d.get("model") or ""), str(d.get("element") or "")
    if model not in _models(pc, p) or element not in {x["id"] for x in assessments(pj.core(pc), [model])}:
        raise EditError("No such risk in the project's models: an Assessment whose Assessment Kind is Risk.", 404)
    return dec.add_link(pc, user, rid, {"kind": "element", "relation": DESCRIBES, "target": element, "model": model})


def count(pc, p: dict) -> int:
    """The project's Risk records (for the page)."""
    return int((_one(pc, "SELECT count(*) AS n FROM proj.gov_records WHERE project_id = :p AND kind = :k", p=p["id"], k=RISK) or {}).get("n") or 0)

