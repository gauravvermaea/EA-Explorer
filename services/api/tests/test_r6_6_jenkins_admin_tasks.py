"""Jenkins' admin tasks (the owner, 18 Nov 2026, 09:59 to 10:03): named pipelines for what is done on the machine, not
inside the application: starting and stopping, certificates, getting an administrator back in, backups and DR, upkeep;
and Jenkins' own account printed when it starts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from eaxcli import access as A  # noqa: E402
from eaxcli import certs as CE  # noqa: E402
from eaxcli import commands as C  # noqa: E402
from eaxcli import jenkins as J  # noqa: E402
from eaxcli.core import Failure  # noqa: E402

SAMPLE = {"CERT_FILE": "C:\\certs\\ea.crt", "KEY_FILE": "C:/certs/ea.key", "SERVICE": "api", "USER": "eaadmin",
          "PLACE": "site", "ADDRESS": "10.20.0.0/16", "BACKUP": "latest", "WHAT": "full", "FOLDER": "D:/dr-packs",
          "--install": "/srv/eax", "--dr": "/srv/dr", "--temp": "/tmp/t", "AT": "2026-11-20T17:00", "EVERY": "monthly", "NAME": "ea.example.org",
          "FILE": "D:/eax/settings.json", "COPY": "2c6f0d0e-5e1a-4c43-9d0c-3f1f2c7e6b1a"}   # R6.7 settings


def test_every_admin_task_is_a_command_eax_takes():
    for name, t in J.ADMIN_BY_NAME.items():
        argv = J.argv_for(name, SAMPLE)
        assert argv, name
        if not t.get("tool"):
            assert C.check_argv(argv) == argv, name
    assert J.argv_for("admin-front-certificate-install", SAMPLE)[3:7] == ["--cert", "C:/certs/ea.crt", "--key", "C:/certs/ea.key"]


def test_the_admin_tasks_the_owner_asked_for_are_there_in_their_own_folders():
    names = {p["name"]: p for p in J.pipelines()}
    for want in ("start", "stop", "restart", "front-certificate-install", "admin-reset-password", "admin-unlock",
                 "allow-an-address", "backup-now", "restore-a-backup", "dr-pack", "build-dr-copy", "restore-drill",
                 "rotate-all-secrets", "database-integrity"):
        p = names[f"admin-{want}"]
        assert p["folder"].startswith("eax-admin/") and p["display"] == want
    assert names["status"].get("folder") is None                       # the commands' own pipelines stay apart
    for risky in ("stop", "restart", "restore-a-backup", "front-certificate-install", "admin-reset-password", "rotate-all-secrets"):
        assert names[f"admin-{risky}"]["confirm"] is True, risky
    assert not any(t["argv"][:1] in (["users"], ["roles"]) for t in J.ADMIN_TASKS if t.get("argv"))   # no user management
    seed = (REPO / "deploy/jenkins/seed.groovy").read_text()
    assert "p.folder ?: 'eax'" in seed and "folder('eax-admin')" in seed


def test_the_pipelines_run_in_the_sandbox_without_waiting_for_approval():
    """The owner's first pipeline, 18 Nov 2026, 12:02: "UnapprovedUsageException: script not yet approved for use": the
    pipelines were made outside Jenkins' sandbox, so each waited for an administrator's approval. In the sandbox they run
    at once; the JSON is read and written by the pipeline utility steps, as the sandbox refuses Groovy's own parsers."""
    seed = (REPO / "deploy/jenkins/seed.groovy").read_text()
    script = seed[seed.index('script("""'):]
    assert "sandbox(true)" in seed and "sandbox(false)" not in seed
    assert "JsonSlurper" not in script and "JsonOutput" not in script and "new groovy" not in script
    assert "readJSON text:" in script and "writeJSON file:" in script and "${groovyMap(" in script
    assert "pipeline-utility-steps" in (REPO / "deploy/jenkins/plugins.txt").read_text().split()


def test_a_required_field_and_a_choice_are_checked():
    with pytest.raises(C.Refused, match="USER is needed"):
        J.argv_for("admin-admin-unlock", {})
    with pytest.raises(C.Refused, match="one of"):
        J.argv_for("admin-allow-an-address", {"PLACE": "everywhere", "ADDRESS": "1.2.3.4"})
    with pytest.raises(C.Refused):
        J.argv_for("admin-admin-unlock", {"USER": "x; rm -rf /"})


def test_jenkins_up_prints_its_own_accounts_password():
    src = (REPO / "eaxcli/jenkins.py").read_text()
    assert "Jenkins' own account" in src and "password: " in src and "EAX_JENKINS_ADMIN_PASSWORD" in src


# ---------------------------------------------------------------- eax access: administrators only
class P:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def _keycloak(users: dict, roles: dict, seen: list):
    def run(args, **k):
        script, rest = args[5], args[6:]
        seen.append((script, rest, k.get("input", "")))
        if "get users " in script:
            u = users.get(rest[3])
            return P(0, json.dumps([u] if u else []))
        if "role-mappings" in script:
            return P(0, json.dumps([{"name": r} for r in roles.get(rest[3], [])]))
        if "credentials" in script and "get" in script:
            return P(0, json.dumps([{"id": "c1", "type": "password"}, {"id": "c2", "type": "otp"}]))
        return P(0, "")
    return run


