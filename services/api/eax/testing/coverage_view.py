"""Coverage as pictures (R3.10; owner, 13 Nov 2026: "coverage should be shown with results in UI with some sort of
graph"): for a run, its code coverage (coverage.json, D642) and its negative tests (negative.json, R3.9), and the trend
over the last runs.

  gauge     the share of the API's lines run, against the goal (85%)
  areas     each area's share, the worst first
  trend     the share over the last runs of the same kind, with the goal as a line
  negative  the negative tests by kind: passed, warnings, failed (a stacked bar each)

The pictures are SVG drawn here from numbers only (area names escaped), so the Self-test page and the HTML report show the
same ones; the page also gets the numbers. Nothing here reads anything but a run's own two files."""

from __future__ import annotations

import html
import json
import math
from collections.abc import Callable, Iterable

GOAL = 85.0                    # D934, owner, 26 Nov 2026, 11:00: "Ok the target is 85%"
GOOD, NEAR, LOW = "#1a9e5a", "#c98a00", "#d64545"       # at the goal; within 15 points; further off
BAR, GRID = "#3d7bd9", "#8a93a0"
OUTCOME_COLOUR = {"passed": GOOD, "warning": NEAR, "failed": LOW}

Reader = Callable[[str, str], bytes | None]               # (folder, file name) -> the file, or None


def _load(raw: bytes | None) -> dict | None:
    if not raw:
        return None
    try:
        out = json.loads(raw)
    except ValueError:
        return None
    return out if isinstance(out, dict) else None


def run_files(folder: str, reader: Reader) -> dict:
    """{coverage, negative, screens} of one run (each None when the run has not got it)."""
    if not folder:
        return {"coverage": None, "negative": None, "screens": None}
    return {"coverage": _load(reader(folder, "coverage.json")), "negative": _load(reader(folder, "negative.json")),
            "screens": _load(reader(folder, "screens-coverage.json"))}


def colour(percent: float, goal: float = GOAL) -> str:
    """A coverage figure's colour against the goal."""
    return GOOD if percent >= goal else NEAR if percent >= goal - 15 else LOW


def trend(runs: Iterable[dict], reader: Reader, scope: str | None = None, limit: int = 30) -> list[dict]:
    """[{run, at, scope, percent, goal}] oldest first, for the runs (newest first, with id, folder, finished_at) that
    kept a coverage.json; only those of `scope` when it is given."""
    out = []
    for r in runs:
        c = _load(reader(r["folder"], "coverage.json")) if r.get("folder") else None
        if not c or c.get("percent") is None or (scope is not None and c.get("scope", "") != scope):
            continue
        out.append({"run": r["id"], "at": str(r.get("finished_at") or ""), "scope": c.get("scope", ""),
                    "percent": float(c["percent"]), "goal": float(c.get("goal") or GOAL)})
        if len(out) >= limit:
            break
    return list(reversed(out))


def negative_totals(neg: dict | None) -> dict[str, int]:
    """The negative tests' totals by outcome."""
    t = {"passed": 0, "warning": 0, "failed": 0}
    for counts in (neg or {}).values():
        for k in t:
            t[k] += int((counts or {}).get(k) or 0)
    return t


