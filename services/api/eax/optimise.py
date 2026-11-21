"""The optimisation report (R5.1; owner, 14 Nov 2026: "measure the platform and suggest optimizations to the user in a
report"; 15 Nov 2026, D697: unused is "not opened or changed in last 180 days. This limit should be configurable";
history before a tag: "Ask what to do"; nothing applied on a schedule without a yes; on screen and as Excel; "all
suggestions are for the entire model/project, so you wont ask one at a time for each").

EA Explorer measures itself and writes a report of suggestions, each with its evidence, what it saves, its risk, how to
undo it and, where it may be applied from the screen, an Apply: **nothing is changed without a person's yes**, and
each suggestion is for a whole model or project (never item by item). Monthly (the 1st, 02:30) and on demand (System
Admin > Optimisation, `eax optimise`); the newest report kept with the ones before, compared; the Super Admins and IT
Admins told when a new one has suggestions. Looked at:
  server     memory and CPU over the last four weeks (the resource history, R3.5-M8): containers near or far below
             their limit, the server short of memory, the API and job servers' count
  unused     models and projects not opened or changed for optimise_unused_days (180): archive them (a background
             task, the Archive page's own; its admins bring it back)
  disk       old self-test runs, log backups and the Docker build cache and dangling images left by updates
  history    a model's history before its last tag: the Model Admin is asked what to do: condense (one version per
             item as at each tag kept) or remove (only the state at the last tag kept); the tag and everything after
             always stay, and so does what governance records and drawn-view evidence need (D445)
  database   the database check's findings (R5.12): swollen tables, unused indexes, the cache
Applying: archive (Model or Project Admin, or Super Admin), history (the model's Model Admin or a Super Admin), the
others by a Super Admin. Every apply is audited; the archive keeps a backup of what it moves.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime

from sqlalchemy import text

from . import permissions as P

AREAS = ("server", "unused", "disk", "history", "database")
LINK = "#/admin/optimisation"


def suggestion(area: str, key: str, title: str, evidence: str, saves: str = "", risk: str = "low", undo: str = "",
               apply: str = "", params: dict | None = None, who: str = "super-admin", choices: list[str] | None = None,
               people: dict | None = None) -> dict:
    """One suggestion. people (owner, 15 Nov 2026: "5.1 report should have names of Admins, creators etc"): for a model
    or project, who made it and who looks after it, so the report says whom to ask."""
    return {"area": area, "key": key, "title": title, "evidence": evidence, "saves": saves, "risk": risk, "undo": undo,
            "apply": apply, "params": params or {}, "who": who, "choices": choices or [], "people": people or {}}


def model_people(conn, model: str) -> dict:
    """A model's creator and its Model Admins and Model Sub Admins, by name."""
    row = conn.execute(text("SELECT id, created_by FROM core.models WHERE guid = CAST(:g AS uuid)"), {"g": model}).first()
    if not row:
        return {}
    roles: dict[str, list[str]] = {}
    for r in conn.execute(text("""SELECT role, username FROM core.model_users WHERE model_id = :m
                                    AND role IN ('model-admin', 'model-sub-admin') ORDER BY role, username"""), {"m": row[0]}):
        roles.setdefault(r[0], []).append(r[1])
    return {"created by": row[1], "Model Admins": roles.get("model-admin", []), "Model Sub Admins": roles.get("model-sub-admin", [])}


def project_people(project: str) -> dict:
    """A project's creator and its Project Admins and Lead Architects, by name (the projects' own database)."""
    try:
        from . import projects as pj
        with pj.connections(write=False) as pc:
            row = pc.execute(text("SELECT id, created_by FROM proj.projects WHERE guid = CAST(:g AS uuid)"), {"g": project}).first()
            if not row:
                return {}
            roles: dict[str, list[str]] = {}
            for r in pc.execute(text("""SELECT role, username FROM proj.members WHERE project_id = :p
                                          AND role IN ('project-admin', 'lead-architect') ORDER BY role, username"""), {"p": row[0]}):
                roles.setdefault(r[0], []).append(r[1])
    except Exception:  # noqa: BLE001 - projects switched off
        return {}
    return {"created by": row[1], "Project Admins": roles.get("project-admin", []), "Lead Architects": roles.get("lead-architect", [])}


