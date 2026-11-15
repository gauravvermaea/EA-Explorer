"""The self-test's reports suite (R4.1; owner, 14 Nov 2026: "add more test cases for reports", "Browser with test
users"): Keycloak test users per run, every report dashboard opened in Chromium as people, judged by what Superset
answers. The browser part runs against a real installation in the full self-test; here: its pieces."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------- what Superset answers
def test_a_chart_answer_is_ok_only_when_every_result_succeeded():
    from eax.testing.reports_check import chart_answer
    ok = json.dumps({"result": [{"status": "success", "error": None, "data": [{"model_name": "m1", "name": "Self-test a"}]}]})
    assert chart_answer(200, ok) == (True, "", [{"model_name": "m1", "name": "Self-test a"}])
    bad = json.dumps({"result": [{"status": "failed", "error": "column x does not exist", "data": []}]})
    assert chart_answer(200, bad) == (False, "column x does not exist", [])
    assert chart_answer(500, "boom")[0] is False and chart_answer(403, '{"message": "x"}')[1].startswith("HTTP 403")
    assert chart_answer(200, "<html>")[:2] == (False, "not JSON")


def test_the_owners_time_limits():
    """Owner, 13 Nov 2026: slower than 30 seconds a warning with its time, not opened after 60 a failure."""
    from eax.testing.reports_check import verdict
    assert verdict(4000, [], 6) == ("passed", "6 charts in 4.0 seconds")
    assert verdict(31000, [], 6)[0] == "warning" and "31 seconds" in verdict(31000, [], 6)[1]
    assert verdict(61000, [], 6) == ("failed", "not loaded after 60 seconds")
    assert verdict(1000, ["HTTP 500: x"], 6) == ("failed", "HTTP 500: x")
    assert verdict(1000, [], 0) == ("failed", "no chart answered")


def test_models_and_the_runs_names_in_the_rows():
    from eax.testing.reports_check import models_in, names_in
    rows = [{"model_name": "self_test_1_1", "name": "Self-test reports 1 committed"}, {"model_name": "Other", "x": 3},
            {"name": "Unrelated"}]
    assert models_in(rows) == {"self_test_1_1", "Other"}
    assert names_in(rows) == {"Self-test reports 1 committed"}


def test_every_report_is_expected_in_reports():
    from eax.report_defs import REPORTS
    from eax.testing.reports_check import expected_dashboards
    assert expected_dashboards() == {r["slug"] for r in REPORTS} and len(expected_dashboards()) >= 30


def test_three_kinds_of_person_and_their_keycloak_roles():
    """The Superset roles follow these realm roles (superset_config.AUTH_ROLES_MAPPING)."""
    from eax.testing.reports_check import PEOPLE
    assert PEOPLE == {"super-admin": "eax-super-admin", "report-viewer": "eax-user", "it-admin": "eax-it-admin"}
    cfg = (REPO / "deploy/superset/superset_config.py").read_text()
    assert '"eax-super-admin": ["Admin"]' in cfg and '"eax-it-admin": ["Gamma"]' in cfg and '"eax-user": ["Gamma", READER]' in cfg


def test_a_password_satisfies_the_usual_policies():
    from eax.testing.reports_check import password
    p = password()
    assert len(p) >= 24 and any(c.isupper() for c in p) and any(c.islower() for c in p) and any(c.isdigit() for c in p) \
        and "!" in p and p != password()


# ---------------------------------------------------------------- Keycloak test users
class _Resp(io.BytesIO):
    def __init__(self, status: int, body):
        super().__init__(json.dumps(body).encode() if body is not None else b"")
        self.status, self.headers = status, {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeKeycloak:
    """Stands in for Keycloak's admin API: records each call."""

    def __init__(self, users=None, token_status=200):
        self.calls, self.users, self.token_status = [], users or [], token_status

    def __call__(self, req, timeout=0):
        url, method = req.full_url, req.get_method()
        self.calls.append((method, url.split("/auth", 1)[1]))
        if url.endswith("/realms/master/protocol/openid-connect/token"):
            if self.token_status != 200:
                raise urllib.error.HTTPError(url, self.token_status, "no", {}, io.BytesIO(b"{}"))
            return _Resp(200, {"access_token": "t"})
        if method == "POST" and url.endswith("/users"):
            body = json.loads(req.data)
            self.users.append({"id": f"id-{body['username']}", "username": body["username"], "attributes": body["attributes"]})
            return _Resp(201, None)
        if method == "GET" and "/users?exact=true" in url:
            name = url.split("username=")[1]
            return _Resp(200, [u for u in self.users if u["username"] == name])
        if method == "GET" and "/users?search=" in url:
            return _Resp(200, self.users)
        if method == "GET" and "/roles/" in url:
            return _Resp(200, {"id": "r1", "name": url.rsplit("/", 1)[1]})
        if method == "DELETE":
            return _Resp(204, None)
        return _Resp(204, None)


