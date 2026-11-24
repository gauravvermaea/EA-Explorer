"""Release 14's open bugs (owner, 24 Nov 2026, 06:08: "please fix everything in bugs you can"): R14.18, R14.16, R14.31
and the rest, each with its test."""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
WEB = REPO / "services/web/src"
sys.path.insert(0, str(REPO))


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------- R14.16: one SonarQube scan at a time
def test_a_second_scan_is_refused_while_one_runs(monkeypatch, tmp_path):
    from eaxcli import core
    from eaxcli import sonar as S
    monkeypatch.setattr(S, "LOCK", tmp_path / "tests/sonar/running")
    monkeypatch.setattr(S, "WORK", tmp_path)
    S.take_lock(now=1000.0)
    with pytest.raises(core.Failure, match="Another SonarQube scan is running"):
        S.take_lock(now=1000.0 + 600)                        # ten minutes later: the first still runs
    S.take_lock(now=1000.0 + S.LOCK_HOURS * 3600 + 1)          # a lock left by a scan that stopped: taken over


def test_the_scan_lets_go_of_its_lock_however_it_ends(monkeypatch, tmp_path):
    from eaxcli import core
    from eaxcli import sonar as S
    monkeypatch.setattr(S, "LOCK", tmp_path / "running")
    monkeypatch.setattr(S, "docker_ok", lambda: True)

    def boom(rest):
        assert S.LOCK.is_file()
        raise core.Failure("the scanner stopped")
    monkeypatch.setattr(S, "_scan", boom)
    with pytest.raises(core.Failure):
        S.main([])
    assert not S.LOCK.exists()


# ---------------------------------------------------------------- R14.18: the Jenkins pipelines that could never run
def test_the_admin_pipelines_that_take_ea_explorer_offline_ask_for_its_name():
    from eaxcli import jenkins as J
    by = {p["name"]: p for p in J.pipelines()}
    assert all(by[n]["confirm"] for n in ("admin-start", "admin-maintenance-page-on", "admin-maintenance-page-off",
                                          "admin-maintenance-clear", "menu", "screen", "console"))
    assert not by["status"]["confirm"]                       # a command that changes nothing still asks for nothing


# ---------------------------------------------------------------- the TOGAF roles saved are shown at once
def test_my_profile_shows_the_roles_it_saved_not_the_old_copy():
    src = _read(WEB / "Skills.jsx")
    assert "setTg({ roles: r.togaf_roles ?? tg?.roles ?? [], levels: r.togaf_levels ?? tg?.levels ?? {} });" in src
    assert "refreshAll(); setTg(null);" not in src


def test_the_skills_journey_checks_what_a_token_account_can_see():
    from eax.testing import ui_flows as F
    j = next(x for x in F.JOURNEYS if x["name"] == "TOGAF skills: on my profile, then by role")
    sels = [s.get("expect_sel") for s in j["steps"]]
    assert sels.count('label:has-text("Data Architect") input:checked') == 2
    assert {"expect": "Data Architect"} not in j["steps"]     # a token account is not among the organisation's people



# ---------------------------------------------------------------- R14.23: eax diag wrote only its header and footer
def test_eax_diag_is_handed_to_the_one_python_report():
    """D331: one program. The PowerShell copy of the report (Save-Diagnostics) wrote an empty report on 22 Nov 2026;
    eax diag is now the Python one, with this test, in every form."""
    ps1, sh = _read(REPO / "eax.ps1"), _read(REPO / "eax.sh")
    assert '"sonar", "images", "diag"))' in ps1 and '"diag"    { Save-Diagnostics }' not in ps1
    assert "sonar|images|diag)" in sh and "  diag)    diagnostics ;;" not in sh


def test_the_report_holds_each_command_and_its_answer(monkeypatch, tmp_path):
    import io

    from eaxcli import core

    class FakePopen:
        def __init__(self, args, **kw):
            self.stdout = io.StringIO(f"answer of {args[0]} {args[-1]}\n")

        def wait(self):
            return 0

    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_VERSION=13.0.0\nEAX_DB_PASSWORD=secret\n", encoding="utf-8")
    log = io.StringIO()
    monkeypatch.setattr(core, "ENV_FILE", env)
    monkeypatch.setattr(core, "compose_out", lambda args: ["api", "db"])
    monkeypatch.setattr(core, "compose_args", lambda args: ["docker", "compose", *args])
    monkeypatch.setattr(core.subprocess, "Popen", FakePopen)
    monkeypatch.setitem(core._log, "file", log)
    core.diagnostics()
    text = log.getvalue()
    body = text.split("==================== DIAGNOSTICS", 1)[1].split("==================== END DIAGNOSTICS", 1)[0]
    for part in ("> docker version", "> docker compose version", "> docker system df", "EAX_VERSION=13.0.0", " ps -a",
                 " images", "logs --no-color --timestamps --tail 300 api", "logs --no-color --timestamps --tail 300 db",
                 "answer of docker"):
        assert part in body, part
    assert "secret" not in body                                    # only the settings it names, never a password