def people_text(people: dict) -> str:
    """The people of a suggestion in one line (who made it, who looks after it)."""
    return "; ".join(f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in (people or {}).items() if v)


def _iso(v):
    return v.isoformat(timespec="seconds") if hasattr(v, "isoformat") else v


# ---------------------------------------------------------------- measuring
def server(conn, days: int = 28) -> list[dict]:
    """Suggestions about the server from four weeks of resource history: containers' memory limits, the host's memory,
    the API's copies."""
    from . import databases, resources
    out: list[dict] = []
    try:
        on = databases.on("operations", conn)
        rows = [dict(r) for r in on.execute(text(f"SELECT * FROM {resources.TABLE} WHERE at > now() - make_interval(days => :d) ORDER BY at"),
                                            {"d": days}).mappings()]
    except Exception:  # noqa: BLE001 - no resource history yet
        rows = []
    if not rows:
        return [suggestion("server", "no-history", "No resource history yet",
                           "Memory and CPU are sampled every 15 minutes (System Admin > Footprint); suggestions about the server "
                           "come once there are a few days of it.", risk="none")]
    m = resources.merge(rows)
    for c in m.get("containers") or []:
        peak, limit = c.get("memory_peak_mb"), c.get("memory_limit_mb")
        if not peak or not limit:
            continue
        if peak > 0.9 * limit:
            out.append(suggestion("server", f"limit-{c['container']}", f"Give {c['container']} more memory",
                                  f"its peak was {peak:.0f} MB of a {limit:.0f} MB limit over {days} days",
                                  "fewer restarts and slow answers", "low", "set the limit back", "", {"container": c["container"]}))
        elif peak < 0.4 * limit and limit - peak > 256:
            out.append(suggestion("server", f"limit-{c['container']}", f"{c['container']} needs less memory than it is given",
                                  f"its peak was {peak:.0f} MB of a {limit:.0f} MB limit over {days} days",
                                  f"about {limit - max(peak * 1.5, peak + 128):.0f} MB of the server's memory", "low",
                                  "set the limit back", "", {"container": c["container"]}))
    host = m.get("host") or {}
    total, least = host.get("total_mb"), host.get("least_available_mb")
    if total and least is not None and least < 0.1 * total:
        out.append(suggestion("server", "host-memory", "The server ran short of memory",
                              f"at its lowest {least:.0f} MB of {total:.0f} MB was free; swap used up to {host.get('most_swap_used_mb', 0):.0f} MB",
                              "steady answers under load", "none", "", "", {}, "it-admin"))
    cpus = [c.get("cpu_peak_percent") or 0 for c in m.get("containers") or [] if c.get("container", "").startswith("api")]
    if cpus and max(cpus) > 85:
        out.append(suggestion("server", "api-servers", "Run one more API and job server",
                              f"the API's CPU peaked at {max(cpus):.0f}%", "faster answers at busy times", "low",
                              "back to the number before (System Admin > Scaling)", "scale", {"add": 1}))
    return out


def unused(conn, days: int) -> list[dict]:
    """Models and projects not opened or changed for `days`: archive each whole, with who made and looks after it."""
    from .mcp_operations import unused as find
    found = find(conn, days)
    out = []
    for mdl in found["models"]:
        if mdl.get("last_changed") and str(mdl["last_changed"])[:10] >= found["since"]:
            continue                                  # changed lately though not opened: still in use (D697)
        blocked = "; ".join(mdl.get("blocking") or [])
        out.append(suggestion("unused", f"model-{mdl['id']}", f"Archive the model {mdl['name']}",
                              f"not opened or changed for {days} days (last used {mdl.get('last_used') or 'never'}, last changed "
                              f"{mdl.get('last_changed') or 'never'}; {mdl.get('entities', 0)} elements)" + (f"; cannot move while {blocked}" if blocked else ""),
                              "space in the working database; shorter lists", "low", "bring it back from the Archive page",
                              "" if blocked else "archive-model", {"model": mdl["id"], "name": mdl["name"]}, "model-admins",
                              people=model_people(conn, mdl["id"])))
    for p in found["projects"]:
        out.append(suggestion("unused", f"project-{p['id']}", f"Archive the project {p['name']}",
                              f"not changed for {days} days (last changed {p.get('last_changed')}; {p.get('status')})",
                              "space in the working database; shorter lists", "low", "bring it back from the Archive page",
                              "archive-project", {"project": p["id"], "name": p["name"]}, "project-admins",
                              people=project_people(p["id"])))
    return out


