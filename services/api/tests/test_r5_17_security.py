"""R5.17 (owner, 14 Nov 2026: "In next release add Story for automated security test"): scheduled, a signed-in ZAP
scan, code and secrets scanning, Release 3's attacks as tests, a gate with accepted findings that expire, a trend."""

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax.testing import attacks, codescan  # noqa: E402
from eax.testing import security_gate as G  # noqa: E402

TODAY = date(2026, 12, 1)


def trivy(vid, sev, fixed=""):
    return {"Results": [{"Vulnerabilities": [{"VulnerabilityID": vid, "Severity": sev, "PkgName": "p", "InstalledVersion": "1",
                                               **({"FixedVersion": fixed} if fixed else {})}]}]}


def test_the_gate_fails_on_high_and_critical_not_accepted():
    found = G.from_trivy(trivy("CVE-1", "CRITICAL", "2"), "api") + G.from_trivy(trivy("CVE-2", "HIGH"), "api") \
        + G.from_zap({"site": [{"@name": "https://proxy", "alerts": [{"pluginid": "10055", "riskcode": "2", "alert": "CSP"}]}]})
    g = G.gate(found, [], TODAY)
    assert [f["id"] for f in g["failing"]] == ["CVE-1"]                 # a fix exists: fails
    assert [f["id"] for f in g["no_fix"]] == ["CVE-2"]                  # no fix released yet: listed, not failed
    assert g["counts"]["zap medium"] == 1                               # medium never fails


def test_an_accepted_finding_passes_until_its_date_then_fails_again():
    found = G.from_trivy(trivy("CVE-1", "CRITICAL", "2"), "web")
    ok = [{"id": "CVE-1", "where": "image web", "reason": "r", "until": "2026-12-31", "by": "x"}]
    assert not G.gate(found, ok, TODAY)["failing"] and G.gate(found, ok, TODAY)["accepted"][0]["reason"] == "r"
    late = G.gate(found, ok, date(2027, 1, 1))
    assert late["failing"] and late["expired"]
    other = [{**ok[0], "where": "image api"}]                           # accepted for another image only
    assert G.gate(found, other, TODAY)["failing"]


def test_the_accepted_list_is_kept_with_the_code_and_checked():
    data = json.loads((REPO / "services/api/eax/testing/security_accepted.json").read_text())
    assert G.clean_accepted(data)["accepted"][0]["id"] == "zap:10055"   # the CSP finding of 14 Nov 2026, with its reason
    with pytest.raises(ValueError, match="reason"):
        G.clean_accepted({"accepted": [{"id": "x", "until": "2027-01-01"}]})
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        G.clean_accepted({"accepted": [{"id": "x", "reason": "r", "until": "soon"}]})


def test_the_run_keeps_its_findings_and_says_what_is_new(tmp_path):
    old, new = tmp_path / "20261101T000000Z", tmp_path / "20261108T000000Z"
    old.mkdir()
    new.mkdir()
    (old / G.FINDINGS).write_text(json.dumps({"findings": G.from_trivy(trivy("CVE-1", "HIGH", "2"), "api")}))
    (new / "trivy-api.json").write_text(json.dumps({"Results": [{"Vulnerabilities": [
        {"VulnerabilityID": "CVE-1", "Severity": "HIGH", "PkgName": "p", "InstalledVersion": "1", "FixedVersion": "2"},
        {"VulnerabilityID": "CVE-9", "Severity": "CRITICAL", "PkgName": "q", "InstalledVersion": "1", "FixedVersion": "2"}]}]}))
    got = []
    out = G.judge(new, lambda *a: got.append(a), TODAY)
    assert [f["id"] for f in out["new"]] == ["CVE-9"]
    assert got[0][0] == G.GATE and got[0][1] == "failed" and got[0][2].startswith("2 high or critical")
    assert json.loads((new / G.FINDINGS).read_text())["new"][0]["id"] == "CVE-9"


def test_no_report_no_gate(tmp_path):
    got = []
    G.judge(tmp_path, lambda *a: got.append(a))
    assert got[0][1] == "skipped"


def test_the_trend_per_run_and_kind():
    rows = [{"run": 2, "at": None, "name": "image api (Trivy)", "outcome": "warning"},
            {"run": 2, "at": None, "name": G.GATE, "outcome": "failed"},
            {"run": 1, "at": None, "name": "attack: SSRF: x", "outcome": "passed"},
            {"run": 1, "at": None, "name": "OWASP ZAP signed-in API scan", "outcome": "warning"}]
    t = G.trend(rows)
    assert [x["run"] for x in t] == [1, 2]
    assert t[0]["kinds"]["attacks"]["passed"] == 1 and t[0]["kinds"]["zap-api"]["warning"] == 1
    assert t[1]["kinds"]["gate"]["failed"] == 1 and t[1]["kinds"]["trivy"]["warning"] == 1


def test_the_signed_in_scan_only_reads_the_runs_own_data():
    from eax.testing.api_matrix import fill
    spec = {"openapi": "3.0.3", "paths": {
        "/api/v1/models/{model_id}/entities": {"get": {"parameters": [{"in": "query", "name": "q"}, {"in": "path", "name": "model_id"}]},
                                              "post": {}},
        "/api/v1/admin/settings": {"get": {}}, "/api/v1/models/{model_id}/export/csv": {"get": {}},
        "/api/v1/things/{nothing}": {"get": {}}, "/api/v1/me": {"get": {}}}}
    t = G.zap_targets(spec, {"model": "m-1"}, fill)
    assert set(t["paths"]) == {"/api/v1/models/m-1/entities", "/api/v1/me"}
    assert list(t["paths"]["/api/v1/models/m-1/entities"]) == ["get"]                     # reads only
    assert t["paths"]["/api/v1/models/m-1/entities"]["get"]["parameters"] == [{"in": "query", "name": "q"}]


