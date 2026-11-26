"""D945: Stop is seen at the next check, not only at the next log line (owner, 26 Nov 2026, 18:50: run 19 stayed on
"reports: ..." after `eax test stop 19`: the reports suite logs once, then opens dashboards for an hour)."""

from __future__ import annotations

import pytest

from eax.testing import run


class Conn:
    def __init__(self, asked, looks):
        self.asked, self.looks = asked, looks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        self.looks.append(1)
        return type("R", (), {"scalar": lambda _self: self.asked})()


class Engine:
    def __init__(self, asked=None):
        self.asked, self.looks = asked, []

    def connect(self):
        return Conn(self.asked, self.looks)

    def begin(self):
        return Conn(self.asked, self.looks)


def _run(asked=None):
    r = run.Run.__new__(run.Run)
    r.engine, r.id, r.only, r.ids, r.left_out, r.dog = Engine(asked), 19, None, {}, 0, None
    return r


def test_stopped_is_not_an_exception_a_suite_would_swallow():
    assert issubclass(run.Stopped, BaseException) and not issubclass(run.Stopped, Exception)
    try:
        try:
            raise run.Stopped("eaadmin")
        except Exception:  # noqa: BLE001 - what each dashboard and journey does
            pytest.fail("a suite's except Exception took the stop")
    except run.Stopped:
        pass


def test_a_stop_asked_is_raised_at_a_check():
    r = _run("eaadmin (eax test stop)")
    with pytest.raises(run.Stopped):
        r.stop_asked(now=1000.0)


def test_it_looks_at_most_every_ten_seconds():
    r = _run(None)
    r.stop_asked(now=1000.0)
    r.stop_asked(now=1005.0)
    r.stop_asked(now=1011.0)
    assert len(r.engine.looks) == 2 and run.STOP_EVERY == 10


def test_a_database_hiccup_never_ends_the_run():
    r = _run(None)
    r.engine = object()                  # no connect: the look fails quietly
    r.stop_asked(now=1000.0)


def test_every_check_looks_recorded_or_left_out():
    r = _run("eaadmin")
    r.only = set()                       # a repeat: this check is left out, still a check done
    with pytest.raises(run.Stopped):
        r.recorder("reports")("reports: Report 1 as super-admin", "passed")