def disk(conn) -> list[dict]:
    """Suggestions about disk: old self-test runs, Docker's build cache and unused images."""
    out = []
    try:
        from .testing import cleanup, store
        with store.engine().connect() as t:
            old = cleanup.pick(t, older_than_days=30)
        if old:
            out.append(suggestion("disk", "self-test-runs", f"Delete {len(old)} self-test runs older than 30 days",
                                  "their test data, results, screenshots, videos and reports",
                                  "disk space", "low", "none: they are deleted (newer runs stay)", "selftest-cleanup", {"days": 30}))
    except Exception:  # noqa: BLE001
        pass
    try:
        from .mcp_operations import helper
        df = helper("GET", "/docker/space", timeout=150)
        mb = float(df.get("build_cache_mb") or 0) + float(df.get("dangling_mb") or 0)
        if mb > 1024:
            out.append(suggestion("disk", "docker-cache", "Clear Docker's build cache and unused images",
                                  f"{float(df.get('build_cache_mb') or 0) / 1024:.1f} GB of build cache and {df.get('dangling_images', 0)} images "
                                  "nothing uses, left by earlier updates", f"about {mb / 1024:.1f} GB",
                                  "low", "none needed: the next build makes what it needs", "docker-prune", {}))
    except Exception:  # noqa: BLE001
        pass
    return out


def history(conn) -> list[dict]:
    """Models with history from before their last tag, biggest first: the Model Admin is asked what to do."""
    rows = [dict(r) for r in conn.execute(text("""
        SELECT m.guid::text AS model, m.name, t.at AS tag_at, t.name AS tag,
               (SELECT count(*) FROM history.row_versions h WHERE h.model_id = m.id AND h.changed_at < t.at) AS before
          FROM core.models m
          JOIN LATERAL (SELECT created_at AS at, name FROM core.model_tags WHERE model_id = m.id ORDER BY created_at DESC LIMIT 1) t ON true
         WHERE NOT m.is_deleted""")).mappings()]
    out = []
    for r in sorted(rows, key=lambda x: -int(x["before"])):
        if int(r["before"]) < 1000:
            continue
        out.append(suggestion("history", f"history-{r['model']}", f"{r['name']}: history from before its tag {r['tag']}",
                              f"{int(r['before']):,} versions recorded before {r['tag_at']:%Y-%m-%d}",
                              "database space; quicker history", "medium: the steps before the tag can no longer be viewed",
                              "none: removed versions cannot come back (the tag and everything after stay)", "history",
                              {"model": r["model"], "name": r["name"], "tag_at": _iso(r["tag_at"])}, "model-admins",
                              ["condense", "remove"], people=model_people(conn, r["model"])))
    return out


def database(conn) -> list[dict]:
    """Suggestions from the last database check: a tidy per database, and findings for IT."""
    from . import dbmaint
    last = dbmaint.last_check(conn)
    if not last:
        return []
    out = []
    by_db: dict[str, list] = {}
    for f in last["findings"]:
        if f["key"] in ("bloat", "stale_stats", "invalid_index", "unused_index", "cache"):
            by_db.setdefault(f["database"], []).append(f)
    for db, fs in by_db.items():
        tidy = [f for f in fs if f["key"] in ("bloat", "stale_stats", "invalid_index")]
        if tidy:
            out.append(suggestion("database", f"tidy-{db}", f"Tidy the database {db}",
                                  "; ".join(f["what"] for f in tidy[:5]) + (f" and {len(tidy) - 5} more" if len(tidy) > 5 else ""),
                                  "space and speed", "low", "none needed", "db-tidy", {"database": db}))
        for f in fs:
            if f["key"] in ("unused_index", "cache"):
                out.append(suggestion("database", f"{f['key']}-{db}-{f.get('target')}", f["what"], f["detail"], "", "low",
                                      "", "", {}, "it-admin"))
    return out