def test_the_helper_deletes_the_token_whatever_happens(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("testruns_r517", REPO / "services/ops/testruns.py")
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    monkeypatch.setattr(T, "WORK", str(tmp_path))
    (tmp_path / "tests/run1").mkdir(parents=True)
    (tmp_path / "tests/run1/zap-openapi.json").write_text("{}")
    (tmp_path / "tests/run1/zap-auth.txt").write_text("abc.def.ghi")
    seen = {}
    # the scanner is named and labelled now and goes through attackscans.run_tagged (R12.6, D833)
    monkeypatch.setattr(T.subprocess, "run", lambda args, **k: seen.update(args=args, **k) or T.subprocess.CompletedProcess(args, 0, "", ""))
    T._zap_api("run1", "/host/run1", "net_frontend", lambda m: None)
    assert not (tmp_path / "tests/run1/zap-auth.txt").exists()
    assert "abc.def.ghi" not in " ".join(seen["args"]) and seen["env"]["ZAP_AUTH_HEADER_VALUE"] == "Bearer abc.def.ghi"
    assert "zap-api-scan.py" in seen["args"] and "2.15.0" not in T.ZAP_IMAGE


def test_secrets_are_found_and_shown_without_their_value(tmp_path):
    key = "-----BEGIN RSA PRIVATE KEY-----\n" + "M" * 80
    (tmp_path / "a.py").write_text(f'K = """{key}"""\n')
    (tmp_path / "b.env").write_text("EAX_API_" + "TOKEN=" + "q8Zr2Lm9Xw4Pt7Ks\n")
    (tmp_path / "c.env").write_text("EAX_DB_PASSWORD=${FROM_VAULT}\nEAX_X_PASSWORD=\n")      # references and blanks: fine
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/t.env").write_text("EAX_T_PASSWORD=q8Zr2Lm9Xw4Pt7Ks\n")             # a test's own: fine
    found = codescan.secrets(tmp_path)
    assert sorted(f["where"] for f in found) == ["a.py:1", "b.env:1"]
    assert not any("q8Zr" in json.dumps(f) or "MMMM" in json.dumps(f) for f in found)


def test_the_repository_has_no_secret_committed():
    assert codescan.secrets(REPO) == []


def test_bandit_and_licences_are_read():
    b = {"results": [{"test_id": "B602", "issue_severity": "HIGH", "issue_confidence": "HIGH", "issue_text": "shell", "filename": "x.py",
                      "line_number": 3}, {"test_id": "B101", "issue_severity": "LOW", "issue_confidence": "LOW"}]}
    f = G.from_bandit(b)
    assert len(f) == 1 and f[0]["severity"] == "high" and f[0]["where"] == "x.py:3"
    assert codescan.COPYLEFT.search("GNU Affero General Public License (AGPL)") and not codescan.COPYLEFT.search("MIT License")


def test_the_attacks_must_be_refused(monkeypatch):
    calls, got = [], []

    def fake(base, method, path, token, raw, timeout=60, limit=800):
        calls.append((method, path, json.loads(raw) if raw else None))
        if method == "POST" and "discovery-sources" in path and "10.0.0.1" in (raw or b"").decode():
            return 201, '{"id": "s-1"}'                                   # one that is (wrongly) saved
        if path == "/api/v1/settings" and token:
            return 200, json.dumps({"currency": "EUR", "smtp_password": "x"})
        return (401 if not token else 403), ""

    monkeypatch.setattr(attacks, "send", fake)
    monkeypatch.setattr(attacks, "identity", lambda *a: None)
    monkeypatch.setattr(attacks, "uploads", lambda *a: None)
    attacks.run("http://api", {"architect": "t", "report-viewer": "r"}, {"model": "m", "other_model": "o"},
                lambda n, o, d, ms: got.append((n, o, d)))
    by = {n: o for n, o, _ in got}
    assert by["attack: SSRF: a discovery source at a private network"] == "failed"
    assert ("DELETE", "/api/v1/discovery-sources/s-1", None) in calls             # what was saved is removed at once
    assert by["attack: SSRF: a discovery source at the cloud's metadata address"] == "passed"
    assert by["attack: the screens' settings hold no password, secret or token"] == "failed"
    assert by["attack: a discovery source signing in with the database's password"] == "passed"
    assert by["attack: cross-model: GET on a model with no role"] == "passed"
    assert by["attack: unsigned: GET /api/v1/me"] == "passed"


def test_it_runs_by_itself_and_fails_the_ci_job():
    jobs = (REPO / "services/api/eax/jobs.py").read_text()
    assert 'name="eax.security_weekly"' in jobs and '@app.periodic(cron="20 3 * * 0")' in jobs and "security_test_weekly" in jobs
    ci = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    steps = " ".join(str(s.get("run", "")) for s in ci["jobs"]["security"]["steps"])
    assert "eax.testing.codescan" in steps and "pip-audit" in steps and "npm audit" in steps
    run = (REPO / "services/api/eax/testing/run.py").read_text()
    assert "security_gate.judge(r.dir, rec)" in run and "attacks.run(API, tokens, ids, rec)" in run and "codescan.run(" in run
    assert '"security": ("High or critical security findings' in (REPO / "services/api/eax/alerts.py").read_text()
    assert "bandit==" in (REPO / "services/api/Dockerfile.test").read_text()
    assert '["security", "Security"]' in (REPO / "services/web/src/TestRuns.jsx").read_text()