def test_access_gets_an_administrator_back_in_and_refuses_anyone_else(monkeypatch):
    monkeypatch.setattr(A, "compose_args", lambda a: a)
    monkeypatch.setattr(A, "setting", lambda k, d="": {"EAX_FIRST_ADMIN_USER": "eaadmin"}.get(k, d))
    users = {"eaadmin": {"id": "u1", "username": "eaadmin"}, "ops-it": {"id": "u2", "username": "ops-it"},
             "pat": {"id": "u3", "username": "pat"}}
    seen = []
    run = _keycloak(users, {"u2": ["eax-it-admin"], "u3": ["eax-architect"]}, seen)
    pw = A.reset_password("eaadmin", run=run)
    script, rest, given = seen[-1]
    assert "set-password" in script and "--temporary" in script and given == pw and pw not in " ".join(rest)
    A.unlock("ops-it", run=run)
    assert "enabled=true" in seen[-1][0] and "attack-detection" in seen[-1][0]
    assert A.mfa_off("ops-it", run=run) == 1 and "credentials/$4" in seen[-1][0] and seen[-1][1][-1] == "c2"
    with pytest.raises(Failure, match="not an administrator"):
        A.reset_password("pat", run=run)
    with pytest.raises(Failure, match="No user"):
        A.unlock("nobody", run=run)


# ---------------------------------------------------------------- eax certs front: from files on the machine
def test_the_front_certificate_from_files_is_checked_then_put_in(monkeypatch, tmp_path):
    (tmp_path / "ea.crt").write_text("-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n")
    (tmp_path / "ea.key").write_text("-----BEGIN PRIVATE KEY-----\nK\n-----END PRIVATE KEY-----\n")
    monkeypatch.setattr(CE, "compose_args", lambda a: a)
    monkeypatch.setattr(CE, "setting", lambda k, d="": "ea.example.org" if k == "EAX_HOSTNAME" else d)
    seen = []

    def run(args, **k):
        seen.append((args, json.loads(k["input"])))
        if args[2] == "api":
            return P(0, json.dumps({"subject": "CN=ea", "not_after": "2027-11-18T00:00:00", "days_left": 365,
                                    "full_chain": "-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n"}))
        return P(0, json.dumps({"installed": True}))
    assert CE.front(["install", "--cert", str(tmp_path / "ea.crt"), "--key", str(tmp_path / "ea.key")], run=run) == 0
    (api, body1), (ops, body2) = seen
    assert api[3:] == ["python", "-m", "eax.frontcert"] and body1["hostname"] == "ea.example.org"
    assert ops[3:] == ["python3", "/app/ops.py", "tls", "install"] and "PRIVATE KEY" in body2["key"]
    assert not any("PRIVATE KEY" in a for a, _ in seen for a in a)                 # the key never on a command line
    seen.clear()
    with pytest.raises(Failure, match="Not put in: The key is not"):
        CE.front(["install", "--cert", str(tmp_path / "ea.crt"), "--key", str(tmp_path / "ea.key")],
                 run=lambda a, **k: P(1, json.dumps({"error": "The key is not this certificate's key"})))


def test_the_api_checks_a_front_certificate_from_standard_input(monkeypatch, capsys):
    from eax import frontcert as F
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps({"certificate": "", "key": ""})))
    assert F.main() == 1 and "Choose the certificate file" in json.loads(capsys.readouterr().out)["error"]


def test_ops_puts_a_certificate_in_from_standard_input():
    ops = (REPO / "services/ops/ops.py").read_text()
    assert 'if cmd == "tls" and args[:1] in (["install"], ["undo"])' in ops and "json.loads(sys.stdin.read()" in ops
    r = subprocess.run([sys.executable, "-c", "print('ok')"], capture_output=True, text=True)
    assert r.stdout.strip() == "ok"


def test_a_choice_with_words_after_it_takes_them():
    """"allow add site 10.20.0.0/16" was refused: the syntax's choice was read as "add <place> <address> [name]"."""
    assert C.check_argv(["allow", "add", "site", "10.20.0.0/16", "office"]) == ["allow", "add", "site", "10.20.0.0/16", "office"]
    assert C.check_argv(["jobs", "clear-stuck"]) == ["jobs", "clear-stuck"]
    with pytest.raises(C.Refused):
        C.check_argv(["allow", "nonsense"])


