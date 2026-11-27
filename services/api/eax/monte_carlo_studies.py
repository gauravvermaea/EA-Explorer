"""Monte Carlo studies in a project (Release 14.7, R14.7.2 to R14.7.6; D957, D962).

A **study** answers one question with ranges instead of single numbers, and is kept in the project's own tables, the
model never changed (D957 (3)); a project may hold several, side by side (the supplier's estimates and our own). Four
kinds (D957 (1)):

* **roadmap** (roadmap confidence): the work packages' durations as ranges and what each waits for; how likely the
  end, or a milestone (a set of work packages), is by a date; which work packages are most often on the critical path.
* **business_case** (an option's cost and benefit): benefit and cost lines as ranges; the range of net value and the
  chance it is positive; the lines that matter most.
* **risk** (risk exposure): risks as events, each with a chance in the year (or a Likelihood 1 to 5) and a loss (a
  range, or an Impact 1 to 5), optionally their chance after controls; the chance the year's losses pass an amount,
  before and after controls; the risks that drive it. Likelihood and Impact become numbers by the organisation's risk
  scale, set once (D957 (6)), which a risk may override with its own chance and amounts.
* **scenarios** (scenario planning with chances): each option's score in each future as a range; each option's chance
  of being best, in each future and across them (weighted by how likely each future is, when given).

The ranges are drafted by the person's AI through MCP (a preview, then a yes, D458) or typed on the project's Monte
Carlo tab (D957 (2)); each input says who set it and where it came from. Every figure is EA Explorer's own code
(eax/monte_carlo.py), never the AI's (D857 (4)). A **run** is kept with the inputs, groups, settings and seed it used,
so it can be opened later and shows the same numbers, and run again gives the same answer. Reading needs a role on
the project; changing and running a contributing role; the risk scale is set by a Super Admin. Nothing here is logic in
the database (D248).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text

from . import monte_carlo as mc
from . import projects as pj
from .metamodel_edit import EditError

KINDS = {
    "roadmap": {"name": "Roadmap confidence",
                "answers": "How likely the work packages end, or a milestone is reached, by a date; which work packages "
                           "decide it most often."},
    "business_case": {"name": "An option's business case",
                      "answers": "The range of an option's net value (benefits less costs) and the chance it is positive."},
    "risk": {"name": "Risk exposure",
             "answers": "The chance the year's losses pass an amount, before and after controls; the risks that drive it."},
    "scenarios": {"name": "Scenario planning with chances",
                  "answers": "Each option's chance of being best, in each future and across them."},
}
UNITS = ("days", "weeks", "months")
SIDES = ("benefit", "cost")
MAX_INPUTS = 500
MAX_GROUPS = 50
DEFAULT_SCALE = {   # a starting point the organisation changes (System admin, Super Admins): the chance in a year, a loss
    "likelihood": {"1": 0.05, "2": 0.15, "3": 0.35, "4": 0.6, "5": 0.85},
    "impact": {"1": [0, 10_000, 50_000], "2": [50_000, 150_000, 500_000], "3": [500_000, 1_500_000, 5_000_000],
               "4": [5_000_000, 15_000_000, 50_000_000], "5": [50_000_000, 150_000_000, 500_000_000]},
    "currency": "",
}
STEPS = [
    "1. Choose what the study answers (mc_kinds): roadmap, business_case, risk or scenarios; start it (mc_start).",
    "2. Read the project's documents and models for the numbers (work packages, cost lines, risks, options), and ask "
    "the people who own them.",
    "3. Draft each input as three numbers (low, most likely, high) or, for a risk, a chance and a loss; say where each "
    "came from (source). Save them (mc_save inputs) after the person's yes.",
    "4. Ask which inputs move together (one supplier, one currency) and how strongly; save them (mc_save groups).",
    "5. Settings: a roadmap's target and milestones, a risk study's amounts, the futures' weights (mc_save settings).",
    "6. Run it (mc_run): EA Explorer's engine does the working; explain the result in plain words with its link.",
]


def _rows(conn, sql: str, **p) -> list[dict]:
    return [dict(r) for r in conn.execute(text(sql), p).mappings().all()]


def _one(conn, sql: str, **p) -> dict | None:
    r = _rows(conn, sql, **p)
    return r[0] if r else None


# ---------------------------------------------------------------- the rows (the only SQL)
def _scale_row(pc) -> dict | None:
    return _one(pc, "SELECT likelihood, impact, currency, set_by, set_at FROM proj.mc_risk_scale WHERE id = 1")


def _save_scale(pc, clean: dict, who: str) -> None:
    pc.execute(text("""INSERT INTO proj.mc_risk_scale (id, likelihood, impact, currency, set_by)
                       VALUES (1, CAST(:l AS jsonb), CAST(:i AS jsonb), :c, :u)
                       ON CONFLICT (id) DO UPDATE SET likelihood = EXCLUDED.likelihood, impact = EXCLUDED.impact,
                           currency = EXCLUDED.currency, set_by = EXCLUDED.set_by, set_at = now()"""),
               {"l": json.dumps(clean["likelihood"]), "i": json.dumps(clean["impact"]), "c": clean["currency"], "u": who})


def _studies(pc, p: dict) -> list[dict]:
    return _rows(pc, "SELECT * FROM proj.mc_studies WHERE project_id = :p ORDER BY lower(name)", p=p["id"])


def _runs(pc, s: dict) -> list[dict]:
    return _rows(pc, "SELECT * FROM proj.mc_runs WHERE study_id = :s ORDER BY number DESC", s=s["id"])


def _insert_study(pc, row: dict) -> dict:
    return _one(pc, """INSERT INTO proj.mc_studies (project_id, name, kind, question, currency, unit, created_by, updated_by)
                       VALUES (:project_id, :name, :kind, :question, :currency, :unit, :by, :by) RETURNING *""", **row)


def _update_study(pc, sid: int, sets: dict, who: str) -> None:
    cols = ", ".join(f"{k} = CAST(:{k} AS jsonb)" if k in ("inputs", "groups", "settings") else f"{k} = :{k}" for k in sets)
    pc.execute(text(f"UPDATE proj.mc_studies SET {cols}, updated_by = :by, updated_at = now() WHERE id = :id"),
               {"id": sid, "by": who, **{k: json.dumps(v) if k in ("inputs", "groups", "settings") else v for k, v in sets.items()}})


def _delete_study(pc, sid: int) -> None:
    pc.execute(text("DELETE FROM proj.mc_studies WHERE id = :id"), {"id": sid})


def _insert_run(pc, row: dict) -> dict:
    return _one(pc, """INSERT INTO proj.mc_runs (study_id, number, inputs, runs, seed, digest, result, run_by)
                       VALUES (:study_id, :number, CAST(:inputs AS jsonb), :runs, :seed, :digest, CAST(:result AS jsonb), :by)
                       RETURNING *""", **{**row, "inputs": json.dumps(row["inputs"]), "result": json.dumps(row["result"])})


def _text(v: Any, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


def _num(v: Any, what: str) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError) as exc:
        raise EditError(f"{what} must be a number.") from exc
    if x != x or x in (float("inf"), float("-inf")):
        raise EditError(f"{what} must be a number.")
    return x


def kinds() -> list[dict]:
    """What each kind of study answers."""
    return [{"kind": k, **v} for k, v in KINDS.items()]


# ---------------------------------------------------------------- the risk scale (the organisation's, set once)
def risk_scale(pc) -> dict:
    """What Likelihood and Impact 1 to 5 mean: the organisation's, or the defaults until a Super Admin sets them."""
    r = _scale_row(pc)
    if not r:
        return {**DEFAULT_SCALE, "set_by": None, "set_at": None, "default": True}
    return {"likelihood": r["likelihood"], "impact": r["impact"], "currency": r["currency"], "set_by": r["set_by"],
            "set_at": r["set_at"].isoformat() if r["set_at"] else None, "default": False}


