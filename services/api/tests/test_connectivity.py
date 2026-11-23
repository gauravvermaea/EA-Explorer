"""Connectivity (D894; the owner, 23 Nov 2026: "In smoke and full tests please build a test api check which tests all
connectivity also this should be in heartbeat"): every connection the product depends on, made as it makes them; in
the self-test's smoke and full runs, in the public heartbeat (counts only, never waited for), on the Health page."""

from __future__ import annotations

import inspect
import time
import types
from pathlib import Path

from eax import connectivity as C
from eax import sites
from eax.testing import run as R

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT.parent / "web" / "src"


def test_every_connection_is_made_as_the_product_makes_it():
    src = inspect.getsource(C.links)
    for n in ("Database as the API", "Database as the migrations", "Database as reports", "Documents' database", "Documents",
              "Documents' queue", "Keycloak service account", "Keycloak signing keys", "Library service", "Drawn views service",
              "Operations helper", "Reports", "draw.io", "Job queue", "Backups folder"):
        assert f'"{n}"' in src, n
    assert 'd.kind == "url"' in src                             # each database part the API serves
    assert "mayan._db_token()" in inspect.getsource(C._dms_db)    # the very sign-in that failed on 23 Nov 2026 (D893)
    assert "X-Ops-Token" in inspect.getsource(C._ops)


def test_a_link_is_up_down_or_off_and_never_raises(monkeypatch):
    up = C._link("a", "X", "how", lambda: "fine")()
    assert up["status"] == "up" and up["detail"] == "fine"

    def boom():
        raise RuntimeError('certificate authentication failed for user "mayan"\nmore')
    down = C._link("b", "X", "how", boom)()
    assert down["status"] == "down" and down["detail"].startswith("certificate authentication failed")
    assert C._link("c", "X", "how", lambda: None)()["status"] == "off"


def test_check_counts_and_the_heartbeat_summary(monkeypatch):
    monkeypatch.setattr(C, "links", lambda: [C._link("a", "X", "h", lambda: "ok"), C._link("b", "X", "h", lambda: 1 / 0),
                                             C._link("c", "X", "h", lambda: None)])
    out = C.check()
    assert (out["status"], out["up"], out["down"], out["off"]) == ("degraded", 1, 1, 1)
    s = C.summary()                                               # kept: counts only, no detail
    assert s["status"] == "degraded" and s["down"] == 1 and "links" not in s
    C._kept.update(result=None, at=0.0, running=False)
    started = []
    monkeypatch.setattr(C, "_refresh", lambda: started.append(time.time()))
    assert C.summary() == {"status": "checking"}                  # never waited for: checked in the background


def test_in_the_heartbeat_the_page_and_the_site_picker():
    hb = (ROOT / "eax" / "api" / "heartbeat.py").read_text(encoding="utf-8")
    assert '"connectivity": connectivity.summary()' in hb and '@blp.route("/connectivity")' in hb
    assert "connectivity = fields.Dict(" in (ROOT / "eax" / "api" / "schemas.py").read_text(encoding="utf-8")
    colour, why, _v = sites.health_of({"status": "ok", "connectivity": {"status": "degraded", "down": 2}})
    assert colour == "amber" and "2 connections failing" in why
    assert sites.health_of({"status": "ok", "connectivity": {"status": "ok"}})[0] == "green"
    ui = (WEB / "Heartbeat.jsx").read_text(encoding="utf-8")
    assert "function Connectivity()" in ui and "{signedIn() && <Connectivity />}" in ui


def test_in_the_smoke_and_full_runs(monkeypatch):
    src = inspect.getsource(R.cmd_run)
    assert 'connectivity(r, tokens.get("super-admin", ""))' in src
    assert src.index("services_ready(r") < src.index("connectivity(r, tokens")
    assert src.index("connectivity(r, tokens") < src.index('if level == "smoke":')   # before smoke and full split
    got = []
    r = types.SimpleNamespace(recorder=lambda suite: (lambda name, outcome, *a, **k: got.append((suite, name, outcome))),
                              log=lambda m: got.append(("log", m, "")))
    body = ('{"links": [{"name": "Documents", "to": "Documents", "how": "its key", "status": "down", "detail": "refused", "ms": 3},'
            '{"name": "draw.io", "status": "up", "detail": "ok"}, {"name": "Library service", "status": "off"}]}')
    R.connectivity(r, "t", call=lambda *a, **k: (200, body))
    assert ("smoke", "connectivity: Documents", "failed") in got and ("smoke", "connectivity: draw.io", "passed") in got
    assert ("smoke", "connectivity: Library service", "skipped") in got
    got.clear()
    R.connectivity(r, "t", call=lambda *a, **k: (500, "oops"))
    assert got[0][1] == "connectivity: every connection checked" and got[0][2] == "failed"