def gauge_svg(percent: float, goal: float = GOAL, size: int = 180) -> str:
    """A half-ring from 0 to 100% with the goal marked."""
    import math
    w, h, r, sw = size, size * 0.62, size * 0.4, size * 0.09
    cx, cy = w / 2, size * 0.5

    def at(p: float) -> tuple[float, float]:
        a = math.pi * (1 - max(0.0, min(100.0, p)) / 100)
        return cx + r * math.cos(a), cy - r * math.sin(a)

    x0, y0 = at(0)
    x1, y1 = at(100)
    xp, yp = at(percent)
    gx, gy = at(goal)
    ox, oy = cx + (r + sw) * (gx - cx) / r, cy + (r + sw) * (gy - cy) / r
    ix, iy = cx + (r - sw) * (gx - cx) / r, cy + (r - sw) * (gy - cy) / r
    value = (f"<path d='M{x0:.1f},{y0:.1f} A{r:.1f},{r:.1f} 0 0 1 {xp:.1f},{yp:.1f}' fill='none' stroke='{colour(percent, goal)}' "
             f"stroke-width='{sw:.1f}' stroke-linecap='round'/>") if percent > 0 else ""
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h:.0f}' width='{w}' height='{h:.0f}' role='img' "
            f"aria-label='Code coverage {percent:g}% against a goal of {goal:g}%'>"
            f"<path d='M{x0:.1f},{y0:.1f} A{r:.1f},{r:.1f} 0 0 1 {x1:.1f},{y1:.1f}' fill='none' stroke='{GRID}' stroke-opacity='0.3' "
            f"stroke-width='{sw:.1f}' stroke-linecap='round'/>{value}"
            f"<line x1='{ix:.1f}' y1='{iy:.1f}' x2='{ox:.1f}' y2='{oy:.1f}' stroke='currentColor' stroke-width='2'/>"
            f"<text x='{cx:.1f}' y='{cy - 4:.1f}' text-anchor='middle' font-size='{size * 0.16:.0f}' font-weight='700' "
            f"fill='currentColor'>{percent:g}%</text>"
            f"<text x='{cx:.1f}' y='{cy + size * 0.1:.1f}' text-anchor='middle' font-size='{size * 0.07:.0f}' fill='currentColor' "
            f"opacity='0.7'>goal {goal:g}%</text></svg>")


def areas_svg(areas: list[dict], goal: float = GOAL, width: int = 420) -> str:
    """One bar per area, the least covered first, with the goal as a dashed line."""
    rows = sorted(areas or [], key=lambda a: a.get("percent", 0.0))
    if not rows:
        return ""
    lab, bh, gap = 110, 16, 6
    plot = width - lab - 48
    h = len(rows) * (bh + gap) + 8
    gx = lab + plot * goal / 100
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {h}' width='{width}' height='{h}' role='img' "
           f"aria-label='Coverage by area, the least covered first'>"]
    for i, a in enumerate(rows):
        y, p = 4 + i * (bh + gap), float(a.get("percent", 0.0))
        out.append(f"<text x='{lab - 6}' y='{y + bh - 4}' text-anchor='end' font-size='12' fill='currentColor'>"
                   f"{html.escape(str(a.get('area', '')))}</text>"
                   f"<rect x='{lab}' y='{y}' width='{plot}' height='{bh}' rx='3' fill='{GRID}' fill-opacity='0.15'/>"
                   f"<rect x='{lab}' y='{y}' width='{plot * min(p, 100) / 100:.1f}' height='{bh}' rx='3' fill='{colour(p, goal)}'>"
                   f"<title>{html.escape(str(a.get('area', '')))}: {p:g}% ({a.get('run', '?')} of {a.get('lines', '?')} lines)</title></rect>"
                   f"<text x='{lab + plot + 6}' y='{y + bh - 4}' font-size='12' fill='currentColor'>{p:g}%</text>")
    out.append(f"<line x1='{gx:.1f}' y1='0' x2='{gx:.1f}' y2='{h}' stroke='currentColor' stroke-dasharray='4 3' opacity='0.6'/>"
               "</svg>")
    return "".join(out)


