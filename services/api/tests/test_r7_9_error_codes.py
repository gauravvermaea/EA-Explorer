"""Release 7.9 (D787): error codes. One list (eax/errors.json) gives every problem a code EAX-AREA-NNN with what it
means, its cause and what to do; the API's answers, the logs, System Admin's health and alerts, `eax status` and the
error guide all read it."""

import importlib.util
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API = Path(__file__).resolve().parents[1]


def _errors():
    from eax import errors
    return errors


def test_every_code_has_the_shape_and_says_what_to_do():
    items = _errors().all_errors()
    codes = [e["code"] for e in items]
    assert len(codes) == len(set(codes)), "a code is listed twice"
    for e in items:
        assert re.fullmatch(r"EAX-[A-Z]+-\d{3}", e["code"]), e["code"]
        assert e["code"].split("-")[1] == e["area"], e["code"]
        for field in ("title", "meaning", "cause", "to_do"):
            assert e.get(field, "").strip(), f"{e['code']} has no {field}"
    raw = (API / "eax" / "errors.json").read_bytes()
    assert all(b < 128 for b in raw), "the list is ASCII, so every form of eax can print it"


def test_an_answer_gets_the_code_of_its_status():
    E = _errors()
    assert E.for_status(404) == "EAX-API-404"
    assert E.for_status(413) == "EAX-API-413"
    assert E.for_status(400) == "EAX-API-400"          # not EAX-API-101, which also answers 400
    assert E.for_status(418) == "EAX-API-400"          # any other 4xx
    assert E.for_status(507) == "EAX-API-500"          # any other 5xx


def test_every_health_check_has_its_own_code_when_down():
    E = _errors()
    names = set(re.findall(r'_(?:result|http|off|schema_check)\(\s*"([^"]+)"', (API / "eax" / "health.py").read_text()))
    names |= {"Job runner", "Break-glass account", "Personal data", "Operations"}
    names -= {"API", "Backup", "Break-glass account"}    # the API is up by answering; the other two only ever warn
    for name in sorted(names):
        code = E.for_health({"name": name, "status": "down", "detail": ""})
        assert code and code != "EAX-API-503", f"{name} down has no code of its own"
    assert E.for_health({"name": "Database", "status": "up"}) == ""
    assert E.for_health({"name": "Backup", "status": "warning", "detail": "no backup yet (run: eax backup)"}) == "EAX-BAK-003"
    assert E.for_health({"name": "Backup", "status": "warning", "detail": "newest 2026-11-01 (90 h ago; limit 36 h)"}) == "EAX-BAK-004"
    assert E.for_health({"name": "Backup", "status": "warning",
                         "detail": "the nightly backup is switched off (Administration > Backups)"}) == "EAX-BAK-001"


def test_every_alert_check_has_a_code():
    from eax import alerts
    E = _errors()
    for key in alerts.DEFAULTS:
        assert E.for_alert(key), f"the alert {key} has no code"
    assert E.for_alert("custom:my-check") == "EAX-ALRT-001"
    assert E.for_alert("service:Sign-in", "not reachable", "CRITICAL") == "EAX-AUTH-001"
    assert E.for_alert("service:Job runner", "3 failed", "WARNING") == "EAX-JOB-002"


def test_problems_list_each_code_once_critical_first():
    E = _errors()
    health = {"services": [{"name": "Sign-in", "status": "down", "detail": "not reachable"},
                           {"name": "Database", "status": "up", "detail": ""}]}
    rows = [{"check_key": "disk", "state": "WARNING", "what": "Disk", "message": "85% used"},
            {"check_key": "service:Sign-in", "state": "CRITICAL", "what": "Sign-in", "message": "not reachable"},
            {"check_key": "memory", "state": "OK", "what": "Memory", "message": ""}]
    got = E.problems(health, rows)
    assert [p["code"] for p in got] == ["EAX-AUTH-001", "EAX-DISK-001"]
    assert all(p["to_do"] for p in got)


def test_an_error_answer_carries_its_code_what_to_do_and_the_header(client):
    r = client.get("/api/v1/no-such-thing-at-all")
    assert r.status_code == 404
    assert r.headers.get("X-EAX-Error-Code") == "EAX-API-404"
    body = r.get_json()
    assert body["error_code"] == "EAX-API-404"
    assert body["to_do"]
    assert body["code"] == 404                            # the HTTP status keeps its own field


