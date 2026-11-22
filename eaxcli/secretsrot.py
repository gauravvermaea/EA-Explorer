"""Rotating the passwords and keys (Release 6, R6-R1, R6-T1, D743 to D745).

Runs wherever eax runs with the installation's folder: on the machine itself (`eax secrets rotate`), or in the
Command centre's short-lived runner when the Secrets tab or the schedule asks (System admin > Secrets). Each rotation:

  1. a new value (eaxcli/secrets.generate), or the one a person gave (`eax secrets set`);
  2. where the value is also kept: a database login's password changed in the database (as postgres, inside the db
     container, never over the network), a Keycloak client's secret changed in Keycloak (kcadm.sh inside its
     container);
  3. the config file changed (a dated copy first, work/config-history);
  4. the services that use it made again (docker compose up --force-recreate --no-deps), so each gets the new file
     under /run/secrets (R6-F1): a few seconds each;
  5. its age noted in persist/secrets/state.json (never the value), which the Secrets tab and the alerts read.

What needs a person (NEEDS_A_PERSON: kept elsewhere or offline) is never rotated here: it is reported, and the admins
are alerted at 30, 14 and 7 days before it is due (R6-R1). Every 90 days by default (EAX_ROTATE_PASSWORD_DAYS).

One rotation at a time (the owner, 18 Nov 2026, 09:19: two Rotate now clicks six seconds apart made the same containers
again at once, Docker refused both half way ("No such container") and EA Explorer was left half made again, signed-in
people seeing no role): every rotation holds work/secrets-rotate.lock; a second one waits for it. Making the services
again is tried three times. `eax secrets rotate --all` (the Secrets tab's Rotate all, 09:19: "bring rotate all as a
capability. It rotates all the stuff") rotates every one eax can rotate in one go, with one making-again at the end."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import persist as P
from .core import ENV_FILE, ROOT, Failure, say
from .secrets import (
    DB_LOGINS,
    DERIVED,
    EXTERNAL_DB_WHY,
    KEYCLOAK_CLIENTS,
    NEEDS_A_PERSON,
    NOT_USED_WITH_CERTIFICATES,
    dated_copy,
    generate,
    kind_of,
)

DEFAULT_DAYS = 90
WARN_DAYS = (30, 14, 7)


# ---------------------------------------------------------------- the state: when each was last changed
def state_path() -> Path:
    """persist/secrets/state.json: survives resets (D558); only names and times, never a value."""
    return P.folder() / "secrets" / "state.json"


def read_state() -> dict:
    """When each secret was last changed, by whom and how (never a value)."""
    return P.read_json(state_path(), {})[0]


def note_changed(key: str, by: str, how: str, when: datetime | None = None) -> None:
    """Notes that a secret was changed (and its derived copy)."""
    state = read_state()
    at = (when or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for k in [key, *[d for d, src in DERIVED.items() if src == key]]:
        state[k] = {"changed": at, "by": by, "how": how}
    P.write_json(state_path(), state)


def _parse(at: str) -> datetime | None:
    try:
        return datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def rows(values: dict[str, str], state: dict, days: int = DEFAULT_DAYS, now: datetime | None = None,
         mode: str = "password") -> list[dict]:
    """Every secret by name, with how it is rotated, when it last changed, when it is next due and whether it is due
    or near (pure). A secret never changed through eax counts from the first time it was seen. In certificate mode a
    service login's password is marked not_used: its certificate signs it in (D877)."""
    now = now or datetime.now(UTC)
    certificate = mode == "certificate"
    out = []
    for key in sorted(values):
        if key in DERIVED:
            continue
        kind = kind_of(key)
        s = state.get(key) or {}
        changed = _parse(s.get("changed", ""))
        due_at = (changed + timedelta(days=days)) if changed else None
        left = (due_at - now).days if due_at else None
        out.append({"key": key, "kind": kind, "set": bool(values[key]), "changed": s.get("changed", ""),
                    "by": s.get("by", ""), "how": s.get("how", ""), "due_at": due_at.strftime("%Y-%m-%d") if due_at else "",
                    "days_left": left, "due": left is not None and left <= 0,
                    "warn": next((w for w in sorted(WARN_DAYS) if left is not None and 0 < left <= w), None),
                    "why": NEEDS_A_PERSON.get(key, "") or (EXTERNAL_DB_WHY if kind == "person" else ""),
                    "auto": kind != "person", "not_used": certificate and key in NOT_USED_WITH_CERTIFICATES})
    return out


