"""R5.3 multi-factor sign-in (D690: "A setting, off by default"; "kepp mfa off by default") and R5.22 the Auditor
(D693: "this role can view everything like a super admin but can not make any changes"; "No secrets; sees AI activity")."""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import auth  # noqa: E402
from eax import keycloak_upkeep as ku  # noqa: E402
from eax import permissions as P  # noqa: E402
from eax import settings as st  # noqa: E402


# ---------------------------------------------------------------- R5.3
def test_mfa_is_a_setting_off_by_default():
    group, _label, typ, default, choices, _help = st.REGISTRY["mfa_mode"]
    assert (group, typ, default, choices) == ("security", "choice", "off", ["off", "admins", "everyone"])


def test_who_must_set_up_a_code():
    assert not ku.wanted("off", {"eax-super-admin"})
    assert ku.wanted("admins", {"eax-it-admin"}) and ku.wanted("admins", {"eax-audit"}) and not ku.wanted("admins", {"eax-user"})
    assert ku.wanted("everyone", {"eax-user"})
    assert ku.skipped("svc-self-test-1-sa") and ku.skipped("service-account-eax-admin") and ku.skipped("user_architect")
    assert not ku.skipped("ann")


class FakeKc:
    """Keycloak's admin API, in memory: users with roles, required actions, attributes and credentials."""

    def __init__(self, users):
        self.token, self.users, self.calls = "t", {u["id"]: u for u in users}, []

    def _call(self, method, path, body=None, form=None):
        self.calls.append((method, path, body))
        if path.startswith("/authentication/required-actions/"):
            return 204, None, {}
        if method == "GET" and path.startswith("/users?first="):
            return 200, list(self.users.values()) if "first=0" in path else [], {}
        if method == "GET" and path.startswith("/users?exact=true"):
            name = path.split("username=")[1]
            return 200, [u for u in self.users.values() if u["username"] == name], {}
        parts = path.split("/")
        u = self.users.get(parts[2]) if len(parts) > 2 else None
        if method == "GET" and path.endswith("/role-mappings/realm/composite"):
            return 200, [{"name": r} for r in u["roles"]], {}
        if method == "GET" and path.endswith("/credentials"):
            return 200, [{"id": "c1", "type": "otp"}] if u.get("otp") else [], {}
        if method == "DELETE" and "/credentials/" in path:
            u["otp"] = False
            return 204, None, {}
        if method == "PUT" and len(parts) == 3:
            u.update(body)
            return 204, None, {}
        return 404, None, {}


def people():
    return [{"id": "1", "username": "ann", "roles": ["eax-super-admin"], "requiredActions": [], "attributes": {}},
            {"id": "2", "username": "bob", "roles": ["eax-user"], "requiredActions": [], "attributes": {}},
            {"id": "3", "username": "cat", "roles": ["eax-it-admin"], "requiredActions": [], "attributes": {}, "otp": True},
            {"id": "4", "username": "user_it_admin", "roles": ["eax-it-admin"], "requiredActions": [], "attributes": {}}]


def test_admins_mode_asks_admins_without_a_code_and_off_takes_it_back():
    kc = FakeKc(people())
    r = ku.apply_mfa("admins", kc)
    assert r == {"mode": "admins", "asked": 1, "released": 0, "set_up": 1, "codes_removed": 0}
    assert kc.users["1"]["requiredActions"] == [ku.ACTION] and kc.users["1"]["attributes"][ku.ASKED] == ["1"]
    assert kc.users["2"]["requiredActions"] == [] and kc.users["4"]["requiredActions"] == []   # not an admin; a test user
    assert ("PUT", f"/authentication/required-actions/{ku.ACTION}") in [(m, p) for m, p, _b in kc.calls]
    r = ku.apply_mfa("off", kc)
    assert r["released"] == 1 and kc.users["1"]["requiredActions"] == [] and ku.ASKED not in kc.users["1"]["attributes"]


def test_off_removes_the_code_people_set_up_because_they_were_asked():
    """R5.25 (owner, 15 Nov 2026, 19:09): MFA on, signed in once (the code set up), MFA off: still asked for a code,
    because Keycloak asks anyone who has one. Off removes the code EA Explorer asked for; one set up unasked stays."""
    kc = FakeKc(people())
    ku.apply_mfa("admins", kc)
    kc.users["1"]["otp"] = True                                  # ann signs in and sets up her authenticator
    kc.users["1"]["requiredActions"] = []                        # Keycloak clears the request once done
    assert ku.apply_mfa("admins", kc)["set_up"] == 2             # the hourly upkeep leaves her as she is
    r = ku.apply_mfa("off", kc)
    assert r["released"] == 1 and r["codes_removed"] == 1
    assert not kc.users["1"]["otp"] and ku.ASKED not in kc.users["1"]["attributes"]
    assert kc.users["3"]["otp"]                                  # cat set hers up herself: kept


def test_everyone_mode_asks_everyone_and_new_people():
    kc = FakeKc(people())
    assert ku.apply_mfa("everyone", kc)["asked"] == 2
    body = next(b for m, p, b in kc.calls if p.startswith("/authentication/required-actions/"))
    assert body["defaultAction"] is True