def clean_scale(data: Any) -> dict:
    """A risk scale checked: a chance (0 to 1, rising) for each Likelihood 1 to 5; a loss [low, likely, high] for each
    Impact 1 to 5, each in order and rising (pure)."""
    if not isinstance(data, dict):
        raise EditError("The scale is {likelihood: {1..5: chance}, impact: {1..5: [low, likely, high]}, currency}.")
    lk, im = data.get("likelihood") or {}, data.get("impact") or {}
    out_l, out_i = {}, {}
    for lvl in "12345":
        c = _num(lk.get(lvl, lk.get(int(lvl))) if isinstance(lk, dict) else None, f"Likelihood {lvl}'s chance")
        if not 0 <= c <= 1:
            raise EditError(f"Likelihood {lvl}'s chance is 0 to 1.")
        out_l[lvl] = c
        three = im.get(lvl, im.get(int(lvl))) if isinstance(im, dict) else None
        if not isinstance(three, list | tuple) or len(three) != 3:
            raise EditError(f"Impact {lvl} is [low, likely, high].")
        lo, li, hi = (_num(x, f"Impact {lvl}") for x in three)
        if not 0 <= lo <= li <= hi:
            raise EditError(f"Impact {lvl} runs 0 <= low <= likely <= high.")
        out_i[lvl] = [lo, li, hi]
    for a, b in zip("1234", "2345", strict=True):
        if out_l[a] > out_l[b]:
            raise EditError(f"Likelihood {b}'s chance is lower than {a}'s.")
        if out_i[a][1] > out_i[b][1]:
            raise EditError(f"Impact {b}'s likely loss is lower than {a}'s.")
    return {"likelihood": out_l, "impact": out_i, "currency": _text(data.get("currency"), 8)}