def measure(conn, days: int | None = None) -> dict:
    """Everything measured now: one report of suggestions (an area that cannot be measured says why)."""
    from . import settings as st
    days = int(days or st.values(conn).get("optimise_unused_days") or 180)
    out: list[dict] = []
    for area, fn in (("server", lambda: server(conn)), ("unused", lambda: unused(conn, days)), ("disk", lambda: disk(conn)),
                     ("history", lambda: history(conn)), ("database", lambda: database(conn))):
        try:
            out += fn()
        except Exception as exc:  # noqa: BLE001 - one area that cannot be measured is said, not a failure
            out.append(suggestion(area, f"{area}-unmeasured", f"{area.title()} could not be measured", str(exc)[:200], risk="none"))
    return {"at": datetime.now(UTC).isoformat(timespec="seconds"), "unused_days": days, "suggestions": out}


# ---------------------------------------------------------------- kept and compared
def save(conn, report: dict, by: str) -> int:
    """Keeps a report; returns its id."""
    return conn.execute(text("INSERT INTO core.optimisation_reports (by_whom, report) VALUES (:b, CAST(:r AS jsonb)) RETURNING id"),
                        {"b": by, "r": json.dumps(report, default=str)}).scalar()


def latest(conn, n: int = 2) -> list[dict]:
    """The newest reports (two: this one and the one before)."""
    return [{**dict(r), "at": r["at"].isoformat()} for r in conn.execute(text(
        "SELECT id, at, by_whom, report, applied FROM core.optimisation_reports ORDER BY at DESC LIMIT :n"), {"n": n}).mappings()]


def compare(new: dict, old: dict | None) -> dict:
    """A report against the one before: how many suggestions are new, gone and the same."""
    if not old:
        return {"new": len(new["suggestions"]), "gone": 0, "same": 0}
    a, b = {s["key"] for s in new["suggestions"]}, {s["key"] for s in old["suggestions"]}
    return {"new": len(a - b), "gone": len(b - a), "same": len(a & b)}


# ---------------------------------------------------------------- applying (a person's yes, a whole model or project)
class NotAllowed(Exception):
    """The person may not apply this suggestion."""
    pass


def _model_admin(conn, user, model: str) -> bool:
    return P.SUPER_ADMIN in user.roles or "model-admin" in P.model_roles(conn, user.username, model)