# ---------------------------------------------------------------- coverage joined: the runner sees work/tests
def test_a_runner_the_helper_starts_sees_the_unit_tests_coverage_beside_its_folder():
    """The full test of 24 Nov 2026 said "joined": false: the helper mounted only the run's folder, so the self-test could
    not read work/tests/unit-coverage.json (nor the earlier runs' figures) one level up."""
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location("testruns_r14_cov", REPO / "services/ops/testruns.py")
    tr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tr)
    own = [{"Destination": "/eax-work", "Source": "/host/work"}]
    tr.H["docker"] = lambda *a, **k: json.dumps(own) if a[0] == "inspect" else ""
    tr.socket.gethostname = lambda: "ops"
    tr.runner_image = lambda info=None: "eaexplorer/testrunner:dev"
    info = {"Config": {"Env": []}, "NetworkSettings": {"Networks": {"eax_backend": {}}}}
    args = tr._runner_args(info, "eax-testrunner", "F1", ["run"])
    pairs = [args[i + 1] for i, a in enumerate(args) if a == "-v"]
    assert "/host/work/tests:/results:ro" in pairs and "/host/work/tests/F1:/results/F1" in pairs
    assert pairs.index("/host/work/tests:/results:ro") < pairs.index("/host/work/tests/F1:/results/F1")   # the folder on top


# ---------------------------------------------------------------- R14.27 / R14.33: what would slow a full test down
def test_a_full_test_says_first_when_docker_has_too_little_memory_or_ocr_is_waiting(monkeypatch):
    from eaxcli import preflight as P
    said = []
    monkeypatch.setattr(P, "warn", said.append)
    monkeypatch.setattr(P, "say", lambda t="", c="": None)

    def run(args):
        if args[:2] == ["docker", "info"]:
            return 0, str(8 * P.GB)
        return 0, "queue 7000\nqueue 445\ndone\n"
    found = P.check(run, compose_args=lambda a: ["docker", "compose", *a])
    assert len(found) == 2 and said == found
    assert "8.0 GB" in found[0] and f"about {P.NEED_GB} GB" in found[0]
    assert "7445 OCR job(s) waiting" in found[1] and "packs ocr --clear" in found[1]


def test_nothing_is_said_when_nothing_is_in_the_way(monkeypatch):
    from eaxcli import preflight as P
    monkeypatch.setattr(P, "warn", lambda t: (_ for _ in ()).throw(AssertionError(t)))
    monkeypatch.setattr(P, "say", lambda t="", c="": None)
    run = lambda args: (0, str(32 * P.GB)) if args[:2] == ["docker", "info"] else (0, "done\n")   # noqa: E731
    assert P.check(run, compose_args=lambda a: a) == []
    assert P.ocr_waiting(lambda a: (1, ""), compose_args=lambda a: a) is None       # Documents off: nothing said


def test_the_full_test_runs_the_check_first():
    src = _read(REPO / "eaxcli/main.py")
    assert src.index("preflight.check()") < src.index('steps.append(full_step("dev check"')


# ---------------------------------------------------------------- R14.32: the seed asks for no right eax_migrator lacks
NOT_GIVEN_TO_THE_MIGRATOR = ("CREATE TEMP", "TEMPORARY TABLE", "CREATE EXTENSION", "CREATE ROLE", "ALTER ROLE",
                             "CREATE DATABASE", "ALTER SYSTEM", "CREATE SCHEMA")


def test_the_seed_asks_for_no_right_the_production_database_does_not_give_its_login():
    """D896: the Release 12 model upgrade made a temporary table; eax_migrator may not (the production database takes every
    right from PUBLIC: deploy/postgres/initdb), and the test database gave every right, so nothing caught it. Until a
    database set up as in production runs in CI, the seed's own SQL is read for what that login may not do."""
    import re
    api = REPO / "services/api/eax"
    files = sorted((api / "seed").rglob("*.py")) + [api / "industry_packs.py", api / "library_models.py"]
    bad = []
    for f in files:
        if not f.is_file():
            continue
        text = re.sub(r"#.*", "", _read(f)).upper()
        bad += [f"{f.name}: {w}" for w in NOT_GIVEN_TO_THE_MIGRATOR if w in text]
    assert bad == [], bad
    initdb = _read(REPO / "deploy/postgres/initdb/01-databases.sh")
    assert 'REVOKE ALL ON DATABASE :"eax_db" FROM PUBLIC;' in initdb            # the rule this test stands for


