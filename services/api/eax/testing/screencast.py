"""Watching the self-test's browsers live (R5.20; owner, 14 Nov 2026: "be able to open a screen and view how testing is
going I mean actual clicks etc in chromium"; 08:42: "This needs to be performance optimized and stream to start only on
demand").

Each browser page the runner drives is a **Caster**. Nothing is captured unless someone has the Live browser panel
open: the panel's every ask sets watched_until (now + 30 seconds) on the browsers' rows (tests.live_browsers), and the
one shown large gets large_until too. At each step of a journey, and each page of the sweep, the runner calls
tick(); at most once a second it reads those two times and:

  nobody watching        the screencast is off; nothing is captured, nothing written (a run nobody watches costs nothing)
  watched, not large     a small still (a quarter size, JPEG 35%) every THUMB_EVERY seconds for its tile
  shown large            Chromium's own screencast (Page.startScreencast): frames scaled to MAX_WIDTH, JPEG at QUALITY,
                         only when the page changed, written at most MAX_FPS a second; each frame replaces the one
                         before (the newest only: a slow viewer skips frames, never falls behind)

The screencast runs beside the test (Chromium sends its frames as the page paints), never in its way; a click is
marked where it lands (a ring, drawn by a small script in the page only while it streams) and what is typed shows
beside the field. A run started to be watched can be slowed (Playwright's slow motion) and **paused after each step**:
tick() then waits for Step or Continue (tests.live_controls). Every viewer shares one stream per browser. When the
run is collected its rows are deleted: the frames never outlive the run (its recordings stay, R5.20 (4)).
"""

from __future__ import annotations

import base64
import time
from typing import Any

from sqlalchemy import text

POLL, THUMB_EVERY, MAX_FPS, MAX_WIDTH, QUALITY = 1.0, 4.0, 4, 1280, 55
SLOW_MS, PAUSE_LIMIT = 400, 3600

# the marks: a ring where a click lands, the keys typed beside the field; drawn only while it streams (window.__eaxMark)
MARK_SCRIPT = """
(() => {
  if (window.__eaxMarks) return; window.__eaxMarks = true;
  const ring = (x, y) => { if (!window.__eaxMark) return; const d = document.createElement('div');
    d.style.cssText = `position:fixed;left:${x - 18}px;top:${y - 18}px;width:36px;height:36px;border:3px solid #e8590c;` +
      'border-radius:50%;pointer-events:none;z-index:2147483647;transition:opacity .8s;opacity:1';
    document.documentElement.appendChild(d); setTimeout(() => { d.style.opacity = '0'; }, 400); setTimeout(() => d.remove(), 1300); };
  addEventListener('mousedown', (e) => ring(e.clientX, e.clientY), true);
  addEventListener('keydown', (e) => { if (!window.__eaxMark || !e.target || !e.target.getBoundingClientRect) return;
    const r = e.target.getBoundingClientRect(); let t = document.getElementById('__eax_typed');
    if (!t) { t = document.createElement('div'); t.id = '__eax_typed'; document.documentElement.appendChild(t); }
    t.style.cssText = `position:fixed;left:${r.left}px;top:${Math.max(0, r.top - 22)}px;background:#e8590c;color:#fff;` +
      'font:12px sans-serif;padding:1px 6px;border-radius:3px;pointer-events:none;z-index:2147483647';
    t.textContent = e.key.length === 1 ? (t.dataset.k = ((t.dataset.k || '') + e.key).slice(-30)) : e.key;
    clearTimeout(window.__eaxT); window.__eaxT = setTimeout(() => { t.remove(); }, 1500); }, true);
})();
"""


