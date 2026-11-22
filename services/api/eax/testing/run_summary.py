"""A self-test run's summary, kept in its row (tests.test_runs.summary) and as summary.json in its folder (D825; owner,
21 Nov 2026: "We also need the ability to only keep summary in a DB table or something and delete detailed result
files form UI or command line").

The summary is what the full test's summary page shows of the run once its detailed files are gone: the counts, the
functional health and why, the code coverage (this run, the unit tests, joined, against the goal), the security gate's
counts and the attack test's tools and findings. It is small (a few kilobytes) and made from what the run already
wrote; nothing is measured again. Pure functions, apart from save()."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

FILE = "summary.json"
SEVERITIES = ("critical", "high", "medium", "low", "info")
ATTACK_SOURCES = ("zap-full", "schemathesis", "nuclei", "semgrep", "gitleaks")


def _load(folder: Path | None, name: str) -> dict | None:
    if folder is None:
        return None
    try:
        got = json.loads((folder / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) else None


def _num(v: Any) -> float | None:
    try:
        return None if v is None else round(float(v), 1)
    except (TypeError, ValueError):
        return None


def coverage(c: dict | None) -> dict | None:
    """The coverage figures only (never which lines ran)."""
    if not c or c.get("percent") is None:
        return None
    return {"percent": _num(c.get("percent")), "live": _num(c.get("live")), "unit": _num(c.get("unit")),
            "goal": _num(c.get("goal")), "lines": int(c.get("lines") or 0), "run": int(c.get("run") or 0),
            "joined": bool(c.get("joined"))}


def security(found: dict | None) -> dict | None:
    """The gate's counts from security-findings.json: failing, accepted, expired, no fix yet, new; by source and
    severity."""
    if not found:
        return None
    gate = found.get("gate") or {}
    by: dict[str, dict[str, int]] = {}
    for f in found.get("findings") or []:
        src, sev = str(f.get("source") or "?"), str(f.get("severity") or "info").lower()
        by.setdefault(src, {}).setdefault(sev, 0)
        by[src][sev] += 1
    n = lambda k: len(gate.get(k) or [])  # noqa: E731
    return {"findings": len(found.get("findings") or []), "failing": n("failing"), "accepted": n("accepted"),
            "expired": n("expired"), "no_fix": n("no_fix"), "new": len(found.get("new") or []), "by_source": by}


def attack(tools: dict | None, sec: dict | None) -> dict | None:
    """The attack test's scanners (each one's image, whether it was brought up to date) and their findings."""
    if not tools:
        return None
    out = {"tools": {name: {"pulled": bool(t.get("pulled")), "present": bool(t.get("present")),
                            "created": str(t.get("created") or "")[:25], "note": str(t.get("note") or "")[:120]}
                     for name, t in (tools.get("tools") or {}).items()}}
    by = (sec or {}).get("by_source") or {}
    out["findings"] = {s: by[s] for s in ATTACK_SOURCES if s in by}
    return out


def mcp(results: list[dict]) -> dict | None:
    """The MCP suite's checks, for a card of their own on the full test's summary page (owner, 22 Nov 2026, 14:12: "they
    should have there own cards"): the counts, and each check with its outcome (failures first)."""
    rows = [r for r in results if r.get("suite") == "mcp"]
    if not rows:
        return None
    count = {k: sum(1 for r in rows if r.get("outcome") == k) for k in ("passed", "failed", "warning", "skipped")}
    return {**count, "checks": [{"name": str(r.get("name") or "").removeprefix("mcp: ")[:120], "outcome": r.get("outcome"),
                                 "detail": str(r.get("detail") or "")[:200]} for r in rows][:400]}


def make(detail: dict, folder: Path | None) -> dict[str, Any]:
    """The summary of a finished run from store.run_detail() and its folder's files."""
    run, hs, t = detail.get("run") or {}, detail.get("health") or {}, detail.get("tally") or {}
    sec = security(_load(folder, "security-findings.json"))
    return {
        "run": run.get("id"), "folder": run.get("folder") or "", "state": run.get("state") or "",
        "suites": list(run.get("suites") or []), "level": run.get("level") or "", "version": run.get("version") or "",
        "started_at": str(run.get("started_at") or "")[:19], "finished_at": str(run.get("finished_at") or "")[:19],
        "tally": {k: int(t.get(k) or 0) for k in ("passed", "failed", "warning", "skipped")},
        "health": hs.get("health") or "", "reason": str(hs.get("reason") or "")[:400],
        "by_suite": {s: {k: int(v.get(k) or 0) for k in ("passed", "failed", "warning", "skipped")}
                     for s, v in (hs.get("suites") or {}).items()},
        "mcp": mcp(detail.get("results") or []),
        "coverage": coverage(_load(folder, "coverage.json")),
        "security": sec,
        "attack": attack(_load(folder, "attack-tools.json"), sec),
    }


def save(conn, run_id: int, summary: dict, folder: Path | None) -> None:
    """Kept in the run's row and, when the folder is there, as summary.json beside the report."""
    conn.execute(text("UPDATE tests.test_runs SET summary = CAST(:s AS jsonb) WHERE id = :id"),
                 {"s": json.dumps(summary, default=str), "id": run_id})
    if folder is not None and folder.is_dir():
        (folder / FILE).write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