def test_a_test_user_has_a_password_for_good_and_one_realm_role():
    from eax.testing.reports_check import Keycloak
    fake = FakeKeycloak()
    kc = Keycloak("http://keycloak:8080/auth", "eaexplorer", "kcadmin", "pw", opener=fake)
    kc.sign_in()
    uid = kc.make("svc-self-test-7-report-viewer", "Secret1!", "eax-user")
    assert uid == "id-svc-self-test-7-report-viewer"
    assert ("POST", "/admin/realms/eaexplorer/users/id-svc-self-test-7-report-viewer/role-mappings/realm") in fake.calls
    assert ("GET", "/admin/realms/eaexplorer/roles/eax-user") in fake.calls
    assert kc.remove(uid) and ("DELETE", "/admin/realms/eaexplorer/users/id-svc-self-test-7-report-viewer") in fake.calls


def test_users_a_stopped_run_left_are_found_after_a_day_but_never_this_runs():
    from eax.testing.reports_check import Keycloak
    old = {"id": "a", "username": "svc-self-test-3-it-admin", "attributes": {"eax_self_test": ["2026-11-01T10:00:00+00:00"]}}
    new = {"id": "b", "username": "svc-self-test-4-it-admin", "attributes": {"eax_self_test": ["2026-11-14T10:00:00+00:00"]}}
    mine = {"id": "c", "username": "svc-self-test-9-it-admin", "attributes": {"eax_self_test": ["2026-11-01T10:00:00+00:00"]}}
    person = {"id": "d", "username": "svc-self-test-someone", "attributes": {}}
    kc = Keycloak("http://k/auth", "r", "u", "p", opener=FakeKeycloak([old, new, mine, person]))
    from datetime import datetime
    assert kc.stale("9", now=datetime.fromisoformat("2026-11-14T12:00:00+00:00").timestamp()) == ["a"]


def test_without_the_administrator_nothing_else_runs():
    from eax.testing import reports_check as rc
    got = []
    kc = rc.Keycloak("http://k/auth", "r", "u", "p", opener=FakeKeycloak(token_status=401))
    sent = []
    out = rc.run("https://api", {"super-admin": "a", "model-admin": "m", "report-viewer": "v"},
                 {"sid": "5", "model": "g", "model_name": "self_test_5_1"}, lambda *a, **k: got.append(a),
                 log=lambda m: None, send=lambda *a: sent.append(a) or (200, "[]"), keycloak=kc, playwright=lambda: None)
    assert got == [("reports: Keycloak test users", "failed", "Keycloak's administrator could not sign in (401)", got[0][3])]
    assert out["failed"] == 1
    assert [a[1:3] for a in sent][:2] == [("post", "/api/v1/models/g/content/entities"), ("post", "/api/v1/models/g/changes/commit")]


def test_without_a_test_model_it_is_skipped():
    from eax.testing import reports_check as rc
    got = []
    rc.run("https://api", {}, {}, lambda *a, **k: got.append(a), playwright=lambda: None)
    assert got[0][:2] == ("reports: Keycloak test users", "skipped")


# ---------------------------------------------------------------- wired in
def test_a_suite_of_the_full_test_before_the_backups():
    from eax.testing import SUITES, WEB_SUITES
    assert SUITES == ("api", "ui", "db", "security", "reports", "performance", "backup", "restore") and "reports" in WEB_SUITES
    run = (REPO / "services/api/eax/testing/run.py").read_text()
    assert run.index('if "reports" in suites:') < run.index('if "backup" in suites:')
    assert 'reports_check.run(API, tokens, ids, r.recorder("reports"), r.log)' in run
    sql = (REPO / "services/api/migrations/sql/0075_selftest_reports_suite.sql").read_text()
    assert "'security', 'reports', 'backup', 'restore']" in sql and "'security', 'reports', 'backup', 'restore'))" in sql
    assert 'down_revision = "0074_release_3_5_0"' in (REPO / "services/api/migrations/versions/0075_selftest_reports_suite.py").read_text()
    assert '"reports": (5, 15)' in (REPO / "services/api/eax/testing/store.py").read_text()
    assert 'export const ALL_SUITES = ["api", "ui", "db", "security", "reports", "backup"];' in \
        (REPO / "services/web/src/selfTestDriver.js").read_text()
    assert "  reports  only the reports (part of full, R4.1)" in (REPO / "eaxcli/help.txt").read_text()


