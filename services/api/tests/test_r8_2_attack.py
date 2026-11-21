"""R8.2 (D817): the attack test, `eax test attack` (owner, 21 Nov 2026, 10:15: "Build what is needed for R 8.2 so that
we can run it"). What is checked here, without Docker or a running installation:

  the suite     on demand only (never in the full test), the security suite with it, its constraint migration
  the scope     the fuzzer's description: reads, and writes only on the run's own things; never DELETE, admin or
                download paths; the token file written for the helper and deleted after
  the helper    each scanner pulled first and its version kept, offline the last image used, missing ones left out;
                the commands each scanner runs; a server refused unless marked a test installation
  the reports   Nuclei, Semgrep, Gitleaks, Schemathesis and the ZAP full scan read into the gate's findings; SQL built
                from text accepted as D800 says; one result a tool
  forged tokens unsigned, expired, tampered and rubbish tokens made for the security suite's new attack
  the command   in the help, the command list and the launchers, which pass it to the helper"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax.testing import (  # noqa: E402
    FULL_SUITES,
    ON_DEMAND,
    SUITES,
    attack_scope,
    attacks,
    security_gate,
    store,
)


def _ops(name: str):
    spec = importlib.util.spec_from_file_location(f"ops_{name}_r82", REPO / f"services/ops/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- the suite
def test_attack_is_a_suite_run_only_by_name():
    assert "attack" in SUITES and "attack" in ON_DEMAND and "attack" not in FULL_SUITES
    assert store.clean_suites("attack") == ["attack"] and "attack" not in store.clean_suites(None)
    assert store.estimate_minutes("detailed", ["attack"])[1] >= 180
    ops = _ops("testruns")
    assert "attack" in ops.SUITES and "attack" in ops.ON_DEMAND and "attack" not in ops.suites_of("all")


def test_the_command_brings_the_security_suite_with_it():
    src = (REPO / "services/ops/testruns.py").read_text()
    assert 'if "attack" in suites and "security" not in suites:' in src
    assert "_attackscans().run_all(H, info, folder, WORK, host_work(), say)" in src
    assert "attack_allowed()" in src.split("def run_sequence", 1)[1]


def test_the_constraint_takes_the_new_suite():
    sql = (REPO / "services/api/migrations/sql/0110_selftest_attack_suite.sql").read_text()
    body = "\n".join(line for line in sql.splitlines() if not line.startswith("--"))
    assert "'performance', 'attack', 'backup'" in body and body.count("'attack'") == 2
    py = (REPO / "services/api/migrations/versions/0110_selftest_attack_suite.py").read_text()
    assert 'down_revision = "0109_release_7_9_0"' in py and "0110_selftest_attack_suite.sql" in py


# ---------------------------------------------------------------- the scope
SPEC = {"openapi": "3.0.3", "components": {"schemas": {"Thing": {"type": "object"}}}, "paths": {
    "/api/v1/models": {"get": {"parameters": [{"name": "q", "in": "query"}]}, "post": {"requestBody": {}}},
    "/api/v1/models/{model}": {"get": {}, "put": {"requestBody": {"content": {}}}, "delete": {}},
    "/api/v1/models/{model}/entities/{entity}": {"patch": {"requestBody": {}}, "get": {"parameters": [
        {"name": "model", "in": "path"}, {"name": "Authorization", "in": "header"}, {"name": "fields", "in": "query"}]}},
    "/api/v1/admin/users/{user}": {"get": {}, "put": {}},
    "/api/v1/backups/{name}": {"get": {}},
    "/api/v1/models/{model}/export": {"get": {}},
    "/api/v1/projects/{nothing_known}": {"get": {}, "post": {}},
}}
IDS = {"model": "m-1", "entity": "e-1", "user": "u-1"}


def _fill(path, ids):
    from eax.testing.api_matrix import fill
    return fill(path, ids)


def test_reads_everywhere_writes_only_on_the_run_s_own_things_never_delete():
    t = attack_scope.targets(SPEC, IDS, _fill)
    p = t["paths"]
    assert set(p["/api/v1/models"]) == {"get"}                         # a bare collection: no POST (outside test data)
    assert set(p["/api/v1/models/m-1"]) == {"get", "put"}             # the run's model: written, never deleted
    assert set(p["/api/v1/models/m-1/entities/e-1"]) == {"get", "patch"}
    assert not any(k.startswith(("/api/v1/admin", "/api/v1/backups")) for k in p)
    assert "/api/v1/models/m-1/export" not in p
    assert not any("nothing_known" in k or "{" in k for k in p)       # an id the run does not have: left out
    assert t["servers"] == [{"url": "https://proxy"}] and t["components"] == {"schemas": {"Thing": {"type": "object"}}}
    got = p["/api/v1/models/m-1/entities/e-1"]["get"]["parameters"]
    assert [x["name"] for x in got] == ["fields"]                     # no path params, never an Authorization header
    assert "requestBody" in p["/api/v1/models/m-1"]["put"] and "requestBody" not in p["/api/v1/models/m-1"]["get"]
    assert attack_scope.counts(t) == {"get": 3, "put": 1, "patch": 1}


def test_the_scope_and_token_are_written_and_the_token_forgotten(tmp_path):
    n = attack_scope.prepare(tmp_path, SPEC, IDS, "tok.en.value", _fill)
    assert n["get"] == 3
    assert json.loads((tmp_path / "attack-openapi.json").read_text())["info"]["title"].endswith("attack test scope)")
    auth = tmp_path / "attack-auth.txt"
    assert auth.read_text() == "tok.en.value" and oct(auth.stat().st_mode)[-3:] == "600"
    attack_scope.forget_token(tmp_path)
    assert not auth.exists()
    attack_scope.forget_token(tmp_path)                                # already gone: no error


# ---------------------------------------------------------------- the helper's scanners
class _Docker:
    """Stands in for the docker command line: records each call; pulls fail when offline."""

    def __init__(self, offline=(), missing=()):
        self.calls, self.offline, self.missing = [], set(offline), set(missing)

    def __call__(self, args, timeout=0, env=None):
        self.calls.append(args)
        if args[:2] == ["docker", "pull"]:
            image = args[-1]
            return (1, "no network") if any(k in image for k in self.offline | self.missing) else (0, "")
        if args[:3] == ["docker", "image", "inspect"]:
            image = args[-1]
            return (1, "Error: no such image") if any(k in image for k in self.missing) else (0, "repo@sha256:abcdef1234567890|2026-11-20")
        return 0, ""


def test_each_scanner_is_brought_up_to_date_first_and_its_version_kept(tmp_path):
    A = _ops("attackscans")
    d = _Docker(offline=("nuclei",), missing=("gitleaks",))
    got = A.versions(str(tmp_path), lambda m: None, d)
    assert [c[2] for c in d.calls if c[:2] == ["docker", "pull"]] == ["--quiet"] * len(A.IMAGES)
    assert got["zap"]["pulled"] and got["zap"]["note"] == "the newest"
    assert got["nuclei"]["present"] and not got["nuclei"]["pulled"] and got["nuclei"]["note"].startswith("offline")
    assert not got["gitleaks"]["present"]
    kept = json.loads((tmp_path / "attack-tools.json").read_text())["tools"]
    assert kept["zap"]["digest"] == "repo@sha256:abcdef1234567890"


def test_the_whole_run_calls_each_tool_and_leaves_out_one_that_is_not_there(tmp_path):
    A = _ops("attackscans")
    work = tmp_path / "work"
    here = work / "tests" / "RUN"
    here.mkdir(parents=True)
    (here / "attack-openapi.json").write_text("{}")
    (here / "attack-auth.txt").write_text("abc.def.ghi")
    d = _Docker(missing=("gitleaks",))
    containers = [{"id": "c1", "service": "api", "name": "eaexplorer-api-1", "state": "running"},
                  {"id": "c2", "service": "ops", "name": "eaexplorer-ops-1", "state": "running"},
                  {"id": "c3", "service": "db", "name": "eaexplorer-db-1", "state": "exited"}]
    inspect = {"c1": {"Config": {"ExposedPorts": {"8000/tcp": {}, "8001/tcp": {}, "53/udp": {}}},
                      "NetworkSettings": {"Networks": {"x_backend": {}, "x_frontend": {}}}}}
    H = {"containers": lambda: containers, "docker": lambda *a, **k: json.dumps(inspect[a[-1]])}
    info = {"NetworkSettings": {"Networks": {"x_backend": {}, "x_frontend": {}}}}
    said = []
    ran = A.run_all(H, info, "RUN", str(work), "/host/repo/work", said.append, d)
    assert ran == {"zap": True, "schemathesis": True, "nuclei": True, "semgrep": True}
    joined = [" ".join(c) for c in d.calls]
    zap = next(c for c in joined if "zap-full-scan.py" in c)
    assert "--network x_frontend" in zap and "-t https://proxy/" in zap and "-J zap-full.json" in zap
    fuzz = next(c for c in d.calls if "schemathesis" in " ".join(c) and c[1] == "run")
    assert "abc.def.ghi" not in " ".join(fuzz)                         # the token by the environment, never the command
    assert not (here / "attack-auth.txt").exists()
    nuc = [c for c in joined if "-l /out/nuclei-targets" in c]
    assert len(nuc) == 2 and all("-etags dos,fuzz,intrusive" in c for c in nuc)
    assert (here / "nuclei-targets-0.txt").read_text().split() == ["eaexplorer-api-1:8000", "eaexplorer-api-1:8001"]
    sem = next(c for c in joined if " semgrep scan " in f" {c} ")
    assert "-v /host/repo:/src:ro" in sem and "--metrics off" in sem and "--exclude work" in sem
    assert not any("gitleaks git" in c for c in joined)
    assert any("gitleaks" in m and "left out" in m for m in said)


def test_a_server_is_refused_unless_marked_a_test_installation():
    A = _ops("attackscans")
    assert A.allowed({})[0] and A.allowed({"EAX_DEPLOYMENT": "laptop"})[0]
    ok, why = A.allowed({"EAX_DEPLOYMENT": "server"})
    assert not ok and "EAX_ATTACK_ALLOWED=yes" in why and "Nothing was run" in why
    assert A.allowed({"EAX_DEPLOYMENT": "server", "EAX_ATTACK_ALLOWED": "yes"})[0]


def test_the_folder_beside_work_in_the_host_s_own_spelling():
    A = _ops("attackscans")
    assert A.repo_of("/home/me/eax/work") == "/home/me/eax"
    assert A.repo_of("C:\\Users\\me\\EA-Enterpise\\work") == "C:\\Users\\me\\EA-Enterpise"


def test_the_ops_image_carries_the_new_module():
    assert "COPY attackscans.py /app/attackscans.py" in (REPO / "services/ops/Dockerfile").read_text()


# ---------------------------------------------------------------- the reports, read
def test_each_tool_s_report_becomes_findings(tmp_path):
    (tmp_path / "nuclei.jsonl").write_text(json.dumps({"template-id": "exposed-panel", "info": {"name": "Panel", "severity": "high"},
                                                       "matched-at": "db:5432"}) + "\nnot json\n")
    (tmp_path / "semgrep.json").write_text(json.dumps({"results": [
        {"check_id": "python.lang.security.audit.formatted-sql-query", "path": "/src/services/api/eax/x.py", "start": {"line": 9},
         "extra": {"severity": "ERROR", "message": "SQL"}},
        {"check_id": "javascript.react.dangerous-html", "path": "/src/web/a.jsx", "start": {"line": 3},
         "extra": {"severity": "WARNING", "message": "html"}}]}))
    (tmp_path / "gitleaks.json").write_text(json.dumps([{"RuleID": "generic-api-key", "Description": "key", "File": "a.env",
                                                         "StartLine": 2, "Commit": "0123456789abcdef"}]))
    (tmp_path / "schemathesis").mkdir()
    (tmp_path / "schemathesis" / "junit.xml").write_text(
        '<testsuites><testsuite><testcase name="GET /api/v1/models/m-1"><failure message="Server error">500</failure>'
        '</testcase><testcase name="PUT /api/v1/models/m-1"><failure message="Response violates schema"/></testcase>'
        '<testcase name="ok"/></testsuite></testsuites>')
    (tmp_path / "zap-full.json").write_text(json.dumps({"site": [{"@name": "https://proxy", "alerts": [
        {"pluginid": "40012", "riskcode": "3", "alert": "XSS"}]}]}))
    f = security_gate.collect(tmp_path)
    by = {x["source"]: [] for x in f}
    for x in f:
        by[x["source"]].append(x)
    assert by["nuclei"][0]["severity"] == "high" and by["nuclei"][0]["where"] == "db:5432"
    assert [x["severity"] for x in by["semgrep"]] == ["high", "medium"]
    assert by["semgrep"][0]["where"] == "services/api/eax/x.py:9"
    assert by["gitleaks"][0]["severity"] == "high" and "commit 0123456789ab" in by["gitleaks"][0]["where"]
    assert {(x["id"], x["severity"]) for x in by["schemathesis"]} == {("fuzz:server-error", "high"),
                                                                      ("fuzz:not-as-described", "medium")}
    assert by["zap-full"][0]["severity"] == "high"


def test_sql_built_from_text_is_accepted_for_semgrep_as_for_bandit():
    accept = security_gate.accepted()
    sql = security_gate.finding("semgrep", "semgrep:python.lang.security.audit.formatted-sql-query", "high", "SQL", "x.py:1")
    other = security_gate.finding("semgrep", "semgrep:python.flask.security.injection.ssrf", "high", "SSRF", "x.py:2")
    g = security_gate.gate([sql, other], accept)
    assert [x["id"] for x in g["failing"]] == ["semgrep:python.flask.security.injection.ssrf"]


def test_one_result_a_tool_and_one_for_their_versions(tmp_path):
    (tmp_path / "attack-tools.json").write_text(json.dumps({"tools": {
        "zap": {"present": True, "pulled": True, "digest": "z@sha256:1111111111111111", "note": "the newest"},
        "nuclei": {"present": True, "pulled": False, "digest": "n@sha256:2222", "note": "offline: the last one pulled"},
        "gitleaks": {"present": False, "pulled": False, "note": "not there and could not be pulled"}}}))
    (tmp_path / "zap-full.json").write_text("{}")
    got = []
    found = [security_gate.finding("zap-full", "zap:1", "high", "x"), security_gate.finding("zap-full", "zap:2", "low", "y")]
    attack_scope.judge(tmp_path, lambda n, o, d="", ms=0: got.append((n, o, d)), found)
    names = {n: (o, d) for n, o, d in got}
    assert names["attack test: the scanners brought up to date"][0] == "warning"
    assert "offline" in names["attack test: the scanners brought up to date"][1]
    zap = next(v for k, v in names.items() if "ZAP full scan" in k)
    assert zap == ("passed", "1 high, 1 low")
    git = next(v for k, v in names.items() if "Gitleaks" in k)
    assert git[0] == "warning" and "could not be pulled" in git[1]
    assert len(got) == 1 + len(attack_scope.REPORTS)


def test_the_new_kinds_show_in_the_security_trend():
    assert security_gate.kind_of("attack test: OWASP ZAP full scan of the front door (as no one)") == "zap-full"
    assert security_gate.kind_of("attack test: Nuclei's templates against every container's ports") == "nuclei"
    assert security_gate.kind_of("OWASP ZAP signed-in API scan") == "zap-api"


# ---------------------------------------------------------------- forged tokens
def _claims(tok: str) -> dict:
    part = tok.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def test_forged_tokens_are_made_from_a_real_one_and_from_nothing():
    real = "aGVhZA.Ym9keQ.c2lnbmF0dXJl"
    got = dict(attacks.forged(real))
    assert set(got) == {"unsigned (alg none), claiming Super Admin", "long expired, claiming Super Admin", "rubbish",
                        "its own token with the signature changed", "its own token claiming Super Admin, the old signature kept"}
    assert got["unsigned (alg none), claiming Super Admin"].endswith(".")
    assert _claims(got["long expired, claiming Super Admin"])["exp"] == 1_000_000_000
    changed = got["its own token with the signature changed"]
    assert changed != real and changed.rsplit(".", 1)[0] == real.rsplit(".", 1)[0]
    kept = got["its own token claiming Super Admin, the old signature kept"]
    assert kept.endswith(".c2lnbmF0dXJl") and _claims(kept)["realm_access"]["roles"] == ["super-admin"]
    opaque = dict(attacks.forged("opaquetoken"))
    assert opaque["its own token with a character changed"] == "opaquetokeA"


def test_the_forged_tokens_are_part_of_the_security_suite():
    src = (REPO / "services/api/eax/testing/attacks.py").read_text()
    assert "        forged_tokens(base, architect, record)\n" in src


# ---------------------------------------------------------------- the runner and the command
def test_the_runner_prepares_the_scope_and_collect_reads_the_reports():
    src = (REPO / "services/api/eax/testing/run.py").read_text()
    assert '            if "attack" in suites:                   # the attack test (R8.2)' in src
    assert "attack_scope.judge(r.dir, r.recorder(\"attack\"), security_gate.collect(r.dir))" in src
    assert src.count("attack_scope.forget_token(r.dir)") == 3           # whatever happens, the token goes


def test_the_command_is_in_the_help_and_the_list():
    helptext = (REPO / "eaxcli/help.txt").read_text(encoding="utf-8")
    assert "|performance|attack|sonar" in helptext and "$ {eax} test attack" in helptext
    assert "  attack  the attack test (R8.2; part of full from the command line, D823)" in helptext
    cmds = (REPO / "eaxcli/commands.py").read_text()
    assert '"clean", "sonar", "attack"]' in cmds and '"performance", "attack", "backup", "all"]' in cmds
    for launcher in ("eax.ps1", "eax.sh"):                              # passed through to the helper as it is
        assert "ops.py" in (REPO / launcher).read_text(encoding="utf-8")


# ---------------------------------------------------------------- the documents (owner, 21 Nov 2026, 10:27: "ensure
# command line and testing documents are being updated ... Add new guide for security testing and performance testing")
def test_a_printed_guide_and_a_website_guide_for_security_and_performance_testing():
    manuals = json.loads((REPO / "docs/manuals/manuals.json").read_text(encoding="utf-8"))["manuals"]
    g = manuals[-1]
    assert g["id"] == "26-security-and-performance-testing" and g["title"] == "Security and performance testing guide"
    sources = [s for c in g["chapters"] for s in c["sources"]]
    assert "page:docs/site/guides/test-security-and-performance.md" in sources and "help:commands=test,sonar" in sources
    page = (REPO / "docs/site/guides/test-security-and-performance.md").read_text(encoding="utf-8")
    for words in ("eax test attack", "eax test performance", "eax test sonar", "eax test security", "EAX_ATTACK_ALLOWED=yes",
                  "Schemathesis", "Nuclei", "Semgrep", "Gitleaks", "security_accepted.json", "attack-tools.json"):
        assert words in page, words


def test_the_testing_document_has_the_new_tests():
    md = (REPO / "docs/testing.md").read_text(encoding="utf-8")
    assert "| **Attack test** (R8.2) |" in md and "eax test attack" in md and "| Attack (on demand, R8.2) |" in md
    assert "| **Benchmark** (R5.18) |" in md and "| **SonarQube scan** (Release 8) |" in md


# ---------------------------------------------------------------- Jenkins (owner, 21 Nov 2026, 10:47: "Add pipeline in
# Jenkins to do attack")
def test_jenkins_has_an_attack_test_pipeline():
    sys.path.insert(0, str(REPO))
    from eaxcli import jenkins as J
    task = J.ADMIN_BY_NAME["admin-attack-test"]
    assert task["argv"] == ["test", "attack"] and task["group"] == "Upkeep" and len(task["summary"]) <= 102
    got = next(p for p in J.pipelines() if p["name"] == "admin-attack-test")
    assert got["folder"] == "eax-admin/upkeep" and got["display"] == "attack-test" and got["params"] == []
    assert J.admin_argv("admin-attack-test", {}) == ["test", "attack"]
    test = next(p for p in J.pipelines() if p["name"] == "test")
    what = next(f for f in test["params"] if f["key"] == "what")
    assert "attack" in what["choices"]                                  # and the test pipeline offers it too
    doc = (REPO / "docs/manuals/new/jenkins-in-ea-explorer.md").read_text(encoding="utf-8")
    assert "## Testing from Jenkins" in doc and "**attack-test**" in doc


# ---------------------------------------------------------------- in the full test (owner, 21 Nov 2026, 13:03: "make
# attack part of full test suite from command line"; D823)
def test_the_full_test_from_the_command_line_has_the_attack_test(monkeypatch, capsys):
    T = _ops("testruns")
    seen = {}
    monkeypatch.setattr(T, "run_sequence", lambda level, suites, *a, **k: seen.update(level=level, suites=list(suites))
                        or {"code": 0, "run_id": 1, "folder": "f", "results": {}})
    for args, allowed, want in ((["full"], (True, "ok"), True), (["full", "--no-attack"], (True, "ok"), False),
                                (["full", "--ci"], (True, "ok"), False),
                                (["full"], (False, "This is a server installation: no"), False)):
        monkeypatch.setattr(T, "attack_allowed", lambda a=allowed: a)
        seen.clear()
        try:
            T.cli(args)
        except Exception:  # noqa: BLE001, S110 - only what reached run_sequence matters here
            pass
        assert ("attack" in seen["suites"]) is want, args
        assert set(T.FULL_SUITES) - {"restore"} <= set(seen["suites"]) and seen["level"] == "detailed"
    out = capsys.readouterr().out
    assert "left out of this full test (--no-attack)" in out and "left out of this full test: This is a server installation" in out


def test_naming_suites_never_adds_the_attack_test(monkeypatch):
    T = _ops("testruns")
    seen = {}
    monkeypatch.setattr(T, "attack_allowed", lambda: (True, "ok"))
    monkeypatch.setattr(T, "run_sequence", lambda level, suites, *a, **k: seen.update(suites=list(suites)) or {"code": 0})
    try:
        T.cli(["--suite", "security"])
    except Exception:  # noqa: BLE001, S110
        pass
    assert seen["suites"] == ["security"]