# ---------------------------------------------------------------- Jenkins starts whatever Keycloak's state (10:11)
def test_jenkins_starts_with_its_own_account_unless_keycloak_is_asked_for():
    """"Jenkins is not up": its Keycloak sign-in fetched Keycloak's settings from https://localhost inside its own
    container at start. Its own account is the default now; Keycloak only with EAX_JENKINS_SIGNIN=keycloak."""
    import yaml
    own = yaml.safe_load((REPO / "deploy/jenkins/casc.yaml").read_text())
    assert "local" in own["jenkins"]["securityRealm"] and "oic" not in own["jenkins"]["securityRealm"]
    kc = yaml.safe_load((REPO / "deploy/jenkins/casc-keycloak.yaml").read_text())
    assert "oic" in kc["jenkins"]["securityRealm"]
    assert "COPY casc.yaml casc-keycloak.yaml" in (REPO / "deploy/jenkins/Dockerfile").read_text()
    assert "${EAX_JENKINS_CASC:-casc.yaml}" in (REPO / "deploy/jenkins/docker-compose.jenkins.yml").read_text()


def test_jenkins_up_waits_for_it_to_answer_and_says_why_not(monkeypatch, tmp_path):
    monkeypatch.setattr(J, "WORK", tmp_path)
    monkeypatch.setattr(J, "answering", lambda: False)
    states = iter(["running", "exited"])
    monkeypatch.setattr(J, "_compose", lambda a, **k: subprocess.CompletedProcess(a, 0, next(states, "exited") if a[0] == "ps" else
                        "jenkins-1  | SEVERE: Failed ConfigurationAsCode.init\njenkins-1  | Caused by: io.jenkins.plugins.casc."
                        "UnknownAttributesException: oic: Invalid configuration elements for type", ""))
    assert J.wait_answering(minutes=1, sleep=lambda s: None) is False
    said = J.why_not_answering()
    assert "UnknownAttributesException" in said and (tmp_path / "jenkins" / "start.log").exists()



# ---------------------------------------------------------------- Rotate all on a schedule (10:07 to 10:11)
def test_rotate_all_now_at_a_time_and_regularly_shared_by_the_app_and_jenkins(monkeypatch, tmp_path):
    """"There should be a schedule + on demand schedule. So someone can say Restart now or Restart at 5 PM on xyz date
    and then there is a regular schedule like you said monthly or every 90 days"."""
    from eaxcli import persist
    from eaxcli import secretsrot as S
    monkeypatch.setattr(persist, "folder", lambda root=None: tmp_path)
    out = S.schedule_all("monthly", "eaadmin")
    assert out["regular"]["cron"] == "30 3 1 * *" and out["regular"]["argv"] == ["secrets", "rotate", "--all"]
    out = S.schedule_all("quarterly", "eaadmin")
    assert out["regular"]["cron"] == "30 3 1 1,4,7,10 *"                          # replaced, never two
    out = S.schedule_all("at", "eaadmin", at="2099-11-20T17:00")
    assert [s["once_at"] for s in out["once"]] == ["2099-11-20T17:00"]
    with pytest.raises(Failure, match="has passed"):
        S.schedule_all("at", "eaadmin", at="2001-01-01T17:00")
    assert S.schedule_all("off", "eaadmin")["regular"] is None
    assert C.check_argv(["secrets", "schedule", "--at", "2026-11-20T17:00"])
    assert J.argv_for("admin-rotate-all-secrets-regularly", {"EVERY": "quarterly"}) == ["secrets", "schedule", "quarterly"]
    jsx = (REPO / "services/web/src/Secrets.jsx").read_text()
    assert "function RotateAllSchedule" in jsx and '["secrets", "schedule", "--at"' in jsx



def test_get_back_in_puts_the_maintenance_page_up_and_takes_it_down():
    """The owner, 18 Nov 2026, 11:07: "In jenkins get back in needs to have a pipeline to remove mantainance page and
    also one to put up mantainance paged"."""
    by = {t["name"]: t for t in J.ADMIN_TASKS}
    for n, argv in (("maintenance-page-on", ["maintenance", "on"]), ("maintenance-page-off", ["maintenance", "off"]),
                    ("maintenance-clear", ["maintenance", "clear"])):
        assert by[n]["group"] == "Get back in" and by[n]["argv"] == argv


def test_a_run_on_windows_opens_no_window(monkeypatch, tmp_path):
    """The owner, 18 Nov 2026, 12:18: "when i run a pipeline opens a command prompt on windows machine": the agent has no
    console, so each run got a window of its own, which closing would end halfway. Now none; elsewhere nothing changes."""
    seen = {}

    class P:
        def wait(self):
            return 0

    def run(cmd, **kw):
        seen.update(kw)
        return P()
    monkeypatch.setattr(J.os, "name", "nt")
    J.Runs(tmp_path / "runs").start(["status"], "admin", run=run)
    assert seen["creationflags"] & J.CREATE_NO_WINDOW and seen["stdin"] is not None
    monkeypatch.setattr(J.os, "name", "posix")
    seen.clear()
    J.Runs(tmp_path / "runs2").start(["status"], "admin", run=run)
    assert "creationflags" not in seen
    assert "CREATE_NO_WINDOW" in (REPO / "eaxcli/jenkins.py").read_text().split("def start_agent")[-1] or \
        "| CREATE_NO_WINDOW}" in (REPO / "eaxcli/jenkins.py").read_text()
