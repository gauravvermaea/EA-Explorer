"""Brings the built-in views (VP-01 to VP-49) and the report audiences in line with eax/report_defs.py
(build phase 8.2, D161). Run by the seed on every start as the installer's login; idempotent. An
organisation's own views (not built in) are left alone.
"""

from __future__ import annotations

import json

from ..report_defs import AUDIENCES, REPORTS, VIEWS


def _lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "ARRAY[" + ", ".join(_lit(x) for x in v) + "]::text[]" if v else "'{}'::text[]"
    return "'" + str(v).replace("'", "''") + "'"


def catalog_sql() -> str:
    """The report catalogue (audiences, views, reports) as SQL to load."""
    out = ["SELECT set_config('eax.actor', 'system:seed', true);\n"]
    rows = [f"({_lit(c)}, {_lit(n)}, {_lit(g)}, {i})" for i, (c, n, g) in enumerate(AUDIENCES, 1)]
    out.append("INSERT INTO core.report_audiences (code, name, audience_group, sort_order) VALUES\n    "
               + ",\n    ".join(rows) + "\nON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, "
               "audience_group = EXCLUDED.audience_group, sort_order = EXCLUDED.sort_order;\n")
    out.append("DELETE FROM core.report_audiences WHERE code NOT IN (" + ", ".join(_lit(c) for c, _n, _g in AUDIENCES) + ");\n")
    for i, v in enumerate(VIEWS, 1):
        out.append(
            "INSERT INTO core.viewpoints (code, name, category, purpose, concerns, stakeholders, element_types, relationship_types,"
            " heat_attribute, audiences, is_builtin, source, sort_order, default_view, togaf_artifact) VALUES ("
            + ", ".join(_lit(x) for x in (v["code"], v["name"], v["category"], v["purpose"], v["concerns"], v["stakeholders"],
                                          v["element_types"], v["relationship_types"], v["heat_attribute"], v["audiences"],
                                          True, v["source"], i, v["default_view"], v["togaf_artifact"]))
            + ") ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, category = EXCLUDED.category, purpose = EXCLUDED.purpose,"
              " concerns = EXCLUDED.concerns, stakeholders = EXCLUDED.stakeholders, element_types = EXCLUDED.element_types,"
              " relationship_types = EXCLUDED.relationship_types, heat_attribute = EXCLUDED.heat_attribute,"
              " audiences = EXCLUDED.audiences, is_builtin = true, source = EXCLUDED.source, sort_order = EXCLUDED.sort_order,"
              " default_view = EXCLUDED.default_view, togaf_artifact = EXCLUDED.togaf_artifact, modified_at = now()"
              # only when something changed (the backup and restore test, 16 Nov 2026: every start stamped every built-in
              # view as modified, so a restored installation never looked like its backup)
              " WHERE (core.viewpoints.name, core.viewpoints.category, core.viewpoints.purpose, core.viewpoints.concerns,"
              " core.viewpoints.stakeholders, core.viewpoints.element_types, core.viewpoints.relationship_types,"
              " core.viewpoints.heat_attribute, core.viewpoints.audiences, core.viewpoints.is_builtin, core.viewpoints.source,"
              " core.viewpoints.sort_order, core.viewpoints.default_view, core.viewpoints.togaf_artifact)"
              " IS DISTINCT FROM (EXCLUDED.name, EXCLUDED.category, EXCLUDED.purpose, EXCLUDED.concerns, EXCLUDED.stakeholders,"
              " EXCLUDED.element_types, EXCLUDED.relationship_types, EXCLUDED.heat_attribute, EXCLUDED.audiences, true,"
              " EXCLUDED.source, EXCLUDED.sort_order, EXCLUDED.default_view, EXCLUDED.togaf_artifact);\n")
    out.append("DELETE FROM core.viewpoints WHERE is_builtin AND code NOT IN ("
               + ", ".join(_lit(v["code"]) for v in VIEWS) + ");\n")
    links = sorted({(r["code"], a) for r in REPORTS for a in r["audiences"]})
    out.append("DELETE FROM core.report_audience_links;\n")
    out.append("INSERT INTO core.report_audience_links (report_code, audience_code) VALUES\n    "
               + ",\n    ".join(f"({_lit(r)}, {_lit(a)})" for r, a in links) + ";\n")
    return "".join(out)


def catalog_summary() -> str:
    """How many views, audiences and reports the catalogue has."""
    return json.dumps({"views": len(VIEWS), "audiences": len(AUDIENCES), "reports": len(REPORTS)})
