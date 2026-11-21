"""Release 8, R8 (D740, D792): SonarQube in the self-test. `eax test sonar` scans the whole repository with the newest
SonarQube and its default rules (owner, 19 Nov 2026, 00:07: "Newest + Sonar way"), writes every issue into a report and
fails on any issue not accepted in writing. Every fix made from it is tested before and after (00:09)."""

import json
import sys
import urllib.error
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


def _s():
    from eax.testing import sonar
    return sonar


ISSUES = [
    {"key": "a", "rule": "python:S1192", "component": "ea-explorer:services/api/eax/app.py", "line": 10,
     "type": "CODE_SMELL", "severity": "CRITICAL", "message": "Define a constant"},
    {"key": "b", "rule": "python:S5754", "component": "ea-explorer:eaxcli/main.py", "line": 3,
     "impacts": [{"softwareQuality": "RELIABILITY", "severity": "HIGH"}], "message": "Catch a narrower exception"},
    {"key": "c", "rule": "javascript:S6582", "component": "ea-explorer:services/web/src/auth.js", "line": 7,
     "impacts": [{"softwareQuality": "SECURITY", "severity": "MEDIUM"}, {"softwareQuality": "MAINTAINABILITY", "severity": "LOW"}],
     "message": "Prefer an optional chain"},
]
HOTSPOTS = [{"key": "h", "ruleKey": "python:S4790", "component": "ea-explorer:services/api/eax/x.py", "line": 5,
             "vulnerabilityProbability": "LOW", "message": "Weak hash"}]


def test_sonarqube_and_its_scanner_are_in_the_test_profile_only_with_no_port():
    svc = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    for name in ("sonarqube", "sonar-scanner"):
        assert svc[name]["profiles"] == ["test"], name
        assert "ports" not in svc[name], name                                  # only the proxy publishes ports
        assert svc[name]["networks"] == ["backend"], name                      # the internal network
    assert "sonarqube:community" in svc["sonarqube"]["image"]                 # the newest Community Build
    assert svc["sonarqube"]["environment"]["SONAR_TELEMETRY_ENABLE"] == "false"
    assert "./:/usr/src:ro" in svc["sonar-scanner"]["volumes"]                # the repository, read only
    web = (ROOT / "services/web/src/ContainerConsole.jsx").read_text(encoding="utf-8")
    assert "sonarqube:" in web and '"sonar-scanner":' in web                  # every container says what it is for


def test_the_scan_covers_the_code_and_leaves_out_what_is_made_or_downloaded():
    props = dict(line.split("=", 1) for line in (ROOT / "sonar-project.properties").read_text(encoding="utf-8").splitlines()
                 if "=" in line and not line.startswith("#"))
    assert props["sonar.projectKey"] == "ea-explorer" and props["sonar.sources"] == "."
    for out in ("**/node_modules/**", "work/**", "documents/**", "services/web/public/site/**", "services/api/tests/**"):
        assert out in props["sonar.exclusions"], out
    assert props["sonar.tests"] == "services/api/tests,services/web/tests,deploy/drawio/tests"   # D804: every test folder                       # tests read as tests, not twice


def test_kind_and_severity_read_from_old_and_new_issues():
    S = _s()
    assert [S.kind_of(i) for i in ISSUES] == ["CODE_SMELL", "BUG", "VULNERABILITY"]
    assert [S.severity_of(i) for i in ISSUES] == ["CRITICAL", "HIGH", "MEDIUM"]
    assert S.file_of(ISSUES[1]) == "eaxcli/main.py"


def test_an_issue_accepted_in_writing_does_not_fail_the_scan():
    S = _s()
    accepted = [{"rule": "python:S1192", "file": "services/api/eax/*.py", "reason": "x", "by": "owner"}]
    assert S.is_accepted(ISSUES[0], accepted) and not S.is_accepted(ISSUES[1], accepted)
    assert S.is_accepted(ISSUES[0], [{"rule": "python:S1192", "file": "*", "line": 11}]) is None   # another line
    got = S.summarise(ISSUES, HOTSPOTS, accepted)
    assert got["to_fix"] == 3 and got["accepted"] == 1 and not got["passed"]
    assert got["by_kind"] == {"BUG": 1, "VULNERABILITY": 1, "SECURITY_HOTSPOT": 1}
    assert S.summarise([], [], [])["passed"]
    data = json.loads((ROOT / "services/api/eax/testing/sonar_accepted.json").read_text(encoding="utf-8"))
    assert "about" in data and isinstance(data["accepted"], list)
    for a in data["accepted"]:
        assert a["rule"] and a["file"] and a["reason"] and a["by"], a        # each with why and the owner's approval


def test_the_report_lists_every_issue_to_fix_by_file_and_line():
    S = _s()
    md = S.report_md(S.summarise(ISSUES, HOTSPOTS, []), ISSUES, HOTSPOTS, [], "26.1")
    assert "**FAILED**: 4 to fix" in md and "SonarQube 26.1" in md
    assert "`eaxcli/main.py:3` BUG HIGH python:S5754" in md
    listed = md[md.index("## Every issue to fix"):]
    assert listed.index("BUG HIGH") < listed.index("VULNERABILITY") < listed.index("CODE_SMELL")   # the worst first
    assert "## Security hotspots to review" in md and "`services/api/eax/x.py:5`" in md


