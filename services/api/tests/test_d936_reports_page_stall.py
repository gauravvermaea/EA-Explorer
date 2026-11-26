"""D936: run 17's "every report opens" ended at VP-04 with "Page.goto: Timeout 300000ms exceeded": Reports answered each
dashboard in 2 to 3 seconds (its own log), but the test runner's one page had opened thirty dashboards and its browser
had grown to 6.7 GB on a laptop already paging. A page that never opens now fails its dashboard only, the next opens in a
new page, and a fresh page is taken every PAGE_EVERY dashboards. And the import's line at Reports' start, rolled out of
the 500 KB Docker keeps, is said, not warned about (tests in test_reports_check.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eax.testing import reports_check as R  # noqa: E402


class _Page:
    def __init__(self, stall: bool):
        self.stall, self.closed, self.on_, self.opened = stall, False, {}, 0

    def on(self, name, fn):
        self.on_[name] = fn

    def goto(self, *_a, **_k):
        self.opened += 1
        if self.stall:
            raise TimeoutError("Page.goto: Timeout 300000ms exceeded.")

    def wait_for_timeout(self, _ms):
        pass

    def close(self):
        self.closed = True


class _Ctx:
    def __init__(self, stalls: int = 0):
        self.pages, self.stalls = [], stalls

    def new_page(self):
        p = _Page(stall=len(self.pages) < self.stalls)
        self.pages.append(p)
        return p


class _Browser:
    def __init__(self, stalls: int = 0):
        self.ctx = _Ctx(stalls)

    def new_context(self, **_k):
        return self.ctx


def test_a_page_that_never_opens_fails_its_dashboard_and_the_suite_goes_on(monkeypatch):
    monkeypatch.setattr(R, "FAIL_MS", 0)
    b = _Browser(stalls=1)
    s = R.Session(b, "super-admin", "u", "p", "https://reports.x")
    _ms, answers = s.open({"slug": "eax-vp04"})
    assert answers[-1][0] == 0 and "did not open" in answers[-1][1]
    ok, why, _rows = R.chart_answer(*answers[-1])
    assert not ok and "did not open" in why
    assert b.ctx.pages[0].closed and s.page is b.ctx.pages[1]
    _ms, answers = s.open({"slug": "eax-vp03"})                       # the next one opens in the new page
    assert not any("did not open" in a[1] for a in answers)


def test_a_fresh_page_every_ten_dashboards(monkeypatch):
    monkeypatch.setattr(R, "FAIL_MS", 0)
    b = _Browser()
    s = R.Session(b, "super-admin", "u", "p", "https://reports.x")
    for i in range(25):
        s.open({"slug": f"eax-vp{i:02d}"})
    assert R.PAGE_EVERY == 10
    assert len(b.ctx.pages) == 3                                       # pages for 1-10, 11-20, 21-25
    assert [p.opened for p in b.ctx.pages] == [10, 10, 5]
    assert all(p.closed for p in b.ctx.pages[:2]) and not b.ctx.pages[2].closed


def test_anything_else_still_ends_the_suite(monkeypatch):
    monkeypatch.setattr(R, "FAIL_MS", 0)

    class _Odd(_Ctx):
        def new_page(self):
            p = super().new_page()
            p.goto = lambda *a, **k: (_ for _ in ()).throw(ValueError("odd"))
            return p

    class _B(_Browser):
        def __init__(self):
            self.ctx = _Odd()
    s = R.Session(_B(), "super-admin", "u", "p", "https://reports.x")
    try:
        s.open({"slug": "x"})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