def test_a_log_line_carries_the_code():
    from eax.logging_setup import JsonFormatter
    rec = logging.LogRecord("eax", logging.INFO, __file__, 1, "EAX-API-404 GET /x answered 404", None, None)
    rec.error_code = "EAX-API-404"
    assert json.loads(JsonFormatter().format(rec))["error_code"] == "EAX-API-404"
    plain = logging.LogRecord("eax", logging.INFO, __file__, 1, "nothing wrong", None, None)
    assert "error_code" not in json.loads(JsonFormatter().format(plain))


def test_eax_status_says_each_container_problem_with_its_code():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import problems as P
    rows = P.containers(['{"Service":"keycloak","State":"exited","Status":"Exited (1) 2 minutes ago","ExitCode":1}',
                         '[{"Service":"setup","State":"exited","Status":"Exited (0)","ExitCode":0},'
                         '{"Service":"web","State":"running","Status":"Up 2 hours (unhealthy)"},'
                         '{"Service":"api","State":"running","Status":"Up 2 hours (healthy)"},'
                         '{"Service":"drawio","State":"exited","Status":"Exited (0)","ExitCode":0},'
                         '{"Service":"testrunner","State":"exited","Status":"Exited (1) 13 hours ago","ExitCode":1}]'])
    got = {p["what"]: p for p in P.container_problems(rows, switched_off={"drawio"})}
    assert set(got) == {"container keycloak", "container web"}
    assert got["container keycloak"]["code"] == "EAX-AUTH-001"
    assert got["container web"]["code"] == "EAX-STACK-002"
    assert "eax logs web" in got["container web"]["to_do"]


def test_every_form_of_eax_lists_the_problems():
    help_txt = (ROOT / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    assert "### status [problems]" in help_txt
    assert "eaxpy.ps1\") status problems" in (ROOT / "eax.ps1").read_text(encoding="utf-8")
    assert "eaxpy.sh status problems" in (ROOT / "eax.sh").read_text(encoding="utf-8")
    assert 'rest[:1] == ["problems"]' in (ROOT / "eaxcli" / "main.py").read_text(encoding="utf-8")


def test_the_screens_show_the_code():
    src = ROOT / "services" / "web" / "src"
    assert "X-EAX-Error-Code" in (src / "auth.js").read_text(encoding="utf-8")
    assert "s.error_code" in (src / "Heartbeat.jsx").read_text(encoding="utf-8")
    assert "c.error_code" in (src / "AlertsPage.jsx").read_text(encoding="utf-8")


def test_the_error_guide_agrees_with_the_list_and_is_in_guide_21():
    spec = importlib.util.spec_from_file_location("error_guide", ROOT / "tools" / "error_guide.py")
    guide = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guide)
    page = guide.page()
    assert guide.PAGE.read_text(encoding="utf-8") == page, "run python tools/error_guide.py"
    for e in _errors().all_errors():
        assert f"**{e['code']}: " in page
    manuals = json.loads((ROOT / "docs" / "manuals" / "manuals.json").read_text(encoding="utf-8"))
    g21 = next(g for g in manuals["manuals"] if g["id"] == "21-troubleshooting")
    assert any("page:docs/site/guides/error-codes.md" in s for c in g21["chapters"] for s in c["sources"])


# ---------------------------------------------------------------- eax errors, Jenkins and the documents (owner, 23:25:
# "build inline and pdf docs and web / eax utility for this. ensure test cases"; 23:29: "error code can be queried from
# jenkins", "they give enviornment status")
def _cli():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import problems
    return problems


def test_eax_errors_finds_a_code_an_area_or_words():
    P = _cli()
    assert [e["code"] for e in P.find("eax-auth-001")] == ["EAX-AUTH-001"]          # any case
    assert {e["code"] for e in P.find("BAK")} == {"EAX-BAK-001", "EAX-BAK-002", "EAX-BAK-003", "EAX-BAK-004"}
    assert {e["code"] for e in P.find("EAX-BAK")} == {e["code"] for e in P.find("BAK")}
    assert "EAX-BAK-003" in {e["code"] for e in P.find("no backup")}
    assert len(P.find("")) == len(_errors().all_errors())
    assert P.find("nothing-is-called-this") == []