def first_seen(values: dict[str, str]) -> int:
    """Secrets with no age yet get today's (the day eax first saw them), so the 90 days start now; returns how many."""
    state = read_state()
    n = 0
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    for k in values:
        if k not in state and k not in DERIVED:
            state[k] = {"changed": now, "by": "eax", "how": "first seen"}
            n += 1
    if n:
        P.write_json(state_path(), state)
    return n


# ---------------------------------------------------------------- which services use a secret
def users_of(key: str, compose_text: str | None = None) -> list[str]:
    """The services docker-compose.yml gives this secret to (R6-F1): made again after it changes (pure but for reading
    the compose file)."""
    text = compose_text if compose_text is not None else (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    out, service = [], None
    for line in text.splitlines():
        m = re.match(r"^  ([a-z][a-z0-9-]*):\s*$", line)
        if m:
            service = m.group(1)
        m = re.match(r"^    secrets: \[([^\]]*)\]", line)
        if m and service and key in [x.strip() for x in m.group(1).split(",")]:
            out.append(service)
    return out


# ---------------------------------------------------------------- the changes themselves
def _compose(args: list[str], stdin: str = "", check: bool = True) -> str:
    from .core import compose_args
    p = subprocess.run(compose_args(args), cwd=ROOT, input=stdin, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", check=False)
    if check and p.returncode != 0:
        raise Failure(f"docker compose {' '.join(args[:3])} failed: {(p.stderr or p.stdout).strip()[-400:]}")
    return p.stdout


def change_login(login: str, value: str) -> None:
    """ALTER ROLE inside the db container as postgres (its own socket: no password, nothing over the network); the
    statement on psql's input, never on a command line. A login this installation does not have (the standby's
    eax_replicator without a standby: the owner's Rotate all, 18 Nov 2026, 10:53) is left alone: its value is the one
    it will be made with."""
    quoted = value.replace("'", "''")
    _compose(["exec", "-T", "db", "psql", "-v", "ON_ERROR_STOP=1", "-q", "-U", "postgres", "-d", "postgres"],
             stdin=(f"DO $eaxrot$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{login}') THEN "
                    f"EXECUTE format('ALTER ROLE %I PASSWORD %L', '{login}', '{quoted}'); END IF; END $eaxrot$;\n"))


def change_client(client: str, value: str, values: dict[str, str]) -> None:
    """A Keycloak client's secret changed in Keycloak (kcadm.sh inside its container), before the config file."""
    realm = values.get("EAX_KEYCLOAK_REALM") or "eaexplorer"
    admin = values.get("EAX_KC_ADMIN") or "kcadmin"
    script = (f'set -e; K=/opt/keycloak/bin/kcadm.sh; '
              f'$K config credentials --server http://localhost:8080/auth --realm master --user "{admin}" '
              f'--password "$(cat /run/secrets/EAX_KC_ADMIN_PASSWORD)" >/dev/null; '
              f'ID=$($K get clients -r "{realm}" -q clientId="{client}" --fields id --format csv --noquotes); '
              f'test -n "$ID" || {{ echo "Keycloak has no client {client} in the realm {realm}" >&2; exit 1; }}; '
              f'$K update "clients/$ID" -r "{realm}" -s "secret=$(cat)"')
    _compose(["exec", "-T", "keycloak", "bash", "-c", script], stdin=value)


def write_value(key: str, value: str, why: str) -> None:
    """The config file with the new value (and its derived copy), a dated copy first."""
    from .secrets import replace_values
    text = ENV_FILE.read_text(encoding="utf-8")
    dated_copy(text)
    new = {key: value, **{d: value for d, src in DERIVED.items() if src == key}}
    out, _ = replace_values(text, new)
    for k, v in new.items():
        if not re.search(rf"^{k}=", out, re.MULTILINE):
            out = out.rstrip("\n") + f"\n{k}={v}\n"
    ENV_FILE.write_text(out, encoding="utf-8", newline="\n")


# run once at a start, never made again by a rotation: making setup again ran it again, it failed, and the API, the
# library and the views waited on it ("interrupted by the unmet condition service_completed_successfully of service
# setup": the owner's Rotate all, 18 Nov 2026, 10:53); what they set up reads the new values at the next start
ONE_SHOT = {"setup", "reports-init", "testrunner", "testrunner-service"}


def recreate(services: list[str], tries: int = 3, sleep=time.sleep) -> None:
    """The services made again, so each reads the new secret file (only those, no others; never the ones that run once
    at a start); tried three times (Docker can refuse half way while it still tidies an earlier change)."""
    services = [s for s in services if s not in ONE_SHOT]
    if not services:
        return
    for n in range(1, tries + 1):
        try:
            _compose(["up", "-d", "--no-deps", "--force-recreate", *sorted(set(services))])
            return
        except Failure as exc:
            if n == tries:
                raise Failure(f"{exc}. The new values are saved; make the services again with: eax restart") from exc
            say(f"  making the services again failed (try {n} of {tries}); trying again in 10 seconds", "yellow")
            sleep(10)


LOCK_WAIT = 30 * 60


def lock_path() -> Path:
    """The lock file one rotation holds while it runs: work/secrets-rotate.lock, beside the config file."""
    return ENV_FILE.parent / "secrets-rotate.lock"


class rotation_lock:  # noqa: N801 - used as `with rotation_lock():`
    """One rotation at a time on this installation (see the module): the lock file made exclusively; a second rotation
    waits up to half an hour; a lock left by a run that ended without removing it (older than two hours) is taken over."""

    def __init__(self, wait: int = LOCK_WAIT, sleep=time.sleep, stale: int = 2 * 3600):
        self.wait, self.sleep, self.stale = wait, sleep, stale

    def __enter__(self):
        path, end, said = lock_path(), time.time() + self.wait, False
        while True:
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {datetime.now(UTC).isoformat()}".encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - path.stat().st_mtime > self.stale:
                        path.unlink()
                        continue
                except OSError:
                    continue
                if time.time() >= end:
                    raise Failure("Another rotation is still running: try again when it has finished "
                                  f"(or remove {path} if none is)") from None
                if not said:
                    say("  another rotation is running: waiting for it to finish")
                    said = True
                self.sleep(5)

    def __exit__(self, *exc):
        try:
            lock_path().unlink()
        except OSError:
            pass
        return False


def rotate_one(key: str, values: dict[str, str], by: str, value: str | None = None, restart: bool = True) -> list[str]:
    """One secret changed everywhere it is kept; the services made again. Returns the services made again."""
    kind = kind_of(key)
    if value is None and kind == "person":
        raise Failure(f"{key} is not rotated by eax: {NEEDS_A_PERSON.get(key) or EXTERNAL_DB_WHY}")
    new = value if value is not None else generate([key])[key]
    if key in DB_LOGINS:
        change_login(DB_LOGINS[key], new)
    elif key in KEYCLOAK_CLIENTS:
        change_client(KEYCLOAK_CLIENTS[key], new, values)
    write_value(key, new, "rotate" if value is None else "set")
    note_changed(key, by, "rotated" if value is None else "set by a person")
    services = [s for k in [key, *[d for d, src in DERIVED.items() if src == key]] for s in users_of(k)]
    if key == "EAX_KEYCLOAK_DB_PASSWORD":
        services.append("keycloak")
    if restart:
        recreate(services)
    return sorted(set(services))


def rotate(what: str, by: str, days: int | None = None, given: str | None = None, ops=None, api=None) -> dict:
    """`eax secrets rotate KEY|--due|--all` and `eax secrets set KEY`: what was changed, what needs a person. One at a
    time (rotation_lock). --all behind the maintenance page, once the background has finished (quiet_for_all)."""
    with rotation_lock():
        if what != "--all":
            return _rotate(what, by, days, given)
        with quiet_for_all(ops, api):
            return _rotate(what, by, days, given)


class quiet_for_all:  # noqa: N801 - used as `with quiet_for_all():`
    """Rotate all behind the maintenance page, as a backup is taken (the owner, 18 Nov 2026, 09:56: "Rotate all puts up
    mantiance page, waits for jobs to be be finished and then does it"): the page on and the background paused, then
    waited for until it has finished what it was doing (at most half an hour; otherwise nothing is rotated); afterwards
    the page off and the background back, whatever happened."""

    def __init__(self, ops=None, api=None):
        from . import drill as D
        self.ops = ops or (lambda *a: D._ops(*a))
        self.api = api or (lambda cmd: D._api(cmd, {}))

    def __enter__(self):
        say("  the maintenance page on and the background paused")
        out = self.ops("quiet", "on")
        if out.get("error"):
            raise Failure(f"the maintenance page could not be put up: {out['error']}. Nothing was rotated.")
        _flags_say(WHAT_ALL)
        say("  waiting for the background to finish what it is doing")
        idle = self.api("idle")
        if idle.get("error") or not idle.get("idle", True):
            self.__exit__(None, None, None)
            raise Failure(f"{idle.get('error') or 'the background did not finish'}. Nothing was rotated.")
        return self

    def __exit__(self, *exc):
        out = self.ops("quiet", "off")
        left = _flags_off()   # taken down here too: the operations helper may itself have just been made again
        say("  the background back and the maintenance page off" if not left
            else f"  the maintenance page could not be taken down ({out.get('error') or ', '.join(left)}): eax maintenance clear",
            "yellow")
        return False


WHAT_ALL = "Every password and key is being rotated: EA Explorer is back in a few minutes."


def _flags() -> list:
    return [ENV_FILE.parent / "quiet.json", ENV_FILE.parent / "proxy" / "maintenance"]


def _flags_say(what: str) -> None:
    """The maintenance page and the paused background say what is going on (not "Backup and restore test")."""
    q, page = _flags()
    try:
        if q.exists():
            q.write_text(json.dumps({"since": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "by": "eax secrets rotate --all",
                                     "what": what}), encoding="utf-8")
        if page.exists():
            page.write_text(what, encoding="utf-8")
    except OSError:
        pass


def _flags_off() -> list[str]:
    """The maintenance page's and the pause's files removed if still there; what could not be."""
    left = []
    for f in _flags():
        try:
            f.unlink(missing_ok=True)
        except OSError:
            left.append(f.name)
    return left


def _rotate(what: str, by: str, days: int | None = None, given: str | None = None) -> dict:
    from .deploy import secret_values
    values = {**_config_values(), **secret_values(ENV_FILE.read_text(encoding="utf-8"))}
    secrets_ = secret_values(ENV_FILE.read_text(encoding="utf-8"))
    days = days or int(values.get("EAX_ROTATE_PASSWORD_DAYS") or DEFAULT_DAYS)
    if values.get("EAX_DEPLOYMENT", "laptop") == "laptop" and what == "--due" and values.get("EAX_ROTATE_ON_LAPTOP", "") != "on":
        return {"rotated": [], "person": [], "skipped": "a laptop keeps its passwords unless EAX_ROTATE_ON_LAPTOP=on"}
    first_seen(secrets_)
    if what == "--all":     # every one eax can rotate; what needs a person listed, never changed here
        every = [r for r in rows(secrets_, read_state(), days) if r["set"]]
        keys = [r["key"] for r in every if r["auto"]]
        person = [{"key": r["key"], "why": r["why"]} for r in every if not r["auto"]]
    elif what == "--due":
        due = [r for r in rows(secrets_, read_state(), days) if r["due"] and r["set"]]
        keys = [r["key"] for r in due if r["auto"]]
        person = [{"key": r["key"], "why": r["why"]} for r in due if not r["auto"]]
    else:
        keys, person = [what], []
    # one that fails never leaves the others half done (the owner's Rotate all, 18 Nov 2026, 09:40: eight database
    # passwords changed, then a Keycloak client failed and nothing was made again: EA Explorer could not reach its
    # databases): the rest carry on, and the services of every one changed are always made again at the end
    done, failed, services = [], [], set()
    try:
        for k in keys:
            try:
                services |= set(rotate_one(k, values, by, value=given, restart=False))
                done.append(k)
                say(f"  {k} changed")
            except Failure as exc:
                failed.append(f"{k}: {exc}")
                say(f"  {k} NOT changed (it keeps its value): {exc}", "red")
    finally:
        recreate(sorted(services))
    if failed:
        raise Failure(f"{len(done)} changed and their services made again; {len(failed)} not changed (they keep their "
                      f"values): " + "; ".join(failed))
    return {"rotated": done, "person": person, "made_again": sorted(s for s in services if s not in ONE_SHOT)}


def _config_values() -> dict[str, str]:
    out = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip("'\"")
    return out


def listing() -> dict:
    """What the Secrets tab and `eax secrets` show: every secret by name, never a value."""
    from .deploy import secret_values
    values = secret_values(ENV_FILE.read_text(encoding="utf-8"))
    cfg = _config_values()
    first_seen(values)
    days = int(cfg.get("EAX_ROTATE_PASSWORD_DAYS") or DEFAULT_DAYS)
    mode = cfg.get("EAX_AUTH_MODE", "password")
    return {"mode": mode, "days": days, "secrets": rows(values, read_state(), days, mode=mode)}


def main_json(argv: list[str]) -> int:
    """For the Command centre runner and the operations helper: one JSON line."""
    try:
        if argv[:1] == ["list"]:
            out = listing()
        else:
            out = {"error": "secretsrot list"}
    except (Failure, OSError, ValueError) as exc:
        out = {"error": str(exc)[:500]}
    print(json.dumps(out), flush=True)
    return 1 if out.get("error") else 0


# ---------------------------------------------------------------- Rotate all on a schedule (D763)
# The owner, 18 Nov 2026, 10:07: "make a scheduled rotate both in jenkins and in the app"; 10:11: "There should be a
# schedule + on demand schedule. So someone can say Restart now or Restart at 5 PM on xyz date and then there is a
# regular schedule like you said monthly or every 90 days". Now: Rotate all (the Secrets tab, Jenkins). At a date and
# time: a one-off schedule. Regularly: one schedule, monthly or every three months (about 90 days), or off. All are the
# Command centre's schedules (persist/schedules.json), so the app and Jenkins share them and nothing runs twice.
ALL_ARGV = ["secrets", "rotate", "--all"]
REGULAR_ID = "r6rotateall"
EVERY = {"monthly": ("30 3 1 * *", "Rotate all passwords and keys, monthly (1st, 03:30)"),
         "quarterly": ("30 3 1 1,4,7,10 *", "Rotate all passwords and keys, every three months (1st, 03:30)")}


def all_schedules(root=None) -> dict:
    """Rotate all's schedules: the regular one (or none) and the one-off ones still to come."""
    from . import schedules as SC
    items = SC.listing(root)["schedules"]
    mine = [s for s in items if s.get("argv") == ALL_ARGV]
    regular = next((s for s in mine if s.get("id") == REGULAR_ID), None)
    once = [s for s in mine if s.get("once_at") and s.get("next")]
    return {"regular": regular if regular and regular.get("enabled") else None, "once": once}


def schedule_all(what: str, by: str, at: str = "", root=None) -> dict:
    """monthly | quarterly | off: the regular one; at: a one-off at YYYY-MM-DDTHH:MM (the installation's time zone)."""
    from . import schedules as SC
    items, _ = SC.load(root)
    now = datetime.now(SC.zone(root)).isoformat(timespec="seconds")
    base = {"argv": ALL_ARGV, "created_by": by, "created_at": now, "checked": now, "wipe": False, "backup_first": False,
            "keep": 3, "banner": False, "confirmed": None, "last": {}}
    if what in EVERY or what == "off":
        items = [x for x in items if x.get("id") != REGULAR_ID]
        if what != "off":
            cron, name = EVERY[what]
            items.append({**base, "id": REGULAR_ID, "name": name, "cron": cron, "enabled": True, "system": True})
        SC.save(items, root)
        return all_schedules(root)
    if what == "at":
        when = SC.preset("once", at=at)
        if datetime.fromisoformat(when["once_at"]).replace(tzinfo=SC.zone(root)) <= datetime.now(SC.zone(root)):
            raise Failure("That time has passed: give a time to come (YYYY-MM-DDTHH:MM).")
        sid = f"{REGULAR_ID}-{secrets_hex()}"
        items.append({**base, "id": sid, "name": f"Rotate all passwords and keys at {when['once_at'].replace('T', ' ')}",
                      **when, "enabled": True})
        SC.save(items, root)
        return all_schedules(root)
    raise Failure("eax secrets schedule monthly | quarterly | off | --at YYYY-MM-DDTHH:MM")


def secrets_hex() -> str:
    """A short random id for a one-off schedule."""
    import secrets as _s
    return _s.token_hex(3)
