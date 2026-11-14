"""The key vault: OpenBao, a container of its own (Release 4, R4.19, D218, D684; owner, 14 Nov 2026: "In R4 create a story
for laptop mode init to have OpenBao, we need the secrets working"; "Unseals by itself"; "Docker secrets"; "Server also
keeps unseal keys like laptop non manually puts them").

With EAX_SECRETS_FROM=openbao:eax/eaexplorer in work/eaexplorer.env, every password and key (each value the server
template holds as change-me) is kept in OpenBao, and the config file holds a reference in its place:
    EAX_DB_PASSWORD=openbao:EAX_DB_PASSWORD
Each eax command that runs docker compose first makes sure the vault runs, is initialised (once: one unseal key and a
root token, kept in persist/vault/keys.json, readable by the owner only) and unsealed (by itself, laptop and server alike),
then reads the values into its own environment only: Docker Compose takes them from there for every container (values
in the environment win over the config file), so they are never written to disk in clear. Every read is in the vault's
audit log (in its volume, eax-vault, kept in every infrastructure backup with keys.json).

Plain Python (no package), so eax.sh and eax.ps1 (through eaxpy: `eaxpy secrets env`) and the operations helper (which
mounts eaxcli) use the same code."""

from __future__ import annotations

import json
import os
import re
import secrets as _random
import stat
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

# Switched off (owner, 14 Nov 2026, 20:34: "For now disable openbao by default. No installation can use it. All passwords
# go back in env file. I want to think about this."): no installation keeps its passwords in OpenBao until this is True
ALLOWED = False
OFF = ("OpenBao is switched off for now (owner, 14 Nov 2026): the passwords stay in work/eaexplorer.env. "
       "eax secrets pull brings back values an installation had put in the vault.")
PREFIX = "openbao:"
DEFAULT_WHERE = "eax/eaexplorer"          # the KV (version 2) engine mounted at eax/, one secret: eaexplorer
KEYS_REL = "persist/vault/keys.json"     # persist/ (D558): no reset deletes it; in every infrastructure backup
AUDIT_FILE = "/openbao/file/audit/audit.log"
LAPTOP_URL = "http://127.0.0.1:{port}"
CONTAINER_URL = "http://openbao:8200"
WAIT_SECONDS = 60
# values made from another value, never generated on their own
DERIVED = {"EAX_DMS_BROKER_PASSWORD_URLENC": "EAX_DMS_BROKER_PASSWORD"}


class VaultError(Exception):
    pass


# ---------------------------------------------------------------- the config file's side
def where(env_text: str) -> str | None:
    """The mount/secret the passwords are kept in, when the config file says OpenBao (EAX_SECRETS_FROM=openbao:...)."""
    m = re.search(r"^EAX_SECRETS_FROM=['\"]?openbao:([^'\"\n]*)", env_text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip() or DEFAULT_WHERE


def references(env_text: str) -> dict[str, str]:
    """Each key the config file holds as a reference (KEY=openbao:NAME), with the name kept in the vault."""
    return {m.group(1): m.group(2).strip() or m.group(1)
            for m in re.finditer(r"^([A-Z0-9_]+)=['\"]?openbao:([A-Z0-9_]*)['\"]?\s*$", env_text, re.MULTILINE)}


def is_reference(value: str) -> bool:
    return (value or "").strip().strip("'\"").startswith(PREFIX)


def with_references(env_text: str, keys) -> str:
    """The config file with each of `keys` holding its reference instead of its value."""
    keys = set(keys)

    def sub(m: re.Match) -> str:
        return f"{m.group(1)}={PREFIX}{m.group(1)}" if m.group(1) in keys else m.group(0)
    return re.sub(r"^([A-Z0-9_]+)=(.*)$", sub, env_text, flags=re.MULTILINE)


def generate(keys, keep: dict[str, str] | None = None) -> dict[str, str]:
    """A new random value for each key (letters and digits only, so no file, URL or shell ever needs it quoted); those
    in `keep` keep theirs. A derived value is its source's (the broker's URL-encoded password: the same, as it needs
    no encoding)."""
    keep = keep or {}
    out = {k: keep[k] if k in keep else _random.token_hex(20) for k in keys if k not in DERIVED}
    for k, src in DERIVED.items():
        if k in keys:
            out[k] = keep.get(k) or out.get(src, "")
    return out


# ---------------------------------------------------------------- the keys, readable by the owner only
def keys_path(root: Path, persist: str = "") -> Path:
    """persist/vault/keys.json: beside the settings that survive resets (D558), so a cleanup that keeps the volumes keeps
    the vault's keys with them (persist: EAX_PERSIST_DIR when set; the operations helper sees it as /eax-persist)."""
    folder = Path(persist.strip()) if persist and persist.strip() else root / "persist"
    if not folder.is_absolute():
        folder = root / folder
    return folder / "vault" / "keys.json"


def save_keys(p: Path, data: dict) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.parent.chmod(stat.S_IRWXU)
    except OSError:
        pass
    tmp = p.with_suffix(".new")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, p)
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return p


