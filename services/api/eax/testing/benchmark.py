"""The performance suite: benchmarking (R5.18; owner, 14 Nov 2026: "automated performance test (bench marking)"; 15 Nov
2026, D695: k6 in a container of the test profile, `eax test performance`, compared with a kept baseline, part of the
full test).

How a run goes:
  1. the runner (here) fills the run's own test model to a fixed size (SIZES: small, medium or large) through the same
     functions as the screens and MCP, timing the writes that matter (adding elements, adding relationships, a commit);
  2. it times each read that matters (OPERATIONS: the start, the models, the tree, the grids, search, an element,
     reports, history), one person at a time, REPEATS times each: the median and the 95th percentile;
  3. it writes the plan for k6 (bench-plan.json, with the run's test users' tokens in a file the helper deletes) and the
     operations helper runs k6 in its container: USERS people at once for MINUTES, on the same reads, while it samples
     every container's memory and CPU (bench-load.json, bench-resources.json);
  4. when the run is collected, judge() compares each operation with the **baseline** of the last release and with the
     run before: one more than MARGIN (10% unless set) slower, a load-test error rate above 1%, or a container over its
     memory limit **fails** the run. The first passing run of a version becomes that version's baseline (kept in
     work/tests/benchmarks/<size>/), so each release is measured against the one before.
Nothing outside the run's own test data is written; the reads are the reads anyone signed in makes.
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import Callable
from pathlib import Path

SIZES = {"small": (300, 400), "medium": (3000, 4000), "large": (15000, 20000)}   # elements, relationships
REPEATS, MARGIN, ERROR_RATE = 10, 10.0, 0.01
PLAN, SINGLE, LOAD, RESOURCES, TOKENS = "bench-plan.json", "bench-single.json", "bench-load.json", "bench-resources.json", "bench-tokens.txt"
BASELINES = "benchmarks"
NOISE_MS = 25           # a difference smaller than this is never "slower": timer and network noise on fast reads
OPERATIONS: list[tuple[str, str, str]] = [
    ("me", "who am I (every page's first call)", "/api/v1/me"),
    ("models", "the models", "/api/v1/models"),
    ("tree", "a model's tree", "/api/v1/models/{model}/tree/types"),
    ("metamodel", "a model's metamodel", "/api/v1/models/{model}/tree/metamodel"),
    ("grid", "the grid of applications", "/api/v1/models/{model}/grids/entities/ApplicationComponent"),
    ("grid_rel", "the grid of relationships", "/api/v1/models/{model}/grids/relationships"),
    ("search", "search", "/api/v1/search?q=Bench"),
    ("element", "one element", "/api/v1/models/{model}/entities/{entity}"),
    ("reports", "a model's reports", "/api/v1/models/{model}/reports"),
    ("commits", "a model's history", "/api/v1/models/{model}/commits"),
]


def pct(values: list[float], p: float) -> float:
    """A percentile of the values (interpolated)."""
    if not values:
        return 0.0
    v = sorted(values)
    k = (len(v) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 1)


def summary(ms: list[float]) -> dict:
    """Timings as their count, median, 95th percentile and maximum."""
    return {"n": len(ms), "p50_ms": round(statistics.median(ms), 1) if ms else 0.0, "p95_ms": pct(ms, 95),
            "max_ms": round(max(ms), 1) if ms else 0.0}


def fill_data(me, model: str, size: str, as_, log) -> dict:
    """The run's test model filled to a size, timed: elements and relationships added in batches as MCP adds them, then
    a commit. Returns {operation: summary}."""
    from .. import mcp_build as mb
    n_el, n_rel = SIZES[size]
    out, half = {}, n_el // 2
    t = []
    for start in range(0, n_el, 500):
        names = [{"name": f"Bench {'application' if i < half else 'capability'} {i}"} for i in range(start, min(start + 500, n_el))]
        apps = [x for x in names if "application" in x["name"]]
        caps = [x for x in names if "capability" in x["name"]]
        t0 = time.perf_counter()
        if apps:
            as_(me, mb.add_entities(model, "ApplicationComponent", apps))
        if caps:
            as_(me, mb.add_entities(model, "Capability", caps))
        t.append((time.perf_counter() - t0) * 1000)
    out["add_elements"] = {**summary(t), "label": f"add {n_el} elements, 500 at a time"}
    t = []
    for start in range(0, n_rel, 500):
        rels = [{"relationship_type": "Association", "source": f"Bench application {i % half}",
                 "target": f"Bench capability {half + (i * 7) % (n_el - half)}"} for i in range(start, min(start + 500, n_rel))]
        t0 = time.perf_counter()
        try:
            as_(me, mb.add_relationships(model, rels))
        except Exception as exc:  # noqa: BLE001 - a repeated pair is refused: the rest still counts
            log(f"benchmark: some relationships not added: {str(exc)[:120]}")
        t.append((time.perf_counter() - t0) * 1000)
    out["add_relationships"] = {**summary(t), "label": f"add {n_rel} relationships, 500 at a time"}
    t0 = time.perf_counter()
    try:
        as_(me, mb.commit_my_changes(model, "Benchmark data"))
    except RuntimeError:
        pass
    out["commit"] = {**summary([(time.perf_counter() - t0) * 1000]), "label": "commit them"}
    return out


def paths(ids: dict[str, str]) -> list[tuple[str, str, str]]:
    """The operations' paths with the run's ids filled in (those without their id left out)."""
    out = []
    for key, label, p in OPERATIONS:
        try:
            out.append((key, label, p.format(**ids)))
        except KeyError:
            continue                                   # no such id in this run (no element): left out, said by the caller
    return out


def time_reads(base: str, token: str, ids: dict[str, str], call: Callable, repeats: int = REPEATS) -> dict:
    """Each read, one at a time, `repeats` times after one warm-up call: its median and 95th percentile."""
    out = {}
    for key, label, path in paths(ids):
        call(base, "get", path, token)
        ms, bad = [], 0
        for _ in range(repeats):
            t0 = time.perf_counter()
            status, _ = call(base, "get", path, token)
            ms.append((time.perf_counter() - t0) * 1000)
            bad += status >= 400
        out[key] = {**summary(ms), "label": label, "path": path, "errors": bad}
    return out


def plan(folder: Path, base: str, ids: dict[str, str], tokens: list[str], users: int, minutes: float, size: str) -> None:
    """What the helper's k6 runs: the same reads, as the run's own test users; the tokens in their own file (deleted by
    the helper when k6 ends)."""
    folder.joinpath(PLAN).write_text(json.dumps({"target": base, "size": size, "users": users, "minutes": minutes,
                                                 "paths": [p for _k, _l, p in paths(ids)]}), encoding="utf-8")
    t = folder / TOKENS
    t.write_text(",".join(tokens), encoding="utf-8")
    t.chmod(0o600)


# ---------------------------------------------------------------- judging, against the baseline
def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _vkey(v: str) -> tuple:
    out = []
    for part in v.split("-")[0].split("."):
        out.append(int(part) if part.isdigit() else 0)
    return tuple(out)


def baseline_for(root: Path, size: str, version: str) -> tuple[str, dict] | tuple[None, None]:
    """The newest baseline of a version before this one (the last release); else this version's own."""
    d = root / BASELINES / size
    files = sorted(d.glob("baseline-*.json"), key=lambda f: _vkey(f.stem.removeprefix("baseline-"))) if d.is_dir() else []
    older = [f for f in files if _vkey(f.stem.removeprefix("baseline-")) < _vkey(version)]
    pick = older[-1] if older else next((f for f in files if f.stem == f"baseline-{version}"), None)
    return (pick.stem.removeprefix("baseline-"), _read(pick)) if pick else (None, None)


