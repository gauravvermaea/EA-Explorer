"""R12 fix (owner, 21 Nov 2026, 14:39: "when tests run they will bring down the contianer not in use"; 14:40: "This is
important stray containers are hard on memory").

Before: the scanners a test starts (ZAP, Schemathesis, Nuclei, Semgrep, Gitleaks, Trivy, k6) were plain `docker run
--rm`, unnamed and unlabelled: at a time limit only the command waiting for one was stopped and the scanner ran on (a
ZAP full scan, 1 to 2 GB for an hour), and eax up and down could not find it. After: each is named and labelled with
its run (eaexplorer.test=<folder>), removed at its time limit, swept at the end and start of every run, and removed by
eax up and down unless its run is still going; the full test fails when one is still there."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


def _ops(name: str):
    spec = importlib.util.spec_from_file_location(f"ops_{name}_r126", REPO / f"services/ops/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _ops("attackscans")


def test_every_scanner_is_named_and_labelled_with_its_run():
    args, name = A.tag(["docker", "run", "--rm", "-v", "x:/y", "img", "scan"], "20261121T142504Z", "zap")
    assert args[:6] == ["docker", "run", "--name", name, "--label", "eaexplorer.test=20261121T142504Z"]
    assert name.startswith("eax-test-zap-20261121T142504Z-") and len(name) <= 63
    assert A.tag(["docker", "pull", "img"], "f", "x") == (["docker", "pull", "img"], "")   # only docker run


def test_each_attack_scanner_goes_through_the_tag():
    calls = []

    def run(args, timeout=0, env=None):
        calls.append(args)
        return 0, ""
    A.zap_full("/w/tests/F1", "net", lambda _m: None, run)
    A.semgrep("/w/tests/F1", "/repo", lambda _m: None, run)
    A.gitleaks("/w/tests/F1", "/repo", lambda _m: None, run)
    assert calls and all("--label" in c and "eaexplorer.test=F1" in c for c in calls)


def test_at_its_time_limit_the_container_itself_is_removed(monkeypatch):
    removed = []

    def fake_run(args, **kw):
        if args[:2] == ["docker", "rm"]:
            removed.append(args[-1])
            return subprocess.CompletedProcess(args, 0, "", "")
        raise subprocess.TimeoutExpired(args, kw.get("timeout"))
    monkeypatch.setattr(A.subprocess, "run", fake_run)
    code, out = A.run_tagged(["docker", "run", "--rm", "img"], "F2", "nuclei", 60)
    assert code == 124 and len(removed) == 1 and removed[0].startswith("eax-test-nuclei-F2-")


def test_a_runs_containers_are_swept(monkeypatch):
    seen = []

    def fake_run(args, **kw):
        seen.append(args)
        if args[:2] == ["docker", "ps"]:
            return subprocess.CompletedProcess(args, 0, "eax-test-zap-F3-aa\neax-test-k6-F3-bb\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(A.subprocess, "run", fake_run)
    assert A.sweep("F3") == ["eax-test-zap-F3-aa", "eax-test-k6-F3-bb"]
    assert ["docker", "ps", "-a", "--filter", "label=eaexplorer.test=F3", "--format", "{{.Names}}"] == seen[0]
    assert [a[-1] for a in seen if a[:2] == ["docker", "rm"]] == ["eax-test-zap-F3-aa", "eax-test-k6-F3-bb"]


def test_the_helper_sweeps_at_the_start_and_end_of_every_run_and_tags_its_own_scans():
    src = (REPO / "services/ops/testruns.py").read_text(encoding="utf-8")
    assert "left = _attackscans().sweep()" in src and "left = _attackscans().sweep(folder)" in src
    for tool in ('"zap-baseline"', '"zap-api"', '"k6"', 'f"trivy-{short}"'):
        assert tool in src
    assert 'subprocess.run(check=False, args=["docker", "run"' not in src       # no untagged scanner left
    assert "left = sweep(folder)" in (REPO / "services/ops/attackscans.py").read_text(encoding="utf-8")


def test_up_and_down_remove_what_a_finished_run_left_but_never_a_run_going(tmp_path):
    from eaxcli import stack
    (tmp_path / "LIVE").mkdir()
    (tmp_path / "LIVE" / ".alive").write_text("1")
    (tmp_path / "OLD").mkdir()
    old = tmp_path / "OLD" / ".alive"
    old.write_text("1")
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    got = stack.stale_tests(["eax-test-zap-LIVE-1 LIVE", "eax-test-zap-OLD-2 OLD", "eax-test-k6-GONE-3 GONE",
                             "eax-test-x-4 ../etc", ""], tmp_path)
    assert got == ["eax-test-zap-OLD-2", "eax-test-k6-GONE-3", "eax-test-x-4"]


def test_all_three_ways_of_eax_remove_them():
    ps1 = (REPO / "eax.ps1").read_bytes().decode("ascii")
    sh = (REPO / "eax.sh").read_text(encoding="utf-8")
    py = (REPO / "eaxcli/stack.py").read_text(encoding="utf-8")
    for src in (ps1, sh):
        assert "label=eaexplorer.test" in src and ".alive" in src
    assert 'TEST_LABEL = "eaexplorer.test"' in py and 'f"label={TEST_LABEL}"' in py
    assert "TotalSeconds -lt 180" in ps1 and "-mmin -3" in sh and 'BEAT, BEAT_STALE = ".alive", 180' in py


def test_the_full_test_fails_when_a_test_container_is_still_there(tmp_path, monkeypatch):
    from eaxcli import main as M
    monkeypatch.setattr(M, "WORK", tmp_path)
    monkeypatch.setattr(M, "version", lambda: "7.9.0")
    kept = []
    assert M.full_summary([("self-test", True, "")], time.time(), keep=kept.append,
                          containers=lambda: ["eax-test-zap-F-1"]) == 1
    page = (tmp_path / "tests" / kept[0] / "index.html").read_text(encoding="utf-8")
    assert "Test containers" in page and "eax-test-zap-F-1" in page
    assert M.full_summary([("self-test", True, "")], time.time(), keep=kept.append, containers=lambda: []) == 0