def load_keys(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise VaultError(f"{KEYS_REL} cannot be read ({exc}): the vault cannot be unsealed without it.") from exc


# ---------------------------------------------------------------- OpenBao's API (the Vault API)
class Client:
    def __init__(self, url: str, token: str = "", timeout: int = 10):
        self.url, self.token, self.timeout = url.rstrip("/"), token, timeout
        self.fresh = False          # made in this call (ready): its values are generated
        self.audited = False

    def call(self, method: str, path: str, body: dict | None = None, ok=(200, 204)) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Vault-Token"] = self.token
        req = urllib.request.Request(f"{self.url}/v1/{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            if exc.code in ok:
                return json.loads(raw) if raw else {}
            try:
                errors = "; ".join(json.loads(raw).get("errors") or [])
            except ValueError:
                errors = raw.decode(errors="replace")[:200]
            raise VaultError(f"OpenBao refused {method} {path} ({exc.code}): {errors or exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise VaultError(f"OpenBao is not reachable at {self.url} ({getattr(exc, 'reason', exc)}).") from exc

    def health(self) -> dict:
        """initialized / sealed, answered whatever the state (sys/health answers 501 and 503 with a body too)."""
        return self.call("GET", "sys/health?standbyok=true&sealedcode=200&uninitcode=200")

    def init(self) -> dict:
        got = self.call("PUT", "sys/init", {"secret_shares": 1, "secret_threshold": 1})
        if not got.get("root_token") or not (got.get("keys_base64") or got.get("keys")):
            raise VaultError("OpenBao's initialisation answered without a key or a root token.")
        return got

    def unseal(self, key: str) -> dict:
        got = self.call("PUT", "sys/unseal", {"key": key})
        if got.get("sealed"):
            raise VaultError("OpenBao is still sealed after the unseal key from persist/vault/keys.json: is it this vault's key?")
        return got

    def mounted(self, mount: str) -> bool:
        got = self.call("GET", "sys/mounts")
        return f"{mount}/" in (got.get("data") or got)

    def mount_kv(self, mount: str) -> None:
        if not self.mounted(mount):
            self.call("POST", f"sys/mounts/{mount}", {"type": "kv", "options": {"version": "2"},
                                                       "description": "EA Explorer's passwords and keys"})

    def audit_on(self) -> bool:
        """Every request in the audit log (a file in the vault's volume), switched on once; False when this OpenBao
        refuses audit devices made through the API (eax secrets then says the audit log is off)."""
        try:
            if "eax/" in (self.call("GET", "sys/audit").get("data") or {}):
                return True
            self.call("PUT", "sys/audit/eax", {"type": "file", "options": {"file_path": AUDIT_FILE}})
            return True
        except VaultError:
            return False

    def read(self, where_: str) -> dict[str, str]:
        mount, _, name = where_.partition("/")
        got = self.call("GET", f"{mount}/data/{name or 'eaexplorer'}", ok=(200, 404))
        return {k: str(v) for k, v in ((got.get("data") or {}).get("data") or {}).items()}

    def write(self, where_: str, values: dict[str, str]) -> None:
        mount, _, name = where_.partition("/")
        self.call("POST", f"{mount}/data/{name or 'eaexplorer'}", {"data": values})


# ---------------------------------------------------------------- ready: running, initialised, unsealed
def url_for(env_text: str = "", inside: bool = False) -> str:
    if os.environ.get("EAX_VAULT_URL"):
        return os.environ["EAX_VAULT_URL"]
    if inside:
        return CONTAINER_URL
    m = re.search(r"^EAX_VAULT_PORT=(\d+)", env_text, re.MULTILINE)
    return LAPTOP_URL.format(port=m.group(1) if m else "8200")


def ready(keys_file: Path, url: str, where_: str, start: Callable[[], None] | None = None,
          say: Callable[[str], None] = lambda _m: None, wait: int = WAIT_SECONDS) -> Client:
    """The vault running (started when not), initialised (the first time: its key and root token into keys.json),
    unsealed (with that key) and holding the engine; answered as a client signed in with the root token."""
    c = Client(url)
    started, deadline, h = False, time.monotonic() + wait, None
    while True:
        try:
            h = c.health()
            break
        except VaultError:
            if not started and start is not None:
                say("Starting the key vault (OpenBao)...")
                start()                              # may fetch its image first: the wait starts once it runs
                started, deadline = True, time.monotonic() + wait
            if time.monotonic() > deadline:
                raise VaultError(f"OpenBao did not answer at {url} within {wait} s: see its log (docker compose logs openbao).") from None
            time.sleep(1)
    keys = load_keys(keys_file)
    if not h.get("initialized"):
        if keys.get("root_token"):                  # its volume went (eax cleanup --all): a new vault, the old keys kept aside
            old = keys_file.with_name(f"keys.{time.strftime('%Y%m%d-%H%M%S')}.old.json")
            keys_file.replace(old)
            say(f"The key vault's volume is new, so its old keys were moved aside ({old.name}); a new vault is made. If "
                "the databases were kept, restore a backup instead: their logins are the old vault's.")
            keys = {}
        say("Setting up the key vault (OpenBao) for the first time...")
        got = c.init()
        keys = {"unseal_key": (got.get("keys_base64") or got.get("keys"))[0], "root_token": got["root_token"],
                "made": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "url": url}
        save_keys(keys_file, keys)
        c.fresh = True
        h = c.health()
    if h.get("sealed"):
        if not keys.get("unseal_key"):
            raise VaultError(f"OpenBao is sealed and {KEYS_REL} has no unseal key: restore it from a backup (config/).")
        c.unseal(keys["unseal_key"])
    c.token = keys.get("root_token", "")
    c.mount_kv(where_.partition("/")[0])
    c.audited = c.audit_on()
    return c


def resolve(env_text: str, client: Client, where_: str) -> dict[str, str]:
    """The values behind the config file's references; refused when one is missing (never started with a reference)."""
    refs = references(env_text)
    if not refs:
        return {}
    held = client.read(where_)
    if not held and client.fresh:                   # a new vault (eax init): every value made here, never seen anywhere
        held = generate(sorted(set(refs.values())))
        client.write(where_, held)
    missing = sorted(k for k, name in refs.items() if name not in held)
    if missing:
        raise VaultError(f"The key vault holds no value for {', '.join(missing)}: eax secrets push (the values from a config "
                         "file), or eax secrets new (a new value for each one missing).")
    return {k: held[name] for k, name in refs.items()}


def env_lines(values: dict[str, str]) -> str:
    """KEY=VALUE lines for eax.sh and eax.ps1 to take into their own environment (over a pipe, never a file)."""
    return "".join(f"{k}={v}\n" for k, v in sorted(values.items()) if "\n" not in v)