def trend_svg(points: list[dict], goal: float = GOAL, width: int = 420, height: int = 140) -> str:
    """The share over the runs, oldest on the left, the goal dashed."""
    if not points:
        return ""
    left, right, top, bottom = 34, 10, 8, 20
    pw, ph = width - left - right, height - top - bottom

    def y(p: float) -> float:
        return top + ph * (1 - max(0.0, min(100.0, p)) / 100)

    n = len(points)
    xs = [left + (pw * i / (n - 1) if n > 1 else pw / 2) for i in range(n)]
    line = " ".join(f"{x:.1f},{y(p['percent']):.1f}" for x, p in zip(xs, points, strict=True))
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' width='{width}' height='{height}' "
           f"role='img' aria-label='Coverage over the last {n} runs'>"]
    for t in (0, 50, 100):
        out.append(f"<line x1='{left}' x2='{width - right}' y1='{y(t):.1f}' y2='{y(t):.1f}' stroke='{GRID}' stroke-opacity='0.25'/>"
                   f"<text x='{left - 4}' y='{y(t) + 4:.1f}' text-anchor='end' font-size='10' fill='currentColor' opacity='0.7'>{t}%</text>")
    out.append(f"<line x1='{left}' x2='{width - right}' y1='{y(goal):.1f}' y2='{y(goal):.1f}' stroke='currentColor' "
               f"stroke-dasharray='4 3' opacity='0.6'/>")
    if n > 1:
        out.append(f"<polyline points='{line}' fill='none' stroke='{BAR}' stroke-width='2'/>")
    for x, p in zip(xs, points, strict=True):
        out.append(f"<circle cx='{x:.1f}' cy='{y(p['percent']):.1f}' r='3.5' fill='{colour(p['percent'], goal)}'>"
                   f"<title>Run {p['run']}: {p['percent']:g}%</title></circle>")
    out.append(f"<text x='{left}' y='{height - 4}' font-size='10' fill='currentColor' opacity='0.7'>run {points[0]['run']}</text>"
               f"<text x='{width - right}' y='{height - 4}' text-anchor='end' font-size='10' fill='currentColor' opacity='0.7'>"
               f"run {points[-1]['run']}</text></svg>")
    return "".join(out)


def negative_svg(neg: dict | None, width: int = 420) -> str:
    """A stacked bar per kind of negative test: passed, warnings, failed."""
    rows = [(k, v) for k, v in (neg or {}).items() if sum((v or {}).values())]
    if not rows:
        return ""
    lab, bh, gap = 110, 16, 6
    plot = width - lab - 60
    h = len(rows) * (bh + gap) + 8
    most = max(sum(v.values()) for _, v in rows)
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {h}' width='{width}' height='{h}' role='img' "
           f"aria-label='Negative tests by kind'>"]
    for i, (kind, v) in enumerate(rows):
        y, x = 4 + i * (bh + gap), float(lab)
        out.append(f"<text x='{lab - 6}' y='{y + bh - 4}' text-anchor='end' font-size='12' fill='currentColor'>{html.escape(kind)}</text>")
        for outcome in ("passed", "warning", "failed"):
            n = int(v.get(outcome) or 0)
            if not n:
                continue
            w = plot * n / most
            out.append(f"<rect x='{x:.1f}' y='{y}' width='{w:.1f}' height='{bh}' fill='{OUTCOME_COLOUR[outcome]}'>"
                       f"<title>{html.escape(kind)}: {n} {outcome}</title></rect>")
            x += w
        out.append(f"<text x='{x + 6:.1f}' y='{y + bh - 4}' font-size='12' fill='currentColor'>{sum(v.values())}</text>")
    out.append("</svg>")
    return "".join(out)


