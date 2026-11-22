"""R9.7 (D829; owner, 21 Nov 2026: "force one user setup authenticator from user list if they lost phone or something.
Select the user and force them to go through authenticator flow. This will have to be tested manually"): the Users page
shows each person's authenticator and asks those ticked to set it up again at once: codes removed, Configure OTP asked
for, signed out everywhere, emailed and audited. Who may: User Admins and Super Admins, not on themselves, a Super Admin
only by another, anyone from a break-glass session. The phone part is tested by hand (docs/manual-tests.md)."""

from __future__ import annotations

from pathlib import Path

from eax import keycloak_upkeep as ku
from eax import permissions
from eax.api import access

REPO = Path(__file__).resolve().parents[3]


class FakeKeycloak:
    """Keycloak's admin API as the reset sees it: one person with a code, every call kept."""

    def __init__(self, roles=("eax-user",)):
        self.token = "t"
        self.calls = []
        self.user = {"id": "u1", "username": "thandi", "email": "thandi@example.org", "requiredActions": []}
        self.roles = [{"name": r} for r in roles]

    def _call(self, method, path, body=None, form=None):
        self.calls.append((method, path, body))
        if method == "GET" and path.startswith("/users?exact=true"):
            return 200, [dict(self.user)], {}
        if method == "GET" and path.startswith("/users?first="):
            return 200, [dict(self.user), {"id": "u2", "username": "svc-self-test-1-x", "requiredActions": []},
                         {"id": "u3", "username": "sipho", "requiredActions": ["CONFIGURE_TOTP"]}], {}
        if method == "GET" and path == "/users/u1/credentials":
            return 200, [{"id": "c1", "type": "otp"}, {"id": "c2", "type": "password"}], {}
        if method == "GET" and path.endswith("/credentials"):
            return 200, [], {}
        if method == "GET" and "role-mappings" in path:
            return 200, self.roles, {}
        if method == "POST" and path.endswith("/logout"):
            return 204, None, {}
        return 204, None, {}


def test_the_reset_removes_the_code_asks_for_a_new_one_and_signs_them_out_everywhere():
    kc = FakeKeycloak()
    out = ku.force_setup("thandi", kc)
    assert out == {"username": "thandi", "removed": 1, "signed_out": True}
    assert ("DELETE", "/users/u1/credentials/c1", None) in kc.calls                  # the otp code only
    assert not any(c[0] == "DELETE" and c[1].endswith("/c2") for c in kc.calls)        # never the password
    assert ("PUT", "/users/u1", {"requiredActions": ["CONFIGURE_TOTP"]}) in kc.calls
    assert ("POST", "/users/u1/logout", None) in kc.calls
    assert not any("required-actions" in c[1] or "/attributes" in c[1] for c in kc.calls)   # the MFA setting untouched


def test_each_persons_authenticator_for_the_list():
    states = ku.mfa_states(FakeKeycloak())
    assert states == {"thandi": "set up", "sipho": "asked"}                            # the self-test's account left out
    assert ku.person("thandi", FakeKeycloak(roles=("eax-super-admin",)))["roles"] == ["eax-super-admin"]


def test_who_may_ask_whom():
    user, sa = {"username": "thandi", "roles": ["eax-user"]}, {"username": "boss", "roles": ["eax-super-admin"]}
    assert access.mfa_refusal("ua", ["user-admin"], False, user) == ""
    assert "yourself" in access.mfa_refusal("thandi", ["user-admin"], False, user)
    assert "another Super Admin" in access.mfa_refusal("ua", ["user-admin"], False, sa)
    assert "another Super Admin" in access.mfa_refusal("ua", ["user-admin"], False, {"username": "boss", "roles": [],
                                                                                    "app_roles": ["super-admin"]})
    assert access.mfa_refusal("sa2", ["super-admin"], False, sa) == ""
    assert access.mfa_refusal("break-glass", ["super-admin"], True, {**sa, "username": "break-glass"}) == ""   # the way back in
    assert "service or test" in access.mfa_refusal("sa2", ["super-admin"], False, {"username": "svc-x", "roles": []})


def test_user_admins_and_super_admins_only():
    assert permissions.GLOBAL_PERMISSIONS["users.manage"] == {permissions.USER_ADMIN}  # Super Admins always
    src = (REPO / "services/api/eax/api/access.py").read_text(encoding="utf-8")
    block = src[src.index('@blp.route("/people/mfa-reset")'):src.index("# ---------------------------------------------------------------- who is assigned")]
    assert '@require_auth("users.manage")' in block and "audit.record(" in block and "alerts.send_email(" in block
    assert "len(names) > 100" in block


def test_the_email_says_who_when_and_what_happens_next():
    subject, body = access.mfa_reset_mail({"username": "thandi"}, "user_admin", "2026-11-22 08:00")
    assert "authenticator" in subject and "user_admin" in body and "2026-11-22 08:00 UTC" in body
    assert "QR code" in body and "old phone no longer work" in body


def test_the_users_page_ticks_shows_and_confirms():
    page = (REPO / "services/web/src/Users.jsx").read_text(encoding="utf-8")
    for x in ('apiFetch("/api/v1/people/mfa-reset"', 'useLoad("/api/v1/people/mfa")', 'can("users.manage")',
              'type="checkbox"', "Set up the authenticator again...", '<Modal title="Set up the authenticator again"',
              "<th>Authenticator</th>"):
        assert x in page, x
    import json
    cat = json.loads((REPO / "services/web/src/help/catalogue.json").read_text(encoding="utf-8"))
    assert "popup:Set up the authenticator again" in cat


def test_the_manual_steps_are_written():
    text = (REPO / "docs" / "manual-tests.md").read_text(encoding="utf-8")
    assert "R9.7" in text and "QR code" in text and "old phone" in text and text.count("- [ ]") >= 6


def test_r12_19_the_refusal_for_yourself_names_a_way_that_exists():
    """R12.19 (owner, 22 Nov 2026): ticking yourself said "My profile has your own authenticator", but My profile has
    none; the way that exists is another admin, or a Super Admin on System Admin > Security."""
    me = {"username": "eaadmin", "roles": ["eax-super-admin"], "app_roles": [permissions.SUPER_ADMIN]}
    why = access.mfa_refusal("eaadmin", [permissions.SUPER_ADMIN], False, me)
    assert "yourself" in why and "My profile" not in why
    assert "another admin" in why and "System Admin › Security › Reset the authenticator of" in why
    page = (Path(__file__).resolve().parents[2] / "web" / "src" / "Security.jsx").read_text(encoding="utf-8")
    assert "Reset the authenticator of" in page                  # the field the message names is there
