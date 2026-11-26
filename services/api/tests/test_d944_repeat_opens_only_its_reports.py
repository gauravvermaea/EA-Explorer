"""D944: a repeat opens only the report dashboards whose checks it repeats (owner, 26 Nov 2026, 18:24: "Reports have not
even started yet please check"; run 19 opened every dashboard as two people, 90 minutes in run 18, to record six)."""

from __future__ import annotations

import contextlib
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_reports_check import FakeKeycloak  # noqa: E402

from eax.testing import reports_check as rc  # noqa: E402
from eax.testing import run  # noqa: E402

DASHES = [{"slug": f"d{i}", "dashboard_title": f"Report {i}"} for i in range(6)]


class FakeSession:
    opened: list[tuple[str, str]] = []

    def __init__(self, browser, who, name, pw, base):
        self.who, self.page = who, type("P", (), {"url": ""})()

    def sign_in(self):
        pass

    def dashboards(self):
        return [] if self.who == "it-admin" else DASHES

    def open(self, d):
        FakeSession.opened.append((self.who, d.get("slug")))
        return 100, [(200, '{"result": [{"data": []}]}')]

    def shot(self):
        return None

    def close(self):
        pass


class FakeBrowser:
    def close(self):
        pass


def _playwright():
    pw = type("PW", (), {"chromium": type("C", (), {"launch": staticmethod(lambda **k: FakeBrowser())})()})()
    return contextlib.nullcontext(pw)


def _run(monkeypatch, wants):
    FakeSession.opened = []
    monkeypatch.setattr(rc, "Session", FakeSession)
    monkeypatch.setattr(rc, "expected_dashboards", lambda: {d["slug"] for d in DASHES})
    for name in ("_from_screens", "_remove_superset_users", "files", "import_log", "_content"):
        monkeypatch.setattr(rc, name, lambda *a, **k: None)
    monkeypatch.setattr(rc, "_readable", lambda *a: set())
    monkeypatch.setenv("EAX_KC_ADMIN_PASSWORD", "x")
    got = []

    def record(name, outcome, *a, **k):
        got.append(name)
    if wants is not None:
        record.wants = wants
    kc = rc.Keycloak(opener=FakeKeycloak())
    rc.run("https://api", {"super-admin": "a", "model-admin": "m", "report-viewer": "v"}, {"sid": "s1", "model": "m1"},
           record, log=lambda m: None, send=lambda *a: (200, "[]"), keycloak=kc, playwright=_playwright)
    return FakeSession.opened


def test_a_full_run_opens_every_dashboard_as_both(monkeypatch):
    opened = _run(monkeypatch, None)
    assert len([o for o in opened if o[0] == "super-admin"]) == 6 and len([o for o in opened if o[0] == "report-viewer"]) == 6


def test_a_repeat_opens_only_the_dashboards_it_repeats(monkeypatch):
    wanted = {"reports: Report 2 as super-admin", "reports: Report 4 as report-viewer"}
    assert _run(monkeypatch, lambda n: n in wanted) == [("super-admin", "d2"), ("report-viewer", "d4")]


def test_a_repeated_check_across_every_chart_opens_every_one_as_the_viewer(monkeypatch):
    wanted = {"reports: committed content shows"}
    opened = _run(monkeypatch, lambda n: n in wanted)
    assert [o for o in opened if o[0] == "super-admin"] == [] and len(opened) == 6


def test_the_runs_recorder_says_what_it_wants():
    src = inspect.getsource(run.Run.recorder)
    assert "record.wants = lambda name: self.only is None or (suite, repeat.canon(name, self.ids)) in self.only" in src