class Caster:
    """One browser page of a run, streamed only while watched."""

    def __init__(self, engine, run_id: int, name: str, label: str, page, clock=time.monotonic, now=time.time):
        self.engine, self.run_id, self.name, self.label, self.page = engine, run_id, name, label, page
        self.clock, self.now = clock, now
        self.cdp: Any = None
        self.streaming = self.watched = self.large = False
        self.checked = self.last_thumb = self.last_frame = -1e9
        self.seq, self.step = 0, ""
        self.frames = self.dropped = 0
        with engine.begin() as c:
            c.execute(text("""INSERT INTO tests.live_browsers (run_id, browser, label) VALUES (:r, :b, :l)
                              ON CONFLICT (run_id, browser) DO UPDATE SET label = :l, step = '', updated_at = now()"""),
                      {"r": run_id, "b": name, "l": label[:300]})
        try:
            page.context.add_init_script(MARK_SCRIPT)
        except Exception:  # noqa: BLE001 - no marks, the frames still come
            pass

    def hold(self) -> None:
        """After a step: nothing, unless the run was started to be watched (ui_journeys sets it)."""
        return None

    # ---- what the viewers want (read at most once a POLL)
    def _wanted(self) -> tuple[bool, bool]:
        with self.engine.connect() as c:
            row = c.execute(text("""SELECT watched_until > now() AS w, large_until > now() AS l FROM tests.live_browsers
                                     WHERE run_id = :r AND browser = :b"""), {"r": self.run_id, "b": self.name}).first()
        return (bool(row[0]), bool(row[1])) if row else (False, False)

    def tick(self, step: str = "") -> None:
        """Called at each step: what the step is, and the stream started or stopped as the viewers want."""
        if step:
            self.step = step[:300]
        t = self.clock()
        if t - self.checked < POLL:
            return
        self.checked = t
        try:
            self.watched, self.large = self._wanted()
        except Exception:  # noqa: BLE001 - never in the test's way
            return
        if self.large and not self.streaming:
            self._start()
        elif not self.large and self.streaming:
            self._stop()
        if self.watched:
            self._mark(True)
            self._where()
            if not self.large and t - self.last_thumb >= THUMB_EVERY:
                self.last_thumb = t
                self._thumb()

    def _mark(self, on: bool) -> None:
        try:
            self.page.evaluate(f"window.__eaxMark = {'true' if on else 'false'}")
        except Exception:  # noqa: BLE001
            pass

    def _where(self) -> None:
        try:
            url = self.page.url
        except Exception:  # noqa: BLE001
            url = ""
        with self.engine.begin() as c:
            c.execute(text("UPDATE tests.live_browsers SET step = :s, url = :u, updated_at = now() WHERE run_id = :r AND browser = :b"),
                      {"s": self.step, "u": url[:500], "r": self.run_id, "b": self.name})

    def _session(self):
        if self.cdp is None:
            self.cdp = self.page.context.new_cdp_session(self.page)
            self.cdp.on("Page.screencastFrame", self._frame)
        return self.cdp

    def _start(self) -> None:
        try:
            self._session().send("Page.startScreencast", {"format": "jpeg", "quality": QUALITY, "maxWidth": MAX_WIDTH,
                                                          "maxHeight": MAX_WIDTH, "everyNthFrame": 1})
            self.streaming = True
        except Exception:  # noqa: BLE001 - an older image or a closed page: the tile says so
            self.streaming = False

    def _stop(self) -> None:
        try:
            if self.cdp is not None:
                self.cdp.send("Page.stopScreencast")
        except Exception:  # noqa: BLE001
            pass
        self.streaming = False
        self._mark(False)

    def _frame(self, ev: dict) -> None:
        """A frame from Chromium: acknowledged at once (or it stops sending); written only within the rate cap."""
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": ev.get("sessionId")})
        except Exception:  # noqa: BLE001
            pass
        t = self.clock()
        if t - self.last_frame < 1.0 / MAX_FPS:
            self.dropped += 1
            return
        self.last_frame = t
        self.seq += 1
        self.frames += 1
        try:
            self.put(base64.b64decode(ev.get("data") or ""))
        except Exception:  # noqa: BLE001
            pass

    def put(self, jpeg: bytes, thumb: bool = False) -> None:
        """Writes the newest frame (or tile still), replacing the one before."""
        col = "thumb" if thumb else "frame"
        with self.engine.begin() as c:
            c.execute(text(f"""UPDATE tests.live_browsers SET {col} = :f, frame_seq = :n, frame_at = now(), step = :s,
                               updated_at = now() WHERE run_id = :r AND browser = :b"""),
                      {"f": jpeg, "n": self.seq, "s": self.step, "r": self.run_id, "b": self.name})

    def _thumb(self) -> None:
        try:
            got = self._session().send("Page.captureScreenshot", {"format": "jpeg", "quality": 35,
                                                                  "clip": {"x": 0, "y": 0, "width": 1400, "height": 900, "scale": 0.25}})
            self.seq += 1
            self.put(base64.b64decode(got.get("data") or ""), thumb=True)
        except Exception:  # noqa: BLE001
            pass

    def close(self) -> None:
        """Stops streaming and removes the browser's row."""
        if self.streaming:
            self._stop()
        with self.engine.begin() as c:
            c.execute(text("DELETE FROM tests.live_browsers WHERE run_id = :r AND browser = :b"), {"r": self.run_id, "b": self.name})


