"""The screens' coverage, measured by the journeys (R14.5.1, D924; owner, 25 Nov 2026: "For screens we can measure
coverage not in code but in journyes, and I am ok with that").

Nothing in the screens' code is measured and nothing is built differently: in the browser suite the page sweep lists
every kind of screen and, on each, the controls a person can use (buttons, fields, choices, lists); the journeys note
the screen each of their actions happens on (a click, typing, a choice, a key) and the control it used. Then:

  covered      a screen a journey acts on ("Screen used + controls shown"); or a read-only screen, one with nothing to
               act on, opened and loaded by the sweep ("Just open and ensure it loads. This can be true for anyplace
               thats read only")
  controls     each screen's controls and how many of them the journeys used, so the thin spots show
  left out     controls that cannot safely be pressed on a running installation (stop, restart, restore, delete, switch
               the sign-in mode, update, ...): not counted, listed ("Left out, listed")

Kept as screens-coverage.json in the run's folder and as one result line; the summary page shows it beside the API's
figure. The bar is 90% of the screens counted (BAR; owner, 25 Nov 2026, 12:12). Pure functions, so
the unit tests check them; the browser side is CONTROLS_JS."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FILE = "screens-coverage.json"
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
# controls not pressed on a running installation (D924): what stops, restarts, restores, deletes, switches, wipes or
# updates it. Matched against a control's words.
RISKY = re.compile(r"\b(stop|restart|shut ?down|restore|delete|remove|purge|wipe|erase|reset|clean[- ]?up|switch|"
                   r"update now|start the update|upgrade|roll ?back|rotate|revoke|disable|break[- ]glass|kill|"
                   r"terminate|drop|uninstall|unpair|scale)\b", re.I)
# the screens' bar (owner, 25 Nov 2026, 12:12: "Bar for screens is currently 90%"): of the screens counted, the share
# covered; under it the result is a warning, as the API's goal (D923)
BAR = 90.0
# screens left out of the count, each with why, and listed with the figure (as the API's, owner, 11:02): what needs a
# second installation, restores this one, or starts a test run inside the test run
LEFT_OUT_SCREENS = {
    "#/admin/pairings": "pairing needs a second installation",
    "#/admin/disaster-recovery": "a DR copy needs a second installation (the DR drill covers it)",
    "#/admin/restores": "restores: eax test backup-restore covers them",
    "#/admin/self-test/run": "starts a test run inside the test run",
    "#/admin/self-test/performance": "the benchmark: never part of a test run (R5.29)",
}

# the screens the risky suite opens (D927): counted when the run has --risky, left out otherwise
RISKY_SCREENS = ("#/admin/restores",)

# where a project's frame controls are counted (CONTROLS_JS marks them)
FRAME_HOME = ("#/projects/{id}", "#/metamodel/{id}", "#/model-admin/{id}")

# the kinds of journey step that act on a screen, and the control each names
ACTS = ("click", "fill", "select", "choose", "press", "upload", "check", "drag", "download")   # a download presses its button

# the browser side: the controls a person can use on the page's own content and in an open pop-up dialog (the menu bar,
# the page's tab bars and the help panel are how one moves about, not the page's work). One entry a control: its words
# and its kind. The sweep reads it when a page opens; the journeys read it again before each action (25 Nov 2026: the
# first reading saw only what a page shows when it opens, so an action in a dialog or a later state matched nothing).
CONTROLS_JS = """() => {
  const main = document.querySelector('main') || document.body;
  const dialogs = [...document.querySelectorAll('[role=dialog]')].filter((d) => d.offsetParent !== null && !main.contains(d));
  const roots = [main, ...dialogs];
  const skip = (e) => e.closest('[role=tablist], .tabs, .nav-groups, .nav-menu, nav, .subtabs, .help-panel, .top-menu')
    || (e.closest('header') && !e.closest('[role=dialog]'));
  const shown = (e) => e.offsetParent !== null && !e.disabled;
  const words = (e) => {
    const lab = e.id && document.querySelector(`label[for="${CSS.escape(e.id)}"]`);
    const w = e.getAttribute('aria-label') || (lab && lab.innerText) || (e.closest('label') && e.closest('label').innerText)
      || e.innerText || e.value || e.placeholder || e.name || e.title || '';
    return w.split(/\\s+/).join(' ').trim().slice(0, 80);
  };
  // a project's or a model's own frame (its heading, Pin, Mark complete, Finish, the iteration bar; the model's icon,
  // Pin, Actions, Lock, Details) shows on every tab: marked, and counted on its own page only (Collector.page)
  const frame = (e) => !!e.closest('.project-head, .iteration-bar, .model-head');
  const out = [];
  const seen = new Set();
  const all = roots.flatMap((r) => [...r.querySelectorAll('button, input:not([type=hidden]), select, textarea, [role=button], [role=checkbox], [role=radio], summary')]);
  for (const e of all) {
    if (!shown(e) || skip(e)) continue;
    const kind = e.tagName === 'BUTTON' || e.getAttribute('role') === 'button' || e.tagName === 'SUMMARY' ? 'button'
      : e.tagName === 'SELECT' ? 'choice' : (e.type === 'checkbox' || e.type === 'radio' || /checkbox|radio/.test(e.getAttribute('role') || '')) ? 'tick'
      : 'field';
    const w = words(e);
    const key = kind + ':' + w.toLowerCase();
    if (!w || seen.has(key)) continue;
    seen.add(key);
    out.push(frame(e) ? { words: w, kind, frame: true } : { words: w, kind });
  }
  return out;
}"""


def screen(route: str) -> str:
    """One name for a kind of screen: the address without its question part, with ids, numbers and placeholders as {id}."""
    r = (route or "#/").strip().split("?", 1)[0]
    r = _UUID.sub("{id}", r)
    r = re.sub(r"/\d+(?=/|$)", "/{n}", r)
    # a generated id of letters and digits (a drawn view's, 25 Nov 2026: #/drawio/open/mwvv5exurqmy2g7g counted as a
    # screen of its own for each diagram opened): ten or more lower-case letters and digits, at least one digit
    r = re.sub(r"/(?=[a-z0-9]*\d)[a-z0-9]{10,}(?=/|$)", "/{id}", r)
    r = re.sub(r"\{\$?[a-z_]+\}", "{id}", r)
    return r.rstrip("/") or "#"


def risky(words: str) -> bool:
    """A control not pressed on a running installation (D924)."""
    return bool(RISKY.search(words or ""))


is_risky = risky                       # the name summarise uses, beside its risky flag


def acted(step: dict) -> tuple[str, str] | None:
    """(kind, the control's words) of a journey step that acts on the screen; None for one that only opens or looks."""
    for k in ACTS:
        if k in step:
            v = step[k]
            return k, str(v if not isinstance(v, dict) else v.get("label", "")).strip()
    return None


class Collector:
    """What one browser suite saw: each screen's controls (from the sweep) and the journeys' actions."""

    def __init__(self) -> None:
        self.controls: dict[str, list[dict]] = {}
        self.loaded: set[str] = set()
        self.actions: list[tuple[str, str, str]] = []

    def page(self, route: str, controls: list[dict] | None, loaded: bool) -> None:
        """The sweep opened route: its controls, and whether it loaded (no failure). A project's frame controls count on
        the project's own page only (25 Nov 2026: Pin, Mark complete, Finish and Choose… on every one of its 29 tabs kept
        a tab with nothing of its own from being read only); a model's the same, on the model's own page."""
        s = screen(route)
        have = self.controls.setdefault(s, [])
        known = {(c["kind"], c["words"].lower()) for c in have}
        for c in controls or []:
            if c.get("frame") and s not in FRAME_HOME:
                continue
            if (c.get("kind"), str(c.get("words", "")).lower()) not in known:
                have.append({"words": str(c.get("words", "")), "kind": str(c.get("kind", ""))})
                known.add((c.get("kind"), str(c.get("words", "")).lower()))
        if loaded:
            self.loaded.add(s)

    def action(self, route: str, step: dict) -> None:
        """A journey acted on route with step."""
        a = acted(step)
        if a:
            self.actions.append((screen(route), a[0], a[1]))


def _used(control: dict, actions: list[tuple[str, str]]) -> bool:
    """Whether a journey's action on the screen used this control (the step names the control by its words)."""
    w = control["words"].lower().strip(" ›…")
    for _kind, said in actions:
        s = said.lower().strip(" ›…")
        if s and (s == w or w.startswith(s) or s.startswith(w)):
            return True
    return False


def summarise(c: Collector, risky: bool = False) -> dict[str, Any]:
    """The screens' coverage from what the suite saw (D924). With the risky suite (D927) its screens count and the
    controls it may press (Delete, ...) are counted as any other; without it they are left out and listed."""
    left = {k: v for k, v in LEFT_OUT_SCREENS.items() if not (risky and k in RISKY_SCREENS)}
    by_screen: dict[str, list[tuple[str, str]]] = {}
    for s, kind, said in c.actions:
        by_screen.setdefault(s, []).append((kind, said))
    rows, left_out = [], []
    screens_left_out = [{"screen": s, "why": left[s]} for s in sorted(set(c.controls) | set(by_screen)) if s in left]
    for s in sorted(set(c.controls) | set(by_screen)):
        if s in left:
            continue
        controls = c.controls.get(s, [])
        if risky:
            safe, out = controls, []
        else:
            safe = [x for x in controls if not is_risky(x["words"])]
            out = [x for x in controls if is_risky(x["words"])]
        left_out += [{"screen": s, "words": x["words"], "kind": x["kind"]} for x in out]
        used = [x for x in safe if _used(x, by_screen.get(s, []))]
        read_only = not safe
        acted_on = bool(by_screen.get(s))
        covered = acted_on or (read_only and s in c.loaded)
        rows.append({"screen": s, "controls": len(safe), "used": len(used), "left_out": len(out),
                     "read_only": read_only, "acted_on": acted_on, "covered": covered,
                     "not_used": [x["words"] for x in safe if x not in used][:40]})
    n = len(rows)
    cov = sum(1 for r in rows if r["covered"])
    controls = sum(r["controls"] for r in rows)
    used = sum(r["used"] for r in rows)
    return {"risky": risky, "screens": n, "covered": cov, "percent": round(100 * cov / n, 1) if n else None,
            "acted_on": sum(1 for r in rows if r["acted_on"]), "read_only": sum(1 for r in rows if r["read_only"]),
            "controls": controls, "controls_used": used,
            "controls_percent": round(100 * used / controls, 1) if controls else None,
            "left_out": left_out, "not_covered": [r["screen"] for r in rows if not r["covered"]],
            "bar": BAR, "screens_left_out": screens_left_out, "by_screen": rows}


def save(folder: Path, result: dict) -> None:
    """screens-coverage.json in the run's folder."""
    (folder / FILE).write_text(json.dumps(result, indent=1), encoding="utf-8")


def line(result: dict) -> tuple[str, str]:
    """The result line: (outcome, detail): passed at or over the bar (BAR, 90%), a warning under it (as the API's goal)."""
    if not result.get("screens"):
        return "skipped", "no screen seen (the page sweep did not run)"
    bar = float(result.get("bar") or BAR)
    gone = result.get("screens_left_out") or []
    lowest = sorted((r for r in result["by_screen"] if r["controls"]),
                    key=lambda r: r["used"] / r["controls"])[:5]
    thin = ", ".join(f"{r['screen']} {r['used']}/{r['controls']}" for r in lowest)
    met = (result.get("percent") or 0.0) >= bar
    verdict = f"at or over the bar of {bar:g}%" if met else f"under the bar of {bar:g}% by {round(bar - (result.get('percent') or 0.0), 1)} points"
    return ("passed" if met else "warning"), (f"{verdict}: {result['percent']}% of {result['screens']} screens covered ({result['acted_on']} acted on by a "
                      f"journey, {result['read_only']} read only and opened); controls used {result['controls_used']} of "
                      f"{result['controls']} ({result['controls_percent']}%); {len(result['left_out'])} risky controls left "
                      f"out; {len(gone)} screens left out ({', '.join(g['screen'] for g in gone) or 'none'}); "
                      f"fewest controls used: {thin}; screens-coverage.json in the run's folder")


def summary(result: dict | None) -> dict | None:
    """The figures only, for the run's summary (run_summary.make)."""
    if not result or result.get("percent") is None:
        return None
    return {k: result.get(k) for k in ("screens", "covered", "percent", "acted_on", "read_only", "controls",
                                        "controls_used", "controls_percent")} | {
        "left_out": len(result.get("left_out") or []), "bar": result.get("bar"),
        "screens_left_out": len(result.get("screens_left_out") or [])}
