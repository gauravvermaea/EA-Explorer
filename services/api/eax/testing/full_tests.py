"""The full tests' summaries kept, and the detailed files deleted while the summaries stay (D825; owner, 21 Nov 2026:
"Please add them in one summary page for anyone to check. We also need the ability to only keep summary in a DB table
or something and delete detailed result files form UI or command line").

  save()    the summary eax test full wrote (work/tests/full-<time>/summary.json) kept as a row of tests.full_tests
  listing() the newest full tests, each with its steps' outcomes; get() one with its whole summary
  prune()   the detailed files deleted, the summaries kept: a self-test run's folder in work/tests (its report, log,
            videos and the scanners' reports) and its screenshots in the database; a full test's steps' folders (its
            self-test run's, SonarQube's, the backup and restore test's, the dev check's log). What stays: every run's
            row with its counts and summary (tests.test_runs.summary), its results' names, outcomes and reasons, every
            full test's row and its summary page (work/tests/full-<time>/index.html). A run still going is left.

Deleting a run for good (cleanup.py, R2.43) is unchanged: that removes the summary too."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text

from . import store

FOLDER = re.compile(r"^full-[A-Za-z0-9._-]{1,70}$")
ITEM = re.compile(r"^[A-Za-z0-9._-]{1,120}$")          # a folder or file directly under work/tests
STEP_KEYS = ("title", "passed", "why", "kind")


def clean(summary: dict) -> dict:
    """The summary as kept: its folder checked, the folders of its detailed files plain names under work/tests."""
    if not isinstance(summary, dict) or not FOLDER.match(str(summary.get("folder") or "")):
        raise ValueError("Not a full test's summary: its folder must be full-<time>.")
    summary = dict(summary)
    summary["details"] = [d for d in (summary.get("details") or []) if isinstance(d, str) and ITEM.match(d)
                          and not d.startswith("full-")]
    return summary


def save(conn, summary: dict) -> int:
    """Kept as a row of tests.full_tests (again: the same folder's row is replaced); its id."""
    s = clean(summary)
    run = s.get("selftest") or {}
    row = conn.execute(text("""
        INSERT INTO tests.full_tests (folder, started_by, version, passed, run_id, summary, started_at, finished_at)
        VALUES (:folder, :by, :version, :passed, :run, CAST(:s AS jsonb), CAST(:started AS timestamptz),
                coalesce(CAST(:finished AS timestamptz), now()))
        ON CONFLICT (folder) DO UPDATE SET passed = EXCLUDED.passed, run_id = EXCLUDED.run_id, summary = EXCLUDED.summary,
               finished_at = EXCLUDED.finished_at
        RETURNING id"""), {
        "folder": s["folder"], "by": str(s.get("by") or "")[:200], "version": str(s.get("version") or "")[:40],
        "passed": bool(s.get("passed")), "run": int(run["run"]) if str(run.get("run") or "").isdigit() else None,
        "s": json.dumps(s, default=str), "started": s.get("started_at") or None, "finished": s.get("finished_at") or None,
    }).scalar()
    return int(row)


def _row(r) -> dict[str, Any]:
    d = dict(r)
    for k in ("started_at", "finished_at", "files_deleted_at"):
        d[k] = d[k].isoformat() if d.get(k) is not None else None
    return d


def listing(conn, limit: int = 30) -> list[dict[str, Any]]:
    """The newest full tests: each step's title and outcome (the whole summary with get())."""
    rows = conn.execute(text("""
        SELECT id, folder, started_by, version, passed, run_id, started_at, finished_at, files_deleted_at, files_deleted_by,
               coalesce(summary->'steps', '[]'::jsonb) AS steps
          FROM tests.full_tests ORDER BY finished_at DESC, id DESC LIMIT :n"""),
                        {"n": max(1, min(200, int(limit)))}).mappings().all()
    return [{**_row(r), "steps": [{k: s.get(k) for k in STEP_KEYS} for s in (r["steps"] or []) if isinstance(s, dict)]}
            for r in rows]


def get(conn, full_id: int) -> dict[str, Any] | None:
    """One full test with its whole summary."""
    r = conn.execute(text("""SELECT id, folder, started_by, version, passed, run_id, started_at, finished_at,
                                    files_deleted_at, files_deleted_by, summary FROM tests.full_tests WHERE id = :id"""),
                     {"id": int(full_id)}).mappings().first()
    return _row(r) if r else None


def pick(conn, which: str = "", older_than_days: int | None = None) -> dict[str, list[dict]]:
    """What prune() would take: {runs, fulls}, those with their files still there. which: a run's number, full-<n> (a
    full test's number), all; or every one finished more than N days ago."""
    which = str(which or "").strip()
    if not which and older_than_days is None:
        raise ValueError("Give a run's number, full-<number>, all, or --older-than DAYS.")
    if which and which != "all" and not which.isdigit() and not re.fullmatch(r"full-\d+", which):
        raise ValueError("Give a run's number, full-<number>, all, or --older-than DAYS.")
    if older_than_days is not None and int(older_than_days) < 1:
        raise ValueError("--older-than takes a number of days, 1 or more.")
    age = (f" AND coalesce(finished_at, now()) < now() - make_interval(days => {int(older_than_days)})"
           if older_than_days is not None else "")
    runs, fulls = [], []
    if not which.startswith("full-"):
        where, params = "state NOT IN ('queued', 'running') AND files_deleted_at IS NULL" + age, {}
        if which.isdigit():
            where += " AND id = :id"
            params["id"] = int(which)
        runs = [dict(r) for r in conn.execute(text(f"SELECT id, folder FROM tests.test_runs WHERE {where} ORDER BY id"),
                                              params).mappings()]
    if not which.isdigit():
        where, params = "files_deleted_at IS NULL" + age, {}
        if which.startswith("full-"):
            where += " AND id = :id"
            params["id"] = int(which.removeprefix("full-"))
        fulls = [dict(r) for r in conn.execute(text(f"SELECT id, folder, run_id, summary FROM tests.full_tests WHERE {where} "
                                                    "ORDER BY id"), params).mappings()]
    return {"runs": runs, "fulls": fulls}


LOOSE = re.compile(r"^(sonar|backup-restore|dev-check)-[A-Za-z0-9._-]{1,80}$")


def loose(root, older_than_days: int | None = None, now: float | None = None) -> list[str]:
    """The steps' detailed files run by themselves, not in a full test (eax test sonar, eax test backup-restore, eax dev
    check): sonar-<time>, backup-restore-<time> and dev-check-<time> under work/tests, older than N days (every one
    with None). Read only; prune() deletes them."""
    import time
    from pathlib import Path
    root = Path(root)
    if not root.is_dir():
        return []
    edge = (now or time.time()) - int(older_than_days) * 86400 if older_than_days is not None else None
    out = []
    for p in sorted(root.iterdir()):
        try:
            if LOOSE.match(p.name) and (edge is None or p.stat().st_mtime < edge):
                out.append(p.name)
        except OSError:
            continue
    return out


def prune(engine, picked: dict[str, list[dict]], by: str, remove, say=lambda _m: None) -> dict[str, Any]:
    """Deletes the detailed files of what pick() chose; the summaries stay. remove(names) deletes folders or files
    directly under work/tests and says {removed, left}. A full test's self-test run is pruned with it."""
    out: dict[str, Any] = {"runs": 0, "fulls": 0, "loose": len(picked.get("loose") or []), "screenshots": 0,
                           "removed": [], "left": [], "notes": []}
    names: list[str] = [n for n in picked.get("loose") or [] if isinstance(n, str) and LOOSE.match(n)]
    run_ids = {int(r["id"]) for r in picked.get("runs") or []}
    names += [r["folder"] for r in picked.get("runs") or [] if r.get("folder")]
    for f in picked.get("fulls") or []:
        names += [d for d in (f.get("summary") or {}).get("details") or [] if isinstance(d, str) and ITEM.match(d)
                  and not d.startswith("full-")]
        if f.get("run_id"):
            run_ids.add(int(f["run_id"]))
    with engine.begin() as conn:
        for rid in sorted(run_ids):
            row = conn.execute(text("SELECT state, folder, files_deleted_at FROM tests.test_runs WHERE id = :id"),
                               {"id": rid}).mappings().first()
            if not row:
                continue
            if row["state"] in store.OPEN:
                out["notes"].append(f"run {rid} is still going: its files are kept")
                names = [n for n in names if n != row["folder"]]
                continue
            if row["folder"] and row["folder"] not in names:
                names.append(row["folder"])
            out["screenshots"] += conn.execute(text("UPDATE tests.test_results SET screenshot = NULL WHERE run_id = :id "
                                                    "AND screenshot IS NOT NULL"), {"id": rid}).rowcount
            if row["files_deleted_at"] is None:
                conn.execute(text("UPDATE tests.test_runs SET files_deleted_at = now(), files_deleted_by = :by WHERE id = :id"),
                             {"by": by[:200], "id": rid})
                out["runs"] += 1
            say(f"run {rid}: its detailed files go, its summary stays")
        for f in picked.get("fulls") or []:
            conn.execute(text("UPDATE tests.full_tests SET files_deleted_at = now(), files_deleted_by = :by WHERE id = :id"),
                         {"by": by[:200], "id": int(f["id"])})
            out["fulls"] += 1
            say(f"full test {f['id']} ({f['folder']}): its steps' detailed files go, its summary page stays")
    names = list(dict.fromkeys(n for n in names if n and ITEM.match(n) and not n.startswith("full-")))
    if names:
        done = remove(names) or {}
        out["removed"], out["left"] = list(done.get("removed") or []), list(done.get("left") or [])
    return out


def message(out: dict[str, Any]) -> str:
    """What a prune did, in words."""
    return (f"Detailed files deleted for {out['runs']} self-test run(s), {out['fulls']} full test(s) and "
            f"{out.get('loose', 0)} SonarQube, backup and restore or dev check result(s) run by themselves: "
            f"{len(out['removed'])} folder(s) or file(s) in work/tests and {out['screenshots']} screenshot(s); "
            "the summaries, counts and results stay"
            + (f"; could not remove {', '.join(out['left'])} (delete them in work/tests)" if out["left"] else "")
            + (f"; {'; '.join(out['notes'])}" if out["notes"] else "") + ".")
