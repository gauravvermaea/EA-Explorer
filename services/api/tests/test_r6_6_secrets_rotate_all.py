"""Rotating secrets one at a time, and all at once (the owner, 18 Nov 2026, 09:19).

Two Rotate now clicks six seconds apart (EAX_CHANGELOG_DB_URL, EAX_CONSOLE_IT_PASSWORD) made the same containers again at
once; Docker refused both half way ("No such container: ...") and EA Explorer was left half made again: signed-in people
saw "You have no role yet". Now every rotation holds a lock and a second one waits; making the services again is tried
three times; and "bring rotate all as a capability. It rotates all the stuff": eax secrets rotate --all.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from eaxcli import secretsrot as S  # noqa: E402
from eaxcli.core import Failure  # noqa: E402


@pytest.fixture
def work(monkeypatch, tmp_path):
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_DEPLOYMENT=laptop\nEAX_DB_PASSWORD=a\nEAX_CONSOLE_IT_PASSWORD=b\nEAX_SMTP_PASSWORD=c\n")
    monkeypatch.setattr(S, "ENV_FILE", env)
    return tmp_path


def test_a_second_rotation_waits_for_the_first(work):
    with S.rotation_lock():
        assert S.lock_path().exists()
        with pytest.raises(Failure, match="Another rotation is still running"):
            with S.rotation_lock(wait=0, sleep=lambda s: None):
                pass
    assert not S.lock_path().exists()                                        # released at the end
    with S.rotation_lock(wait=0):                                            # and free again
        pass


def test_a_lock_left_behind_by_a_run_that_died_is_taken_over(work):
    S.lock_path().write_text("123")
    old = time.time() - 3 * 3600
    os.utime(S.lock_path(), (old, old))
    with S.rotation_lock(wait=0):
        pass


def test_rotations_hold_the_lock(work, monkeypatch):
    seen = []
    monkeypatch.setattr(S, "_rotate", lambda *a, **k: seen.append(S.lock_path().exists()) or {"rotated": []})
    S.rotate("EAX_DB_PASSWORD", "test")
    assert seen == [True] and not S.lock_path().exists()


def test_making_the_services_again_is_tried_three_times(monkeypatch):
    calls = []

    def compose(args, **k):
        calls.append(args)
        if len(calls) < 3:
            raise Failure("docker compose up -d --no-deps failed: No such container: e348")
        return ""
    monkeypatch.setattr(S, "_compose", compose)
    S.recreate(["api", "backup"], sleep=lambda s: None)
    assert len(calls) == 3 and calls[0][:4] == ["up", "-d", "--no-deps", "--force-recreate"]
    calls.clear()
    monkeypatch.setattr(S, "_compose", lambda a, **k: calls.append(a) or (_ for _ in ()).throw(Failure("No such container")))
    with pytest.raises(Failure, match="eax restart"):
        S.recreate(["api"], sleep=lambda s: None)
    assert len(calls) == 3


def test_rotate_all_rotates_every_one_eax_can_and_makes_the_services_again_once(work, monkeypatch):
    rows = [{"key": "EAX_DB_PASSWORD", "auto": True, "set": True, "due": False, "why": ""},
            {"key": "EAX_CONSOLE_IT_PASSWORD", "auto": True, "set": True, "due": False, "why": ""},
            {"key": "EAX_SMTP_PASSWORD", "auto": False, "set": True, "due": False, "why": "the mail server's"},
            {"key": "EAX_MCP_DEV_TOKEN", "auto": True, "set": False, "due": False, "why": ""}]
    monkeypatch.setattr(S, "rows", lambda *a, **k: rows)
    monkeypatch.setattr(S, "first_seen", lambda v: 0)
    monkeypatch.setattr(S, "read_state", lambda: {})
    rotated, made = [], []
    monkeypatch.setattr(S, "rotate_one", lambda k, v, by, value=None, restart=True: rotated.append(k) or [f"svc-{k}"])
    monkeypatch.setattr(S, "recreate", lambda services: made.append(services))
    out = S.rotate("--all", "eaadmin", ops=lambda *a: {}, api=lambda c: {"idle": True})
    assert rotated == ["EAX_DB_PASSWORD", "EAX_CONSOLE_IT_PASSWORD"]                  # not the person's, not the unset
    assert out["person"] == [{"key": "EAX_SMTP_PASSWORD", "why": "the mail server's"}]
    assert len(made) == 1 and len(made[0]) == 2                                       # made again once, at the end


def test_rotate_all_is_on_the_secrets_tab_in_the_help_and_in_every_way_in():
    jsx = (REPO / "services/web/src/Secrets.jsx").read_text()
    assert 'rotate("--all")' in jsx and ">Rotate all<" in jsx
    help_ = (REPO / "eaxcli/help.txt").read_text()
    assert "[--all]" in help_ and "rotate --all" in help_
    assert 'key not in ("--due", "--all")' in (REPO / "services/ops/ops.py").read_text()
    assert '"--all"' in (REPO / "eaxcli/secrets.py").read_text()


def test_a_rotation_is_followed_on_the_secrets_tab_itself():
    """The owner, 18 Nov 2026, 09:41: "can we either show status here itself or update when done. I cant even find the
    command page": the tab follows the run (its output, then done or failed) and reads the table again when it ends."""
    jsx = (REPO / "services/web/src/Secrets.jsx").read_text()
    assert "function RotationRun" in jsx and "/api/v1/admin/commands/runs/${run.id}?from=" in jsx
    assert "onDone(s)" in jsx and "setGen((g) => g + 1)" in jsx
    assert "follow it on System Admin › Commands" not in jsx and "#/admin/commands/history" in jsx