# ---------------------------------------------------------------- pause after each step (a run started to be watched)
def controls(engine, run_id: int) -> dict:
    """A run's live controls (paused, steps to take, slow motion)."""
    with engine.connect() as c:
        row = c.execute(text("SELECT paused, steps, slow FROM tests.live_controls WHERE run_id = :r"), {"r": run_id}).mappings().first()
    return dict(row) if row else {"paused": False, "steps": 0, "slow": False}


def hold(engine, run_id: int, sleep=time.sleep, stopped=lambda: False, limit: float = PAUSE_LIMIT) -> str:
    """After a step: while paused, wait for Step (one step taken: steps - 1) or Continue (paused off). Never longer than
    `limit` seconds (then it goes on by itself), never past a Stop."""
    waited = 0.0
    while waited < limit and not stopped():
        with engine.begin() as c:
            row = c.execute(text("""UPDATE tests.live_controls SET steps = greatest(steps - 1, 0)
                                    WHERE run_id = :r AND paused AND steps > 0 RETURNING 'step'"""), {"r": run_id}).first()
            if row:
                return "step"
            on = c.execute(text("SELECT paused FROM tests.live_controls WHERE run_id = :r"), {"r": run_id}).scalar()
        if not on:
            return "go"
        sleep(0.5)
        waited += 0.5
    return "timeout"


def set_controls(conn, run_id: int, action: str, by: str) -> dict:
    """pause | step | continue | slow (when it starts): the run's controls."""
    if action not in ("pause", "step", "continue", "slow"):
        raise ValueError("pause, step, continue or slow.")
    conn.execute(text("""INSERT INTO tests.live_controls (run_id, paused, steps, slow, by_whom)
                         VALUES (:r, :p, 0, :s, :by)
                         ON CONFLICT (run_id) DO UPDATE SET
                             paused = CASE WHEN :a = 'continue' THEN false WHEN :a IN ('pause', 'step') THEN true ELSE tests.live_controls.paused END,
                             steps = CASE WHEN :a = 'step' THEN tests.live_controls.steps + 1 WHEN :a = 'continue' THEN 0 ELSE tests.live_controls.steps END,
                             slow = tests.live_controls.slow OR :s, by_whom = :by, updated_at = now()"""),
                 {"r": run_id, "p": action in ("pause", "step"), "s": action == "slow", "a": action, "by": by})
    return dict(conn.execute(text("SELECT paused, steps, slow FROM tests.live_controls WHERE run_id = :r"), {"r": run_id}).mappings().first())


# ---------------------------------------------------------------- the viewers (the API)
def view(conn, run_id: int, large: str = "", since: int = 0) -> dict:
    """A viewer's ask: every browser of the run watched for 30 seconds more, the one shown large at full rate; the
    tiles (with a small still) and, when it changed since `since`, the large one's newest frame."""
    conn.execute(text("""UPDATE tests.live_browsers SET watched_until = now() + interval '30 seconds',
                                large_until = CASE WHEN browser = :b THEN now() + interval '30 seconds' ELSE large_until END
                          WHERE run_id = :r"""), {"r": run_id, "b": large})
    rows = [dict(r) for r in conn.execute(text("""SELECT browser, label, step, url, frame_seq, frame_at, thumb, frame
                                                    FROM tests.live_browsers WHERE run_id = :r ORDER BY browser"""), {"r": run_id}).mappings()]
    tiles = [{"browser": r["browser"], "label": r["label"], "step": r["step"], "url": r["url"], "seq": r["frame_seq"],
              "thumb": base64.b64encode(bytes(r["thumb"])).decode() if r["thumb"] else None} for r in rows]
    big = next((r for r in rows if r["browser"] == large), None)
    frame = None
    if big and big["frame"] is not None and int(big["frame_seq"]) > int(since or 0):
        frame = {"browser": big["browser"], "seq": big["frame_seq"], "jpeg": base64.b64encode(bytes(big["frame"])).decode(),
                 "step": big["step"], "url": big["url"]}
    ctl = conn.execute(text("SELECT paused, steps, slow FROM tests.live_controls WHERE run_id = :r"), {"r": run_id}).mappings().first()
    return {"tiles": tiles, "frame": frame, "controls": dict(ctl) if ctl else {"paused": False, "steps": 0, "slow": False}}


def forget(conn, run_id: int) -> None:
    """The run's frames and controls deleted (it was collected)."""
    conn.execute(text("DELETE FROM tests.live_browsers WHERE run_id = :r"), {"r": run_id})
    conn.execute(text("DELETE FROM tests.live_controls WHERE run_id = :r"), {"r": run_id})
