"""R5.47: the full self-test of 16 Nov 2026 (run 7: 70 failed; owner, 09:08: "70 tests have failed in full run, looks
like something is wrong please check"). What failed and why:

1. reports: "the reports are all there" said 45 of the 145 report dashboards were missing: they were there, but Reports
   gives at most 100 a page whatever page_size asks. The test now reads every page.
2. reports: 63 dashboards "HTTP 0: request failed: net::ERR_ABORTED": chart requests the previous dashboard still had in
   flight were aborted by the next page load and counted against the next one, and requests Reports itself cancels
   (a filter applied asks again) counted as failures. Each request now belongs to the dashboard it was made for, and an
   aborted one is not an answer (what replaced it is).
3. security: the cross-model attack hit a read without its required type (422, malformed) and a write on a route that
   does not exist (405): neither tried the role check. Now the real read (with its type) and the real create.
4. db: two foreign keys without an index (core.service_tickets.type_key, core.service_ticket_files.ticket_id; the
   service desk of R5.27): migration 0091.
And the owner, 09:12: "This needs to shwo pass fail so that we know which area is not working ... The pass and fail in
each areas tests": each area's card shows its passed, failed, warnings and skipped, live and for a finished run."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]


class FakeSession:
    """reports_check.Session without a browser: its own methods on a fake page."""
    def __init__(self, total):
        from eax.testing import reports_check as rc
        self.rc, self.total, self.asked = rc, total, []

    def api(self, path):
        self.asked.append(path)
        page = int(path.split("page:")[1].split(",")[0])
        rows = [{"slug": f"d{i}"} for i in range(page * 100, min(self.total, page * 100 + 100))]
        return 200, {"result": rows, "count": self.total}


def test_every_page_of_dashboards_is_read():
    from eax.testing import reports_check as rc
    s = FakeSession(145)
    got = rc.Session.dashboards(s)
    assert len(got) == 145 and len(s.asked) == 2 and all("page_size:100" in a for a in s.asked)


class Req:
    def __init__(self, url="/api/v1/chart/data", failure=None):
        self.url, self.failure = url, failure

    def response(self):
        class R:
            status = 200

            def text(self):
                return '{"result": [{"data": []}]}'
        return R()


def _session():
    from eax.testing import reports_check as rc
    s = rc.Session.__new__(rc.Session)
    s.pending, s.answers, s.gen, s.of = set(), [], 0, {}
    import time
    s.last = time.time()
    return s


def test_a_request_of_the_previous_dashboard_is_not_counted():
    s = _session()
    old = Req(failure="net::ERR_ABORTED")
    s._sent(old)                       # made while dashboard 0 was open
    s.gen += 1                         # the next dashboard opens (as open() does)
    s.answers = []
    s._failed(old)                     # the old request is aborted by the page load
    assert s.answers == []


def test_an_aborted_request_is_not_an_answer_but_a_real_failure_is():
    s = _session()
    a, b, c = Req(failure="net::ERR_ABORTED"), Req(failure="net::ERR_CONNECTION_RESET"), Req()
    for r in (a, b, c):
        s._sent(r)
    s._failed(a)
    s._failed(b)
    s._done(c)
    assert len(s.answers) == 2 and s.answers[0][0] == 0 and "CONNECTION_RESET" in s.answers[0][1] and s.answers[1][0] == 200
    assert not s.pending


def test_open_starts_a_new_generation():
    src = (API / "eax" / "testing" / "reports_check.py").read_text()
    body = src[src.index("    def open(self, dash"):src.index("    def shot(self)")]
    assert body.index("self.gen += 1") < body.index("self.page.goto(")


def test_the_cross_model_attack_uses_routes_that_exist():
    from eax.app import create_app
    rules = {(r.rule, m) for r in create_app(testing=True).url_map.iter_rules() for m in r.methods}
    assert ("/api/v1/models/<uuid:model_id>/entities", "GET") in rules
    assert ("/api/v1/models/<uuid:model_id>/content/entities", "POST") in rules
    src = (API / "eax" / "testing" / "attacks.py").read_text()
    assert '/entities?type=Application"' in src and '/content/entities",' in src and '"entity_type": "Application"' in src


def test_the_service_desk_foreign_keys_are_indexed():
    sql = (API / "migrations" / "sql" / "0091_service_desk_fk_indexes.sql").read_text()
    assert "ON core.service_tickets (type_key)" in sql and "ON core.service_ticket_files (ticket_id)" in sql
    assert 'down_revision = "0090_selftest_jobs_suite"' in (API / "migrations" / "versions" / "0091_service_desk_fk_indexes.py").read_text()


def test_each_area_shows_its_passed_and_failed():
    from test_r5_5_3_test_phases import Conn

    from eax.testing import store
    run = {"id": 7, "state": "running", "level": "detailed", "suites": ["api", "db", "reports"]}
    conn = Conn([{"suite": "api", "n": 2077, "last": 2077}, {"suite": "db", "n": 25, "last": 2100},
                 {"suite": "reports", "n": 173, "last": 2300}], {},
                [{"suite": "api", "outcome": "passed", "n": 2077}, {"suite": "db", "outcome": "passed", "n": 24},
                 {"suite": "db", "outcome": "failed", "n": 1}, {"suite": "reports", "outcome": "failed", "n": 65},
                 {"suite": "reports", "outcome": "passed", "n": 108}])
    got = {p["suite"]: p for p in store.phases(conn, run)}
    assert (got["api"]["passed"], got["api"]["failed"]) == (2077, 0)
    assert (got["db"]["passed"], got["db"]["failed"]) == (24, 1)
    assert (got["reports"]["passed"], got["reports"]["failed"]) == (108, 65)
    jsx = (REPO / "services" / "web" / "src" / "TestPhases.jsx").read_text(encoding="utf-8")
    assert "phase-outcomes" in jsx and "has-failed" in jsx and "passed</span>" in jsx and "failed</span>" in jsx
    runs = (REPO / "services" / "web" / "src" / "TestRuns.jsx").read_text(encoding="utf-8")
    assert "{d?.phases && <Phases phases={d.phases} />}" in runs            # a finished run's areas too
    assert '"phases": phases(conn, run)}' in (API / "eax" / "testing" / "store.py").read_text()