def ring_svg(percent: float, run: int | None = None, lines: int | None = None, size: int = 180, label: str = "",
             goal: float = GOAL) -> str:
    """A full ring (R8.1, D824; owner, 21 Nov 2026, 13:18: "Can code coverage of a full test be shown in a ring pie chart
    please? Only for our code"): the share of lines run in the goal's colour, the rest grey, the percent in the middle
    and, when known, how many lines of how many under it; the goal marked as a tick on the ring."""
    import math
    p = max(0.0, min(100.0, float(percent)))
    r, sw = size / 2 - size * 0.08, size * 0.13
    cx = cy = size / 2
    circ = 2 * math.pi * r
    ga = math.radians(goal / 100 * 360 - 90)
    gx1, gy1 = cx + (r - sw / 2 - 2) * math.cos(ga), cy + (r - sw / 2 - 2) * math.sin(ga)
    gx2, gy2 = cx + (r + sw / 2 + 2) * math.cos(ga), cy + (r + sw / 2 + 2) * math.sin(ga)
    sub = f"{run:,} of {lines:,} lines" if run is not None and lines else "lines run"
    tip = html.escape(f"{label}: {p:g}% ({sub})" if label else f"{p:g}% ({sub})")
    arc = (f"<circle cx='{cx}' cy='{cy}' r='{r:.1f}' fill='none' stroke='{colour(p, goal)}' stroke-width='{sw:.1f}' "
           f"stroke-dasharray='{p / 100 * circ:.2f} {circ:.2f}' transform='rotate(-90 {cx} {cy})'/>") if p > 0 else ""
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {size} {size}' width='{size}' height='{size}' role='img' "
            f"aria-label='{tip}'><title>{tip}</title>"
            f"<circle cx='{cx}' cy='{cy}' r='{r:.1f}' fill='none' stroke='{GRID}' stroke-opacity='0.3' stroke-width='{sw:.1f}'/>"
            f"{arc}<line x1='{gx1:.1f}' y1='{gy1:.1f}' x2='{gx2:.1f}' y2='{gy2:.1f}' stroke='currentColor' stroke-width='2'/>"
            f"<text x='{cx}' y='{cy + size * 0.03:.1f}' text-anchor='middle' font-size='{size * 0.17:.0f}' font-weight='700' "
            f"fill='currentColor'>{p:g}%</text>"
            f"<text x='{cx}' y='{cy + size * 0.15:.1f}' text-anchor='middle' font-size='{max(9, size * 0.065):.0f}' "
            f"fill='currentColor' opacity='0.7'>{html.escape(sub)}</text></svg>")


def to_reach(percent, bar: float, total, done, what: str = "lines") -> str:
    """How far a figure is from its bar, in the owner's words (25 Nov 2026, 16:24: "show the actual measure that you say
    here"): "short by 6.7 points: about 783 more lines to run", or "at or over the goal of 85%". The same as the app's
    Summary screen (FullSummary.jsx toReach) and the summary page (eaxcli/fullreport.to_reach)."""
    if percent is None or not total:
        return "-"
    p, b = float(percent), float(bar or GOAL)
    if p >= b:
        return f"at or over the {'bar' if what == 'screens' else 'goal'} of {b:g}%"
    more = max(0, math.ceil(b * float(total) / 100 - float(done or 0)))
    return f"short by {b - p:.1f} points: about {more:,} more {'screens covered' if what == 'screens' else 'lines to run'}"


def rings_svg(c: dict) -> str:
    """The ring of the goal's measure, the API (eax/api, D926; before it our own code, eax), and smaller rings beside it:
    the background jobs, all the server's code, and, when the run's coverage is joined with the unit tests' (D807), each
    of the two."""
    if c.get("percent") is None:
        return ""
    goal = float(c.get("goal") or GOAL)
    together = " (this run and the unit tests together)" if c.get("unit") is not None else ""
    if c.get("goal_percent") is not None:
        main = f"<figure class='cov-ring'>{ring_svg(c['goal_percent'], c.get('goal_run'), c.get('goal_lines'), 190, 'The API', goal)}" \
               f"<figcaption>The API (eax/api), the goal's measure{together}: " \
               f"{html.escape(to_reach(c['goal_percent'], goal, c.get('goal_lines'), c.get('goal_run')))}" \
               + (f"; {c['goal_left_out_lines']} lines left out (pairing, the routes that stop, restart, restore or wipe "
                  "the installation, the self-test's own controls)" if c.get("goal_left_out_lines") else "") + "</figcaption></figure>"
        extra = [(c.get("jobs_percent"), "The background jobs (shown, not judged)"), (c.get("percent"), "All the server's code")]
    else:
        main = f"<figure class='cov-ring'>{ring_svg(c['percent'], c.get('run'), c.get('lines'), 190, 'Our code', goal)}" \
               f"<figcaption>Our code, every line{together}</figcaption></figure>"
        extra = []
    extra_html = "".join(f"<figure class='cov-ring'>{ring_svg(v, size=120, label=t, goal=goal)}<figcaption>{t}</figcaption></figure>"
                         for v, t in extra if v is not None)
    parts = [(c.get("live"), "This run alone"), (c.get("unit"), "The unit tests alone (eax dev check)")]
    small = "".join(f"<figure class='cov-ring'>{ring_svg(v, size=120, label=t, goal=goal)}<figcaption>{t}</figcaption></figure>"
                    for v, t in parts if v is not None and c.get("unit") is not None)
    return f"<div class='cov-rings' style='display:flex;flex-wrap:wrap;gap:16px;align-items:center'>{main}{extra_html}{small}</div>"