def set_risk_scale(pc, user, data: Any, confirm: bool = True) -> dict:
    """The organisation's risk scale set (Super Admins); every study's risks given as levels use it from the next run."""
    if not pj._super(user):
        raise EditError("The risk scale is set by a Super Admin.", 403)
    clean = clean_scale(data)
    plan = {"will": ["set the organisation's risk scale: every risk given as a Likelihood or an Impact level uses it "
                     "from its study's next run (runs made before keep the scale they used)"], "scale": clean}
    if not confirm:
        return {"preview": plan}
    _save_scale(pc, clean, user.username)
    return {"message": "The risk scale is set.", "scale": risk_scale(pc)}


# ---------------------------------------------------------------- checking a study's parts (pure)
def _range_of(item: dict, what: str, lo_ok_negative: bool = False) -> dict:
    lo, li, hi = (_num(item.get(k), f"{what}: {k}") for k in ("low", "likely", "high"))
    if not lo_ok_negative and lo < 0:
        raise EditError(f"{what}: low is 0 or more.")
    if not lo <= li <= hi:
        raise EditError(f"{what}: the range runs low <= likely <= high ({lo:g}, {li:g}, {hi:g}).")
    shape = str(item.get("shape") or "pert").lower()
    if shape not in mc.SHAPES:
        raise EditError(f"{what}: the shape is pert or triangular (log-normal waits).")
    return {"low": lo, "likely": li, "high": hi, "shape": shape}


def _level(v: Any, what: str) -> str:
    s = str(v).strip()
    if s not in ("1", "2", "3", "4", "5"):
        raise EditError(f"{what} is 1 to 5.")
    return s


def _chance(v: Any, what: str) -> float:
    c = _num(v, what)
    if not 0 <= c <= 1:
        raise EditError(f"{what} is from 0 to 1 (a share: 0.2 is 20%).")
    return c


def clean_inputs(kind: str, items: Any, who: str, by: str, before: list[dict] | None = None) -> list[dict]:
    """A study's inputs checked for its kind (pure). An input unchanged from `before` keeps who set it and when."""
    if not isinstance(items, list):
        raise EditError("The inputs are a list.")
    if len(items) > MAX_INPUTS:
        raise EditError(f"At most {MAX_INPUTS} inputs in a study.")
    old = {i["name"]: i for i in before or []}
    out, names = [], set()
    for n, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            raise EditError(f"Input {n} is not an object.")
        if kind == "scenarios":
            option, future = _text(raw.get("option"), 120), _text(raw.get("future"), 120)
            if not option or not future:
                raise EditError(f"Input {n}: a score needs its option and its future.")
            name = f"{option} in {future}"
        else:
            name = _text(raw.get("name"), 200)
        if not name:
            raise EditError(f"Input {n} has no name.")
        if name.lower() in names:
            raise EditError(f"Two inputs are called {name}.")
        names.add(name.lower())
        what = f"{name}"
        item: dict[str, Any] = {"name": name}
        if kind == "roadmap":
            item |= _range_of(raw, what)
            after = raw.get("after") or []
            if not isinstance(after, list):
                raise EditError(f"{what}: after is a list of the work packages it waits for.")
            item["after"] = [_text(a, 200) for a in after if _text(a, 200)]
        elif kind == "business_case":
            side = str(raw.get("side") or "").lower()
            if side not in SIDES:
                raise EditError(f"{what}: side is benefit or cost.")
            item |= {"side": side, **_range_of(raw, what)}
        elif kind == "scenarios":
            item |= {"option": option, "future": future, **_range_of(raw, what, lo_ok_negative=True)}
        elif kind == "risk":
            if raw.get("chance") not in (None, ""):
                item["chance"] = _chance(raw["chance"], f"{what}: chance")
            elif raw.get("likelihood") not in (None, ""):
                item["likelihood"] = _level(raw["likelihood"], f"{what}: Likelihood")
            else:
                raise EditError(f"{what}: give its chance in a year (0 to 1) or its Likelihood (1 to 5).")
            if all(raw.get(k) not in (None, "") for k in ("low", "likely", "high")):
                item |= _range_of(raw, f"{what}'s loss")
            elif raw.get("impact") not in (None, ""):
                item["impact"] = _level(raw["impact"], f"{what}: Impact")
            else:
                raise EditError(f"{what}: give its loss (low, likely, high) or its Impact (1 to 5).")
            if raw.get("chance_after") not in (None, ""):
                item["chance_after"] = _chance(raw["chance_after"], f"{what}: chance after controls")
            elif raw.get("likelihood_after") not in (None, ""):
                item["likelihood_after"] = _level(raw["likelihood_after"], f"{what}: Likelihood after controls")
        else:
            raise EditError(f"A study's kind is one of {', '.join(KINDS)}.")
        item["source"] = _text(raw.get("source"), 500)
        prev = old.get(name)
        same = prev and all(prev.get(k) == item.get(k) for k in item)
        item["by"] = prev.get("by", by) if same else by
        item["set_by"] = prev.get("set_by", who) if same else who
        out.append(item)
    if kind == "roadmap":
        known = {i["name"] for i in out}
        for i in out:
            for a in i["after"]:
                if a not in known:
                    raise EditError(f"{i['name']} waits for {a}, which is not one of the work packages.")
        try:
            mc.order_of({i["name"]: mc.Range(0, 0, 0) for i in out}, {i["name"]: i["after"] for i in out if i["after"]})
        except ValueError as exc:
            raise EditError(str(exc)) from exc
    return out