# ---------------------------------------------------------------- SonarQube's findings on the full test's summary page
def test_the_scan_keeps_a_snapshot_of_what_is_still_to_fix_worst_first():
    """Owner, 24 Nov 2026, 06:40: "When you run tests, put sonar's snapshot of findings on the test report too"."""
    from eax.testing import sonar as S
    issues = [{"component": "eax-explorer:eaxcli/a.py", "line": 3, "rule": "python:S1", "type": "CODE_SMELL", "severity": "MINOR",
               "message": "small"},
              {"component": "eax-explorer:eaxcli/b.py", "line": 9, "rule": "python:S2", "type": "BUG", "severity": "BLOCKER",
               "message": "big"},
              {"component": "eax-explorer:eaxcli/c.py", "line": 1, "rule": "python:S3", "type": "BUG", "severity": "MINOR",
               "message": "accepted"}]
    accepted = [{"rule": "python:S3", "file": "eaxcli/c.py"}]
    rows = S.snapshot(issues, [], accepted)
    assert [r["file"] for r in rows] == ["eaxcli/b.py", "eaxcli/a.py"]          # the accepted one left out, the bug first
    assert rows[0] == {"file": "eaxcli/b.py", "line": 9, "kind": "BUG", "severity": "BLOCKER", "rule": "python:S2",
                       "message": "big"}


def test_the_summary_page_shows_the_findings_and_keeps_them(tmp_path):
    import json

    from eaxcli import fullreport as F
    sq = tmp_path / "sonar-20261124-060000"
    sq.mkdir()
    (sq / "summary.json").write_text(json.dumps({"passed": False, "to_fix": 2, "issues": 5, "hotspots": 0, "accepted": 3}))
    (sq / "to_fix.json").write_text(json.dumps([{"file": "eaxcli/b.py", "line": 9, "kind": "BUG", "severity": "BLOCKER",
                                                 "rule": "python:S2", "message": "<big>"}]))
    s = F.gather(tmp_path, 0, [("SonarQube scan", False, "issues to fix")])
    assert s["sonar"]["findings"][0]["file"] == "eaxcli/b.py"               # kept in summary.json
    html = F.page(s)
    assert "Still to fix" in html and "<code>eaxcli/b.py:9</code>" in html and "&lt;big&gt;" in html
    assert "The first 1 of 2" in html
    assert F.sonar_table([], 0) == "<p>No finding to fix.</p>"


# ---------------------------------------------------------------- SonarQube's slow patterns, read by hand
def test_the_drill_rows_read_by_hand_give_what_the_pattern_gave():
    import random
    import re

    from eaxcli.fullreport import drill_row
    old = re.compile(r"^\| (ok|warn|FAILED) \| (.*?) \| (\d+) \| (.*) \|\s*$")
    rnd = random.Random(7)
    parts = ["| ", "ok", "warn", "FAILED", " | ", "12", "7", "a", " ", "|", "x", " |"]
    for _ in range(50000):
        s = "".join(rnd.choice(parts) for _ in range(rnd.randint(0, 12)))
        m = old.match(s)
        assert drill_row(s) == ((m.group(1), m.group(2), int(m.group(3))) if m else None), s


def test_the_headings_pattern_reads_one_line_each():
    import re
    src = _read(REPO / "services/api/eax/mcp_docs.py")
    pat = r"^(#{2,3})[ \t]+(\S.*)$"
    assert f're.finditer(r"{pat}", text, re.M)' in src and 're.match(r"^(#{1,6})[ \\t]+(\\S.*)$", line)' in src
    text = "# T\n## One\n### Two  \n##\n## Three\n#### not\n"
    assert [m.group(2).strip() for m in re.finditer(pat, text, re.M)] == ["One", "Two", "Three"]   # "##" no longer eats "## Three"


def test_the_sheet_number_is_read_without_a_pattern():
    for src in ("eaxcli/packs.py", "services/api/eax/industry_packs.py"):
        assert 'int(n[len("xl/worksheets/sheet"):-len(".xml")])' in _read(REPO / src)