def screens_svg(scr: dict | None) -> str:
    """The screens covered by the journeys against their bar (D924, D926), as a ring with its figures under it."""
    if not scr or not scr.get("screens"):
        return ""
    bar = float(scr.get("bar") or GOAL)
    sub = (f"{scr.get('covered')} of {scr.get('screens')} screens, bar {bar:g}%: "
           f"{to_reach(scr.get('percent'), bar, scr.get('screens'), scr.get('covered'), 'screens')}; controls used "
           f"{scr.get('controls_used')} of {scr.get('controls')} ({scr.get('controls_percent')}%)")
    return (f"<figure class='cov-ring'>{ring_svg(float(scr.get('percent') or 0.0), size=190, label='The screens', goal=bar)}"
            f"<figcaption>{html.escape(sub)}</figcaption></figure>")


def overall(c: dict, scr: dict | None) -> float | None:
    """The overall coverage (owner, 25 Nov 2026, 16:34: "can there a an overall coverage ring too, these two can be under
    it"): the API's figure and the screens', counted equally (lines and screens are not the same unit), to one decimal;
    one alone when only it was measured. Bar 85% (D934). As eaxcli/fullreport.overall and FullSummary.jsx overall."""
    got = [float(x) for x in (c.get("goal_percent"), (scr or {}).get("percent") if (scr or {}).get("screens") else None)
           if x is not None]
    return round(sum(got) / len(got), 1) if got else None


def overall_svg(c: dict, scr: dict | None) -> str:
    """The overall ring, with the API's and the screens' rings under it; '' unless both were measured."""
    whole = overall(c, scr)
    if whole is None or c.get("goal_percent") is None or not (scr or {}).get("screens"):
        return ""
    goal, bar = float(c.get("goal") or GOAL), float(scr.get("bar") or GOAL)
    words = "at or over the bar" if whole >= GOAL else f"short by {GOAL - whole:.1f} points"
    return (f"<div class='cov-overall' style='display:flex;flex-direction:column;align-items:center;gap:8px'>"
            f"<figure class='cov-ring'>{ring_svg(whole, size=200, label='Overall', goal=GOAL)}"
            f"<figcaption>Overall: the API and the screens counted equally; bar {GOAL:g}%: {words}</figcaption></figure>"
            f"<div style='display:flex;gap:24px;flex-wrap:wrap;justify-content:center'>"
            f"<figure class='cov-ring'>{ring_svg(c['goal_percent'], c.get('goal_run'), c.get('goal_lines'), 130, 'The API', goal)}"
            f"<figcaption>The API</figcaption></figure>"
            f"<figure class='cov-ring'>{ring_svg(float(scr.get('percent') or 0.0), size=130, label='The screens', goal=bar)}"
            f"<figcaption>The screens</figcaption></figure></div></div>")