def test_every_keycloak_client_rotated_is_one_the_realm_has():
    """The owner's Rotate all, 18 Nov 2026, 09:40, stopped at EAX_KC_SERVICE_SECRET: its client is eax-admin, not
    eax-service."""
    import re

    from eaxcli.secrets import KEYCLOAK_CLIENTS
    realm = (REPO / "deploy/keycloak/realm-eaexplorer.json.tmpl").read_text()
    have = set(re.findall(r'"clientId": "([^"]+)"', realm))
    assert set(KEYCLOAK_CLIENTS.values()) <= have, set(KEYCLOAK_CLIENTS.values()) - have
    for key, client in KEYCLOAK_CLIENTS.items():
        i = realm.index(f'"clientId": "{client}"')
        assert "${" + key + "}" in realm[i:i + 800], (key, client)                      # the client takes that secret


def test_one_that_fails_never_leaves_the_others_half_done(work, monkeypatch):
    """09:40: eight passwords changed, then one failed and nothing was made again: the API could not reach its databases."""
    rows = [{"key": k, "auto": True, "set": True, "due": False, "why": ""} for k in ("EAX_DB_PASSWORD", "EAX_KC_SERVICE_SECRET",
                                                                                       "EAX_CONSOLE_IT_PASSWORD")]
    monkeypatch.setattr(S, "rows", lambda *a, **k: rows)
    monkeypatch.setattr(S, "first_seen", lambda v: 0)
    monkeypatch.setattr(S, "read_state", lambda: {})

    def one(k, v, by, value=None, restart=True):
        if k == "EAX_KC_SERVICE_SECRET":
            raise Failure("Keycloak has no client")
        return [f"svc-{k}"]
    made = []
    monkeypatch.setattr(S, "rotate_one", one)
    monkeypatch.setattr(S, "recreate", lambda services: made.append(services))
    with pytest.raises(Failure, match="2 changed and their services made again; 1 not changed"):
        S.rotate("--all", "eaadmin", ops=lambda *a: {}, api=lambda c: {"idle": True})
    assert made == [["svc-EAX_CONSOLE_IT_PASSWORD", "svc-EAX_DB_PASSWORD"]]           # made again all the same



# ---------------------------------------------------------------- Rotate all behind the maintenance page (09:56)
def test_rotate_all_puts_the_maintenance_page_up_and_waits_for_the_background(work, monkeypatch):
    """"Rotate all puts up mantiance page, waits for jobs to be be finished and then does it"."""
    seen = []
    monkeypatch.setattr(S, "_rotate", lambda *a, **k: seen.append("rotated") or {"rotated": []})
    S.rotate("--all", "eaadmin", ops=lambda *a: seen.append(" ".join(a)) or {}, api=lambda c: seen.append(c) or {"idle": True})
    assert seen == ["quiet on", "idle", "rotated", "quiet off"]
    seen.clear()
    S.rotate("EAX_DB_PASSWORD", "eaadmin", ops=lambda *a: seen.append("page") or {}, api=lambda c: seen.append(c) or {})
    assert seen == ["rotated"]                                                   # one alone: no maintenance page


def test_rotate_all_changes_nothing_when_the_background_does_not_finish(work, monkeypatch):
    seen = []
    monkeypatch.setattr(S, "_rotate", lambda *a, **k: seen.append("rotated") or {})
    with pytest.raises(Failure, match="Nothing was rotated"):
        S.rotate("--all", "eaadmin", ops=lambda *a: seen.append(" ".join(a)) or {},
                 api=lambda c: {"idle": False, "error": "the background did not finish within 30 minutes: a job"})
    assert seen == ["quiet on", "quiet off"] and not S.lock_path().exists()


