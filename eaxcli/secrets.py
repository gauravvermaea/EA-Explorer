"""Passwords from a key vault (phase 36, D504).

The passwords and keys of an installation (every value the server template holds as change-me) can be kept in a
key vault as well as in work/eaexplorer.env:
  file:<path>      a file outside the installation (e.g. /etc/eaexplorer/secrets.env), readable by its owner only;
                   on DigitalOcean the same, on the Droplet
  aws:<name>       AWS Secrets Manager: one secret holding them all as JSON
  azure:<vault>    Azure Key Vault: one secret per value (EAX_DB_PASSWORD -> eax-db-password)
The config file says where (EAX_SECRETS_FROM). Docker Compose still reads the values from the config file when it
starts, so the vault is the copy to keep and to restore from:
  eax secrets              where they are kept, and which values
  eax secrets push [--to provider:name]   the config file's values into the vault (eax deploy does this once)
  eax secrets pull [--from provider:name] the vault's values into the config file (a dated copy of it first,
                                          in work/config-history), e.g. after rebuilding a server or rotating a password

OpenBao (R4.19, D684): `openbao:eax/eaexplorer` is the vault EA Explorer runs itself (eax init sets it up; the
config file then holds references, KEY=openbao:KEY, and eax reads the values at each start, eaxcli/vault.py):
  eax secrets                     the vault's state (unsealed, audit log), which values it holds
  eax secrets get KEY             one value, on the screen only (e.g. EAX_FIRST_ADMIN_PASSWORD on a server)
  eax secrets migrate             the config file's values into OpenBao, references left in their place (= push --to openbao)
  eax secrets pull                the values back into the config file in clear (OpenBao no longer used)
  eax secrets rotate KEY          a new value: a database login is changed in the database too; then eax up
  eax secrets set KEY             a value you type (e.g. after changing it in Keycloak's admin console); then eax up
  eax secrets new                 a new value for each reference the vault has none for
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import vault
from .core import EAX, ENV_FILE, ENV_REL, WORK, Failure, say

PROVIDERS = ("file", "aws", "azure", "digitalocean", "openbao")


def kv_name(key: str) -> str:
    """Azure Key Vault names allow letters, digits and dashes."""
    return key.lower().replace("_", "-")


def env_lines(values: dict[str, str]) -> str:
    """Settings as config-file lines."""
    return "".join(f"{k}={v}\n" for k, v in sorted(values.items()))


def push_commands(provider: str, name: str, values: dict[str, str], answers: dict | None = None) -> list[tuple]:
    """What eax deploy runs to keep the values in the vault: ("remote", script, what, stdin) on the server,
    ("local", argv, what[, ok codes]) here, ("file", path, body) a temporary file here, ("delete", path)."""
    answers = answers or {}
    body = env_lines(values)
    if provider in ("file", "digitalocean"):
        folder = str(Path(name).parent).replace("\\", "/")
        return [("remote", f"sudo mkdir -p {shlex.quote(folder)} && sudo install -m 600 /dev/stdin {shlex.quote(name)}",
                 f"the passwords into {name}, readable by root only", body)]
    tmp = str(WORK / "deploy" / "vault.json")
    if provider == "aws":
        region = ["--region", answers["aws_region"]] if answers.get("aws_region") else []
        profile = ["--profile", answers["aws_profile"]] if answers.get("aws_profile") else []
        return [("file", tmp, json.dumps(values, indent=1)),
                ("local", ["aws", *region, *profile, "secretsmanager", "create-secret", "--name", name,
                           "--description", "EA Explorer passwords (eax secrets)", "--secret-string", f"file://{tmp}"],
                 f"the passwords as one secret, {name}", [0, 254, 255]),
                ("local", ["aws", *region, *profile, "secretsmanager", "put-secret-value", "--secret-id", name,
                           "--secret-string", f"file://{tmp}"], "its value (when it existed already)"),
                ("delete", tmp)]
    if provider == "azure":
        out: list[tuple] = []
        if answers.get("az_group") and answers.get("az_location"):
            out.append(("local", ["az", "keyvault", "create", "--name", name, "--resource-group", answers["az_group"],
                                  "--location", answers["az_location"], "--enable-rbac-authorization", "false"],
                        f"the Key Vault {name} (kept if it exists)", [0, 1]))
        for key, value in sorted(values.items()):
            out.append(("file", tmp, value))
            out.append(("local", ["az", "keyvault", "secret", "set", "--vault-name", name, "--name", kv_name(key),
                                  "--file", tmp, "--output", "none"], key))
        out.append(("delete", tmp))
        return out
    raise Failure(f"Unknown key vault {provider!r}: one of {', '.join(PROVIDERS)}")


def _cli(argv: list[str]) -> str:
    exe = shutil.which(argv[0])
    if not exe:
        raise Failure(f"The {argv[0]} command is not installed here.")
    p = subprocess.run([exe, *argv[1:]], capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise Failure(f"{argv[0]} failed: {(p.stderr or p.stdout).strip()[-500:]}")
    return p.stdout


def fetch(provider: str, name: str, keys: list[str]) -> dict[str, str]:
    """The values kept in the vault (only the keys asked for)."""
    if provider in ("file", "digitalocean"):
        try:
            text = Path(name).read_text(encoding="utf-8")
        except OSError as exc:
            raise Failure(f"Could not read {name}: {exc} (it is readable by root only: sudo {EAX} secrets pull)") from exc
        out = {}
        for line in text.splitlines():
            k, _, v = line.partition("=")
            if k in keys:
                out[k] = v
        return out
    if provider == "aws":
        data = json.loads(_cli(["aws", "secretsmanager", "get-secret-value", "--secret-id", name,
                                "--query", "SecretString", "--output", "text"]))
        return {k: str(v) for k, v in data.items() if k in keys}
    if provider == "azure":
        out = {}
        for key in keys:
            try:
                out[key] = _cli(["az", "keyvault", "secret", "show", "--vault-name", name, "--name", kv_name(key),
                                 "--query", "value", "--output", "tsv"]).strip()
            except Failure:
                pass
        return out
    raise Failure(f"Unknown key vault {provider!r}: one of {', '.join(PROVIDERS)}")


def where(env_text: str) -> tuple[str, str]:
    """Where the secrets come from (EAX_SECRETS_FROM)."""
    m = re.search(r"^EAX_SECRETS_FROM=['\"]?([a-z]+):([^'\"\n]+)", env_text, re.MULTILINE)
    return (m.group(1), m.group(2).strip()) if m else ("", "")


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


def main(options: list[str]) -> int:
    """eax secrets: the passwords and keys (show, rotate, the vault's when it is used)."""
    from .deploy import secret_values
    if not ENV_FILE.exists():
        raise Failure(f"No {ENV_REL} yet: run {EAX} init or {EAX} deploy first.")
    text = ENV_FILE.read_text(encoding="utf-8")
    values = secret_values(text)
    action = options[0] if options else "show"
    rest = options[1:]
    target = ""
    for flag in ("--to", "--from"):
        if flag in rest and rest.index(flag) + 1 < len(rest):
            target = rest[rest.index(flag) + 1]
    if action == "migrate":
        action, target = "push", target or f"openbao:{vault.DEFAULT_WHERE}"
    provider, name = (target.split(":", 1) + [""])[:2] if target else where(text)
    if provider == "openbao" or (not target and vault.where(text) is not None):
        return openbao(action, rest, text, name or vault.where(text) or vault.DEFAULT_WHERE, values)
    if action == "show":
        if provider:
            say(f"The passwords are kept in: {provider}:{name} (EAX_SECRETS_FROM in {ENV_REL})")
        else:
            say(f"No key vault is set: the passwords are only in {ENV_REL}. {EAX} secrets push --to file:/etc/eaexplorer/secrets.env "
                "(or aws:<secret name>, azure:<vault name>) keeps them in one.")
        say(f"{len(values)} passwords and keys: {', '.join(sorted(values))}")
        return 0
    if not provider:
        raise Failure(f"Where? --to (or --from) file:<path>, aws:<secret name> or azure:<vault name>, or set EAX_SECRETS_FROM in {ENV_REL}.")
    if provider not in PROVIDERS:
        raise Failure(f"Unknown key vault {provider!r}: one of {', '.join(PROVIDERS)}")
    if action == "push":
        for step in push_commands(provider, name, values):
            kind = step[0]
            if kind == "remote":         # on this machine (eax secrets runs on the installation itself)
                Path(name).parent.mkdir(parents=True, exist_ok=True)
                Path(name).write_text(step[3], encoding="utf-8")
                Path(name).chmod(0o600)
            elif kind == "file":
                Path(step[1]).parent.mkdir(parents=True, exist_ok=True)
                Path(step[1]).write_text(step[2], encoding="utf-8")
                Path(step[1]).chmod(0o600)
            elif kind == "delete":
                Path(step[1]).unlink(missing_ok=True)
            else:
                ok = step[3] if len(step) > 3 else [0]
                exe = shutil.which(step[1][0])
                if not exe:
                    raise Failure(f"The {step[1][0]} command is not installed here.")
                code = subprocess.run([exe, *step[1][1:]], capture_output=True, text=True, check=False).returncode
                if code not in ok:
                    raise Failure(f"{step[1][0]} failed (exit {code}) while keeping {step[2]}")
        if not where(text)[0]:
            ENV_FILE.write_text(text.rstrip("\n") + f"\nEAX_SECRETS_FROM={provider}:{name}\n", encoding="utf-8", newline="\n")
        say(f"{len(values)} passwords and keys kept in {provider}:{name}.")
        return 0
    if action == "pull":
        got = fetch(provider, name, list(values))
        if not got:
            raise Failure(f"Nothing found in {provider}:{name}.")
        new, changed = replace_values(text, got)
        if not changed:
            say(f"{ENV_REL} already holds the vault's values ({len(got)} checked).")
            return 0
        history = WORK / "config-history"
        history.mkdir(parents=True, exist_ok=True)
        copy = history / f"eaexplorer.env.{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}"
        copy.write_text(text, encoding="utf-8", newline="\n")
        ENV_FILE.write_text(new, encoding="utf-8", newline="\n")
        say(f"{len(changed)} values taken from {provider}:{name} into {ENV_REL} (the old file: {copy}): {', '.join(changed)}")
        say(f"Restart to use them: {EAX} restart. A database password changed here must match the database's own login.")
        return 0
    raise Failure(f"{EAX} secrets [show|push|pull] [--to|--from provider:name]")


# ---------------------------------------------------------------- OpenBao (R4.19, D684)
# the database logins each password is (rotate changes it in the database too)
DB_LOGINS = {"EAX_DB_SUPERUSER_PASSWORD": "postgres", "EAX_DB_PASSWORD": "eax_app", "EAX_DB_REPORT_PASSWORD": "eax_report",
             "EAX_DB_MIGRATOR_PASSWORD": "eax_migrator", "EAX_KEYCLOAK_DB_PASSWORD": "keycloak",
             "EAX_SUPERSET_DB_PASSWORD": "superset", "EAX_MAYAN_DB_PASSWORD": "mayan", "EAX_LIBRARY_DB_PASSWORD": "eax_library",
             "EAX_VIEWS_DB_PASSWORD": "eax_views"}
# changed only here: each container takes the new value when eax up makes it again
JUST_HERE = {"EAX_OPS_TOKEN", "EAX_LIBRARY_KEY", "EAX_VIEWS_KEY", "EAX_DMS_BROKER_PASSWORD", "EAX_DMS_BROKER_PASSWORD_URLENC"}
# kept where they are used as well (Keycloak's realm, Superset's encrypted settings): changed there first, then `set`
ELSEWHERE = {"EAX_SUPERSET_SECRET_KEY": "Superset encrypts its database connections with it: changing it loses them",
             "EAX_KC_ADMIN_PASSWORD": "Keycloak keeps it in its database: change it in Keycloak's admin console first",
             "EAX_FIRST_ADMIN_PASSWORD": "Keycloak keeps it: the person changes it when signing in",
             "EAX_SUPERSET_OIDC_SECRET": "the Keycloak client keeps it: change it there first",
             "EAX_MAYAN_OIDC_SECRET": "the Keycloak client keeps it: change it there first",
             "EAX_KC_SERVICE_SECRET": "the Keycloak client keeps it: change it there first",
             "EAX_BREAK_GLASS_PASSWORD": "kept as its hash at the first start: change it on the Break-glass page",
             "EAX_SUPERSET_ADMIN_PASSWORD": "Superset keeps it: change it in Superset first",
             "EAX_MAYAN_ADMIN_PASSWORD": "Mayan keeps it: change it in Mayan first"}


def _client(text: str, where_: str):
    from .core import vault_keys_file, vault_log_tail, vault_profile, vault_start
    vault_profile()
    try:
        return vault.ready(vault_keys_file(), vault.url_for(text), where_, vault_start, say)
    except vault.VaultError as exc:
        raise Failure(f"The key vault: {exc}{vault_log_tail()}") from exc


def _dated_copy(text: str) -> Path:
    history = WORK / "config-history"
    history.mkdir(parents=True, exist_ok=True)
    copy = history / f"eaexplorer.env.{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}.secrets"
    copy.write_text(text, encoding="utf-8", newline="\n")
    return copy


def _set_from(text: str, where_: str | None) -> str:
    """EAX_SECRETS_FROM set to the vault (or taken out, where_ None)."""
    text = re.sub(r"^EAX_SECRETS_FROM=.*\n?", "", text, flags=re.MULTILINE)
    if where_ is None:
        return text
    return text.rstrip("\n") + f"\nEAX_SECRETS_FROM=openbao:{where_}\n"


def _rotate_login(login: str, value: str) -> None:
    """ALTER ROLE in the database, the statement on psql's input (never on a command line)."""
    from .core import _compose_base
    quoted = value.replace("'", "''")
    p = subprocess.run(_compose_base(["exec", "-T", "db", "psql", "-v", "ON_ERROR_STOP=1", "-q", "-U", "postgres", "-d", "postgres"]),
                       input=f"ALTER ROLE \"{login}\" PASSWORD '{quoted}';\n", capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise Failure(f"The database did not take the new password for {login}: {(p.stderr or p.stdout).strip()[-300:]} "
                      "(is the database running? eax up db)")


def openbao(action: str, rest: list[str], text: str, where_: str, values: dict[str, str]) -> int:
    """The key vault's actions (switched off until the owner says)."""
    refs = vault.references(text)
    if not vault.ALLOWED and action not in ("pull", "show", "get", "env"):
        raise Failure(vault.OFF)
    if action == "env":                 # for eax.sh and eax.ps1: KEY=VALUE lines on standard output only, never logged
        import contextlib
        import os
        import sys

        from .core import vault_env
        if refs:
            out = sys.stdout
            with contextlib.redirect_stdout(sys.stderr):        # what it says while starting goes to the screen only
                vault_env()
            out.write(vault.env_lines({k: os.environ.get(k, "") for k in refs}))
        return 0
    if action == "get":                 # one value, to the screen only (a server's first sign-in): never logged
        import sys
        if not rest or rest[0] not in refs:
            raise Failure(f"{EAX} secrets get KEY: one of {', '.join(sorted(refs)) or '(none: no references yet)'}")
        held = _client(text, where_).read(where_)
        if refs[rest[0]] not in held:
            raise Failure(f"The vault holds no value for {rest[0]}: {EAX} up makes them the first time.")
        sys.stdout.write(held[refs[rest[0]]] + "\n")
        return 0
    if action == "show":
        c = _client(text, where_)
        held = c.read(where_)
        say(f"The passwords are kept in OpenBao ({where_}), unsealed; its audit log is {'on' if c.audited else 'OFF'}.")
        say(f"{len(refs)} references in {ENV_REL}; {len(held)} values in the vault.")
        missing = sorted(k for k, n in refs.items() if n not in held)
        clear = sorted(k for k in values if k not in refs)
        if missing:
            say(f"No value in the vault for: {', '.join(missing)} ({EAX} secrets new makes them).", "yellow")
        if clear:
            say(f"Still in {ENV_REL} in clear: {', '.join(clear)} ({EAX} secrets migrate moves them).", "yellow")
        say(f"Its keys: {vault.KEYS_REL} (readable by you only; in every infrastructure backup).")
        return 0
    if action == "push":                # the config file's values into the vault, references in their place
        clear = {k: v for k, v in values.items() if not vault.is_reference(v)}
        c = _client(text, where_)
        held = c.read(where_)
        merged = {**held, **clear}
        c.write(where_, merged)
        copy = _dated_copy(text)
        new = _set_from(vault.with_references(text, set(clear) | set(refs)), where_)
        ENV_FILE.write_text(new, encoding="utf-8", newline="\n")
        say(f"{len(clear)} passwords and keys moved into OpenBao ({where_}); {ENV_REL} holds references now "
            f"(the old file: {copy}).")
        say(f"Nothing changes for the containers: {EAX} up reads the same values from the vault.")
        return 0
    if action == "pull":                # back into the config file in clear; OpenBao no longer used
        c = _client(text, where_)
        got = vault.resolve(text, c, where_)
        copy = _dated_copy(text)
        new, changed = replace_values(text, got)
        ENV_FILE.write_text(_set_from(new, None), encoding="utf-8", newline="\n")
        say(f"{len(changed)} values taken from OpenBao into {ENV_REL} in clear (the old file: {copy}); OpenBao is no longer "
            f"used (its data stays in its volume). {EAX} secrets migrate moves them back.")
        return 0
    if action in ("rotate", "set"):
        if not rest or rest[0] not in refs:
            raise Failure(f"{EAX} secrets {action} KEY: one of {', '.join(sorted(refs)) or '(none: no references yet)'}")
        key = rest[0]
        if action == "rotate" and key in ELSEWHERE:
            raise Failure(f"{key} is not rotated here: {ELSEWHERE[key]}; then {EAX} secrets set {key}.")
        if action == "rotate":
            value = vault.generate([key])[key]
        else:
            import getpass
            value = getpass.getpass(f"New value for {key} (not shown): ").strip()
            if not value or "\n" in value:
                raise Failure("No value given: nothing changed.")
        c = _client(text, where_)
        held = c.read(where_)
        if key in DB_LOGINS:
            _rotate_login(DB_LOGINS[key], value)
        held[refs[key]] = value
        for derived, source in vault.DERIVED.items():
            if source == key and derived in refs:
                held[refs[derived]] = value
        c.write(where_, held)
        say(f"{key} changed in OpenBao{' and in the database' if key in DB_LOGINS else ''}. Run {EAX} up: each container "
            "that uses it is made again with the new value.")
        return 0
    if action == "new":
        c = _client(text, where_)
        held = c.read(where_)
        missing = sorted({n for n in refs.values() if n not in held})
        if not missing:
            say("The vault holds a value for every reference.")
            return 0
        held.update(vault.generate(missing))
        c.write(where_, held)
        say(f"New values for {', '.join(missing)}. A database login made earlier keeps its old password: "
            f"{EAX} secrets rotate KEY changes both.", "yellow")
        return 0
    raise Failure(f"{EAX} secrets [show|get KEY|migrate|pull|rotate KEY|set KEY|new]")