def clean_groups(groups: Any, inputs: list[dict]) -> list[dict]:
    """The "move together" groups checked: a name, members among the inputs, a strength; an input in one group only (pure)."""
    if not isinstance(groups, list):
        raise EditError("The groups are a list of {name, members, strength}.")
    if len(groups) > MAX_GROUPS:
        raise EditError(f"At most {MAX_GROUPS} groups.")
    names = {i["name"] for i in inputs}
    out, seen = [], {}
    for n, g in enumerate(groups, 1):
        if not isinstance(g, dict):
            raise EditError(f"Group {n} is not an object.")
        name = _text(g.get("name"), 120)
        if not name:
            raise EditError(f"Group {n} has no name.")
        strength = str(g.get("strength") or "medium").lower()
        if strength not in mc.STRENGTHS:
            raise EditError(f"Group {name}: the strength is weak, medium or strong.")
        members = [_text(m, 200) for m in g.get("members") or [] if _text(m, 200)]
        if len(members) < 2:
            raise EditError(f"Group {name} needs at least two members.")
        for m in members:
            if m not in names:
                raise EditError(f"Group {name} names {m}, which is not one of the inputs.")
            if m in seen:
                raise EditError(f"{m} is in two groups ({seen[m]} and {name}).")
            seen[m] = name
        out.append({"name": name, "members": members, "strength": strength})
    return out


def clean_settings(kind: str, s: Any, inputs: list[dict]) -> dict:
    """A study's settings checked (pure): a roadmap's target and milestones, a risk study's amounts, the futures'
    weights for scenarios."""
    if s in (None, ""):
        return {}
    if not isinstance(s, dict):
        raise EditError("The settings are an object.")
    out: dict[str, Any] = {}
    if kind == "roadmap":
        if s.get("target") not in (None, ""):
            out["target"] = _num(s["target"], "The target")
        names = {i["name"] for i in inputs}
        ms = []
        for m in s.get("milestones") or []:
            name = _text(m.get("name"), 120)
            packages = [p for p in (m.get("packages") or []) if p]
            if not name or not packages:
                raise EditError("A milestone has a name and the work packages that reach it.")
            for p in packages:
                if p not in names:
                    raise EditError(f"Milestone {name} names {p}, which is not one of the work packages.")
            ms.append({"name": name, "packages": packages,
                       **({"by": _num(m["by"], f"Milestone {name}'s date")} if m.get("by") not in (None, "") else {})})
        if ms:
            out["milestones"] = ms
    elif kind == "risk":
        amounts = s.get("amounts") or []
        if not isinstance(amounts, list):
            raise EditError("The amounts are a list of numbers.")
        out["amounts"] = sorted({_num(a, "An amount") for a in amounts})[:12]
    elif kind == "scenarios":
        w = s.get("weights")
        if w:
            futures = sorted({i["future"] for i in inputs})
            if not isinstance(w, dict) or sorted(w) != futures:
                raise EditError(f"Give a weight for every future ({', '.join(futures)}).")
            ws = {f: _num(w[f], f"{f}'s weight") for f in futures}
            if any(v < 0 for v in ws.values()) or sum(ws.values()) <= 0:
                raise EditError("The weights are 0 or more, and not all 0.")
            out["weights"] = ws
    return out


# ---------------------------------------------------------------- the working (pure)
def _range(i: dict) -> mc.Range:
    return mc.Range(i["low"], i["likely"], i["high"], i.get("shape", "pert"))


def _risk_event(i: dict, scale: dict, after: bool = False) -> mc.Event:
    if after:
        chance = i["chance_after"] if "chance_after" in i else (
            scale["likelihood"][i["likelihood_after"]] if "likelihood_after" in i else None)
        if chance is None:
            chance = i["chance"] if "chance" in i else scale["likelihood"][i["likelihood"]]
    else:
        chance = i["chance"] if "chance" in i else scale["likelihood"][i["likelihood"]]
    loss = _range(i) if "low" in i else mc.Range(*scale["impact"][i["impact"]])
    return mc.Event(chance, loss)


def _groups(study: dict, names: set[str]) -> list[mc.Group]:
    return [mc.Group(g["name"], [m for m in g["members"] if m in names], g["strength"])
            for g in study.get("groups") or [] if len([m for m in g["members"] if m in names]) >= 1]


def _complete(kind: str, inputs: list[dict]) -> None:
    if not inputs:
        raise EditError("The study has no inputs yet: add them on the tab, or ask your AI to draft them.")
    if kind == "scenarios":
        options = sorted({i["option"] for i in inputs})
        futures = sorted({i["future"] for i in inputs})
        have = {(i["option"], i["future"]) for i in inputs}
        missing = [f"{o} in {f}" for o in options for f in futures if (o, f) not in have]
        if missing:
            raise EditError("Every option needs a score in every future; missing: " + ", ".join(missing[:10]) + ".")


