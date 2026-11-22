"""eax access: getting an administrator back in, from the machine (Release 6.6, R6.6-J1; the owner, 18 Nov 2026, 09:59:
"reset password for admin to get in"; 10:01: "These should be things we wont do from inside the application. So user
management is not going to be done here").

Only for the administrators (the first admin, EAX_FIRST_ADMIN_USER, and anyone holding the eax-super-admin or
eax-it-admin role in Keycloak), only to get back in; people and their roles are managed in EA Explorer and Keycloak as
before. Everything runs inside the Keycloak container with its own admin tool (kcadm), signed in with the Keycloak
admin's password from its secret file; nothing goes over the network.

  eax access admins                    the administrators: their names, whether each is enabled, locked out, or has MFA
  eax access reset-password <user>     a new temporary password, shown once here; it must be changed at sign-in
  eax access unlock <user>             the account enabled and its sign-in lock (too many wrong passwords) lifted
  eax access mfa-off <user>            the second factor (an authenticator app) removed, and no new one asked for
                                       (unless the multi-factor setting wants this person to have one)
  eax access mfa-off --all [--yes]     multi-factor sign-in switched off for everyone: the setting set to off, every
                                       authenticator removed and nobody asked to set one up (R12.20)
"""

from __future__ import annotations

import json
import re
import secrets as _random
import subprocess

from .core import EAX, ROOT, Failure, compose_args, say, setting

# MFA off for everyone (R12.20; owner, 22 Nov 2026, 10:49: "Can we have a command in eax to disable mfa", "I want to run
# it now"): run in the api container with the code already there, so it works without a rebuild. The setting is stored
# as the Security page stores it, Keycloak is told as the Security page tells it, then every person's authenticator and
# every request to set one up go too (the Security page's off only takes back what it asked for). Audited.
MFA_OFF_ALL = r"""
import json
from sqlalchemy import text
from eax import audit, keycloak_upkeep as ku, settings as st
from eax.db import get_engine
with get_engine().connect() as conn, conn.begin():
    conn.execute(text("SELECT set_config('eax.actor', 'eax access', true)"))
    before = st.values(conn).get("mfa_mode", "off")
    st.store(conn, {"mfa_mode": "off"})
kc = ku._kc()
ku.apply_mfa("off", kc)
people, codes, asked = [], 0, 0
for u in ku._users(kc):
    name = u.get("username", "")
    if ku.skipped(name):
        continue
    actions = list(u.get("requiredActions") or [])
    n = ku._remove_codes(kc, u["id"])
    if ku.ACTION in actions:
        attrs = dict(u.get("attributes") or {})
        attrs.pop(ku.ASKED, None)
        kc._call("PUT", "/users/" + u["id"], {"requiredActions": [a for a in actions if a != ku.ACTION], "attributes": attrs})
        asked += 1
    if n or ku.ACTION in actions:
        people.append(name)
    codes += n
out = {"before": before, "mode": "off", "people": sorted(people), "codes_removed": codes, "no_longer_asked": asked}
with get_engine().connect() as conn, conn.begin():
    audit.record(conn, actor="eax access", action="security.mfa_off_all", object_type="setting", object_id="mfa_mode",
                 details=out, source="eax")
print(json.dumps(out))
"""

ADMIN_ROLES = ("eax-super-admin", "eax-it-admin")
LOGIN = ('K=/opt/keycloak/bin/kcadm.sh; C=/tmp/eax-access-$$.config; trap "rm -f $C" EXIT; '
         '$K config credentials --config $C --server http://localhost:8080/auth --realm master --user "$1" '
         '--password "$(cat /run/secrets/EAX_KC_ADMIN_PASSWORD)" >/dev/null 2>&1 || { echo "Keycloak would not sign its admin in" >&2; exit 3; }; ')


def _kc(script: str, *args: str, stdin: str = "", run=subprocess.run) -> str:
    """One kcadm script inside Keycloak, signed in first; its output, or Failure in words."""
    p = run(compose_args(["exec", "-T", "keycloak", "bash", "-c", "set -e; " + LOGIN + script, "kc",
                          setting("EAX_KC_ADMIN", "kcadmin"), *args]), cwd=ROOT, input=stdin, capture_output=True,
            text=True, encoding="utf-8", errors="replace", check=False)
    if p.returncode != 0:
        raise Failure(f"Keycloak: {(p.stderr or p.stdout).strip()[-300:] or 'it did not answer'} (is EA Explorer running? {EAX} status)")
    return p.stdout


def _realm() -> str:
    return setting("EAX_KEYCLOAK_REALM", "eaexplorer")


def _user(name: str, run=subprocess.run) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9._@-]{1,100}", name or ""):
        raise Failure("Give the administrator's user name.")
    found = json.loads(_kc('$K get users --config $C -r "$2" -q exact=true -q username="$3"', _realm(), name, run=run) or "[]")
    if not found:
        raise Failure(f"No user {name} in Keycloak.")
    return found[0]


def is_admin(user: dict, roles: list[str]) -> bool:
    """The first admin, or anyone with an administrator's role (pure)."""
    return user.get("username") == setting("EAX_FIRST_ADMIN_USER", "eaadmin") or any(r in ADMIN_ROLES for r in roles)


def _admin(name: str, run=subprocess.run) -> dict:
    """The user, refused unless an administrator: this is for getting back in, not for managing people."""
    u = _user(name, run=run)
    roles = [r.get("name") for r in json.loads(_kc('$K get "users/$3/role-mappings/realm/composite" --config $C -r "$2"',
                                                   _realm(), u["id"], run=run) or "[]")]
    if not is_admin(u, roles):
        raise Failure(f"{name} is not an administrator: people and their roles are managed in EA Explorer and Keycloak, "
                      "not here.")
    return u


