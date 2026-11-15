"""R5.20 (owner, 14 Nov 2026: "be able to open a screen and view how testing is going I mean actual clicks etc in
chromium"; "This needs to be performance optimized and stream to start only on demand"): the tests the story names."""

import base64
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax.testing import screencast as SC  # noqa: E402


class Conn:
    def __init__(self, log, answer):
        self.log, self.answer = log, answer

    def execute(self, sql, params=None):
        self.log.append((str(sql).split()[0], str(sql), dict(params or {})))
        return self

    def first(self):
        return self.answer()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Engine:
    def __init__(self):
        self.log, self.want = [], (False, False)

    def begin(self):
        return Conn(self.log, lambda: None)

    def connect(self):
        return Conn(self.log, lambda: self.want)

    def writes(self, word="UPDATE"):
        return [x for x in self.log if x[0] == word and "frame =" in x[1]]


class CDP:
    def __init__(self):
        self.sent, self.handlers = [], {}

    def on(self, ev, fn):
        self.handlers[ev] = fn

    def send(self, method, params=None):
        self.sent.append(method)
        return {"data": base64.b64encode(b"thumb").decode()} if method == "Page.captureScreenshot" else {}


class Ctx:
    def __init__(self, cdp):
        self.cdp, self.scripts = cdp, []

    def new_cdp_session(self, page):
        return self.cdp

    def add_init_script(self, s):
        self.scripts.append(s)


class Page:
    url = "https://eax.local/#/models"

    def __init__(self):
        self.cdp = CDP()
        self.context = Ctx(self.cdp)
        self.evals = []

    def evaluate(self, js):
        self.evals.append(js)


@pytest.fixture
def cast():
    t = [100.0]
    eng, page = Engine(), Page()
    c = SC.Caster(eng, 7, "001", "journey: a model", page, clock=lambda: t[0])
    return c, eng, page, t


def test_nothing_is_captured_while_nobody_watches(cast):
    c, eng, page, t = cast
    for _ in range(20):
        t[0] += 1.5
        c.tick("step")
    assert page.cdp.sent == [] and not eng.writes() and not c.streaming
    assert SC.MARK_SCRIPT in page.context.scripts                      # the marks are there, drawn only while it streams


def test_the_stream_starts_when_shown_large_and_stops_when_closed(cast):
    c, eng, page, t = cast
    eng.want = (True, True)
    t[0] += 2
    c.tick("step 1")
    assert "Page.startScreencast" in page.cdp.sent and c.streaming and "window.__eaxMark = true" in page.evals
    eng.want = (False, False)                                           # the viewer closed it (or went quiet 30 s)
    t[0] += 2
    c.tick("step 2")
    assert "Page.stopScreencast" in page.cdp.sent and not c.streaming and "window.__eaxMark = false" in page.evals


def test_the_tiles_get_a_small_still_every_few_seconds_only(cast):
    c, eng, page, t = cast
    eng.want = (True, False)
    for _ in range(8):
        t[0] += 1.0
        c.tick()
    assert page.cdp.sent.count("Page.captureScreenshot") == 2 and "Page.startScreencast" not in page.cdp.sent
    assert all("thumb =" in x[1] for x in eng.log if x[0] == "UPDATE" and ":f" in x[1])


def test_a_slow_viewer_gets_the_newest_frame_not_a_backlog(cast):
    c, eng, page, t = cast
    eng.want = (True, True)
    t[0] += 2
    c.tick()
    frame = page.cdp.handlers["Page.screencastFrame"]
    for i in range(40):                                                 # 40 frames in one second
        t[0] += 0.025
        frame({"sessionId": i, "data": base64.b64encode(b"jpeg%d" % i).decode()})
    assert page.cdp.sent.count("Page.screencastFrameAck") == 40         # every one acknowledged: Chromium keeps sending
    assert c.frames <= SC.MAX_FPS + 1 and c.dropped >= 40 - SC.MAX_FPS - 1
    assert eng.writes() and not eng.writes("INSERT")                    # each replaces the one before


