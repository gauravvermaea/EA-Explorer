"""R12.2 (Release 12, stabilisation): the full test of 19 Nov 2026 failed the metamodel's Hierarchy page on
"POST https://localhost/api/v1/operations/deploys/questions: 503 (as super-admin)". The Hierarchy page never asks the
Deploy questions: the Deploy page before it in the sweep did, the operations helper (busy running that very test)
answered late with 503, and the answer landed while the next page was being judged. Now each page is judged only on
the requests it made itself, and the helper answering 502, 503 or 504 is a warning, as the deploy check already has it
(run.deploy_page). A server error of the API itself still fails the page."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax.testing import ui_pages  # noqa: E402

FOUND = {"head": "Hierarchy", "notFound": False, "links": []}
BUSY = "POST https://localhost/api/v1/operations/deploys/questions: 503"


def test_the_helper_busy_is_a_warning_not_a_failure():
    outcome, detail = ui_pages.judge(FOUND, [BUSY], "ok")
    assert outcome == "warning" and "the operations helper did not answer in time" in detail and "deploys/questions" in detail


def test_a_server_error_of_the_api_itself_still_fails_the_page():
    assert ui_pages.judge(FOUND, ["GET https://localhost/api/v1/models/x/hierarchy: 500"], "ok")[0] == "failed"
    assert ui_pages.judge(FOUND, [BUSY, "GET https://localhost/api/v1/models: 503"], "ok")[0] == "failed"
    assert ui_pages.judge(FOUND, ["POST https://localhost/api/v1/operations/deploys/questions: 500"], "ok")[0] == "failed"


def test_with_nothing_wrong_it_passes_as_before():
    assert ui_pages.judge(FOUND, [], "ok") == ("passed", "renders, has a heading, F1 help")


class _Page:
    """Stands in for Playwright's page: the events, and a sweep of two pages where the first one's answer comes late."""

    def __init__(self):
        self.handlers = {}
        self.route = ""

    def on(self, name, fn):
        self.handlers.setdefault(name, []).append(fn)

    def fire(self, name, arg):
        for fn in self.handlers.get(name, []):
            fn(arg)


class _Req:
    def __init__(self, method):
        self.method = method


class _Resp:
    def __init__(self, req, url, status):
        self.request, self.url, self.status = req, url, status


def test_a_late_answer_to_the_page_before_is_not_counted_against_this_page():
    """The sweep's own handlers, as it sets them up: a request made before errors are cleared for the next page is not
    that page's."""
    src = (REPO / "services/api/eax/testing/ui_pages.py").read_text(encoding="utf-8")
    body = src.split("def sweep(", 1)[1]
    assert 'page.on("request", lambda q: mine.add(id(q)))' in body
    assert "and id(r.request) in mine else None" in body
    assert "errors.clear()\n        mine.clear()" in body
    errors, mine = [], set()
    p = _Page()
    p.on("request", lambda q: mine.add(id(q)))
    p.on("response", lambda r: errors.append(f"{r.request.method} {r.url}: {r.status}")
         if "/api/" in r.url and r.status >= 500 and id(r.request) in mine else None)
    deploy_q = _Req("POST")
    p.fire("request", deploy_q)                      # the Deploy page asks its questions
    errors.clear()
    mine.clear()                                     # the sweep moves on to the Hierarchy page
    own = _Req("GET")
    p.fire("request", own)
    p.fire("response", _Resp(deploy_q, "https://localhost/api/v1/operations/deploys/questions", 503))   # late
    assert errors == []
    p.fire("response", _Resp(own, "https://localhost/api/v1/models/x/hierarchy", 500))                 # its own
    assert errors == ["GET https://localhost/api/v1/models/x/hierarchy: 500"]
