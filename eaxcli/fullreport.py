"""The full test's summary page (D825; owner, 21 Nov 2026: "Please add them in one summary page for anyone to check").

At the end of eax test full every step's own result files are read (nothing is run again) and one page is written,
work/tests/full-<time>/index.html, with its figures in summary.json beside it, kept in the database too (eax test
summary; System admin > Self-test > Summary). One card a step:

  dev check          lint, the unit tests, the documents (dev-check-<time>.json)
  code coverage      our code only: the lines run, against the goal, as a ring (the run joined with the unit tests)
  self-test          the counts and the functional health, by suite (the run's summary.json)
  MCP tools          the MCP suite's checks, a card of their own (the self-test's summary.json, "mcp")
  security gate      the findings: failing, accepted, no fix yet, new
  attack test        each scanner, whether it was brought up to date, its findings by severity
  backup and restore every check passed or not (backup-restore-<time>/report.json)
  SonarQube          to fix, issues, security hotspots, accepted in writing (sonar-<time>/summary.json)
  DR drill           each step, the recovery time and the warnings (drill-<time>/report.md; R9.10)

Each card links to its detailed report; once those files are deleted (eax test prune) the card's figures stay. The
page needs nothing from outside (no script, no font, no picture). Standard library only."""

from __future__ import annotations

import html
import json
import math
import re
import time
from pathlib import Path

RUN_FOLDER = re.compile(r"^\d{8}T\d{6}Z$")
KINDS = {"dev check": "dev", "self-test": "selftest", "backup and restore test": "backup", "SonarQube scan": "sonar",
         "DR drill": "dr", "no test container left running": "containers"}
DRILL_STATES = ("ok", "warn", "FAILED")


def drill_row(line: str) -> tuple[str, str, int] | None:
    """A step row of the drill's report.md, "| ok | step | 12 | note |": (state, step, seconds), or None. Read by hand,
    not by the pattern it replaced (SonarQube S8786: two open-ended parts backtracked), giving what that pattern gave:
    the step is everything up to the first "| <digits> |" that has a note after it."""
    s = line.rstrip()
    if not (s.startswith("| ") and s.endswith(" |")) or len(s) < 4:
        return None
    parts = s[2:-2].split(" | ")
    if len(parts) < 4 or parts[0] not in DRILL_STATES:
        return None
    for k in range(2, len(parts) - 1):
        if parts[k] and parts[k].isascii() and parts[k].isdigit():
            return parts[0], " | ".join(parts[1:k]), int(parts[k])
    return None
GOOD, NEAR, LOW, GREY = "#1a7f37", "#b7791f", "#c62828", "#8a8f98"


def _list(path: Path) -> list:
    """A JSON list from a file ([] when it is not there or not a list)."""
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return got if isinstance(got, list) else []


def _json(path: Path) -> dict | None:
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) else None


def _newest(tests: Path, match, since: float) -> Path | None:
    """The newest folder or file under work/tests that match() takes, made or changed since the full test began."""
    found = []
    for p in tests.iterdir() if tests.is_dir() else []:
        try:
            if match(p) and p.stat().st_mtime >= since:
                found.append((p.stat().st_mtime, p.name, p))
        except OSError:
            continue
    return max(found)[2] if found else None


