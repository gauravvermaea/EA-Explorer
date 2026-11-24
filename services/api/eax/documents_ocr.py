"""Documents' OCR: on or off, when it may run, and how far it has got (D903; owner, 23 Nov 2026, 22:45 to 22:54).

"In the whole thing can OCR be turned off by default. We should be able to turn it on in a setting in admin"; "When on in
the status or monitoring tab constantly show how many documents what percent done and so on"; "It should be also a
status for all users to see"; "Also add ability to schedule it so that documents can be indexed at night".

The settings (System Admin > Settings > Documents): documents_ocr (off unless chosen) and the window documents_ocr_from
and documents_ocr_to (HH:MM, local; both empty: any time). Outside the window the OCR jobs waiting are parked aside in
Documents' broker, so Documents reads nothing; inside it they are put back and reading carries on where it stopped.
Every minute (the job eax.documents_ocr_tick) the window is kept and the progress recorded in core.settings under
documents_ocr_progress: the documents asked to be read, the pages waiting (parked included), the most there were, the
percent done, when it started and when it was last looked at. Everyone signed in sees it (GET /api/v1/documents-ocr).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, time

from sqlalchemy import text

from . import mayan

KEY = "documents_ocr_progress"
PARKED = "eax_ocr_parked|"            # a parked queue: eax_ocr_parked|<when>|<its own name>
DONE_AFTER_SECONDS = 180              # no page waiting for this long after the start: done (Documents queues pages late)
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ---------------------------------------------------------------- the window
def window(values: dict) -> tuple[time, time] | None:
    """The OCR window (from, to) as times, or None: any time (both empty, or either not HH:MM)."""
    a, b = (values.get("documents_ocr_from") or "").strip(), (values.get("documents_ocr_to") or "").strip()
    if not (HHMM.match(a) and HHMM.match(b)) or a == b:
        return None
    return time.fromisoformat(a), time.fromisoformat(b)


def inside(win: tuple[time, time] | None, now: time) -> bool:
    """Whether now is inside the window (one that passes midnight, 22:00 to 06:00, included)."""
    if win is None:
        return True
    a, b = win
    return a <= now < b if a < b else (now >= a or now < b)


# ---------------------------------------------------------------- the queue: counted, parked, put back, cleared
def _keys(pattern: str) -> list[str]:
    keys, cursor = [], "0"
    while True:
        cursor, found = mayan._broker(("SELECT", "0"), ("SCAN", cursor, "MATCH", pattern, "COUNT", "1000"))[1]
        keys += found
        if cursor == "0":
            return keys


def queue() -> dict:
    """{waiting, parked}: the OCR jobs in Documents' queues and those parked aside."""
    live, parked = _keys("ocr*"), _keys(PARKED + "*")
    count = lambda keys: sum(int(n or 0) for n in mayan._broker(("SELECT", "0"), *[("LLEN", k) for k in keys])[1:]) if keys else 0  # noqa: E731
    return {"waiting": count(live), "parked": count(parked)}


def park(stamp: str) -> int:
    """The OCR queues moved aside, so Documents reads nothing; returns how many jobs were moved."""
    moved = 0
    for k in _keys("ocr*"):
        n = int(mayan._broker(("SELECT", "0"), ("LLEN", k))[1] or 0)
        mayan._broker(("SELECT", "0"), ("RENAME", k, f"{PARKED}{stamp}|{k}"))
        moved += n
    return moved


def unpark() -> int:
    """The parked queues put back under their own names (added to any that filled meanwhile); returns how many jobs."""
    back = 0
    for p in _keys(PARKED + "*"):
        own = p.split("|", 2)[2]
        n = int(mayan._broker(("SELECT", "0"), ("LLEN", p))[1] or 0)
        if not mayan._broker(("SELECT", "0"), ("EXISTS", own))[1]:
            mayan._broker(("SELECT", "0"), ("RENAME", p, own))
        else:                                           # the queue filled meanwhile: these go after it, in their order
            mayan._broker(("SELECT", "0"), *[("LMOVE", p, own, "RIGHT", "LEFT") for _ in range(n)])
        back += n
    return back