class FakeSonar:
    """SonarQube's web API as the scan uses it, with no server."""

    def __init__(self):
        self.calls, self.password = [], None

    def __call__(self, method, path, params=None, auth=None, token="", timeout=30):
        self.calls.append((method, path, dict(params or {}), auth, token))
        if path == "/api/system/status":
            return {"status": "UP", "version": "26.1"}
        if path == "/api/users/change_password":
            if auth != ("admin", "admin"):
                raise urllib.error.HTTPError(path, 401, "no", {}, None)
            self.password = params["password"]
            return {}
        if path == "/api/user_tokens/generate":
            assert auth == ("admin", self.password)
            return {"token": "squ_abc", "name": params["name"]}
        if path == "/api/ce/component":
            return {"queue": [], "current": {"status": "SUCCESS"}}
        if path == "/api/issues/search":
            return {"issues": ISSUES if params["p"] == 1 else [], "paging": {"total": len(ISSUES)}}
        if path == "/api/hotspots/search":
            return {"hotspots": HOTSPOTS, "paging": {"total": 1}}
        if path == "/api/user_tokens/revoke":
            return {}
        raise AssertionError(path)


def test_a_scan_prepares_once_reports_and_revokes_its_token(tmp_path, monkeypatch):
    S = _s()
    fake = FakeSonar()
    keep = tmp_path / "sonar"
    assert S.prepare(ask=fake, keep=keep) == "26.1"
    pw = (keep / "admin").read_text()
    assert pw == fake.password and len(pw) > 20 and (keep / "token").read_text() == "squ_abc"
    S.prepare(ask=fake, keep=keep)                                              # the password is set once only
    assert [c[1] for c in fake.calls].count("/api/users/change_password") == 1
    monkeypatch.setattr(S, "accepted_list", lambda path=None: [])
    assert S.report("sonar-x", ask=fake, keep=keep, results=tmp_path) is False   # issues to fix: it fails
    out = tmp_path / "sonar-x"
    assert json.loads((out / "summary.json").read_text())["to_fix"] == 4
    assert (out / "issues.json").is_file() and "Every issue to fix" in (out / "report.md").read_text()
    assert not (keep / "token").exists()                                        # the scan's token deleted
    assert any(c[1] == "/api/user_tokens/revoke" for c in fake.calls)
    assert all(c[4] in ("", "squ_abc") for c in fake.calls)                     # read with the scan's token


def test_a_lost_admin_password_says_how_to_start_afresh(tmp_path):
    S = _s()
    fake = FakeSonar()

    def refuses(method, path, params=None, auth=None, token="", timeout=30):
        if path == "/api/users/change_password":
            raise urllib.error.HTTPError(path, 401, "no", {}, None)
        return fake(method, path, params, auth, token, timeout)
    with pytest.raises(S.SonarError, match="eax test sonar --reset"):
        S.admin_password(ask=refuses, keep=tmp_path)


def test_eax_test_sonar_in_every_form_with_the_token_never_on_the_command_line():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import commands as C
    from eaxcli import sonar as X
    assert 'rest[:1] == ["sonar"]' in (ROOT / "eaxcli/main.py").read_text(encoding="utf-8")
    assert '$RestArgs -contains "sonar"' in (ROOT / "eax.ps1").read_text(encoding="utf-8")
    assert '*" sonar "*) exec "$BASH" ./eaxpy.sh' in (ROOT / "eax.sh").read_text(encoding="utf-8")
    assert "sonar [--keep|--open|--reset]" in (ROOT / "eaxcli/help.txt").read_text(encoding="utf-8")
    assert C.check_argv(["test", "sonar", "--keep"]) == ["test", "sonar", "--keep"]
    assert X.scanner_args()[-3:] == ["-e", "SONAR_TOKEN", "sonar-scanner"]       # the value comes from the environment
    assert X.runner(["prepare"])[-3:] == ["-m", "eax.testing.sonar", "prepare"]
    assert X.folder_name(0).startswith("sonar-")


def test_status_does_not_count_the_scan_containers_as_problems():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import problems as P
    rows = [{"Service": "sonarqube", "State": "exited", "Status": "Exited (143)", "ExitCode": 143},
            {"Service": "sonar-scanner", "State": "exited", "Status": "Exited (0)", "ExitCode": 0}]
    assert P.container_problems(rows) == []


def test_after_a_clean_restart_the_scan_starts_sonarqube_afresh_by_itself(tmp_path, monkeypatch, capsys):
    """clean-restart deletes work/ (the admin password's copy) and may keep SonarQube's volume (owner, 19 Nov 2026,
    06:40: "we will do a clean restart"): prepare answers 3 and eax test sonar resets SonarQube and tries again."""
    S = _s()

    def refuses(method, path, params=None, auth=None, token="", timeout=30):
        if path == "/api/system/status":
            return {"status": "UP", "version": "26.1"}
        raise urllib.error.HTTPError(path, 401, "no", {}, None)
    monkeypatch.setattr(S, "call", refuses)
    monkeypatch.setattr(S, "KEEP", tmp_path)
    monkeypatch.setattr(S, "prepare", lambda: S.admin_password(ask=refuses, keep=tmp_path))
    assert S.main(["prepare"]) == 3
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    src = (ROOT / "eaxcli" / "sonar.py").read_text(encoding="utf-8")
    assert "if got == 3:" in src and "reset()" in src