def admins(run=subprocess.run) -> list[dict]:
    """The administrators: the first admin and the direct holders of the administrators' roles."""
    names: dict[str, dict] = {}
    for role in ADMIN_ROLES:
        try:
            for u in json.loads(_kc('$K get "roles/$3/users" --config $C -r "$2"', _realm(), role, run=run) or "[]"):
                names.setdefault(u["username"], u)
        except Failure:
            continue
    first = setting("EAX_FIRST_ADMIN_USER", "eaadmin")
    if first not in names:
        try:
            names[first] = _user(first, run=run)
        except Failure:
            pass
    return sorted(names.values(), key=lambda u: u["username"])


def reset_password(name: str, run=subprocess.run) -> str:
    """A new temporary password (changed at sign-in), set in Keycloak; returned to be shown once."""
    u = _admin(name, run=run)
    pw = _random.token_urlsafe(12) + "-Aa7"
    _kc('$K set-password --config $C -r "$2" --userid "$3" --new-password "$(cat)" --temporary', _realm(), u["id"],
        stdin=pw, run=run)
    return pw


def unlock(name: str, run=subprocess.run) -> None:
    """The account enabled and the brute-force lock lifted."""
    u = _admin(name, run=run)
    _kc('$K update "users/$3" --config $C -r "$2" -s enabled=true; '
        '$K delete "attack-detection/brute-force/users/$3" --config $C -r "$2" >/dev/null 2>&1 || true', _realm(), u["id"], run=run)


def mfa_off(name: str, run=subprocess.run) -> int:
    """Every one-time-code credential removed, and the request to set one up taken back (R12.20: it was left, so the
    next sign-in asked for a new authenticator straight away); how many codes."""
    u = _admin(name, run=run)
    creds = json.loads(_kc('$K get "users/$3/credentials" --config $C -r "$2"', _realm(), u["id"], run=run) or "[]")
    otp = [c["id"] for c in creds if c.get("type") == "otp"]
    for cid in otp:
        _kc('$K delete "users/$3/credentials/$4" --config $C -r "$2"', _realm(), u["id"], cid, run=run)
    actions = list(u.get("requiredActions") or [])
    if "CONFIGURE_TOTP" in actions:
        _kc('$K update "users/$3" --config $C -r "$2" -f -', _realm(), u["id"],
            stdin=json.dumps({"requiredActions": [a for a in actions if a != "CONFIGURE_TOTP"]}), run=run)
    return len(otp)


def mfa_off_all(yes: bool = False, run=subprocess.run, ask=input) -> dict:
    """Multi-factor sign-in off for everyone (R12.20), after the word OFF typed (or --yes)."""
    if not yes:
        say("This switches multi-factor sign-in off for everyone: the setting (System Admin > Security) set to off, "
            "every authenticator removed and nobody asked to set one up. Anyone may add one again later.", "yellow")
        if ask("Type OFF to go on: ").strip() != "OFF":
            raise Failure("Nothing changed.")
    p = run(compose_args(["exec", "-T", "api", "python", "-c", MFA_OFF_ALL]), cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False)
    last = next((x for x in reversed((p.stdout or "").splitlines()) if x.strip().startswith("{")), "")
    if p.returncode != 0 or not last:
        raise Failure(f"MFA could not be switched off: {(p.stderr or p.stdout).strip()[-400:] or 'no answer'} "
                      f"(is EA Explorer running? {EAX} status)")
    return json.loads(last)


def main(argv: list[str]) -> int:
    """eax access admins | reset-password <user> | unlock <user> | mfa-off <user>."""
    action, rest = (argv[0] if argv else "admins"), argv[1:]
    if action == "mfa-off" and "--all" in rest:
        r = mfa_off_all("--yes" in rest or "-y" in rest)
        say(f"Multi-factor sign-in is off for everyone (it was {r['before']}): {r['codes_removed']} authenticator(s) "
            f"removed, {r['no_longer_asked']} no longer asked to set one up"
            + (f" ({', '.join(r['people'])})." if r["people"] else ".") + " Sign out and in again: no code is asked.")
        return 0
    rest = [a for a in rest if a not in ("--yes", "-y")]
    who = rest[0] if rest else setting("EAX_FIRST_ADMIN_USER", "eaadmin")
    if action == "admins":
        say("The administrators (eax access reset-password|unlock|mfa-off <user> to get one back in):")
        for u in admins():
            say(f"  {u['username']:<24} {'enabled' if u.get('enabled', True) else 'DISABLED'}"
                f"{'  ' + u['email'] if u.get('email') else ''}")
        return 0
    if action == "reset-password":
        pw = reset_password(who)
        say(f"{who}'s new temporary password (shown once; it must be changed at the next sign-in):")
        say(f"  {pw}")
        return 0
    if action == "unlock":
        unlock(who)
        say(f"{who} is enabled and may sign in again (the lock after wrong passwords lifted).")
        return 0
    if action == "mfa-off":
        n = mfa_off(who)
        say(f"{who}: {n} authenticator(s) removed and no new one asked for; when the multi-factor setting wants {who} "
            f"to have one, they are asked again within the hour ({EAX} access mfa-off --all switches it off for everyone).")
        return 0
    raise Failure(f"{EAX} access admins | reset-password <user> | unlock <user> | mfa-off <user> | mfa-off --all [--yes]")
