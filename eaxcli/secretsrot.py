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
are alerted at 30, 14 and 7 days before it is due (R6-R1). Every 90 days by default (EAX_ROTATE_PASSWORD_DAYS)."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import persist as P
from .core import ENV_FILE, ROOT, Failure, say
from .secrets import (
    DB_LOGINS,
    DERIVED,
    KEYCLOAK_CLIENTS,
    NEEDS_A_PERSON,
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


def rows(values: dict[str, str], state: dict, days: int = DEFAULT_DAYS, now: datetime | None = None) -> list[dict]:
    """Every secret by name, with how it is rotated, when it last changed, when it is next due and whether it is due
    or near (pure). A secret never changed through eax counts from the first time it was seen."""
    now = now or datetime.now(UTC)
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
                    "why": NEEDS_A_PERSON.get(key, ""), "auto": kind != "person"})
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
    statement on psql's input, never on a command line."""
    quoted = value.replace("'", "''")
    _compose(["exec", "-T", "db", "psql", "-v", "ON_ERROR_STOP=1", "-q", "-U", "postgres", "-d", "postgres"],
             stdin=f'ALTER ROLE "{login}" PASSWORD \'{quoted}\';\n')


def change_client(client: str, value: str, values: dict[str, str]) -> None:
    """A Keycloak client's secret changed in Keycloak (kcadm.sh inside its container), before the config file."""
    realm = values.get("EAX_KEYCLOAK_REALM") or "eaexplorer"
    admin = values.get("EAX_KC_ADMIN") or "kcadmin"
    script = (f'set -e; K=/opt/keycloak/bin/kcadm.sh; '
              f'$K config credentials --server http://localhost:8080/auth --realm master --user "{admin}" '
              f'--password "$(cat /run/secrets/EAX_KC_ADMIN_PASSWORD)" >/dev/null; '
              f'ID=$($K get clients -r "{realm}" -q clientId="{client}" --fields id --format csv --noquotes); '
              f'test -n "$ID"; $K update "clients/$ID" -r "{realm}" -s "secret=$(cat)"')
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


def recreate(services: list[str]) -> None:
    """The services made again, so each reads the new secret file (only those, no others)."""
    if services:
        _compose(["up", "-d", "--no-deps", "--force-recreate", *sorted(set(services))])


def rotate_one(key: str, values: dict[str, str], by: str, value: str | None = None, restart: bool = True) -> list[str]:
    """One secret changed everywhere it is kept; the services made again. Returns the services made again."""
    kind = kind_of(key)
    if value is None and kind == "person":
        raise Failure(f"{key} is not rotated by eax: {NEEDS_A_PERSON[key]}")
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


def rotate(what: str, by: str, days: int | None = None, given: str | None = None) -> dict:
    """`eax secrets rotate KEY|--due` and `eax secrets set KEY`: what was changed, what needs a person."""
    from .deploy import secret_values
    values = {**_config_values(), **secret_values(ENV_FILE.read_text(encoding="utf-8"))}
    secrets_ = secret_values(ENV_FILE.read_text(encoding="utf-8"))
    days = days or int(values.get("EAX_ROTATE_PASSWORD_DAYS") or DEFAULT_DAYS)
    if values.get("EAX_DEPLOYMENT", "laptop") == "laptop" and what == "--due" and values.get("EAX_ROTATE_ON_LAPTOP", "") != "on":
        return {"rotated": [], "person": [], "skipped": "a laptop keeps its passwords unless EAX_ROTATE_ON_LAPTOP=on"}
    first_seen(secrets_)
    if what == "--due":
        due = [r for r in rows(secrets_, read_state(), days) if r["due"] and r["set"]]
        keys = [r["key"] for r in due if r["auto"]]
        person = [{"key": r["key"], "why": r["why"]} for r in due if not r["auto"]]
    else:
        keys, person = [what], []
    done, services = [], set()
    for k in keys:
        services |= set(rotate_one(k, values, by, value=given, restart=False))
        done.append(k)
        say(f"  {k} changed")
    recreate(sorted(services))
    return {"rotated": done, "person": person, "made_again": sorted(services)}


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
    return {"mode": cfg.get("EAX_AUTH_MODE", "password"), "days": days, "secrets": rows(values, read_state(), days)}


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
