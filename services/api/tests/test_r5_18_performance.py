"""R5.18 (owner, 14 Nov 2026: "automated performance test (bench marking)"; 15 Nov 2026, D695: k6 in a container of the
test profile, eax test performance, compared with a kept baseline, part of the full test)."""

import importlib.util
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import testing  # noqa: E402
from eax.testing import benchmark as B  # noqa: E402


def ops_module():
    spec = importlib.util.spec_from_file_location("testruns_r518", REPO / "services/ops/testruns.py")
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    return T


def single(folder: Path, ms: float, size: str = "small"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / B.SINGLE).write_text(json.dumps({"size": size, "operations": {
        "grid": {"p50_ms": ms, "p95_ms": ms * 1.5, "label": "the grid", "errors": 0}}}))


def test_percentiles_and_summary():
    assert B.pct([1, 2, 3, 4, 5], 50) == 3 and B.pct([10, 20], 95) == 19.5 and B.pct([], 95) == 0
    s = B.summary([10, 20, 30, 40])
    assert s == {"n": 4, "p50_ms": 25.0, "p95_ms": 38.5, "max_ms": 40}


def test_slower_than_the_margin_and_the_noise():
    then = {"a": {"p50_ms": 100}, "b": {"p50_ms": 10}}
    c = {x["op"]: x for x in B.compare({"a": {"p50_ms": 130}, "b": {"p50_ms": 20}, "c": {"p50_ms": 5}}, then)}
    assert c["a"]["slower"] and c["a"]["change"] == 30.0
    assert not c["b"]["slower"]                         # 100% slower but 10 ms: noise on a fast read
    assert c["c"]["then"] is None and not c["c"]["slower"]


def test_the_baseline_is_the_last_release_before_this_one(tmp_path):
    d = tmp_path / B.BASELINES / "small"
    d.mkdir(parents=True)
    for v in ("4.0.0", "4.10.0", "5.0.0"):
        (d / f"baseline-{v}.json").write_text(json.dumps({"operations": {"x": {"p50_ms": 1}}, "version": v}))
    assert B.baseline_for(tmp_path, "small", "5.0.0")[0] == "4.10.0"      # numbers, not text: 4.10 after 4.9
    assert B.baseline_for(tmp_path, "small", "5.1.0")[0] == "5.0.0"
    assert B.baseline_for(tmp_path, "small", "4.0.0")[0] == "4.0.0"       # none before: its own
    assert B.baseline_for(tmp_path, "medium", "5.0.0") == (None, None)


def test_a_first_passing_run_becomes_the_baseline_then_a_slow_one_fails(tmp_path):
    got = []
    rec = lambda n, o, d, ms: got.append((n, o, d))   # noqa: E731
    single(tmp_path / "20261201T000000Z", 100)
    B.judge(tmp_path / "20261201T000000Z", rec, "5.0.0")
    assert (tmp_path / B.BASELINES / "small/baseline-5.0.0.json").exists()
    assert ("performance: baseline", "passed") == got[-1][:2]
    got.clear()
    single(tmp_path / "20261202T000000Z", 150)
    out = B.judge(tmp_path / "20261202T000000Z", rec, "5.1.0")             # compared with 5.0.0's baseline
    assert out["failed"] and got[0][1] == "failed" and "slower than the baseline" in got[0][2] and "run before: 100" in got[0][2]
    assert not (tmp_path / B.BASELINES / "small/baseline-5.1.0.json").exists()   # a failing run is never a baseline


def test_load_errors_and_memory_limits_fail(tmp_path):
    f = tmp_path / "20261201T000000Z"
    single(f, 100)
    (f / B.LOAD).write_text(json.dumps({"users": 20, "minutes": 2, "p50_ms": 80, "p95_ms": 300, "p99_ms": 900, "requests": 1000,
                                        "per_second": 8, "error_rate": 0.05}))
    (f / B.RESOURCES).write_text(json.dumps({"eaexplorer-api-1": {"peak_mb": 1020, "limit_mb": 1024, "cpu_peak": 90},
                                             "eaexplorer-db-1": {"peak_mb": 300, "limit_mb": 2048, "cpu_peak": 20}}))
    got = []
    out = B.judge(f, lambda n, o, d, ms: got.append((n, o, d)), "5.0.0")
    by = {n: o for n, o, _ in got}
    assert out["failed"] and by["performance: 20 people at once for 2 minutes (k6)"] == "failed"
    assert by["performance: every container within its memory limit under load"] == "failed"
    assert B.over_limit({"x": {"peak_mb": 10, "limit_mb": 0}}) == []      # no limit known: nothing to say


def test_no_figures_no_judging(tmp_path):
    got = []
    assert B.judge(tmp_path, lambda *a: got.append(a), "5.0.0") == {} and got[0][1] == "skipped"


def test_the_trend_for_the_page(tmp_path):
    single(tmp_path / "20261201T000000Z", 100)
    B.judge(tmp_path / "20261201T000000Z", lambda *a: None, "5.0.0")
    t = B.trend(tmp_path)
    assert t["size"] == "small" and t["runs"][0]["ops"]["grid"] == 100 and t["baselines"]["5.0.0"]["grid"] == 100