def apply(conn, user, report_id: int, key: str, choice: str = "") -> dict:
    """Applies one suggestion of a report, for a whole model or project, by the person who may decide it; recorded and
    audited."""
    row = conn.execute(text("SELECT report, applied FROM core.optimisation_reports WHERE id = :i"), {"i": report_id}).mappings().first()
    if not row:
        raise ValueError(f"No report {report_id}.")
    s = next((x for x in row["report"]["suggestions"] if x["key"] == key), None)
    if not s or not s["apply"]:
        raise ValueError("That suggestion cannot be applied from here.")
    if key in (row["applied"] or {}):
        raise ValueError("It was applied already.")
    p = s["params"]
    if s["apply"] == "archive-model":
        from . import archive as ar
        from . import repository as repo
        from .mcp_operations import _start_task
        m = repo.get_model(conn, p["model"])
        ar._may_move(conn, user, m, "archived")
        out = _start_task("archive.move", f"Archive {m['name']} (optimisation report)",
                          {"model": str(m["id"]), "state": "archived", "note": "optimisation report"}, "#/archive", user)
    elif s["apply"] == "archive-project":
        from . import project_backup as pb
        from . import projects as pj
        from .mcp_operations import _start_task
        with pj.connections(write=False) as pc:
            pr = pj.project_row(pc, p["project"])
            pb.need_manage(pc, pr, user)
        out = _start_task("archive.project_move", f"Archive {pr['name']} (optimisation report)",
                          {"project": str(pr["guid"]), "state": "archived", "note": "optimisation report"}, "#/archive", user)
    elif s["apply"] == "history":
        if choice not in ("condense", "remove"):
            raise ValueError("Say what to do with the history before the tag: condense or remove.")
        if not _model_admin(conn, user, p["model"]):
            raise NotAllowed("Only the model's Model Admin (or a Super Admin) decides about its history.")
        out = trim_history(conn, p["model"], datetime.fromisoformat(p["tag_at"]), choice, user.username)
    else:
        if P.SUPER_ADMIN not in user.roles:
            raise NotAllowed("Only a Super Admin applies this suggestion.")
        if s["apply"] == "selftest-cleanup":
            from .testing import cleanup, store
            with store.engine().connect() as t:
                ids = [r["id"] for r in cleanup.pick(t, older_than_days=int(p.get("days") or 30))]
            from .mcp_operations import helper
            out = cleanup.delete(store.engine(), ids, user.username,
                                 lambda folders: helper("POST", "/tests/results/delete", {"folders": folders}, timeout=300))
        elif s["apply"] == "docker-prune":
            from .mcp_operations import helper
            out = helper("POST", "/docker/prune", {"by": user.username}, timeout=600)
        elif s["apply"] == "db-tidy":
            from . import dbmaint
            why = dbmaint.busy_reason()
            if why:
                raise ValueError(f"Not now: {why}.")
            found = [f for f in dbmaint.check()["findings"] if f["database"] == p["database"]]
            done = dbmaint.tidy(found)
            dbmaint.record(conn, "tidy", user.username, found, done)
            out = {"actions": done}
        elif s["apply"] == "scale":
            from .mcp_operations import helper
            now = helper("GET", "/servers").get("wanted") or 1
            out = helper("POST", "/servers", {"count": int(now) + int(p.get("add") or 1), "by": user.username}, timeout=60)
        else:
            raise ValueError("Unknown kind of suggestion.")
    applied = dict(row["applied"] or {})
    applied[key] = {"by": user.username, "at": datetime.now(UTC).isoformat(timespec="seconds"), "choice": choice}
    conn.execute(text("UPDATE core.optimisation_reports SET applied = CAST(:a AS jsonb) WHERE id = :i"),
                 {"a": json.dumps(applied), "i": report_id})
    from . import audit
    audit.record(conn, actor=user.username, action="optimise.apply", object_type="optimisation", object_id=key,
                 details={"report": report_id, "title": s["title"], "choice": choice})
    return {"key": key, "applied": True, "result": out}


def trim_history(conn, model: str, tag_at: datetime, choice: str, actor: str) -> dict:
    """A model's history before its last tag condensed (the newest version of each item as at every moment that must
    stay viewable: each tag, baseline, merge base and drawn-view evidence) or removed (only as at the last tag kept).
    What governance records need is never touched (D445). The history guard is lifted only inside this transaction."""
    from .operations import _arr, _pins
    m = conn.execute(text("SELECT id FROM core.models WHERE guid = CAST(:g AS uuid)"), {"g": model}).scalar()
    if m is None:
        raise ValueError("No such model.")
    pm, pt, keep = _pins(conn)
    tags = {t.isoformat() for t in conn.execute(text("SELECT created_at FROM core.model_tags WHERE model_id = :m"), {"m": m}).scalars()}
    mine = [t for mid, t in zip(pm, pt, strict=True) if mid == m and t]
    # condense: as at every tag, baseline and piece of evidence; remove: as at the last tag and the evidence only (D445)
    moments = [tag_at.isoformat()] + [t for t in mine if choice == "condense" or t not in tags]
    keep_sql = """SELECT DISTINCT ON (h.row_guid, k.at) h.id FROM history.row_versions h
                    JOIN unnest(CAST(:moments AS timestamptz[])) AS k(at) ON h.changed_at <= k.at
                   WHERE h.model_id = :m ORDER BY h.row_guid, k.at, h.changed_at DESC, h.id DESC"""
    p = {"m": m, "cut": tag_at, "moments": _arr(moments), "keep": _arr(keep)}
    conn.execute(text("ALTER TABLE history.row_versions DISABLE TRIGGER row_versions_no_change"))
    n = conn.execute(text(f"""DELETE FROM history.row_versions WHERE model_id = :m AND changed_at < :cut
                                AND id NOT IN ({keep_sql}) AND NOT (row_guid::text = ANY (CAST(:keep AS text[])))"""), p).rowcount
    conn.execute(text("ALTER TABLE history.row_versions ENABLE TRIGGER row_versions_no_change"))
    on = conn.execute(text("""SELECT tgenabled FROM pg_trigger WHERE tgname = 'row_versions_no_change'
                                AND tgrelid = 'history.row_versions'::regclass""")).scalar()
    if on != "O":
        raise RuntimeError("The history guard did not come back on: nothing is removed.")
    from . import audit
    audit.record(conn, actor=actor, action=f"optimise.history_{choice}", object_type="model", object_id=model,
                 details={"before": tag_at.isoformat(), "removed": n, "moments_kept": len(moments)})
    return {"removed": n, "choice": choice, "kept_as_at": moments}