def work(study: dict, scale: dict, runs: int, seed: int) -> dict:
    """A study worked out by the engine: the figures for its kind, each part said in words too (pure)."""
    kind, inputs = study["kind"], study.get("inputs") or []
    settings = study.get("settings") or {}
    _complete(kind, inputs)
    names = {i["name"] for i in inputs}
    try:
        if kind == "roadmap":
            packages = {i["name"]: _range(i) for i in inputs}
            after = {i["name"]: i["after"] for i in inputs if i.get("after")}
            r = mc.schedule(packages, after, runs, seed, _groups(study, names))
            out = {"result": r.summary(), "unit": study.get("unit") or "weeks"}
            if settings.get("target") is not None:
                out["target"] = {"by": settings["target"], "chance": r.chance_at_most(settings["target"])}
            ms = []
            for m in settings.get("milestones") or []:
                need = _ancestors(m["packages"], after)
                sub = mc.schedule({k: packages[k] for k in need}, {k: v for k, v in after.items() if k in need},
                                  runs, seed, _groups(study, need))
                ms.append({"name": m["name"], "packages": m["packages"], "p50": sub.percentile(50), "p80": sub.percentile(80),
                           "p90": sub.percentile(90), **({"by": m["by"], "chance": sub.chance_at_most(m["by"])} if "by" in m else {})})
            if ms:
                out["milestones"] = ms
            out["in_words"] = _words_roadmap(out)
        elif kind == "business_case":
            benefits = {i["name"]: _range(i) for i in inputs if i["side"] == "benefit"}
            costs = {i["name"]: _range(i) for i in inputs if i["side"] == "cost"}
            r = mc.net(benefits, costs, runs, seed, _groups(study, names))
            out = {"result": r.summary(), "chance_positive": r.chance_above(0)}
            out["in_words"] = _words_business(out, study.get("currency") or "")
        elif kind == "risk":
            before = {i["name"]: _risk_event(i, scale) for i in inputs}
            r = mc.total(before, runs, seed, _groups(study, names))
            out = {"result": r.summary(), "chance_none": r.chance_at_most(0)}
            if any("chance_after" in i or "likelihood_after" in i for i in inputs):
                a = mc.total({i["name"]: _risk_event(i, scale, after=True) for i in inputs}, runs, seed, _groups(study, names))
                out["after"] = a.summary()
            out["amounts"] = [{"amount": x, "before": r.chance_above(x),
                               **({"after": a.chance_above(x)} if "after" in out else {})} for x in settings.get("amounts") or []]
            out["in_words"] = _words_risk(out, study.get("currency") or scale.get("currency") or "")
        elif kind == "scenarios":
            options = sorted({i["option"] for i in inputs})
            futures = sorted({i["future"] for i in inputs})
            scores = {o: {f: _range(next(i for i in inputs if i["option"] == o and i["future"] == f)) for f in futures}
                      for o in options}
            out = {"options": options, "futures": futures,
                   "across": mc.best(scores, runs, seed, settings.get("weights")),
                   "weighted": bool(settings.get("weights")),
                   "in_each": {f: mc.best({o: {f: scores[o][f]} for o in options}, runs, seed) for f in futures}}
            out["in_words"] = _words_scenarios(out)
        else:
            raise EditError(f"A study's kind is one of {', '.join(KINDS)}.")
    except ValueError as exc:
        raise EditError(str(exc)) from exc
    return out


def _ancestors(packages: list[str], after: dict[str, list[str]]) -> set[str]:
    seen, todo = set(), list(packages)
    while todo:
        k = todo.pop()
        if k not in seen:
            seen.add(k)
            todo += after.get(k, [])
    return seen


def _f(x: float) -> str:
    return f"{x:,.0f}" if abs(x) >= 100 else f"{x:,.1f}"


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def _words_roadmap(out: dict) -> list[str]:
    r, u = out["result"], out["unit"]
    said = [f"Half the runs end by {_f(r['p50'])} {u}, 80% by {_f(r['p80'])} and 90% by {_f(r['p90'])} "
            f"(from {_f(r['low'])} to {_f(r['high'])})."]
    if "target" in out:
        said.append(f"The chance of ending by {_f(out['target']['by'])} {u} is {_pct(out['target']['chance'])}.")
    for m in out.get("milestones") or []:
        said.append(f"{m['name']}: 80% by {_f(m['p80'])} {u}" + (f"; {_pct(m['chance'])} by {_f(m['by'])}" if "by" in m else "") + ".")
    crit = [(k, v) for k, v in (r.get("critical") or {}).items() if v > 0]
    if crit:
        said.append("Most often on the critical path: " + ", ".join(f"{k} ({_pct(v)})" for k, v in crit[:3]) + ".")
    return said