def test_the_viewers_ask_and_the_frames_go_with_the_run():
    log = []

    class R:
        def __init__(self, rows=None, one=None):
            self.rows, self.one = rows or [], one

        def mappings(self):
            return self

        def __iter__(self):
            return iter(self.rows)

        def first(self):
            return self.one

    rows = [{"browser": "001", "label": "the page sweep", "step": "open #/x", "url": "u", "frame_seq": 5, "frame_at": None,
             "thumb": b"t", "frame": b"big"}]

    class VConn:
        def execute(self, sql, p=None):
            log.append(str(sql).split()[0])
            return R(rows) if "SELECT browser" in str(sql) else R(one=None)

    got = SC.view(VConn(), 7, "001", since=4)
    assert log[0] == "UPDATE" and got["frame"]["seq"] == 5 and base64.b64decode(got["frame"]["jpeg"]) == b"big"
    assert SC.view(VConn(), 7, "001", since=5)["frame"] is None          # nothing newer: nothing sent
    assert got["tiles"][0]["thumb"] and got["controls"]["paused"] is False
    log.clear()
    SC.forget(VConn(), 7)
    assert log == ["DELETE", "DELETE"]


def test_pause_step_and_continue():
    state = {"paused": True, "steps": 1}

    class HConn:
        def execute(self, sql, p=None):
            s = str(sql)
            if s.startswith("UPDATE") and state["paused"] and state["steps"] > 0:
                state["steps"] -= 1
                return type("X", (), {"first": lambda self: ("step",)})()
            if s.startswith("UPDATE"):
                return type("X", (), {"first": lambda self: None})()
            return type("X", (), {"scalar": lambda self: state["paused"]})()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    eng = type("E", (), {"begin": lambda self: HConn()})()
    assert SC.hold(eng, 7, sleep=lambda s: None) == "step"               # Step: one step taken
    naps = []

    def nap(s):
        naps.append(s)
        if len(naps) == 3:
            state["paused"] = False                                      # Continue
    assert SC.hold(eng, 7, sleep=nap) == "go" and len(naps) == 3
    state["paused"] = True
    assert SC.hold(eng, 7, sleep=lambda s: None, stopped=lambda: True) == "timeout"   # a Stop never waits
    with pytest.raises(ValueError):
        SC.set_controls(None, 7, "jump", "ann")


def test_each_step_ticks_and_holds():
    from eax.testing import ui_flows
    ticks, holds = [], []
    caster = type("C", (), {"tick": lambda self, s="": ticks.append(s), "hold": lambda self: holds.append(1)})()

    class P:
        _eax_caster = caster

    orig = ui_flows.step
    ui_flows.step = lambda page, s, open_route, state=None: ""
    try:
        out = ui_flows.run_one(P(), {"role": "architect", "steps": [{"open": "#/a"}, {"click": "Save"}]}, lambda r: None)
    finally:
        ui_flows.step = orig
    assert out[0] == "passed" and ticks == ["step 1: open #/a", "step 2: click Save"] and len(holds) == 2


def test_only_admins_and_never_ci_or_a_schedule_and_recordings_kept():
    api = (REPO / "services/api/eax/api/platform_tests.py").read_text()
    block = api.split('@blp.route("/tests/<int:run_id>/live-browser")')[1].split("@blp.route(")[0]
    assert block.count('@require_auth("system.operate")') == 2
    run = (REPO / "services/api/eax/testing/run.py").read_text()
    assert 'args.trigger != "ci" and not str(by).startswith("schedule")' in run and "screencast.forget(conn, args.run_id)" in run
    uj = (REPO / "services/api/eax/testing/ui_journeys.py").read_text()
    assert 'ctx.tracing.start(screenshots=True, snapshots=True)' in uj and 'if outcome == "failed" or live.get("keep")' in uj
    assert '"slow_mo": screencast.SLOW_MS' in uj
    for f, needle in (("eaxcli/main.py", '"--browser" in rest'), ("eax.sh", "--browser"), ("eax.ps1", '-contains "--browser"')):
        assert needle in (REPO / f).read_text(), f
    assert "--browser" in (REPO / "eaxcli/help.txt").read_text().split("### test ")[1].split("\n")[0]
    sql = (REPO / "services/api/migrations/sql/0086_r5_live_browser.sql").read_text()
    assert "tests.live_browsers" in sql and "FUNCTION" not in sql
    web = (REPO / "services/web/src/TestWatch.jsx").read_text()
    assert "export function LiveBrowser" in web and "live-browser?large=" in web