def compare(now: dict, then: dict | None, margin: float = MARGIN) -> list[dict]:
    """Each operation's median against `then`'s: slower by more than `margin` per cent (and NOISE_MS) is a regression."""
    out = []
    for key, s in now.items():
        b = (then or {}).get(key)
        if not b or not b.get("p50_ms"):
            out.append({"op": key, "label": s.get("label", key), "now": s["p50_ms"], "then": None, "change": None, "slower": False})
            continue
        change = round((s["p50_ms"] - b["p50_ms"]) * 100 / b["p50_ms"], 1)
        slower = change > margin and s["p50_ms"] - b["p50_ms"] > NOISE_MS
        out.append({"op": key, "label": s.get("label", key), "now": s["p50_ms"], "then": b["p50_ms"], "change": change, "slower": slower})
    return out


def over_limit(res: dict | None) -> list[str]:
    """The containers that reached their memory limit under load."""
    return [f"{c} peaked at {v['peak_mb']:.0f} MB of {v['limit_mb']:.0f} MB" for c, v in sorted((res or {}).items())
            if v.get("limit_mb") and v.get("peak_mb", 0) >= v["limit_mb"] * 0.98]


def judge(folder: Path, record: Callable, version: str, margin: float = MARGIN) -> dict:
    """The run's figures against the baseline and the run before; the first passing run of a version is kept as its
    baseline. One result per operation and one for the load and the resources."""
    single = _read(folder / SINGLE)
    if not single:
        record("performance: benchmark", "skipped", "no benchmark figures in this run (the performance suite did not run)", 0)
        return {}
    size, ops = single["size"], single["operations"]
    root = folder.parent
    bver, base = baseline_for(root, size, version)
    prev = None
    runs = root / BASELINES / size / "runs"
    if runs.is_dir():
        older = sorted(f for f in runs.glob("*.json") if f.stem < folder.name)
        prev = _read(older[-1]) if older else None
    vs_base = compare(ops, (base or {}).get("operations"), margin)
    vs_prev = {c["op"]: c for c in compare(ops, (prev or {}).get("operations"), margin)}
    failed = False
    for c in vs_base:
        p = vs_prev.get(c["op"], {})
        line = f"median {c['now']} ms" + (f" (baseline {bver}: {c['then']} ms, {c['change']:+.1f}%)" if c["then"] is not None else
                                         " (no baseline yet)") + (f"; run before: {p['then']} ms ({p['change']:+.1f}%)" if p.get("then") else "") \
            + f"; p95 {ops[c['op']].get('p95_ms')} ms"
        bad = c["slower"] or ops[c["op"]].get("errors")
        failed |= bool(bad)
        record(f"performance: {c['label']}", "failed" if bad else "passed",
               (f"{margin:.0f}% slower than the baseline: " if c["slower"] else "") +
               (f"{ops[c['op']]['errors']} errors; " if ops[c["op"]].get("errors") else "") + line, int(c["now"]))
    load = _read(folder / LOAD)
    if load:
        rate = float(load.get("error_rate") or 0)
        bl = (base or {}).get("load") or {}
        worse = bl.get("p95_ms") and load.get("p95_ms", 0) > bl["p95_ms"] * (1 + margin / 100) and load["p95_ms"] - bl["p95_ms"] > NOISE_MS
        bad = rate > ERROR_RATE or bool(worse)
        failed |= bad
        record(f"performance: {load.get('users')} people at once for {load.get('minutes')} minutes (k6)", "failed" if bad else "passed",
               f"median {load.get('p50_ms')} ms, p95 {load.get('p95_ms')} ms, p99 {load.get('p99_ms')} ms, {load.get('requests')} requests "
               f"({load.get('per_second')}/s), errors {rate * 100:.2f}%" + (f"; baseline p95 {bl['p95_ms']} ms" if bl.get("p95_ms") else ""),
               int(load.get("p95_ms") or 0))
    else:
        record("performance: people at once (k6)", "skipped", "no load-test figures (k6 did not run: see the run's log)", 0)
    res = _read(folder / RESOURCES)
    over = over_limit(res)
    failed |= bool(over)
    if res:
        top = sorted(res.items(), key=lambda kv: -kv[1].get("peak_mb", 0))[:6]
        record("performance: every container within its memory limit under load", "failed" if over else "passed",
               "; ".join(over) if over else ", ".join(f"{c} {v['peak_mb']:.0f} MB peak, CPU {v.get('cpu_peak', 0):.0f}%" for c, v in top), 0)
    kept = {"version": version, "size": size, "folder": folder.name, "operations": ops, "load": load, "resources": res}
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{folder.name}.json").write_text(json.dumps(kept), encoding="utf-8")
    own = root / BASELINES / size / f"baseline-{version}.json"
    if not failed and not own.exists():
        own.write_text(json.dumps(kept), encoding="utf-8")
        record("performance: baseline", "passed", f"this run is the baseline of {version} ({size} data) from now on", 0)
    return {"failed": failed, "baseline": bver, "compared": vs_base}


def trend(root: Path, size: str = "") -> dict:
    """Each operation's median per run (oldest first) with the baseline it was compared with, for the Self-test page."""
    out: dict = {"sizes": [], "runs": [], "baselines": {}}
    d = root / BASELINES
    if not d.is_dir():
        return out
    out["sizes"] = sorted(p.name for p in d.iterdir() if p.is_dir())
    size = size or ("small" if "small" in out["sizes"] else (out["sizes"][0] if out["sizes"] else ""))
    if not size:
        return out
    for f in sorted((d / size / "runs").glob("*.json"))[-30:]:
        r = _read(f) or {}
        out["runs"].append({"folder": r.get("folder"), "version": r.get("version"),
                            "ops": {k: v.get("p50_ms") for k, v in (r.get("operations") or {}).items()},
                            "load_p95": (r.get("load") or {}).get("p95_ms")})
    for f in sorted((d / size).glob("baseline-*.json")):
        r = _read(f) or {}
        out["baselines"][f.stem.removeprefix("baseline-")] = {k: v.get("p50_ms") for k, v in (r.get("operations") or {}).items()}
    out["size"] = size
    return out