def _words_business(out: dict, cur: str) -> list[str]:
    r, c = out["result"], f"{cur} " if cur else ""
    return [f"The net value is {c}{_f(r['p50'])} in half the runs, between {c}{_f(r['p10'])} and {c}{_f(r['p90'])} in "
            "80% of them.", f"The chance it is positive (pays for itself): {_pct(out['chance_positive'])}."] + (
        [f"What matters most: {r['drivers'][0]['input']}."] if r["drivers"] and r["drivers"][0]["strength"] > 0 else [])


def _words_risk(out: dict, cur: str) -> list[str]:
    r, c = out["result"], f"{cur} " if cur else ""
    said = [f"In {_pct(out['chance_none'])} of years nothing happens; the losses average {c}{_f(r['mean'])}, and 1 year in 10 "
            f"they pass {c}{_f(r['p90'])}."]
    if "after" in out:
        said.append(f"After controls: 1 year in 10 above {c}{_f(out['after']['p90'])} (average {c}{_f(out['after']['mean'])}).")
    for a in out.get("amounts") or []:
        said.append(f"More than {c}{_f(a['amount'])}: {_pct(a['before'])} of years" + (f", {_pct(a['after'])} after controls" if "after" in a else "") + ".")
    if r["drivers"] and r["drivers"][0]["strength"] > 0:
        said.append("The risks that drive it most: " + ", ".join(d["input"] for d in r["drivers"][:3] if d["strength"] > 0) + ".")
    return said


def _words_scenarios(out: dict) -> list[str]:
    across = sorted(out["across"].items(), key=lambda kv: -kv[1])
    said = [("Weighted by how likely each future is" if out["weighted"] else "Over all the futures together") + ", the "
            "chance each option is best: " + ", ".join(f"{o} {_pct(c)}" for o, c in across) + "."]
    for f, ch in out["in_each"].items():
        top = max(ch.items(), key=lambda kv: kv[1])
        said.append(f"In {f}: {top[0]} is best {_pct(top[1])} of the time.")
    return said


# ---------------------------------------------------------------- reading
def _project(pc, project: Any, user, what: str = "read") -> dict:
    p = pj.project_row(pc, project)
    pj._need(pc, p, user, what)
    return p


def _study(pc, p: dict, study: Any) -> dict:
    key = str(study or "").strip()
    s = next((x for x in _studies(pc, p) if str(x["guid"]) == key or x["name"].lower() == key.lower()), None)
    if not s:
        raise EditError(f"{p['name']} has no Monte Carlo study {key}.", 404)
    return s


def _run_out(r: dict, full: bool = True) -> dict:
    out = {"id": str(r["guid"]), "number": r["number"], "runs": r["runs"], "seed": r["seed"], "digest": r["digest"],
           "run_by": r["run_by"], "run_at": r["run_at"].isoformat() if r.get("run_at") else None}
    if full:
        out |= {"inputs": r["inputs"], "result": r["result"]}
    else:
        out["in_words"] = (r["result"] or {}).get("in_words") or []
    return out


def _study_out(s: dict, runs: list[dict] | None = None, full: bool = True) -> dict:
    out = {"id": str(s["guid"]), "name": s["name"], "kind": s["kind"], "kind_name": KINDS.get(s["kind"], {}).get("name", s["kind"]),
           "question": s["question"], "currency": s["currency"], "unit": s["unit"], "runs": s["runs"], "seed": s["seed"],
           "created_by": s["created_by"], "updated_by": s["updated_by"],
           "updated_at": s["updated_at"].isoformat() if s.get("updated_at") else None, "inputs_count": len(s["inputs"] or [])}
    if full:
        out |= {"inputs": s["inputs"] or [], "groups": s["groups"] or [], "settings": s["settings"] or {}}
    if runs is not None:
        out["latest"] = _run_out(runs[0], full) if runs else None
        out["run_count"] = len(runs)
        if runs and full:
            out["changed_since"] = _changed(s, runs[0])
    return out


def _changed(s: dict, run: dict) -> bool:
    """Whether the study's inputs, groups or settings differ from what its latest run used (MC-S07)."""
    used = run["inputs"] or {}
    return any(json.dumps(used.get(k), sort_keys=True) != json.dumps(s[k] or ({} if k == "settings" else []), sort_keys=True)
               for k in ("inputs", "groups", "settings"))


def count(pc, p: dict) -> int:
    """How many Monte Carlo studies a project holds."""
    return len(_studies(pc, p))


def overview(pc, project: Any, user) -> dict:
    """A project's studies, each with its latest run in words; the kinds; the risk scale; what this person may do."""
    p = _project(pc, project, user)
    try:
        pj._need(pc, p, user, "contribute")
        may = True
    except EditError:
        may = False
    studies = [_study_out(s, _runs(pc, s)[:1], full=False) for s in _studies(pc, p)]
    return {"project": p["name"], "project_id": str(p["guid"]), "studies": studies, "kinds": kinds(), "units": list(UNITS),
            "shapes": list(mc.SHAPES), "strengths": list(mc.STRENGTHS), "risk_scale": risk_scale(pc), "may_change": may,
            "may_set_scale": bool(pj._super(user)), "steps": STEPS}