def clear() -> int:
    """Every OCR job, waiting or parked, deleted; returns how many there were."""
    q = queue()
    keys = _keys("ocr*") + _keys(PARKED + "*")
    if keys:
        mayan._broker(("SELECT", "0"), ("DEL", *keys))
    return q["waiting"] + q["parked"]


# ---------------------------------------------------------------- the progress, kept in core.settings
def _read(conn) -> dict:
    r = conn.execute(text("SELECT value FROM core.settings WHERE key = :k"), {"k": KEY}).scalar()
    if isinstance(r, str):
        try:
            r = json.loads(r)
        except ValueError:
            r = None
    return r if isinstance(r, dict) else {}


def _write(conn, state: dict) -> None:
    conn.execute(text("""INSERT INTO core.settings (key, value, name) VALUES (:k, CAST(:v AS jsonb), 'Documents OCR progress')
                         ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, modified_at = now()"""),
                 {"k": KEY, "v": json.dumps(state)})


def _now() -> datetime:
    return datetime.now(UTC)


def started(conn, documents: int) -> dict:
    """Switched on: the documents asked to be read; the count starts again."""
    state = {"state": "running", "documents": documents, "peak": 0, "waiting": 0, "parked": 0,
             "started_at": _now().isoformat(), "checked_at": _now().isoformat()}
    _write(conn, state)
    return state


def stopped(conn, cleared: int) -> dict:
    """Switched off: how many OCR jobs were cleared; nothing is counted until it is switched on again."""
    state = {"state": "off", "cleared": cleared, "checked_at": _now().isoformat()}
    _write(conn, state)
    return state


def tick(conn, values: dict, now_local: time | None = None) -> dict:
    """Every minute: the window kept (parked outside it, put back inside) and the progress recorded."""
    state = _read(conn)
    if not values.get("documents_ocr"):
        return state
    win = window(values)
    now_local = now_local or datetime.now().time()
    if inside(win, now_local):
        unpark()
    else:
        park(_now().strftime("%Y%m%dT%H%M%S"))
    q = queue()
    pending = q["waiting"] + q["parked"]
    peak = max(int(state.get("peak") or 0), pending)
    begun = state.get("started_at") or _now().isoformat()
    age = (_now() - datetime.fromisoformat(begun)).total_seconds()
    if pending:
        phase = "parked" if q["parked"] and not q["waiting"] else "running"
    else:
        phase = "done" if age >= DONE_AFTER_SECONDS or state.get("state") == "done" else "running"
    state = {**state, "state": phase, "waiting": q["waiting"], "parked": q["parked"], "peak": peak, "started_at": begun,
             "checked_at": _now().isoformat()}
    _write(conn, state)
    return state


def status(conn, values: dict) -> dict:
    """What everyone sees: on or off, the window, and how far it has got."""
    state = _read(conn)
    on = bool(values.get("documents_ocr"))
    win = window(values)
    pending = int(state.get("waiting") or 0) + int(state.get("parked") or 0)
    peak = max(int(state.get("peak") or 0), pending)
    percent = 100 if state.get("state") == "done" else (round(100 * (peak - pending) / peak) if peak else 0)
    phase = state.get("state") if on else "off"
    words = {"off": "OCR is off", "done": "every page read",
             "parked": f"waiting for the window ({win[0]:%H:%M} to {win[1]:%H:%M})" if win else "waiting",
             "running": f"{percent}% done, {pending} page(s) to go"}.get(phase or "", "not started")
    return {"on": on, "state": phase or "not started", "window": [f"{win[0]:%H:%M}", f"{win[1]:%H:%M}"] if win else None,
            "documents": state.get("documents"), "waiting": int(state.get("waiting") or 0),
            "parked": int(state.get("parked") or 0), "peak": peak, "percent": percent,
            "started_at": state.get("started_at"), "checked_at": state.get("checked_at"), "words": words}