def test_sonar_open_shows_its_pages_on_this_computer_only_and_only_when_asked():
    """D805 (owner, 19 Nov 2026, 21:27: "i want to turn on sonar to open and run"): eax test sonar --open leaves SonarQube
    running with its own pages at http://localhost:9000, bound to 127.0.0.1, until eax down; without --open, no port."""
    import yaml
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import commands as C
    from eaxcli import sonar as X
    extra = yaml.safe_load((ROOT / X.OPEN_FILE).read_text(encoding="utf-8"))
    assert list(extra["services"]) == ["sonarqube"]                                  # only SonarQube gets a port
    assert extra["services"]["sonarqube"]["ports"] == ["127.0.0.1:${EAX_SONAR_PORT:-9000}:9000"]   # this computer only
    assert X.start_args([]) == ["--profile", "test", "up", "-d", "--no-deps", "sonarqube"]        # before: no port
    assert X.start_args(["--open"])[:2] == ["-f", X.OPEN_FILE] and X.start_args(["--open"])[2:] == X.start_args([])
    assert C.check_argv(["test", "sonar", "--open"]) == ["test", "sonar", "--open"]
    assert X.open_address() in ("http://localhost:9000", f"http://localhost:{__import__('os').environ.get('EAX_SONAR_PORT')}")
    src = (ROOT / "eaxcli/sonar.py").read_text(encoding="utf-8")
    assert 'if "--keep" not in rest and "--open" not in rest:' in src                 # --open keeps it running
    main = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]["sonarqube"]
    assert "ports" not in main and main["profiles"] == ["test"]                       # the stack itself: still no port


def test_eax_sonar_open_shows_the_last_scan_without_scanning_and_close_ends_it(monkeypatch):
    """D805 (owner, 19 Nov 2026, 21:28: "i wanna only execute it not run a test"): eax sonar open starts SonarQube with its
    pages on this computer only and waits for it; it scans nothing. eax sonar close removes it (its data kept)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import sonar as X
    from eaxcli.core import Failure
    calls = []
    monkeypatch.setattr(X, "docker_ok", lambda: True)
    monkeypatch.setattr(X, "compose", lambda args, no_throw=False, quiet=False: calls.append(args) or 0)
    monkeypatch.setattr(X, "heading", lambda *a, **k: None)
    monkeypatch.setattr(X, "say", lambda *a, **k: None)
    monkeypatch.setattr(X, "ok", lambda *a, **k: None)
    monkeypatch.setattr(X, "published_port", lambda: "")                         # before (20 Nov): no port, yet "open"
    with pytest.raises(Failure, match="no port"):
        X.dashboard(["open"])
    calls.clear()
    monkeypatch.setattr(X, "published_port", lambda: "127.0.0.1:9000")           # after: open only with its port
    assert X.dashboard(["open"]) == 0
    assert calls[0] == ["--profile", "test", "build", "testrunner"]               # 20 Nov: an older runner had no "ready"
    assert calls[1] == X.start_args(["--open"])                                   # with its port, on 127.0.0.1
    assert calls[2] == X.runner(["ready"])                                        # waits; makes no token
    assert not any("sonar-scanner" in c or "report" in c for c in calls)          # nothing scanned, no report
    calls.clear()
    assert X.dashboard(["close"]) == 0 and calls == [["--profile", "test", "rm", "-sf", "sonarqube"]]
    with pytest.raises(Failure, match="eax sonar open"):
        X.dashboard([])


def test_ready_waits_and_sets_the_password_without_making_a_token(monkeypatch, capsys):
    S = _s()
    seen = []
    monkeypatch.setattr(S, "wait_up", lambda **k: "26.11")
    monkeypatch.setattr(S, "admin_password", lambda **k: seen.append("password") or "pw")
    monkeypatch.setattr(S, "prepare", lambda **k: seen.append("token"))
    assert S.main(["ready"]) == 0 and seen == ["password"] and "26.11 is ready" in capsys.readouterr().out


def test_the_published_port_is_read_from_docker(monkeypatch):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import sonar as X
    monkeypatch.setattr(X, "project_name", lambda: "eaexplorer")
    seen = []
    monkeypatch.setattr(X, "capture", lambda args: seen.append(args) or (0, "127.0.0.1:9000\n"))
    assert X.published_port() == "127.0.0.1:9000" and seen == [["docker", "port", "eaexplorer-sonarqube-1", "9000"]]
    monkeypatch.setattr(X, "capture", lambda args: (0, ""))
    assert X.published_port() == ""
    monkeypatch.setattr(X, "capture", lambda args: (1, "Error: No such container"))
    assert X.published_port() == ""