def gather(tests: Path, since: float, steps: list[tuple[str, bool, str]], *, version: str = "", by: str = "",
           now: float | None = None) -> dict:
    """The full test's summary from each step's own files (pure but for reading them)."""
    now = now or time.time()
    since = since - 60                                  # a folder named a moment before the clock was read
    out: dict = {"folder": "full-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now)), "version": version, "by": by,
                 "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(since + 60)),
                 "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                 "passed": all(p for _t, p, _w in steps),
                 "steps": [{"title": t, "passed": p, "why": w, "kind": KINDS.get(t, "")} for t, p, w in steps],
                 "details": []}
    dev = _newest(tests, lambda p: p.is_file() and p.name.startswith("dev-check-") and p.suffix == ".json", since)
    if dev:
        d = _json(dev) or {}
        out["dev"] = {"file": d.get("log") or dev.name, "passed": bool(d.get("passed")), "coverage": d.get("coverage"),
                      "steps": d.get("steps") or []}
        out["details"] += [dev.name] + ([d["log"]] if d.get("log") else [])
    run = _newest(tests, lambda p: p.is_dir() and RUN_FOLDER.match(p.name), since)
    if run:
        s = _json(run / "summary.json") or {}
        if not s.get("coverage"):
            c = _json(run / "coverage.json") or {}
            if c.get("percent") is not None:
                s["coverage"] = {k: c.get(k) for k in ("percent", "live", "unit", "goal", "lines", "run")} | {
                    "api": c.get("goal_percent"), "api_lines": c.get("goal_lines"), "api_run": c.get("goal_run"),
                    "api_left_out": c.get("goal_left_out_lines"),
                    "jobs": c.get("jobs_percent"), "jobs_lines": c.get("jobs_lines"), "jobs_run": c.get("jobs_run")}
        out["selftest"] = {**s, "folder": run.name}
        out["details"].append(run.name)
        out["gaps"] = gaps(_json(run / "coverage.json") or {}, _json(run / "screens-coverage.json") or {})
    br = _newest(tests, lambda p: p.is_dir() and p.name.startswith("backup-restore-"), since)
    if br:
        r = _json(br / "report.json") or {}
        checks = r.get("results") or []
        out["backup"] = {"folder": br.name, "passed": bool(r.get("passed")), "checks": len(checks),
                         "failed": sum(1 for c in checks if isinstance(c, dict) and c.get("ok") is False),
                         "failures": [str(c.get("name") or c.get("check") or "")[:160] for c in checks
                                      if isinstance(c, dict) and c.get("ok") is False][:10]}
        out["details"].append(br.name)
    sq = _newest(tests, lambda p: p.is_dir() and p.name.startswith("sonar-"), since)
    if sq:
        s = _json(sq / "summary.json") or {}
        out["sonar"] = {"folder": sq.name, **{k: s.get(k) for k in ("passed", "to_fix", "issues", "hotspots", "accepted",
                                                                    "by_severity", "by_kind")},
                        # the findings themselves, kept with the summary (owner, 24 Nov 2026, 06:40: "put sonar's snapshot
                        # of findings on the test report too"): the scan's folder may be pruned, the summary stays
                        "findings": _list(sq / "to_fix.json")[:SONAR_SHOWN]}
        out["details"].append(sq.name)
    dr = _newest(tests, lambda p: p.is_dir() and p.name.startswith("drill-"), since)
    if dr:
        out["dr"] = {"folder": dr.name, **drill_report(dr / "report.md")}
        out["details"].append(dr.name)
    return out


SONAR_SHOWN = 300          # the findings kept and shown on the summary page; report.md has them all


def sonar_table(rows: list, to_fix=None) -> str:
    """SonarQube's findings still to fix, as a table (the snapshot of the scan the full test ran)."""
    if not rows:
        return "<p>No finding to fix.</p>" if to_fix == 0 else ""
    head = "<tr><th>Severity</th><th>Kind</th><th>File and line</th><th>Rule</th><th>What</th></tr>"
    body = "".join(
        f"<tr><td>{html.escape(str(r.get('severity') or ''))}</td><td>{html.escape(str(r.get('kind') or '').lower().replace('_', ' '))}</td>"
        f"<td><code>{html.escape(str(r.get('file') or ''))}:{html.escape(str(r.get('line') or '-'))}</code></td>"
        f"<td>{html.escape(str(r.get('rule') or ''))}</td><td>{html.escape(str(r.get('message') or ''))}</td></tr>"
        for r in rows if isinstance(r, dict))
    more = (f"<p>The first {len(rows)} of {to_fix}; report.md has every one.</p>"
            if isinstance(to_fix, int) and to_fix > len(rows) else "")
    return f"<h3>Still to fix</h3><table>{head}{body}</table>{more}"