def test_jenkins_rotates_all_and_restarts_and_the_web_page_offers_the_restart():
    """"It should also be runnable from Jenkins. When done from Jenkins then it also restarts the app. If done form web
    app, it asks for restart of the app"."""
    from eaxcli import jenkins as J
    p = next(x for x in J.pipelines() if x["name"] == "admin-rotate-all-secrets")
    assert p["confirm"] is True
    assert J.argv_for("admin-rotate-all-secrets", {}) == ["secrets", "rotate", "--all", "--restart"]
    assert '"--restart" in rest' in (REPO / "eaxcli/secrets.py").read_text()
    jsx = (REPO / "services/web/src/Secrets.jsx").read_text()
    assert "function RestartOffer" in jsx and 'argv: ["restart"]' in jsx and "run.all && state !== \"running\" && ok" in jsx


# ---------------------------------------------------------------- the owner's Rotate all, 18 Nov 2026, 10:53
def test_a_rotation_never_makes_the_run_once_services_again(monkeypatch):
    """Making setup again re-ran it; it failed and the API, the library and the views waited on it."""
    calls = []
    monkeypatch.setattr(S, "_compose", lambda a, **k: calls.append(a) or "")
    S.recreate(["api", "setup", "reports-init", "testrunner", "library"], sleep=lambda s: None)
    assert calls == [["up", "-d", "--no-deps", "--force-recreate", "api", "library"]]


def test_a_login_this_installation_does_not_have_is_left_alone(monkeypatch):
    """EAX_REPLICATION_PASSWORD: role "eax_replicator" does not exist (no standby)."""
    sent = []
    monkeypatch.setattr(S, "_compose", lambda a, stdin="", **k: sent.append(stdin) or "")
    S.change_login("eax_replicator", "x'y")
    assert "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eax_replicator')" in sent[0] and "'x''y'" in sent[0]


def test_the_maintenance_page_comes_down_even_when_the_helper_could_not_do_it(work):
    (work / "proxy").mkdir()
    (work / "quiet.json").write_text("{}")
    (work / "proxy" / "maintenance").write_text("Backup and restore test")
    q = S.quiet_for_all(ops=lambda *a: {}, api=lambda c: {"idle": True})
    q.__enter__()
    assert "rotated" in (work / "proxy" / "maintenance").read_text()            # says what is going on
    q.__exit__(None, None, None)
    assert not (work / "quiet.json").exists() and not (work / "proxy" / "maintenance").exists()


def test_what_is_said_made_again_leaves_out_the_run_once_services(work, monkeypatch):
    rows = [{"key": "EAX_DB_PASSWORD", "auto": True, "set": True, "due": False, "why": ""}]
    monkeypatch.setattr(S, "rows", lambda *a, **k: rows)
    monkeypatch.setattr(S, "first_seen", lambda v: 0)
    monkeypatch.setattr(S, "read_state", lambda: {})
    monkeypatch.setattr(S, "rotate_one", lambda k, v, by, value=None, restart=True: ["api", "setup", "testrunner"])
    monkeypatch.setattr(S, "recreate", lambda services: None)
    assert S.rotate("--all", "x", ops=lambda *a: {}, api=lambda c: {"idle": True})["made_again"] == ["api"]


# ---------------------------------------------------------------- Windows: from PowerShell only (11:31)
def test_on_windows_what_makes_services_again_is_refused_from_the_web_and_schedules(monkeypatch):
    """The owner's Rotate all from the Secrets tab, 18 Nov 2026, 11:31: Keycloak, Documents and Reports "Restarting (127)":
    made again by compose inside the runner, they got Linux paths for the Windows folders."""
    sys.path.insert(0, str(REPO / "services" / "ops"))
    import commandcentre as CC
    assert CC.remakes_services(["secrets", "rotate", "--all", "--by", "x"]) and CC.remakes_services(["certs", "renew"])
    assert not CC.remakes_services(["secrets", "schedule", "monthly"]) and not CC.remakes_services(["status"])
    monkeypatch.setitem(CC.hooks, "me", lambda: {"windows": True, "install": "C:/Users/x/EA", "project": "eaexplorer"})
    with pytest.raises(CC.C.Refused, match=r"PowerShell .*\.\\eax secrets rotate --all\."):
        CC.refuse_on_windows(["secrets", "rotate", "--all", "--by", "eaadmin"])
    CC.refuse_on_windows(["status"])                                           # anything else goes on
    monkeypatch.setitem(CC.hooks, "me", lambda: {"windows": False, "install": "/srv/eax", "project": "eaexplorer"})
    CC.refuse_on_windows(["secrets", "rotate", "--all"])                       # Linux: as before
    src = (REPO / "services/ops/commandcentre.py").read_text()
    assert src.index("refuse_on_windows(argv)") < src.index('hooks["docker"]("create", "--name", name, "--label", f"eax.command=')