def charts(files: dict, points: list[dict] | None = None) -> dict[str, str]:
    """The pictures for a run (each '' when there is nothing to draw): the rings first (D824), then the four of R3.10."""
    c = files.get("coverage") or {}
    goal = float(c.get("goal") or GOAL)
    figure = c.get("goal_percent") if c.get("goal_percent") is not None else c.get("percent")
    return {"overall": overall_svg(c, files.get("screens")),
            "rings": rings_svg(c),
            "screens": screens_svg(files.get("screens")),
            "gauge": gauge_svg(float(figure), goal) if figure is not None else "",
            "areas": areas_svg(c.get("areas") or [], goal),
            "trend": trend_svg(points or [], goal),
            "negative": negative_svg(files.get("negative"))}


def summary_line(files: dict) -> str:
    """One line for `eax test`'s summary: the coverage against the goal and the negative tests."""
    c, neg = files.get("coverage") or {}, files.get("negative")
    parts = []
    scr = files.get("screens") or {}
    whole = overall(c, scr)
    if whole is not None and c.get("goal_percent") is not None and scr.get("screens"):
        parts.append(f"Overall {whole:g}% (the API and the screens counted equally; bar {GOAL:g}%: "
                     + ("at or over it)" if whole >= GOAL else f"short by {GOAL - whole:.1f} points)"))
    if c.get("goal_percent") is not None:          # the goal's measure: the API, eax/api (D926)
        goal = float(c.get("goal") or GOAL)
        parts.append(f"The API {c['goal_percent']:g}% of its {c.get('goal_lines', 0):,} lines (goal {goal:g}%: "
                     f"{to_reach(c['goal_percent'], goal, c.get('goal_lines'), c.get('goal_run'))})"
                     + (f", background jobs {c['jobs_percent']:g}%" if c.get("jobs_percent") is not None else "")
                     + f", all the server's code {c['percent']:g}%")
    elif c.get("percent") is not None:
        goal = float(c.get("goal") or GOAL)
        worst = (sorted(c.get("areas") or [], key=lambda a: a.get("percent", 0.0)) or [{}])[0]
        parts.append(f"Coverage {c['percent']:g}% of the API's lines (goal {goal:g}%"
                     + (f", was {c['before']:g}%" if c.get("before") is not None else "") + ")"
                     + (f"; least covered: {worst['area']} {worst['percent']:g}%" if worst.get("area") else ""))
    if scr.get("screens"):
        bar = float(scr.get("bar") or GOAL)
        parts.append(f"the screens {scr.get('percent')}% covered by journeys ({scr.get('covered')} of {scr.get('screens')}; "
                     f"bar {bar:g}%: {to_reach(scr.get('percent'), bar, scr.get('screens'), scr.get('covered'), 'screens')})")
    if neg:
        t = negative_totals(neg)
        parts.append(f"negative tests {sum(t.values())}: {t['passed']} passed, {t['warning']} warnings, {t['failed']} failed")
    return "; ".join(parts)


def html_section(files: dict, points: list[dict] | None = None) -> str:
    """The report's section: the four pictures, or a line saying the run kept no coverage."""
    ch = charts(files, points)
    if not any(ch.values()):
        return ("<h2>Code coverage</h2><p class='q'>This run kept no code coverage (EAX_COVERAGE=on measures it) and ran no "
                "negative tests.</p>")
    figs = [(k, t) for k, t in (("overall", "Overall: the API and the screens"), ("rings", "The API's lines run, against the goal"),
                                ("screens", "The screens covered by journeys, against the bar"),
                                ("gauge", "Share of the API's lines run"), ("areas", "By area, the least covered first"),
                                ("trend", "Over the last runs of this kind"), ("negative", "Negative tests by kind")) if ch[k]]
    line = html.escape(summary_line(files))
    return ("<h2>Code coverage</h2>" + (f"<p>{line}</p>" if line else "") + "<div class='covcharts'>"
            + "".join(f"<figure>{ch[k]}<figcaption>{t}</figcaption></figure>" for k, t in figs) + "</div>")