def to_reach(percent, bar: float, total, done, what: str = "lines") -> str:
    """How far a figure is from its bar (owner, 25 Nov 2026, 16:24: "show the actual measure that you say here"): "short
    by 6.7 points: about 783 more lines to run", or "at or over the goal of 90%"; as coverage_view.to_reach and the app's
    Summary screen (FullSummary.jsx toReach)."""
    if percent is None or not total:
        return "-"
    p, b = float(percent), float(bar or 90.0)
    if p >= b:
        return f"at or over the {'bar' if what == 'screens' else 'goal'} of {b:g}%"
    more = max(0, math.ceil(b * float(total) / 100 - float(done or 0)))
    return f"short by {b - p:.1f} points: about {more:,} more {'screens covered' if what == 'screens' else 'lines to run'}"


def overall(cov: dict, scr: dict) -> float | None:
    """The overall coverage (owner, 25 Nov 2026, 16:34: "can there a an overall coverage ring too, these two can be under
    it"): the API's and the screens' figures, each counted equally (lines and screens are not the same unit, so neither
    outweighs the other), to one decimal; one alone when only it was measured; None with neither. Its bar is 90%, as
    both of theirs. As coverage_view.overall and the app's Summary screen (FullSummary.jsx overall)."""
    got = [float(x) for x in (cov.get("api"), scr.get("percent")) if x is not None]
    return round(sum(got) / len(got), 1) if got else None


def where_it_stands(s: dict) -> str:
    """The one line at the top of the page: the API and the screens against their bars, the jobs beside them."""
    run = s.get("selftest") or {}
    cov, scr = run.get("coverage") or {}, run.get("screens") or {}
    goal = float(cov.get("goal") or 90.0)
    parts = []
    whole = overall(cov, scr)
    if whole is not None and cov.get("api") is not None and scr.get("percent") is not None:
        parts.append(f"Overall {whole}% (the API and the screens counted equally), bar 90%: "
                     + (f"short by {90 - whole:.1f} points" if whole < 90 else "at or over the bar"))
    if cov.get("api") is not None:
        parts.append(f"The API {cov['api']}% of {cov.get('api_lines', 0)} lines, goal {goal:g}%: "
                     f"{to_reach(cov['api'], goal, cov.get('api_lines'), cov.get('api_run'))}")
    if cov.get("jobs") is not None:
        parts.append(f"background jobs {cov['jobs']}% (shown, not judged)")
    if scr.get("percent") is not None:
        bar = float(scr.get("bar") or 90.0)
        parts.append(f"the screens {scr['percent']}% ({scr.get('covered')} of {scr.get('screens')}), bar {bar:g}%: "
                     f"{to_reach(scr['percent'], bar, scr.get('screens'), scr.get('covered'), 'screens')}")
    return f'<p class="where"><b>Where it stands:</b> {html.escape("; ".join(parts))}.</p>' if parts else ""


def gaps(cov: dict, scr: dict, goal: float = 90.0) -> dict:
    """What is not covered, from the self-test's coverage.json and screens-coverage.json (owner, 25 Nov 2026, 12:19:
    "In the coverage clearly call out areas not being covered in a table"): the API's files under the goal, what is left
    out of the API's goal and why, the background jobs' files, the screens not covered yet (by area) and the screens left
    out and why. Kept in the summary (the figures stay when the detailed files are pruned)."""
    goal = float(cov.get("goal") or goal)
    bar = float(scr.get("bar") or 90.0)
    by_area: dict[str, list[str]] = {}
    for x in scr.get("not_covered") or []:
        parts = [y for y in str(x).split("/") if y and y != "#"]
        by_area.setdefault(parts[0] if parts else "home", []).append(x)
    return {
        "api_goal": goal,
        "api_files": [f for f in cov.get("goal_files") or [] if (f.get("percent") or 0) < goal],
        "api_left_out": [{k: x.get(k) for k in ("file", "route", "methods", "why")} for x in cov.get("goal_left_out") or []],
        "jobs_files": sorted(cov.get("jobs_files") or [], key=lambda f: f.get("percent") or 0),
        "screens_bar": bar,
        "screens_not_covered": [{"area": a, "screens": v} for a, v in sorted(by_area.items(), key=lambda kv: (-len(kv[1]), kv[0]))],
        "screens_left_out": scr.get("screens_left_out") or [],
        "controls_left_out": len(scr.get("left_out") or []),
    }