def get_study(pc, project: Any, user, study: Any) -> dict:
    """One study in full: its inputs, groups and settings, its runs (newest first) and the latest run in full."""
    p = _project(pc, project, user)
    s = _study(pc, p, study)
    runs = _runs(pc, s)
    out = _study_out(s, runs)
    out["runs_list"] = [_run_out(r, full=False) for r in runs]
    out["project"] = p["name"]
    return out


def get_run(pc, project: Any, user, study: Any, number: Any) -> dict:
    """One run of a study in full: the inputs it used and its results."""
    p = _project(pc, project, user)
    s = _study(pc, p, study)
    try:
        n = int(str(number).lstrip("#"))
    except ValueError as exc:
        raise EditError("A run is its number (1, 2, ...).", 404) from exc
    r = next((x for x in _runs(pc, s) if x["number"] == n), None)
    if not r:
        raise EditError(f"{s['name']} has no run {n}.", 404)
    return {"study": s["name"], "kind": s["kind"], **_run_out(r)}


def run_rows(pc, project: Any, user, study: Any, number: Any) -> tuple[list[list], str]:
    """A run as rows for a CSV: the percentiles and the chances (MC-R02)."""
    r = get_run(pc, project, user, study, number)
    res = r["result"]
    rows: list[list] = [["Study", r["study"]], ["Run", r["number"]], ["Runs", r["runs"]], ["Seed", r["seed"]], []]
    main = res.get("result")
    if main:
        rows += [["Figure", "Value"]] + [[k.upper() if k.startswith("p") else k, main[k]]
                                         for k in ("mean", "low", "p10", "p50", "p80", "p90", "high")]
        rows += [[], ["Input", "Strength (what drives the result)"]] + [[d["input"], d["strength"]] for d in main["drivers"]]
    if res.get("critical") or (main or {}).get("critical"):
        rows += [[], ["Work package", "Share of runs on the critical path"]] + [[k, v] for k, v in (main.get("critical") or {}).items()]
    for m in res.get("milestones") or []:
        rows.append([f"Milestone {m['name']}", m["p50"], m["p80"], m["p90"], m.get("chance", "")])
    if "chance_positive" in res:
        rows.append(["Chance the net value is positive", res["chance_positive"]])
    for a in res.get("amounts") or []:
        rows.append([f"Chance of losses above {a['amount']}", a["before"], a.get("after", "")])
    if "across" in res:
        rows += [[], ["Option", "Chance of being best"]] + [[o, c] for o, c in res["across"].items()]
        for f, ch in res["in_each"].items():
            rows += [[f"In {f}"]] + [[o, c] for o, c in ch.items()]
    rows += [[], ["In words"]] + [[w] for w in res.get("in_words") or []]
    return rows, f"{r['study']} run {r['number']}"


# ---------------------------------------------------------------- changing (a preview unless confirm)
def create(pc, project: Any, user, name: str, kind: str, question: str = "", currency: str = "", unit: str = "",
           confirm: bool = True) -> dict:
    """A new study in the project (no inputs yet)."""
    p = _project(pc, project, user, "contribute")
    name = _text(name, 120)
    if not name:
        raise EditError("Give the study a name.")
    if kind not in KINDS:
        raise EditError(f"A study's kind is one of {', '.join(KINDS)}.")
    unit = (unit or ("weeks" if kind == "roadmap" else "")).lower()
    if kind == "roadmap" and unit not in UNITS:
        raise EditError(f"A roadmap's durations are in {', '.join(UNITS)}.")
    if any(s["name"].lower() == name.lower() for s in _studies(pc, p)):
        raise EditError(f"{p['name']} already has a study called {name}.", 409)
    currency = _text(currency, 8) or (risk_scale(pc).get("currency") or "")
    plan = {"will": [f"make the study {name} in {p['name']}: {KINDS[kind]['name']}"
                     + (f", in {unit}" if unit else "") + (f", amounts in {currency}" if currency else "")]}
    if not confirm:
        return {"preview": plan}
    s = _insert_study(pc, {"project_id": p["id"], "name": name, "kind": kind, "question": _text(question, 1000),
                           "currency": currency, "unit": unit if kind == "roadmap" else "", "by": user.username})
    return {"study": _study_out(s, []), "message": f"The study {name} is made: add its inputs.",
            "link": f"/#/projects/{p['guid']}/montecarlo/{s['guid']}"}