def test_eax_errors_says_what_to_do_and_fails_on_an_unknown_code(capsys):
    P = _cli()
    assert P.errors_main(["EAX-AUTH-001"]) == 0
    out = capsys.readouterr().out
    assert "EAX-AUTH-001" in out and "What to do:" in out and "eax logs keycloak" in out
    assert P.errors_main(["EAX-NOPE-999"]) == 1


def test_every_form_of_eax_has_the_errors_command():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import commands as C
    assert "### errors [<code-or-words>...]" in (ROOT / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    assert '"site", "errors")) -or' in (ROOT / "eax.ps1").read_text(encoding="utf-8")
    assert "|site|errors)" in (ROOT / "eax.sh").read_text(encoding="utf-8")
    assert 'command == "errors"' in (ROOT / "eaxcli" / "main.py").read_text(encoding="utf-8")
    assert C.check_argv(["errors", "EAX-AUTH-001"]) == ["errors", "EAX-AUTH-001"]       # a code is a free word
    assert C.check_argv(["errors", "no", "backup"]) == ["errors", "no", "backup"]
    assert C.check_argv(["status", "problems"]) == ["status", "problems"]


def test_jenkins_gives_the_environment_status_and_answers_an_error_code():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import jenkins as J
    names = {p["name"]: p for p in J.pipelines()}
    for want in ("status", "problems", "error-code"):
        assert names[f"admin-{want}"]["folder"] == "eax-admin/status-and-error-codes", want
        assert names[f"admin-{want}"]["confirm"] is False, want                       # they only read
    assert J.argv_for("admin-status", {}) == ["status"]
    assert J.argv_for("admin-problems", {}) == ["status", "problems"]
    assert J.argv_for("admin-error-code", {"CODE": "EAX-BAK-003"}) == ["errors", "EAX-BAK-003"]
    assert J.argv_for("admin-error-code", {}) == ["errors"]
    assert names["errors"]["params"]                                                  # the command's own pipeline
    assert "Status and error codes" in (ROOT / "docs/manuals/new/jenkins-in-ea-explorer.md").read_text(encoding="utf-8")


def test_the_on_screen_help_web_pages_and_printed_guide_explain_the_codes():
    cat = json.loads((ROOT / "services/web/src/help/catalogue.json").read_text(encoding="utf-8"))
    assert any("error code" in h for h in cat["page:#/admin/health"]["how"])
    assert any("error code" in h for h in cat["tab:Alerts"]["how"])
    howdoi = ROOT / "docs/site/how-do-i"
    for page in ("find-what-an-error-code-means", "see-every-problem-from-the-machine"):
        text = (howdoi / f"{page}.md").read_text(encoding="utf-8")
        assert "screen: #/admin/health" in text and "## Steps" in text, page
        assert f"../how-do-i/{page}.md" in (ROOT / "docs/site/guides/error-codes.md").read_text(encoding="utf-8")
    assert "eax errors" in (ROOT / "docs/command-line-and-console.md").read_text(encoding="utf-8")
    assert "error-codes.md" in (ROOT / "docs/site/guides/check-health-and-alerts.md").read_text(encoding="utf-8")
    manuals = json.loads((ROOT / "docs" / "manuals" / "manuals.json").read_text(encoding="utf-8"))
    g21 = json.dumps(next(g for g in manuals["manuals"] if g["id"] == "21-troubleshooting"))
    assert "find-what-an-error-code-means" in g21 and "status,errors,logs,diag" in g21


def test_the_error_code_guide_is_a_printed_guide_of_its_own():
    """The owner, 18 Nov 2026, 23:45: "documents ... still has 24 docs nothing for error codes" (D790): guide 25."""
    manuals = json.loads((ROOT / "docs" / "manuals" / "manuals.json").read_text(encoding="utf-8"))["manuals"]
    g25 = manuals[-1]
    assert g25["id"] == "25-error-codes" and len(manuals) == 25
    assert "page:docs/site/guides/error-codes.md" in json.dumps(g25) and "help:commands=status,errors" in json.dumps(g25)
    assert "of {total}" in (ROOT / "tools" / "build_manuals.py").read_text(encoding="utf-8")   # no "of 24" written in