def gaps_card(g: dict | None) -> str:
    """The "Not covered yet" card: one table a kind of gap, each line with why or how far from the goal."""
    if not g:
        return ""
    e = html.escape

    def table(head: list[str], rows: list[list[str]]) -> str:
        if not rows:
            return '<p class="quiet">None.</p>'
        return ("<table><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr>"
                + "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in rows) + "</table>")
    api = [[f["file"], f"{f.get('percent')}%", str(int(f.get("lines") or 0) - int(f.get("run") or 0))] for f in g.get("api_files") or []]
    out = [f'<h3>The API: files under the goal of {float(g.get("api_goal") or 90):.0f}% ({len(api)})</h3>',
           table(["file", "covered", "lines not run"], api),
           f'<h3>The API: left out of the goal ({len(g.get("api_left_out") or [])})</h3>',
           table(["file", "route", "methods", "why"],
                 [[x.get("file", ""), x.get("route", ""), ", ".join(x["methods"]) if isinstance(x.get("methods"), list)
                   else str(x.get("methods") or "all"), x.get("why", "")] for x in g.get("api_left_out") or []]),
           '<h3>Background jobs (shown, not judged)</h3>',
           table(["file", "covered", "lines not run"],
                 [[f["file"], f"{f.get('percent')}%", str(int(f.get("lines") or 0) - int(f.get("run") or 0))]
                  for f in g.get("jobs_files") or []]),
           f'<h3>Screens not covered yet, by area ({sum(len(x["screens"]) for x in g.get("screens_not_covered") or [])})</h3>',
           table(["area", "screens", "which"], [[x["area"], str(len(x["screens"])), ", ".join(x["screens"])]
                                                for x in g.get("screens_not_covered") or []]),
           f'<h3>Screens left out of the bar ({len(g.get("screens_left_out") or [])})</h3>',
           table(["screen", "why"], [[x.get("screen", ""), x.get("why", "")] for x in g.get("screens_left_out") or []]),
           f'<p class="quiet">{int(g.get("controls_left_out") or 0)} risky controls (stop, restart, restore, delete, ...) '
           'are not pressed and not counted; they are listed in screens-coverage.json.</p>']
    return '<section class="card wide"><h2>Not covered yet</h2>' + "".join(out) + "</section>"


def drill_report(path: Path) -> dict:
    """The DR drill's report.md read: its verdict, the recovery time, each step and the warnings (R9.10)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return {"passed": None, "verdict": "no report", "recovery": None, "steps": [], "warnings": 0}
    lines = text.splitlines()
    verdict = next((x.strip().strip("*").replace("**", "") for x in lines if x.startswith("**")), "")
    rec = re.search(r"Recovery time[^:]*\): (\d+) minutes", text)
    steps = [{"state": m[0], "step": m[1], "seconds": m[2]} for m in (drill_row(x) for x in lines) if m]
    return {"passed": bool(verdict) and not verdict.startswith("Failed"), "verdict": verdict[:300],
            "recovery": int(rec.group(1)) if rec else None, "steps": steps,
            "warnings": sum(1 for x in steps if x["state"] == "warn")}


# ---------------------------------------------------------------- the page
def _colour(p: float | None, goal: float) -> str:
    return GREY if p is None else GOOD if p >= goal else NEAR if p >= goal - 15 else LOW


def ring(percent: float | None, goal: float = 90.0, size: int = 150, label: str = "our code") -> str:
    """A ring: the share of our code's lines run, a tick at the goal (as coverage_view.ring_svg)."""
    r, w = size / 2 - 12, 16
    c = 2 * math.pi * r
    p = max(0.0, min(100.0, percent or 0.0))
    ang = math.radians(goal / 100 * 360 - 90)
    gx, gy = size / 2 + r * math.cos(ang), size / 2 + r * math.sin(ang)
    text = "no figure" if percent is None else f"{p:.1f}%"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="{html.escape(label)}: '
            f'{text} of the lines run, goal {goal:.0f}%">'
            f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="#e3e6ea" stroke-width="{w}"/>'
            f'<circle cx="{size/2}" cy="{size/2}" r="{r}" fill="none" stroke="{_colour(percent, goal)}" stroke-width="{w}" '
            f'stroke-dasharray="{c * p / 100:.1f} {c:.1f}" transform="rotate(-90 {size/2} {size/2})"/>'
            f'<line x1="{gx:.1f}" y1="{gy:.1f}" x2="{size/2 + (r - w) * math.cos(ang):.1f}" '
            f'y2="{size/2 + (r - w) * math.sin(ang):.1f}" stroke="#222" stroke-width="2"/>'
            f'<text x="50%" y="50%" text-anchor="middle" dominant-baseline="middle" font-size="22" font-weight="600">{text}</text>'
            f'<text x="50%" y="66%" text-anchor="middle" font-size="11" fill="#555">{html.escape(label)}</text></svg>')