def test_sample_numbers_are_the_same_every_time_and_not_pythons_random():
    from eax.seed import sample_machine_ops as M
    a, b = M.Seeded(25), M.Seeded(25)
    assert [a.randint(3, 60) for _ in range(20)] == [b.randint(3, 60) for _ in range(20)]
    xs = [M.Seeded(n).random() for n in range(200)]
    assert all(0 <= x < 1 for x in xs) and len(set(xs)) == 200
    assert sorted(M.Seeded(1).sample(list(range(10)), 10)) == list(range(10))
    assert "import random" not in _read(REPO / "services/api/eax/seed/sample_machine_ops.py")
    assert "Math.random" not in _read(REPO / "services/ops/benchmark.js")


def test_the_images_take_only_what_they_run():
    for f, want in (("services/api/Dockerfile", "COPY eax ./eax"), ("services/api/Dockerfile.test", "COPY eax ./eax"),
                    ("services/library/Dockerfile", "COPY libsvc ./libsvc"), ("services/views/Dockerfile", "COPY viewsvc ./viewsvc")):
        src = _read(REPO / f)
        assert "COPY . ." not in src and want in src, f


def test_functions_have_one_way_out_and_do_the_same():
    from datetime import date

    from eax import calendars
    ev = {"starts_on": date(2026, 1, 5), "repeat": "none", "until_on": None, "times": None, "skipped": []}
    assert calendars.occurrences(ev, date(2026, 1, 1), date(2026, 1, 31)) == [date(2026, 1, 5)]
    assert calendars.occurrences(ev, date(2026, 2, 1), date(2026, 2, 28)) == []
    ev = {**ev, "repeat": "daily", "times": 3}
    assert calendars.occurrences(ev, date(2026, 1, 1), date(2026, 1, 31)) == [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)]
    for f in ("eax/testing/discovery_check.py", "eax/testing/jobs_check.py", "eax/testing/reports_check.py",
              "eax/testing/mcp_check.py", "eax/testing/discovery_projects_check.py"):
        src = _read(REPO / "services/api" / f)
        body = src[src.index("def run("):]
        body = body[:body.index("\ndef ", 1)] if "\ndef " in body[1:] else body
        assert body.count("return counts") == 1, f


def test_the_rest_of_sonarqubes_list_is_accepted_in_writing_by_the_owner():
    import json
    acc = json.loads(_read(REPO / "services/api/eax/testing/sonar_accepted.json"))["accepted"]
    mine = [a for a in acc if "D907" in a.get("by", "")]
    assert len(mine) == 39 and all(a["reason"] and a["file"] != "*" for a in mine)
    assert {"python:S4790", "python:S4502", "python:S2068", "python:S5332"} <= {a["rule"] for a in mine}


# ---------------------------------------------------------------- R14.35: the helper's problem once, with its code
def test_the_helper_not_reachable_has_its_own_code_in_every_wording():
    """Owner, 23 Nov 2026, 21:27 (one problem shown three times) and 24 Nov 2026, 06:41: "Add the code now"."""
    import json
    codes = {e["code"]: e for e in json.loads(_read(REPO / "services/api/eax/errors.json"))["errors"]}
    e = codes["EAX-OPS-002"]
    assert e["title"] == "Operations helper not reachable" and "eax logs ops" in e["to_do"] and e["http"] == 503
    for f in ("services/api/eax/api/admin.py", "services/api/eax/admin_check.py", "services/api/eax/api/backups.py"):
        src = _read(REPO / f)
        assert src.count("The operations helper is not reachable") == src.count("is not reachable (EAX-OPS-002"), f
    page = _read(WEB / "ContainerConsole.jsx")
    assert "{h?.helper && !known &&" in page and "known={error}" in page        # said once on the Containers page


# ---------------------------------------------------------------- R14.4: Superset's own image accepted in writing
def test_findings_inside_the_reports_image_are_accepted_until_a_newer_superset():
    from eax.testing import security_gate as G
    acc = [a for a in G.accepted() if a["where"] == "image superset" and a["id"] == "*"]
    assert len(acc) == 1 and acc[0]["until"] == "2027-02-24" and "D907" in acc[0]["by"]
    inside = G.finding("trivy", "CVE-2024-26669", "HIGH", "linux-libc-dev", "image superset", fix=True)
    ours = G.finding("trivy", "CVE-2026-86144", "HIGH", "openssl", "image backup", fix=True)
    out = G.gate([inside, ours], G.accepted(), today=__import__("datetime").date(2026, 12, 1))
    assert [f["where"] for f in out["accepted"]] == ["image superset"] and [f["where"] for f in out["failing"]] == ["image backup"]
    assert "6.1.0" in _read(REPO / "deploy/superset/Dockerfile")                    # the newest Superset, 24 Nov 2026