# ---------------------------------------------------------------- Excel
def workbook(report: dict, applied: dict | None = None) -> bytes:
    """A report as an Excel workbook, with what was applied and the people of each suggestion."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Suggestions"
    ws.append(["EA Explorer optimisation report", report.get("at")])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([])
    head = ["Area", "Suggestion", "Evidence", "Saves", "Risk", "How to undo", "Who decides", "Applied", "Created by and admins"]
    ws.append(head)
    for c in ws[3]:
        c.font = Font(bold=True)
    for s in report["suggestions"]:
        a = (applied or {}).get(s["key"])
        ws.append([s["area"], s["title"], s["evidence"], s["saves"], s["risk"], s["undo"], s["who"],
                   f"{a['by']} {a['at']}" if a else "", people_text(s.get("people"))])
    for col, w in zip("ABCDEFGHI", (12, 50, 70, 30, 30, 40, 16, 28, 50), strict=True):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def tell(conn, report: dict) -> None:
    """The Super and IT Admins told of a report with suggestions; each Model Admin of what is theirs to decide."""
    real = [s for s in report["suggestions"] if s["risk"] != "none"]
    if not real:
        return
    from . import notify
    from .alerts import people
    notify.create(conn, kind="optimise.report", category="system", title=f"Optimisation report: {len(real)} suggestion(s)",
                  body="See System Admin > Optimisation.", link=LINK, actor="system", recipients=people(conn))
    by_model: dict[str, list[str]] = {}
    for s in real:
        if s["params"].get("model"):
            by_model.setdefault(s["params"]["model"], []).append(s["title"])
    for model, titles in by_model.items():
        admins = list(conn.execute(text("""SELECT u.username FROM core.model_users u JOIN core.models m ON m.id = u.model_id
                                             WHERE m.guid = CAST(:g AS uuid) AND u.role = 'model-admin'"""), {"g": model}).scalars())
        if admins:
            notify.create(conn, kind="optimise.model", category="system", title="Your decision on the optimisation report",
                          body="; ".join(titles), link=LINK, actor="system", recipients=admins, needs_action=True)


def main(argv: list[str]) -> None:
    """python -m eax.optimise [report|last]: measure now (kept) or the newest report, printed."""
    from .db import get_engine
    with get_engine().begin() as conn:
        if argv[:1] == ["last"]:
            got = latest(conn, 1)
            if not got:
                print("No report yet: eax optimise measures now.")
                return
            r, rid = got[0]["report"], got[0]["id"]
        else:
            r = measure(conn)
            rid = save(conn, r, "eax optimise")
    for s in r["suggestions"]:
        print(f"[{s['area']:8}] {s['title']}: {s['evidence']}" + (f" (saves {s['saves']})" if s["saves"] else "")
              + (f" [{people_text(s.get('people'))}]" if s.get("people") else ""))
    print(f"Report {rid}: {len(r['suggestions'])} suggestion(s). Apply them on System Admin > Optimisation (nothing is changed here).")


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])             # ending normally is exit code 0