def test_the_reads_are_timed_with_a_warm_up_and_errors_counted():
    calls = []
    out = B.time_reads("http://api", "t", {"model": "m", "entity": "e"},
                       lambda base, method, path, token: calls.append(path) or (500 if "reports" in path else 200, ""), repeats=3)
    assert set(out) == {k for k, _l, _p in B.OPERATIONS}
    assert calls.count("/api/v1/me") == 4 and out["reports"]["errors"] == 3 and out["me"]["errors"] == 0
    assert "element" not in B.time_reads("http://api", "t", {"model": "m"}, lambda *a: (200, ""), repeats=1)   # no element id


def test_the_plan_keeps_the_tokens_apart(tmp_path):
    B.plan(tmp_path, "https://proxy", {"model": "m", "entity": "e"}, ["tok-a", "tok-b"], 30, 3, "medium")
    p = json.loads((tmp_path / B.PLAN).read_text())
    assert p["users"] == 30 and "/api/v1/models/m/grids/relationships" in p["paths"] and "tok-" not in json.dumps(p)
    assert (tmp_path / B.TOKENS).read_text() == "tok-a,tok-b"


def test_the_helper_runs_k6_and_deletes_the_tokens(tmp_path, monkeypatch):
    T = ops_module()
    monkeypatch.setattr(T, "WORK", str(tmp_path))
    monkeypatch.setattr(T, "host_work", lambda: "/host/work")
    monkeypatch.setattr(T, "_networks", lambda info: ["eax_frontend"])
    monkeypatch.setattr(T, "_sample_resources", lambda stop, out, every=5: out.update({"api": {"peak_mb": 1, "limit_mb": 2}}))
    d = tmp_path / "tests/run1"
    d.mkdir(parents=True)
    B.plan(d, "https://proxy", {"model": "m"}, ["tok-1"], 5, 1, "small")
    seen = {}
    # the scanner is named and labelled now and goes through attackscans.run_tagged (R12.6, D833)
    monkeypatch.setattr(T.subprocess, "run", lambda args, **k: seen.update(args=args, **k) or T.subprocess.CompletedProcess(args, 0, "", ""))
    T._k6({}, "run1", lambda m: None)
    assert not (d / B.TOKENS).exists() and (d / "benchmark.js").exists()
    assert "tok-1" not in " ".join(seen["args"]) and seen["env"]["TOKENS"] == "tok-1"
    assert T.K6_IMAGE in seen["args"] and "--network" in seen["args"]
    assert json.loads((d / B.RESOURCES).read_text())["api"]["peak_mb"] == 1
    assert T._mb("1.5GiB") == 1536 and T._mb("512MiB") == 512 and T._mb("") == 0


def test_eax_test_performance_takes_its_size_people_and_minutes(monkeypatch):
    T = ops_module()
    seen = {}
    monkeypatch.setattr(T, "run_sequence", lambda *a, **k: seen.update(suites=a[1], **k) or {"run_id": 1, "folder": "f", "code": 0})
    assert T.cli(["performance", "--size", "medium", "--users", "40", "--minutes", "3"]) == 0
    assert seen["suites"] == ["performance"] and seen["bench"] == {"size": "medium", "users": "40", "minutes": "3"}
    assert T.cli(["performance", "--size", "huge"]) == 2


def test_it_is_a_suite_everywhere_and_part_of_the_full_test():
    T = ops_module()
    for suites in (testing.SUITES, T.SUITES):
        assert "performance" in suites and suites[-1] == "restore" and suites.index("performance") < suites.index("backup")
    sql = (REPO / "services/api/migrations/sql/0084_selftest_performance_suite.sql").read_text()
    assert sql.count("'reports', 'performance', 'backup'") == 2 and "FUNCTION" not in sql
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text().replace("<<: *logging", "").replace("<<: [*secrets, *folders]", ""))
    assert compose["services"]["k6"]["profiles"] == ["test"]                 # never running otherwise
    run = (REPO / "services/api/eax/testing/run.py").read_text()
    assert "_performance_suite(r, tokens, ids, args)" in run and "benchmark.judge(r.dir" in run
    assert "COPY benchmark.js" in (REPO / "services/ops/Dockerfile").read_text()
    assert "test performance" in (REPO / ".github/workflows/ci.yml").read_text()
    assert "performance" in (REPO / "eaxcli/help.txt").read_text().split("### test ")[1].split("\n")[0]
    assert '["performance", "Performance"]' in (REPO / "services/web/src/TestRuns.jsx").read_text()


def test_the_run_keeps_its_tokens_until_collect():
    run = (REPO / "services/api/eax/testing/run.py").read_text()
    tail = run.split("    if keep_open and not (error or stopped):")[1]
    assert tail.index('print("SCANS_NEXT"') < tail.index("_close_access(engine, run_id, by, repo)")


def test_a_full_run_from_before_the_performance_suite_still_reads_as_the_full_test():
    """R5.18 added a suite: a full run recorded before it (every other suite) is still shown as eax test --detailed."""
    from eax.testing import store
    old = [s for s in testing.SUITES if s != "performance"]
    assert store.command_line({"level": "detailed", "suites": old}, "./eax.sh") == "./eax.sh test --detailed"
    assert store.command_line({"level": "detailed", "suites": ["api", "db"]}, "./eax.sh").endswith("--suite api --suite db")