def test_the_services_under_test_no_longer_name_the_two_parts_of_the_api():
    """R3.5-M1b: operations and personal are served by the API container; a run said they were off."""
    from eax.testing.run import UNDER_TEST
    assert "operations" not in UNDER_TEST and "personal" not in UNDER_TEST and "reports" in UNDER_TEST


def test_reports_switched_off_is_skipped_with_the_reason():
    """R4.1 (6): Reports switched off or still starting is said and skipped, never a failure of EA Explorer."""
    from eax.testing import run as rn
    got = []

    class R:
        ready = {"reports": "off"}
        counts: dict = {}

        def recorder(self, suite):
            return lambda *a, **k: got.append((suite, *a))

        def log(self, m):
            pass
    rn._reports_suite(R(), {}, {})
    assert got == [("reports", "reports: every report opens", "skipped", "Reports is switched off", 0)]


# ---------------------------------------------------------------- R4.1 (3) to (5)
def _xlsx(text_: str) -> bytes:
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/worksheets/sheet1.xml", "<x/>")
        z.writestr("xl/sharedStrings.xml", f"<sst><si><t>{text_}</t></si></sst>")
    return buf.getvalue()


def test_a_report_file_must_open_and_name_the_model():
    from eax.testing.reports_check import opens_as
    assert opens_as(b"%PDF-1.7 ... %%EOF\n", "pdf") == (True, "a PDF of 19 bytes")
    assert opens_as(b"<html>error</html>", "pdf")[0] is False
    assert opens_as(_xlsx("self_test_5_1"), "xlsx", "self_test_5_1") == (True, "a workbook of 1 sheets with the model's name")
    assert opens_as(_xlsx("other"), "xlsx", "self_test_5_1")[1] == "a workbook of 1 sheets without the model's name"
    assert opens_as(b"not a zip", "xlsx")[1] == "not a workbook"


def test_the_files_are_fetched_as_the_report_viewer(monkeypatch):
    from eax.testing import reports_check as rc
    asked = []

    def fetch(base, path, token):
        asked.append((path, token))
        return (200, b"%PDF-1 %%EOF") if path.endswith("/pdf") else (200, _xlsx("self_test_5_1")) if "quality" in path \
            else (500, b"boom")
    monkeypatch.setattr(rc, "fetch", fetch)
    got = []
    rc.files("https://api", {"report-viewer": "v"}, {"model": "g", "model_name": "self_test_5_1"},
             lambda n, o, d, ms=0, **k: got.append((n, o)))
    assert got == [("files: the quality report as PDF", "passed"), ("files: the quality report as Excel", "passed"),
                   ("files: the model's tree as Excel", "failed")]
    assert {t for _p, t in asked} == {"v"} and asked[2][0] == "/api/v1/models/g/tree/xlsx?scope=entities"


def test_the_import_at_start_up_must_say_none_failed():
    from eax.testing import reports_check as rc
    for line, outcome in (("EA Explorer: report dashboards imported: 3 new or changed, 40 unchanged, 0 failed (12 s)", "passed"),
                          ("EA Explorer: report dashboards imported: 3 new or changed, 39 unchanged, 1 failed (12 s)", "failed")):
        got = []
        rc.import_log("https://api", "t", lambda *a, got=got, **k: got.append(a),
                      send=lambda *a, line=line: (200, json.dumps({"lines": ["x", f"2026-11-14T10:00:00Z {line}"]})))
        assert got[0][1] == outcome
    got = []
    rc.import_log("https://api", "t", lambda *a, **k: got.append(a), send=lambda *a: (200, json.dumps({"lines": []})))
    assert got[0][1] == "warning"


def test_from_the_screens_a_reports_link_opens_it_signed_in(monkeypatch):
    from eax.testing import reports_check as rc
    monkeypatch.setattr(rc, "reports_url", lambda: "https://reports.localhost")
    ok = json.dumps({"result": [{"status": "success", "data": []}]})

    class Viewer:
        class page:
            url = "https://reports.localhost/superset/dashboard/application-inventory/"

        def open(self, d):
            assert d == {"url": "/login/keycloak?next=/superset/dashboard/application-inventory/"}
            return 900, [(200, ok)]

        def shot(self):
            return None
    links = {"reports": [{"url": "https://reports.localhost/login/keycloak?next=/superset/dashboard/application-inventory/"}]}
    got = []
    rc._from_screens("https://api", {"report-viewer": "v"}, "g", Viewer(), {"application-inventory"},
                     lambda n, o, d, ms=0, **k: got.append((n, o)), lambda *a: (200, json.dumps(links)))
    assert got == [("from the screens: a model's Reports tab links every report", "passed"),
                   ("from the screens: a report's link opens it, signed in as the same person", "passed")]