# ---------------------------------------------------------------- last night's warnings, fixed where they could be
def test_the_maintenance_page_has_a_csp_that_allows_its_own_script_only():
    """ZAP (full test, 24 Nov 2026): "Content Security Policy (CSP) Header Not Set", the maintenance page shown while the
    screens were busy. Its one script is allowed by its hash; any change to the script must change the hash."""
    import base64
    import hashlib
    import re
    page = _read(REPO / "deploy/proxy/static/eax-maintenance.html")
    scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
    assert len(scripts) == 1
    want = "sha256-" + base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode()
    conf = _read(REPO / "deploy/proxy/templates/default.conf.template")
    places = [ln for ln in conf.splitlines() if "location = /eax-maintenance.html" in ln]
    assert len(places) == 4
    for ln in places:
        assert f"script-src '{want}'" in ln and "default-src 'none'" in ln and "always" in ln


def test_the_views_check_says_it_is_skipped_in_certificate_mode(monkeypatch):
    from eax.testing import db_checks as D
    monkeypatch.setenv("EAX_AUTH_MODE", "certificate")
    outcome, why = D.drawn_view_bindings(None, "host=db user=eax_views")
    assert outcome == "skipped" and "certificate mode" in why


def test_a_report_fails_only_after_120_seconds():
    """Owner, 24 Nov 2026, 06:55: "Make timeout 120" (it was 60; under load nine took 32 to 55 seconds)."""
    from eax.testing import reports_check as R
    assert (R.WARN_MS, R.FAIL_MS) == (30000, 120000)
    assert "timeout=60000" not in _read(REPO / "services/api/eax/testing/reports_check.py")


# ---------------------------------------------------------------- every list of models a 500 (the full test, 24 Nov 2026)
def test_no_module_defines_the_same_name_twice():
    """A helper split out for SonarQube (D907) took the name of another function further down the same file
    (repository._library_counts); Python keeps the last, so list_models called the wrong one and every list of models,
    in the screens, the API and MCP, was a server error. Lint does not see it when the first is used before the second."""
    import ast
    import collections
    known = {("services/api/eax/api/schemas.py", "RuleResultOut")}   # older: each use bound before the second (harmless)
    bad = []
    for base in ("services/api/eax", "eaxcli", "services/ops", "testbench"):
        for f in sorted((REPO / base).rglob("*.py")):
            tree = ast.parse(_read(f))
            names = collections.Counter(n.name for n in tree.body
                                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
            rel = f.relative_to(REPO).as_posix()
            bad += [f"{rel}: {k} x{v}" for k, v in names.items() if v > 1 and (rel, k) not in known]
    assert bad == [], bad


def test_the_list_of_models_fills_in_the_library_models_counts(monkeypatch):
    from contextlib import contextmanager

    from eax import library_models as lm
    from eax import repository as repo

    class Rows:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return self.rows

    class Conn:
        def execute(self, *a, **k):
            return Rows([{"model_id": "m1", "etc": 3, "ec": 40, "rc": 12, "icon": "lib:cloud", "iv": 7}])

    @contextmanager
    def connect():
        yield Conn()

    monkeypatch.setattr(lm, "routed", lambda: False)
    monkeypatch.setattr(lm, "connect", connect)
    rows = [{"_id": "m1", "content_schema": lm.SCHEMA, "icon": None}, {"_id": "m2", "content_schema": "core"}]
    out = repo._library_parts(rows)
    assert out is rows and rows[0]["entity_count"] == 40 and rows[0]["icon"] == "lib:cloud" and "entity_count" not in rows[1]

    @contextmanager
    def away():
        raise RuntimeError("library schema away")
        yield
    monkeypatch.setattr(lm, "connect", away)
    rows = [{"_id": "m1", "content_schema": lm.SCHEMA}]
    assert repo._library_parts(rows) == [{"_id": "m1", "content_schema": lm.SCHEMA}]   # shown, without counts


def test_the_ocr_journey_starts_the_first_run_setup_with_its_cards_button():
    from eax.testing import ui_flows as F
    j = next(x for x in F.JOURNEYS if x["name"] == "documents ocr: the setting and its first-run step")
    step = next(s for s in j["steps"] if s.get("opens") == ".ed-dialog")
    assert step == {"click": "Start", "within": '.wiz-card:has-text("First-run setup")', "opens": ".ed-dialog"}
    assert '<Card title="First-run setup"' in _read(WEB / "SystemWizards.jsx") and "<button onClick={onClick}>Start…</button>" in _read(WEB / "SystemWizards.jsx")
