"""eax secrets: the installation's passwords and keys (phase 36, D504; Release 6, D743 to D746).

The passwords and keys (every value the server template holds as change-me) live in work/eaexplorer.env, and reach each
container as files of its own (Docker secrets, R6-F1), never as environment variables. No key vault is run (OpenBao
dropped, D744) and no cloud service is used (D746).

  eax secrets                         which passwords and keys there are, how old each is, which are due
  eax secrets rotate KEY              a new value now: a database login is changed in the database too, a Keycloak
                                      client's secret in Keycloak too; the services that use it are made again
  eax secrets rotate --all            every one eax can rotate, now, in one go (the Secrets tab's Rotate all)
  eax secrets rotate --due            every one that is due (the schedule runs this; every 90 days by default, R6-T1;
                                      a laptop only with EAX_ROTATE_ON_LAPTOP=on)
  eax secrets set KEY                 a value you type (after changing it where it is also kept, e.g. the mail server)
  eax secrets push --to file:<path>   a copy of them in a file outside the installation (readable by its owner only)
  eax secrets pull --from file:<path> the values back from such a file (a dated copy of the config file first)

Certificates (certificate mode, R6-C1) are `eax certs`.
"""

from __future__ import annotations

import os
import re
import secrets as _random
from datetime import datetime
from pathlib import Path

from .core import EAX, ENV_FILE, ENV_REL, ROOT, WORK, Failure, say

# a value made from another (the broker's URL-encoded password: the same, as generated values need no encoding)
DERIVED = {"EAX_DMS_BROKER_PASSWORD_URLENC": "EAX_DMS_BROKER_PASSWORD"}

# the database logins each password is (rotate changes it in the database too)
DB_LOGINS = {"EAX_DB_SUPERUSER_PASSWORD": "postgres", "EAX_DB_PASSWORD": "eax_app", "EAX_DB_REPORT_PASSWORD": "eax_report",
             "EAX_DB_MIGRATOR_PASSWORD": "eax_migrator", "EAX_KEYCLOAK_DB_PASSWORD": "keycloak",
             "EAX_SUPERSET_DB_PASSWORD": "superset", "EAX_MAYAN_DB_PASSWORD": "mayan", "EAX_LIBRARY_DB_PASSWORD": "eax_library",
             "EAX_VIEWS_DB_PASSWORD": "eax_views", "EAX_REPLICATION_PASSWORD": "eax_replicator",
             "EAX_CONSOLE_IT_PASSWORD": "eax_console_it", "EAX_CONSOLE_SUPER_PASSWORD": "eax_console_super"}
# in certificate mode (R6-C1) these logins sign in with their service's certificate, not their password
# (deploy/postgres/certificate/pg_ident.conf): the password is kept, and still rotated, so a switch back to passwords
# works at once; the superuser and the standby's replication login keep signing in with their passwords (owner, 22 Nov
# 2026, 20:43: "should we not only show what is relevent ... call out this is not applicable", D877)
NOT_USED_WITH_CERTIFICATES = {k for k, login in DB_LOGINS.items() if login not in ("postgres", "eax_replicator")}
# the Keycloak clients' secrets: changed in Keycloak through its admin API too
KEYCLOAK_CLIENTS = {"EAX_SUPERSET_OIDC_SECRET": "superset", "EAX_MAYAN_OIDC_SECRET": "mayan", "EAX_KC_SERVICE_SECRET": "eax-admin"}   # as deploy/keycloak/realm-eaexplorer.json.tmpl names them
# kept where they are used as well, or by people: not rotated by themselves; the admins are alerted when due (R6-R1)
NEEDS_A_PERSON = {
    "EAX_SUPERSET_SECRET_KEY": "Superset encrypts its database connections with it: changing it loses them",
    "EAX_KC_ADMIN_PASSWORD": "Keycloak keeps it in its database: change it in Keycloak's admin console, then eax secrets set",
    "EAX_FIRST_ADMIN_PASSWORD": "a person's own password: they change it when signing in",
    "EAX_BREAK_GLASS_PASSWORD": "people keep it offline: change it on the Break-glass page and store the new one",
    "EAX_SUPERSET_ADMIN_PASSWORD": "Superset keeps it: change it in Superset first, then eax secrets set",
    "EAX_MAYAN_ADMIN_PASSWORD": "Mayan keeps it: change it in Mayan first, then eax secrets set",
    "EAX_SMTP_PASSWORD": "the mail server's account: change it there, then eax secrets set",
    "EAX_TEST_USER_PASSWORD": "the test accounts' shared password, for the self-test only",
}


def generate(keys, keep: dict[str, str] | None = None) -> dict[str, str]:
    """A new random value for each key (letters and digits only, so no file, URL or shell ever needs it quoted); those
    in `keep` keep theirs; a derived value is its source's."""
    keep = keep or {}
    out = {k: keep[k] if k in keep else _random.token_hex(20) for k in keys if k not in DERIVED}
    for k, src in DERIVED.items():
        if k in keys:
            out[k] = keep.get(k) or out.get(src, "")
    return out


