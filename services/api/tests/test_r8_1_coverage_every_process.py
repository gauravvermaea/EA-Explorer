"""D810: code coverage measures the job runners and the MCP server as well as the web API (dev check and the full test
of 20 Nov 2026: eax/mcp_server.py, mcp_analysis.py, mcp_build.py, mcp_operations.py and background.py at 0%, though the
self-test runs the MCP tools and the jobs hundreds of times: only eax/wsgi.py started the probe, and the job runners
(procrastinate --app=eax.jobs.app) and the MCP server (uvicorn eax.mcp_server:app) are processes of their own).

Each process's entry module starts the probe before the rest of its imports; it measures once per process, so the API
(which imports eax.jobs too) is not measured twice; off, nothing is measured."""

from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

from eax import coverage_probe

EAX = Path(coverage_probe.__file__).resolve().parent
ENTRYPOINT = EAX.parent / "entrypoint.sh"


def _first_start_line(path: Path) -> tuple[int, int]:
    """(the line coverage_probe.start() is called on, the line of the first import of anything else but the probe and
    the standard library modules imported before it)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    start = next(n.lineno for n in tree.body if isinstance(n, ast.Expr) and "coverage_probe.start" in ast.unparse(n))
    others = [n.lineno for n in tree.body if isinstance(n, ast.ImportFrom) and n.level == 1
              and [a.name for a in n.names] != ["coverage_probe"]]
    return start, min(others)


def test_the_job_runners_and_the_mcp_server_start_the_probe_before_their_code():
    for entry in ("jobs.py", "mcp_server.py", "wsgi.py"):
        start, first_own = _first_start_line(EAX / entry)
        assert start < first_own, entry


def test_those_are_the_modules_the_container_starts():
    sh = ENTRYPOINT.read_text(encoding="utf-8")
    assert sh.count("procrastinate --app=eax.jobs.app worker") == 3
    assert "uvicorn eax.mcp_server:app" in sh


class _FakeCoverage:
    made: list = []

    def __init__(self, **kw):
        self.kw = kw
        _FakeCoverage.made.append(self)

    def start(self):
        pass

    def save(self):
        pass


def test_it_measures_once_per_process_and_not_at_all_when_off(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "coverage", types.SimpleNamespace(Coverage=_FakeCoverage))
    monkeypatch.setattr(coverage_probe, "_cov", {"c": None})
    monkeypatch.setattr(coverage_probe.atexit, "register", lambda f: None)
    monkeypatch.setattr(coverage_probe.threading, "Thread", lambda **kw: types.SimpleNamespace(start=lambda: None))
    monkeypatch.setenv("EAX_COVERAGE_DIR", str(tmp_path))
    _FakeCoverage.made = []
    monkeypatch.setenv("EAX_COVERAGE", "off")
    assert coverage_probe.start() is False and _FakeCoverage.made == []
    monkeypatch.setenv("EAX_COVERAGE", "on")
    assert coverage_probe.start() is True                  # the first entry module of the process (wsgi, jobs or MCP)
    assert coverage_probe.start() is False                 # the API importing eax.jobs later: still one measurement
    assert len(_FakeCoverage.made) == 1
    kw = _FakeCoverage.made[0].kw
    assert kw["data_suffix"] is True                       # each process its own file, combined by report()
    assert kw["data_file"].startswith(str(tmp_path))