def _state(ok) -> str:
    return ('<span class="pill none">not run</span>' if ok is None else
            '<span class="pill good">passed</span>' if ok else '<span class="pill bad">failed</span>')


def _link(href: str, words: str) -> str:
    return f'<a href="{html.escape(href)}">{html.escape(words)}</a>'


def _rows(pairs) -> str:
    return "<table>" + "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in pairs) + "</table>"


def cards(s: dict) -> list[str]:
    """One card a step, as HTML."""
    out = []
    steps = {x.get("kind"): x for x in s.get("steps") or []}
    dev = s.get("dev")
    st = steps.get("dev")
    if dev or st:
        body = _rows((x.get("title"), ("ok" if x.get("passed") else "FAILED") + (f": {x['why']}" if x.get("why") else ""))
                     for x in (dev or {}).get("steps") or []) if dev else f"<p>{html.escape((st or {}).get('why') or '')}</p>"
        link = _link(f"../{dev['file']}", "The whole check's log") if dev and dev.get("file") else ""
        out.append(f'<section class="card"><h2>Dev check {_state((st or dev or {}).get("passed"))}</h2>{body}<p>{link}</p></section>')
    run = s.get("selftest") or {}
    cov = run.get("coverage") or {}
    unit = ((s.get("dev") or {}).get("coverage") or {}).get("percent")
    goal = float(cov.get("goal") or 90)
    api = cov.get("api")                                  # the goal's measure: eax/api (D923); else all our code
    pairs = [*([("the API (eax/api), the goal's measure", f"{api}% ({cov.get('api_run', 0)} of {cov.get('api_lines', 0)} lines)"),
                ("to reach the goal", to_reach(api, goal, cov.get("api_lines"), cov.get("api_run"))),
                *([("left out of the goal", f"{cov['api_left_out']} lines: pairing (a second installation), the routes "
                    "that stop, restart, restore or wipe it and the self-test's own controls; listed in coverage.json")] if cov.get("api_left_out") else []),
                *([("the background jobs", f"{cov['jobs']}% ({cov.get('jobs_run', 0)} of {cov.get('jobs_lines', 0)} lines)")]
                  if cov.get("jobs") is not None else []),
                ("all the server's code", f"{cov.get('percent')}%")] if api is not None else []),
             ("the risky suite (--risky)", "on: the routes it runs count" if cov.get("risky") else "off: its routes left out"),
             ("this run alone", f"{cov['live']}%" if cov.get("live") is not None else "-"),
             ("the unit tests alone", f"{cov.get('unit') if cov.get('unit') is not None else unit}%" if
              (cov.get("unit") is not None or unit is not None) else "-"),
             ("lines", f"{cov.get('run', 0)} of {cov.get('lines', 0)} run" if cov.get("lines") else "-"),
             ("goal", f"{goal:.0f}%")]
    shown = api if api is not None else cov.get("percent")
    scr = run.get("screens") or {}
    whole = overall(cov, scr)
    if whole is not None and api is not None and scr.get("percent") is not None:     # one ring over the two below it
        small = (f'<div class="pair">{ring(api, goal, 120, "the API")}'
                 f'{ring(scr.get("percent"), float(scr.get("bar") or 90), 120, "the screens")}</div>')
        out.append(f'<section class="card wide overall"><h2>Overall coverage</h2><div class="ring">{ring(whole, 90.0, 190, "overall")}</div>'
                   f'{small}<p class="quiet">Overall: the API ({api}%) and the screens ({scr["percent"]}%) counted equally. '
                   f'Bar 90%: {"at or over it" if whole >= 90 else f"short by {90 - whole:.1f} points"}. Each is in full in its '
                   'own card below.</p></section>')
    out.append(f'<section class="card"><h2>Code coverage</h2><div class="ring">{ring(shown, goal, label="the API" if api is not None else "our code")}</div>'
               f'{_rows(pairs)}<p class="quiet">The goal is measured on the API (eax/api); the rest of our code is shown, '
               'not judged. Joined line by line with the unit tests\'.</p></section>')
    if scr.get("percent") is not None:              # the screens, by the journeys (R14.5.1, D924)
        pairs = [("screens covered", f"{scr.get('covered', 0)} of {scr.get('screens', 0)}"),
                 ("to reach the bar", to_reach(scr.get("percent"), float(scr.get("bar") or 90), scr.get("screens"),
                                               scr.get("covered"), "screens")),
                 ("acted on by a journey", str(scr.get("acted_on", 0))), ("read only, opened", str(scr.get("read_only", 0))),
                 ("controls used", f"{scr.get('controls_used', 0)} of {scr.get('controls', 0)} ({scr.get('controls_percent')}%)"),
                 ("risky controls left out", str(scr.get("left_out", 0))),
                 ("screens left out", f"{scr.get('screens_left_out', 0)} (a second installation, restores, a test run in the run)"),
                 ("bar", f"{float(scr.get('bar') or 90):.0f}%")]
        out.append(f'<section class="card"><h2>Screens covered by journeys</h2><div class="ring">{ring(scr.get("percent"), float(scr.get("bar") or 90), label="the screens")}</div>'
                   f'{_rows(pairs)}<p class="quiet">A screen a journey acts on, or a read-only one that opens; the list is in '
                   'screens-coverage.json in the self-test\'s folder. The bar: 90% of the screens counted.</p></section>')
    stp = steps.get("selftest")
    if run or stp:
        t = run.get("tally") or {}
        suites = "".join(f"<tr><th>{html.escape(k)}</th><td>{v.get('passed', 0)} passed, {v.get('failed', 0)} failed, "
                         f"{v.get('warning', 0)} warnings</td></tr>" for k, v in (run.get("by_suite") or {}).items())
        link = _link(f"../{run['folder']}/report.html", f"Self-test {run.get('run', '')}: the whole report") if run.get("folder") else ""
        out.append(f'<section class="card"><h2>Self-test {_state((stp or {}).get("passed", run.get("state") == "passed"))}</h2>'
                   f'<p class="big">{t.get("passed", 0)} passed · {t.get("failed", 0)} failed · {t.get("warning", 0)} warnings · '
                   f'{t.get("skipped", 0)} skipped</p><p>Functional health: <b>{html.escape(str(run.get("health") or "-"))}</b> '
                   f'{html.escape(str(run.get("reason") or ""))}</p><table>{suites}</table><p>{link}</p></section>')
    mc = run.get("mcp")
    if mc:                     # the MCP tools, called as an AI calls them, a card of their own (owner, 22 Nov 2026)
        bad = [c for c in mc.get("checks") or [] if c.get("outcome") == "failed"]
        body = (_rows((c["name"], c.get("detail") or "") for c in bad[:30]) if bad else
                "<p>Every tool answered as it should: the reading tools with the run's data, the tools that change "
                "something with a preview (and a wrong confirm token refused), the others refusing what is not there.</p>")
        out.append(f'<section class="card"><h2>MCP tools {_state(not bad)}</h2><p class="big">{mc.get("passed", 0)} passed · '
                   f'{mc.get("failed", 0)} failed · {mc.get("skipped", 0)} skipped</p>{body}</section>')
    sec = run.get("security")
    if sec:
        out.append(f'<section class="card"><h2>Security gate {_state(not sec.get("failing"))}</h2>' + _rows([
            ("findings", sec.get("findings", 0)), ("high or critical, not accepted", sec.get("failing", 0)),
            ("accepted in writing", sec.get("accepted", 0)), ("accepted until a date now past", sec.get("expired", 0)),
            ("no fix released yet", sec.get("no_fix", 0)), ("new since the run before", sec.get("new", 0))])
            + (f'<p>{_link(f"../{run["folder"]}/security-findings.json", "Every finding")}</p>' if run.get("folder") else "")
            + "</section>")
    att = run.get("attack")
    if att:
        tools = "".join(f"<tr><th>{html.escape(n)}</th><td>{'the newest' if t.get('pulled') else 'the last pulled' if t.get('present') else 'not there: left out'}"
                        f"{(' (' + html.escape(t['created'][:10]) + ')') if t.get('created') else ''}</td></tr>"
                        for n, t in (att.get("tools") or {}).items())
        found = "".join(f"<tr><th>{html.escape(src)}</th><td>{html.escape(', '.join(f'{n} {sev}' for sev, n in sorted(by.items())))}</td></tr>"
                        for src, by in (att.get("findings") or {}).items())
        out.append(f'<section class="card"><h2>Attack test</h2><h3>Scanners</h3><table>{tools}</table><h3>Findings</h3>'
                   f'<table>{found or "<tr><td>none</td></tr>"}</table></section>')
    br, bst = s.get("backup"), steps.get("backup")
    if br or bst:
        fails = "".join(f"<li>{html.escape(x)}</li>" for x in (br or {}).get("failures") or [])
        body = (f'<p class="big">{br["checks"] - br["failed"]} of {br["checks"]} checks passed</p>'
                + (f"<ul>{fails}</ul>" if fails else "") + f'<p>{_link(f"../{br["folder"]}/report.md", "The whole report")}</p>'
                if br else f"<p>{html.escape((bst or {}).get('why') or '')}</p>")
        out.append(f'<section class="card"><h2>Backup and restore {_state((bst or br or {}).get("passed"))}</h2>{body}</section>')
    sq, sst = s.get("sonar"), steps.get("sonar")
    if sq or sst:
        body = (_rows([("to fix", sq.get("to_fix")), ("issues", sq.get("issues")), ("security hotspots", sq.get("hotspots")),
                       ("accepted in writing", sq.get("accepted"))]
                      + [(f"severity {k.lower()}", v) for k, v in (sq.get("by_severity") or {}).items()])
                + sonar_table(sq.get("findings") or [], sq.get("to_fix"))
                + f'<p>{_link(f"../{sq["folder"]}/report.md", "Every issue by file and line")}</p>'
                if sq else f"<p>{html.escape((sst or {}).get('why') or '')}</p>")
        out.append(f'<section class="card"><h2>SonarQube {_state((sst or sq or {}).get("passed"))}</h2>{body}</section>')
    dr, dst = s.get("dr"), steps.get("dr")
    if dr or dst:
        body = ((f'<p class="big">{html.escape(dr.get("verdict") or "")}</p>'
                 + (f'<p>Recovery time: <b>{dr["recovery"]} minutes</b> (the installation shut down to the DR copy '
                    'restored and signed in to)</p>' if dr.get("recovery") is not None else "")
                 + _rows((x["step"], x["state"]) for x in dr.get("steps") or [])
                 + f'<p>{_link(f"../{dr["folder"]}/report.md", "The whole report")}</p>')
                if dr else f"<p>{html.escape((dst or {}).get('why') or '')}</p>")
        out.append(f'<section class="card"><h2>DR drill {_state((dst or dr or {}).get("passed"))}</h2>{body}</section>')
    ct = steps.get("containers")
    if ct:
        out.append(f'<section class="card"><h2>Test containers {_state(ct.get("passed"))}</h2><p>'
                   + (html.escape(ct.get("why") or "") if not ct.get("passed") else
                      "None left running: every scanner, k6 and the test runner removed when done.") + "</p></section>")
    return out