def update(pc, project: Any, user, study: Any, data: dict, by: str = "person", confirm: bool = True) -> dict:
    """A study's name, question, currency, unit, runs, seed, inputs, groups or settings changed (each only when given)."""
    p = _project(pc, project, user, "contribute")
    s = _study(pc, p, study)
    if not isinstance(data, dict):
        raise EditError("Send the parts to change.")
    sets: dict[str, Any] = {}
    if data.get("name") not in (None, ""):
        name = _text(data["name"], 120)
        if name.lower() != s["name"].lower() and any(x["name"].lower() == name.lower() for x in _studies(pc, p)):
            raise EditError(f"{p['name']} already has a study called {name}.", 409)
        sets["name"] = name
    if "question" in data:
        sets["question"] = _text(data["question"], 1000)
    if "currency" in data:
        sets["currency"] = _text(data["currency"], 8)
    if "unit" in data and s["kind"] == "roadmap":
        if str(data["unit"]).lower() not in UNITS:
            raise EditError(f"A roadmap's durations are in {', '.join(UNITS)}.")
        sets["unit"] = str(data["unit"]).lower()
    if "runs" in data:
        n = int(_num(data["runs"], "Runs"))
        if not 100 <= n <= mc.MAX_RUNS:
            raise EditError(f"Runs is 100 to {mc.MAX_RUNS:,}.")
        sets["runs"] = n
    if "seed" in data:
        sets["seed"] = int(_num(data["seed"], "The seed")) % 2_000_000_000
    inputs = s["inputs"] or []
    if "inputs" in data:
        inputs = clean_inputs(s["kind"], data["inputs"], user.username, "ai" if by == "ai" else "person", inputs)
        sets["inputs"] = inputs
    groups = clean_groups(data["groups"], inputs) if "groups" in data else [
        g for g in (s["groups"] or []) if all(m in {i["name"] for i in inputs} for m in g["members"])]
    if "groups" in data or groups != (s["groups"] or []):
        sets["groups"] = groups
    if "settings" in data:
        sets["settings"] = clean_settings(s["kind"], data["settings"], inputs)
    if not sets:
        raise EditError("Nothing to change.")
    plan = {"will": [f"change {', '.join(sets)} of the study {s['name']}"],
            **{k: v for k, v in sets.items() if k in ("inputs", "groups", "settings")}}
    if not confirm:
        return {"preview": plan}
    _update_study(pc, s["id"], sets, user.username)
    return {"message": f"The study {sets.get('name', s['name'])} is saved.", "changed": list(sets),
            "study": get_study(pc, project, user, s["guid"])}


def delete(pc, project: Any, user, study: Any, confirm: bool = True) -> dict:
    """A study and its runs removed."""
    p = _project(pc, project, user, "contribute")
    s = _study(pc, p, study)
    n = len(_runs(pc, s))
    if not confirm:
        return {"preview": {"will": [f"delete the study {s['name']} and its {n} run(s)"]}}
    _delete_study(pc, s["id"])
    return {"message": f"The study {s['name']} and its {n} run(s) are deleted."}


def run(pc, project: Any, user, study: Any, runs: Any = None, seed: Any = None, confirm: bool = True) -> dict:
    """The study run by the engine and kept with the inputs, groups, settings and seed it used. The same inputs and seed
    give the same answer every time."""
    p = _project(pc, project, user, "contribute")
    s = _study(pc, p, study)
    n = int(_num(runs, "Runs")) if runs not in (None, "") else s["runs"]
    if not 100 <= n <= mc.MAX_RUNS:
        raise EditError(f"Runs is 100 to {mc.MAX_RUNS:,}.")
    sd = int(_num(seed, "The seed")) % 2_000_000_000 if seed not in (None, "") else s["seed"]
    scale = risk_scale(pc)
    result = work(s, scale, n, sd)
    used = {"kind": s["kind"], "inputs": s["inputs"] or [], "groups": s["groups"] or [], "settings": s["settings"] or {},
            "currency": s["currency"], "unit": s["unit"]}
    if s["kind"] == "risk":
        used["scale"] = {k: scale[k] for k in ("likelihood", "impact", "currency")}
    digest = hashlib.sha256(json.dumps([used, n, sd], sort_keys=True, default=str).encode("utf-8")).hexdigest()
    if not confirm:
        return {"preview": {"will": [f"run {s['name']} {n:,} times (seed {sd}) and keep the run"], "result": result}}
    number = max((r["number"] for r in _runs(pc, s)), default=0) + 1
    r = _insert_run(pc, {"study_id": s["id"], "number": number, "inputs": used, "runs": n, "seed": sd, "digest": digest,
                         "result": result, "by": user.username})
    return {"run": _run_out(r), "in_words": result.get("in_words") or [],
            "link": f"/#/projects/{p['guid']}/montecarlo/{s['guid']}", "message": f"Run {number} of {s['name']} is kept."}


# ---------------------------------------------------------------- the project report
def report_section(pc, p: dict) -> list[dict]:
    """Each study's latest run, in words, for the project report (MC-R01)."""
    out = []
    for s in _studies(pc, p):
        runs = _runs(pc, s)[:1]
        if runs:
            r = runs[0]
            out.append({"name": s["name"], "kind": KINDS.get(s["kind"], {}).get("name", s["kind"]), "run": r["number"],
                        "run_at": r["run_at"].isoformat() if r["run_at"] else None,
                        "in_words": (r["result"] or {}).get("in_words") or [],
                        "s_curve": ((r["result"] or {}).get("result") or {}).get("s_curve") or []})
    return out
