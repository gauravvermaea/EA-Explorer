"""R12.20: a command to switch MFA off (owner, 22 Nov 2026, 10:49: "I removed the MFA but it is still asking me after
logout. Can we have a command in eax to disable mfa"; "I want to run it now"; "it may restart whatever container it
needs to").

Two faults found: `eax access mfa-off <user>` (and the Security page's reset) removed the authenticator but left
Keycloak's request to set one up, so the next sign-in asked again; and nothing switched MFA off for everyone from the
machine. Now mfa-off takes the request back too, and `eax access mfa-off --all` sets the setting to off, tells Keycloak,
and removes every authenticator and every request; it runs in the api container with the code already there (no
rebuild), asks for OFF unless --yes, and is audited.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from eaxcli import access as A  # noqa: E402
from eaxcli.core import Failure  # noqa: E402


class P:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def _keycloak(users: dict, seen: list):
    def run(args, **k):
        script, rest = args[5], args[6:]
        seen.append((script, rest, k.get("input", "")))
        if "get users " in script:
            u = users.get(rest[3])
            return P(0, json.dumps([u] if u else []))
        if "role-mappings" in script:
            return P(0, json.dumps([{"name": "eax-super-admin"}]))
        if "credentials" in script and "get" in script:
            return P(0, json.dumps([{"id": "c1", "type": "password"}, {"id": "c2", "type": "otp"}]))
        return P(0, "")
    return run


def test_mfa_off_for_one_person_also_takes_back_the_request_to_set_one_up(monkeypatch):
    monkeypatch.setattr(A, "compose_args", lambda a: a)
    monkeypatch.setattr(A, "setting", lambda k, d="": {"EAX_FIRST_ADMIN_USER": "eaadmin"}.get(k, d))
    users = {"eaadmin": {"id": "u1", "username": "eaadmin", "requiredActions": ["CONFIGURE_TOTP", "VERIFY_EMAIL"]}}
    seen = []
    assert A.mfa_off("eaadmin", run=_keycloak(users, seen)) == 1
    script, rest, given = seen[-1]
    assert "update" in script and '"users/$3"' in script and "-f -" in script and rest[-1] == "u1"
    assert json.loads(given) == {"requiredActions": ["VERIFY_EMAIL"]}          # only the authenticator's request goes
    assert any("credentials/$4" in s and r[-1] == "c2" for s, r, _ in seen)


def test_mfa_off_for_one_person_changes_nothing_more_when_nothing_was_asked(monkeypatch):
    monkeypatch.setattr(A, "compose_args", lambda a: a)
    monkeypatch.setattr(A, "setting", lambda k, d="": {"EAX_FIRST_ADMIN_USER": "eaadmin"}.get(k, d))
    seen = []
    A.mfa_off("eaadmin", run=_keycloak({"eaadmin": {"id": "u1", "username": "eaadmin"}}, seen))
    assert not any(" update " in s for s, _r, _g in seen)


def test_mfa_off_all_asks_for_off_runs_in_the_api_container_and_says_what_it_did(monkeypatch):
    monkeypatch.setattr(A, "compose_args", lambda a: a)
    seen = []

    def run(args, **k):
        seen.append(args)
        return P(0, "noise\n" + json.dumps({"before": "everyone", "mode": "off", "people": ["eaadmin"],
                                            "codes_removed": 1, "no_longer_asked": 1}) + "\n")
    with pytest.raises(Failure, match="Nothing changed"):
        A.mfa_off_all(run=run, ask=lambda _q: "no")
    assert not seen
    r = A.mfa_off_all(run=run, ask=lambda _q: "OFF")
    assert r["before"] == "everyone" and r["people"] == ["eaadmin"]
    assert seen[-1][:5] == ["exec", "-T", "api", "python", "-c"] and seen[-1][5] == A.MFA_OFF_ALL
    A.mfa_off_all(True, run=run, ask=lambda _q: pytest.fail("--yes asks nothing"))


def test_mfa_off_all_fails_in_words_when_the_api_does_not_answer(monkeypatch):
    monkeypatch.setattr(A, "compose_args", lambda a: a)
    with pytest.raises(Failure, match="could not be switched off: service \"api\" is not running"):
        A.mfa_off_all(True, run=lambda *a, **k: P(1, "", 'service "api" is not running'))


def test_the_command_line_routes_all_and_yes(monkeypatch, capsys):
    monkeypatch.setattr(A, "mfa_off_all", lambda yes: {"before": "admins", "mode": "off", "people": [], "codes_removed": 0,
                                                       "no_longer_asked": 0} if yes else pytest.fail("--yes lost"))
    assert A.main(["mfa-off", "--all", "--yes"]) == 0
    assert "off for everyone (it was admins)" in capsys.readouterr().out


def test_the_script_in_the_api_container_switches_everything_off(monkeypatch):
    """MFA_OFF_ALL run against stand-ins for the api's own modules: the setting stored as off, Keycloak told, every
    person's codes and request removed (never a test or service account's), audited, the answer printed."""
    calls = {"stored": None, "applied": None, "puts": [], "removed": [], "audit": None}

    class Conn:
        def execute(self, *a, **k):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def begin(self):
            return self

    sqlalchemy = types.ModuleType("sqlalchemy")
    sqlalchemy.text = lambda s: s
    st = types.ModuleType("eax.settings")
    st.values = lambda conn=None: {"mfa_mode": "everyone"}
    st.store = lambda conn, clean: calls.__setitem__("stored", clean)
    db = types.ModuleType("eax.db")
    db.get_engine = lambda: types.SimpleNamespace(connect=Conn)
    audit = types.ModuleType("eax.audit")
    audit.record = lambda conn, **k: calls.__setitem__("audit", k)

    class KC:
        def _call(self, method, path, body=None):
            calls["puts"].append((method, path, body))
            return 200, None, None

    ku = types.ModuleType("eax.keycloak_upkeep")
    ku.ACTION, ku.ASKED = "CONFIGURE_TOTP", "eax_mfa_asked"
    ku._kc = lambda kc=None: KC()
    ku.apply_mfa = lambda mode, kc=None: calls.__setitem__("applied", mode)
    ku.skipped = lambda name: name.startswith("svc-") or name == "user_architect"
    ku._users = lambda kc: [
        {"id": "u1", "username": "eaadmin", "requiredActions": ["CONFIGURE_TOTP"], "attributes": {"eax_mfa_asked": ["1"], "x": ["y"]}},
        {"id": "u2", "username": "thandi", "requiredActions": []},
        {"id": "u3", "username": "user_architect", "requiredActions": ["CONFIGURE_TOTP"]},
        {"id": "u4", "username": "svc-ops", "requiredActions": []}]
    ku._remove_codes = lambda kc, uid: (calls["removed"].append(uid), {"u1": 0, "u2": 1}.get(uid, 5))[1]
    eax = types.ModuleType("eax")
    eax.audit, eax.keycloak_upkeep, eax.settings = audit, ku, st
    for name, mod in {"sqlalchemy": sqlalchemy, "eax": eax, "eax.settings": st, "eax.db": db, "eax.audit": audit,
                      "eax.keycloak_upkeep": ku}.items():
        monkeypatch.setitem(sys.modules, name, mod)
    printed = []
    exec(compile(A.MFA_OFF_ALL, "mfa_off_all", "exec"), {"print": printed.append, "__name__": "__main__"})
    out = json.loads(printed[-1])
    assert calls["stored"] == {"mfa_mode": "off"} and calls["applied"] == "off"
    assert calls["removed"] == ["u1", "u2"]                             # never a test or service account
    assert calls["puts"] == [("PUT", "/users/u1", {"requiredActions": [], "attributes": {"x": ["y"]}})]
    assert out == {"before": "everyone", "mode": "off", "people": ["eaadmin", "thandi"], "codes_removed": 1,
                   "no_longer_asked": 1}
    assert calls["audit"]["action"] == "security.mfa_off_all" and calls["audit"]["details"] == out


def test_help_and_launchers_in_step():
    h = (REPO / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    assert "### access [admins|reset-password|unlock|mfa-off] [USER] [--all] [--yes]" in h
    assert "$ {eax} access mfa-off --all" in h and all(ord(c) < 128 for c in h)
    assert '"access"' in (REPO / "eax.ps1").read_text(encoding="utf-8")


def test_jenkins_has_mfa_off_for_everyone_asking_to_be_confirmed():
    """Owner, 22 Nov 2026, 10:52: "add this ability in jenkins too"."""
    from eaxcli import commands as C
    from eaxcli import jenkins as J
    t = J.ADMIN_BY_NAME["admin-mfa-off-for-everyone"]
    assert t["group"] == "Get back in" and t["confirm"] is True
    argv = J.admin_argv("admin-mfa-off-for-everyone", {})
    assert argv == ["access", "mfa-off", "--all", "--yes"]
    C.check_argv(argv)                                                  # every word a known one
    assert J.command_line(argv)[-4:] == argv                            # run through eaxpy, as written