CSS = """body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:24px;color:#1f2328;background:#f6f8fa}
h1{margin:0 0 4px}.quiet{color:#57606a;font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-top:16px}
.card{background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:14px 16px}.card h2{font-size:17px;margin:0 0 10px}
.card h3{font-size:13px;margin:10px 0 4px;color:#57606a}table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;font-weight:500;color:#57606a;padding:3px 8px 3px 0;vertical-align:top}td{padding:3px 0}
.pill{font-size:12px;border-radius:10px;padding:2px 8px;margin-left:6px;vertical-align:middle;color:#fff}
.good{background:#1a7f37}.bad{background:#c62828}.none{background:#8a8f98}.big{font-size:16px;font-weight:600}
.ring{text-align:center}ol{margin:6px 0 0 18px;padding:0;font-size:14px}.wide{grid-column:1/-1}.pair{display:flex;justify-content:center;gap:32px;margin:4px 0 8px}.where{margin:8px 0;padding:8px 12px;border-left:4px solid #2563eb;background:#fff}"""


def page(s: dict) -> str:
    """The whole page."""
    steps = "".join(f"<li>{'ok' if x.get('passed') else '<b>FAILED</b>'} {html.escape(str(x.get('title')))}"
                    + (f": {html.escape(str(x['why']))}" if x.get("why") else "") + "</li>" for x in s.get("steps") or [])
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Full test {html.escape(s["finished_at"])}</title>'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><style>{CSS}</style></head><body>'
            f'<h1>EA Explorer full test {_state(s.get("passed"))}</h1>'
            f'<p class="quiet">Version {html.escape(s.get("version") or "?")} · began {html.escape(s.get("started_at") or "")} · '
            f'ended {html.escape(s.get("finished_at") or "")}' + (f' · by {html.escape(s["by"])}' if s.get("by") else "")
            + '</p><ol>' + steps + '</ol>' + where_it_stands(s) + '<div class="grid">' + "".join(cards(s))
            + gaps_card(s.get("gaps")) + '</div>'
            '<p class="quiet">The figures on this page stay when the detailed files are deleted (eax test prune, or System '
            'admin &gt; Self-test &gt; History); its links then no longer open.</p></body></html>')


def write(tests: Path, summary: dict) -> Path:
    """work/tests/full-<time>/index.html and summary.json; the folder."""
    folder = tests / summary["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    (folder / "index.html").write_text(page(summary), encoding="utf-8")
    return folder