EXTERNAL_DB_WHY = ("the database is the customer's own server (R6.6.2): their DBA changes the login's password there, "
                   "then eax secrets set <key> puts the same in the config file")


def kind_of(key: str, external_db: bool | None = None) -> str:
    """How a secret is rotated: database, keycloak, person or here. With the customer's own database server (R6.6.2)
    the database logins' passwords are a person's (their DBA changes them on that server)."""
    if key in DB_LOGINS or key == "EAX_DB_SUPERUSER_PASSWORD":
        if external_db is None:
            try:
                from .core import setting
                external_db = bool(setting("EAX_EXTERNAL_DB_HOST", ""))
            except Exception:  # noqa: BLE001 - no config file here (the operations helper reads its own)
                external_db = bool(os.environ.get("EAX_EXTERNAL_DB_HOST"))
        if external_db:
            return "person"
    if key in DB_LOGINS:
        return "database"
    if key in KEYCLOAK_CLIENTS:
        return "keycloak"
    if key in NEEDS_A_PERSON:
        return "person"
    return "here"


def env_lines(values: dict[str, str]) -> str:
    """Settings as config-file lines."""
    return "".join(f"{k}={v}\n" for k, v in sorted(values.items()))


def replace_values(env_text: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """The config file with some values replaced; which were changed."""
    changed = []

    def sub(m: re.Match) -> str:
        k, v = m.group(1), m.group(2)
        if k in values and values[k] != v.strip("'\""):
            changed.append(k)
            return f"{k}={values[k]}"
        return m.group(0)
    return re.sub(r"^([A-Z0-9_]+)=(.*)$", sub, env_text, flags=re.MULTILINE), changed


def read_file(path: str, keys: list[str]) -> dict[str, str]:
    """The values kept in a file outside the installation (only the keys asked for)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise Failure(f"Could not read {path}: {exc} (it is readable by its owner only: sudo {EAX} secrets pull)") from exc
    out = {}
    for line in text.splitlines():
        k, _, v = line.partition("=")
        if k in keys:
            out[k] = v
    return out


def dated_copy(text: str) -> Path:
    """The config file kept as it was, before a change (work/config-history)."""
    history = WORK / "config-history"
    history.mkdir(parents=True, exist_ok=True)
    copy = history / f"eaexplorer.env.{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}.secrets"
    copy.write_text(text, encoding="utf-8", newline="\n")
    return copy


def _target(rest: list[str]) -> str:
    for flag in ("--to", "--from"):
        if flag in rest and rest.index(flag) + 1 < len(rest):
            return rest[rest.index(flag) + 1]
    return ""


def fill(env_file: Path | None = None, say_=None) -> list[str]:
    """Settings a newer release added (its template has them, the config file does not): added at the end of the config
    file before eax up starts anything, so an update needs no hand editing. A password or key a server lacks is made
    strong and random here; any other the template's value. Returns the names added (never the values)."""
    from .core import ROOT
    env_file = env_file or ENV_FILE
    text = env_file.read_text(encoding="utf-8")
    have = {m.group(1) for m in re.finditer(r"^([A-Z0-9_]+)=", text, re.MULTILINE)}
    kind = (re.search(r"^EAX_DEPLOYMENT=['\"]?([a-z]+)", text, re.MULTILINE) or [None, "laptop"])[1]
    template = ROOT / "deploy" / "templates" / f"eaexplorer.{kind}.env"
    if not template.exists():
        template = ROOT / "deploy" / "templates" / "eaexplorer.laptop.env"
    missing = [(m.group(1), m.group(2)) for m in re.finditer(r"^([A-Z0-9_]+)=(.*)$", template.read_text(encoding="utf-8"),
                                                            re.MULTILINE) if m.group(1) not in have]
    if not missing:
        return []
    made = generate([k for k, v in missing if v.startswith("change-me")])
    # an installation made before Release 6 signs in with passwords: it stays so until a person switches it
    # (eax certs switch certificate), however its template now starts new servers (R6-C1)
    made["EAX_AUTH_MODE"] = "password"
    lines = [f"{k}={made.get(k, v)}" for k, v in missing]
    dated_copy(text)
    env_file.write_text(text.rstrip("\n") + "\n\n# ---- Added by eax up: settings a newer release brought (passwords made here) ----\n"
                        + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if say_:
        say_(f"Added to {ENV_REL} from the newer release: {', '.join(k for k, _ in missing)}.")
    return [k for k, _ in missing]


def main(options: list[str]) -> int:
    """eax secrets [show|rotate KEY|rotate --due|rotate --all|set KEY|fill|push --to file:<path>|pull --from file:<path>]."""
    from .deploy import secret_values
    if not ENV_FILE.exists():
        raise Failure(f"No {ENV_REL} yet: run {EAX} init or {EAX} deploy first.")
    text = ENV_FILE.read_text(encoding="utf-8")
    values = secret_values(text)
    action = options[0] if options else "show"
    rest = options[1:]
    if action == "fill":                      # eax up runs this first (every form): a newer release's new settings
        fill(say_=say)
        return 0
    if action == "show":
        from . import secretsrot
        out = secretsrot.listing()
        say(f"The services sign in with {'certificates' if out['mode'] == 'certificate' else 'passwords'} "
            f"(EAX_AUTH_MODE); passwords rotate every {out['days']} days.")
        for s in out["secrets"]:
            due = "  DUE" if s["due"] else (f"  due in {s['days_left']} days" if s["warn"] else "")
            say(f"  {s['key']:<34} {s['kind']:<9} changed {s['changed'][:10] or 'not yet'}{due}"
                f"{'  (a person: ' + s['why'] + ')' if s['why'] and (s['due'] or s['warn']) else ''}"
                f"{'  (not used: its certificate signs in; kept for a switch back)' if s.get('not_used') else ''}")
        return 0
    if action == "schedule":           # Rotate all now, at a time, or regularly (D763)
        from . import secretsrot
        by = next((rest[i + 1] for i, a in enumerate(rest) if a == "--by" and i + 1 < len(rest)), "eax command")
        at = next((rest[i + 1] for i, a in enumerate(rest) if a == "--at" and i + 1 < len(rest)), "")
        what = "at" if at else next((a for a in rest if a in ("show", "monthly", "quarterly", "off")), "show")
        out = secretsrot.all_schedules() if what == "show" else secretsrot.schedule_all(what, by, at)
        r = out["regular"]
        say(f"Rotate all, regularly: {r['when'] + ' (next ' + str(r['next']).replace('T', ' ') + ')' if r else 'off'}.")
        for s in out["once"]:
            say(f"Rotate all, once: {str(s['next']).replace('T', ' ')} (eax schedule remove {s['id']} to cancel it).")
        return 0
    if action in ("rotate", "set"):
        from . import secretsrot
        flag = next((f for f in ("--all", "--due") if action == "rotate" and f in rest), "")
        what = flag or (rest[0] if rest else "")
        if not what:
            raise Failure(f"{EAX} secrets rotate KEY, {EAX} secrets rotate --due, {EAX} secrets rotate --all or {EAX} secrets set KEY")
        if what not in ("--due", "--all") and what not in values:
            raise Failure(f"{EAX} secrets {action} KEY: one of {', '.join(sorted(values))}")
        given = None
        if action == "set":
            import getpass
            given = getpass.getpass(f"New value for {what} (not shown): ").strip()
            if not given or "\n" in given:
                raise Failure("No value given: nothing changed.")
        by = next((rest[i + 1] for i, a in enumerate(rest) if a == "--by" and i + 1 < len(rest)), "eax command")
        out = secretsrot.rotate(what, by, given=given)
        if "--restart" in rest:          # Jenkins' Rotate all restarts EA Explorer afterwards (owner, 18 Nov 2026, 09:56)
            import subprocess
            import sys as _sys
            say("Restarting EA Explorer with the new values (eax restart).")
            code = subprocess.run([_sys.executable, str(ROOT / "eaxpy.py"), "restart"], cwd=ROOT, check=False).returncode
            if code:
                raise Failure(f"The values are rotated, but eax restart ended with {code}: run it again.")
        if out.get("skipped"):
            say(f"Nothing rotated: {out['skipped']}.")
        for r in out.get("person", []):
            say(f"  {r['key']} {'needs a person' if what == '--all' else 'is due and needs a person'}: {r['why']}", "yellow")
        if out.get("made_again"):
            say(f"Made again with the new values: {', '.join(out['made_again'])}.")
        elif action == "rotate" and not out.get("rotated"):
            say("Nothing was due.")
        return 0
    if action in ("push", "pull"):
        provider, _, name = _target(rest).partition(":")
        if provider != "file" or not name:
            raise Failure(f"{EAX} secrets {action} {'--to' if action == 'push' else '--from'} file:<path> "
                          "(a file outside the installation; no key vault or cloud service is used, D744, D746)")
        if action == "push":
            Path(name).parent.mkdir(parents=True, exist_ok=True)
            Path(name).write_text(env_lines(values), encoding="utf-8")
            Path(name).chmod(0o600)
            say(f"{len(values)} passwords and keys kept in {name} (readable by its owner only).")
            return 0
        got = read_file(name, list(values))
        if not got:
            raise Failure(f"Nothing found in {name}.")
        new, changed = replace_values(text, got)
        if not changed:
            say(f"{ENV_REL} already holds the file's values ({len(got)} checked).")
            return 0
        copy = dated_copy(text)
        ENV_FILE.write_text(new, encoding="utf-8", newline="\n")
        say(f"{len(changed)} values taken from {name} into {ENV_REL} (the old file: {copy}): {', '.join(changed)}")
        say(f"Restart to use them: {EAX} restart --reset-passwords sets the database's logins to them (R6-D1).")
        return 0
    raise Failure(f"{EAX} secrets [show|rotate KEY|rotate --due|rotate --all|set KEY|push --to file:<path>|pull --from file:<path>]")
