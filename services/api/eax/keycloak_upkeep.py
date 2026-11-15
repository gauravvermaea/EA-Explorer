"""Keycloak kept in step with EA Explorer's settings, with the installation's own Keycloak administrator (EAX_KC_ADMIN).

Release 5:
  * **multi-factor sign-in** (R5.3, D690: "A setting, off by default"; "kepp mfa off by default"): the setting
    mfa_mode is off (the default), admins or everyone. Keycloak's own authenticator-app codes (TOTP): its standard
    browser sign-in already asks for a code from anyone who has set one up, so turning it on is asking people to set
    one up ("Configure OTP", a required action at their next sign-in). Admins are the Super, IT, User and Keycloak
    Admins and the Auditors. Applied when the setting changes and every hour (new admins, new people). People whose
    set-up EA Explorer asked for carry the attribute eax_mfa_asked, so turning it off takes back only what it asked
    (codes people set up themselves stay). An admin can reset a person's device: their code is removed and they set
    up a new one at the next sign-in.
  * **the Auditor role** (R5.22, D693): the realm role eax-audit is made when it is missing (realms made before
    Release 5 do not have it; Keycloak imports a realm only once).
"""

from __future__ import annotations

import urllib.parse

from .testing.reports_check import Keycloak

MODES = ("off", "admins", "everyone")
ADMIN_ROLES = ("eax-super-admin", "eax-it-admin", "eax-user-admin", "eax-keycloak-admin", "eax-audit")
ACTION = "CONFIGURE_TOTP"
ASKED = "eax_mfa_asked"
AUDIT_ROLE = {"name": "eax-audit", "description": "EA Explorer Auditor: sees everything a Super Admin sees (secrets "
              "only as set or not set), every report and all data; changes nothing (R5.22)"}


class UpkeepError(Exception):
    """The multi-factor upkeep could not reach or change Keycloak."""
    pass


def _kc(kc: Keycloak | None = None) -> Keycloak:
    kc = kc or Keycloak()
    if not kc.token:
        try:
            kc.sign_in()
        except RuntimeError as exc:
            raise UpkeepError(str(exc)) from exc
    return kc


def _users(kc: Keycloak) -> list[dict]:
    out, first = [], 0
    while True:
        s, page, _ = kc._call("GET", f"/users?first={first}&max=200&briefRepresentation=false")
        if s != 200 or not isinstance(page, list):
            raise UpkeepError(f"Keycloak did not list its users ({s})")
        out += page
        if len(page) < 200:
            return out
        first += 200


def _has_code(kc: Keycloak, uid: str) -> bool:
    s, creds, _ = kc._call("GET", f"/users/{uid}/credentials")
    return s == 200 and any(c.get("type") == "otp" for c in creds or [])


def _roles(kc: Keycloak, uid: str) -> set[str]:
    s, roles, _ = kc._call("GET", f"/users/{uid}/role-mappings/realm/composite")
    return {r["name"] for r in roles or []} if s == 200 else set()


def skipped(username: str) -> bool:
    """Never asked for a code: Keycloak's service accounts, EA Explorer's own (svc-, the self-test's included) and the
    laptop's test users (they sign in without a person, eax/permissions.py TEST_USERS)."""
    from .permissions import TEST_USERS
    return username.startswith(("service-account-", "svc-")) or username in {u for u, _r, _m in TEST_USERS}


def wanted(mode: str, roles: set[str]) -> bool:
    """Whether someone with these realm roles must use a code under this mode."""
    if mode == "everyone":
        return True
    if mode == "admins":
        return bool(roles & set(ADMIN_ROLES))
    return False


def apply_mfa(mode: str, kc: Keycloak | None = None) -> dict:
    """Ask for a code to be set up by whoever the mode wants and has none; take back what was asked of the others."""
    if mode not in MODES:
        raise UpkeepError(f"mfa_mode is {', '.join(MODES)}.")
    kc = _kc(kc)
    kc._call("PUT", f"/authentication/required-actions/{ACTION}",
             {"alias": ACTION, "name": "Configure OTP", "providerId": ACTION, "enabled": True,
              "defaultAction": mode == "everyone", "priority": 10, "config": {}})
    asked, released, have = 0, 0, 0
    for u in _users(kc):
        name = u.get("username", "")
        if skipped(name):
            continue
        uid, actions = u["id"], list(u.get("requiredActions") or [])
        attrs = dict(u.get("attributes") or {})
        mine = bool(attrs.get(ASKED))
        if wanted(mode, _roles(kc, uid)):
            if _has_code(kc, uid):
                have += 1
                continue
            if ACTION not in actions:
                kc._call("PUT", f"/users/{uid}", {"requiredActions": actions + [ACTION], "attributes": {**attrs, ASKED: ["1"]}})
                asked += 1
        elif mine:
            attrs.pop(ASKED, None)
            kc._call("PUT", f"/users/{uid}", {"requiredActions": [a for a in actions if a != ACTION], "attributes": attrs})
            released += 1
    return {"mode": mode, "asked": asked, "released": released, "set_up": have}


def reset_device(username: str, kc: Keycloak | None = None) -> dict:
    """A person's authenticator removed; they set up a new one at their next sign-in."""
    kc = _kc(kc)
    s, found, _ = kc._call("GET", f"/users?exact=true&username={urllib.parse.quote(username)}")
    if s != 200 or not found:
        raise UpkeepError(f"No person {username} in Keycloak.")
    u = found[0]
    s, creds, _ = kc._call("GET", f"/users/{u['id']}/credentials")
    removed = 0
    for c in creds or []:
        if c.get("type") == "otp":
            kc._call("DELETE", f"/users/{u['id']}/credentials/{c['id']}")
            removed += 1
    actions = list(u.get("requiredActions") or [])
    if ACTION not in actions:
        kc._call("PUT", f"/users/{u['id']}", {"requiredActions": actions + [ACTION]})
    return {"username": username, "removed": removed}


def mfa_status(kc: Keycloak | None = None) -> dict:
    """Who has a code set up, and who has been asked to set one up."""
    kc = _kc(kc)
    people, with_code, asked = 0, [], []
    for u in _users(kc):
        if skipped(u.get("username", "")):
            continue
        people += 1
        if _has_code(kc, u["id"]):
            with_code.append(u["username"])
        elif ACTION in (u.get("requiredActions") or []):
            asked.append(u["username"])
    return {"people": people, "with_code": sorted(with_code), "asked": sorted(asked)}


def ensure_audit_role(kc: Keycloak | None = None) -> bool:
    """The realm role eax-audit, made when missing (R5.22). True when it was made."""
    kc = _kc(kc)
    s, _, _ = kc._call("GET", f"/roles/{AUDIT_ROLE['name']}")
    if s == 200:
        return False
    s, d, _ = kc._call("POST", "/roles", AUDIT_ROLE)
    if s not in (201, 409):
        raise UpkeepError(f"Keycloak did not make the role eax-audit ({s}: {d})")
    return True