def test_resetting_a_device():
    kc = FakeKc(people())
    out = ku.reset_device("cat", kc)
    assert out["removed"] == 1 and kc.users["3"]["requiredActions"] == [ku.ACTION] and not kc.users["3"]["otp"]
    with pytest.raises(ku.UpkeepError):
        ku.reset_device("nobody", kc)


def test_mfa_is_applied_when_changed_and_every_hour():
    src = (REPO / "services/api/eax/settings.py").read_text()
    assert 'if "mfa_mode" in clean:' in src and "keycloak_upkeep.apply_mfa" in src
    jobs = (REPO / "services/api/eax/jobs.py").read_text()
    assert 'name="eax.keycloak_upkeep"' in jobs and "ku.ensure_audit_role()" in jobs


# ---------------------------------------------------------------- R5.22
def test_the_auditor_is_a_global_role_with_no_permission_of_its_own():
    assert P.AUDITOR in P.GLOBAL_ROLES
    assert not any(P.allowed([P.AUDITOR], p) for p in P.GLOBAL_PERMISSIONS)
    assert ("user_auditor", "eax-audit", {}) in P.TEST_USERS


@pytest.mark.parametrize("method,path,read", [
    ("GET", "/api/v1/models", True), ("POST", "/api/v1/models", False), ("DELETE", "/api/v1/models/x", False),
    ("POST", "/api/v1/search", True), ("POST", "/api/v1/sql/query", True), ("POST", "/api/v1/compare/download", True),
    ("PUT", "/api/v1/admin/settings", False), ("PATCH", "/api/v1/x", False)])
def test_reads_and_changes_are_told_apart(method, path, read):
    assert P.is_read(method, path) is read


def test_an_auditor_reads_as_a_super_admin_and_changes_with_their_other_roles_only():
    roles, view = P.auditor_roles([P.AUDITOR, P.USER], "GET", "/api/v1/models")
    assert view and P.SUPER_ADMIN in roles and P.allowed(roles, "settings.manage")
    roles, view = P.auditor_roles([P.AUDITOR, P.USER], "POST", "/api/v1/models")
    assert not view and not P.allowed(roles, "models.create") and not P.allowed(roles, "settings.manage")
    roles, _ = P.auditor_roles([P.AUDITOR, P.MODEL_CREATOR], "POST", "/api/v1/models")
    assert P.allowed(roles, "models.create")                                  # another role still lets them
    assert P.view_only([P.AUDITOR, P.USER]) and not P.view_only([P.AUDITOR, P.IT_ADMIN])


def test_the_auditor_sees_no_secret():
    out = auth.hide_secrets({"EAX_DB_PASSWORD": "s3cret", "rows": [{"key": "EAX_OPS_TOKEN", "value": "abc"},
                                                                    {"key": "EAX_HOSTNAME", "value": "ea.example"}],
                             "text": "EAX_HOSTNAME=ea.example\nEAX_KC_ADMIN_PASSWORD=xyz\nEAX_LIBRARY_KEY=k\n",
                             "env": ["EAX_DB_PASSWORD=pw", "PATH=/bin"], "secret": True, "empty_token": ""})
    assert out["EAX_DB_PASSWORD"] == "(set)" and out["rows"][0]["value"] == "(set)" and out["rows"][1]["value"] == "ea.example"
    assert "xyz" not in out["text"] and "EAX_HOSTNAME=ea.example" in out["text"] and "EAX_LIBRARY_KEY=(set)" in out["text"]
    assert out["env"] == ["EAX_DB_PASSWORD=(set)", "PATH=/bin"] and out["secret"] is True and out["empty_token"] == "(not set)"
    assert "hide_secrets(out) if user.auditor_view else out" in (REPO / "services/api/eax/auth.py").read_text()


def test_the_auditor_through_mcp():
    from eax import mcp_server as M
    reader = next(t["name"] for t in __import__("eax.mcp_catalogue", fromlist=["x"]).tools() if not t["changes"])
    writer = next(t["name"] for t in __import__("eax.mcp_catalogue", fromlist=["x"]).tools() if t["changes"])
    who = P.Principal("aud", (P.AUDITOR, P.USER))
    assert P.SUPER_ADMIN in M.auditor_principal(who, reader).roles
    assert M.auditor_principal(who, writer) is who


def test_the_auditor_everywhere_else():
    sql = (REPO / "services/api/migrations/sql/0079_r5_auditor.sql").read_text()
    assert "('eax-audit', 'auditor'" in sql and "ARRAY['super-admin', 'auditor']" in sql
    assert '"eax-audit": ["Gamma", READER]' in (REPO / "deploy/superset/superset_config.py").read_text()
    assert '"name": "eax-audit"' in (REPO / "deploy/keycloak/realm-eaexplorer.json.tmpl").read_text()
    js = (REPO / "services/web/src/auth.js").read_text()
    assert "Auditor: view only" in js and "export function viewOnly()" in js
    py_regex = P.READ_POSTS.pattern.replace("\\", "")
    js_regex = js.split("const READ_POSTS = /")[1].split("/;")[0].replace("\\", "")
    assert py_regex.strip("/") .replace("$", "") in js_regex.replace("$", "") or js_regex.startswith("/(search|query")
    assert '"view_only": permissions.view_only(real)' in (REPO / "services/api/eax/api/me.py").read_text()
