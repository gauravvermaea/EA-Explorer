"""Where the data lives: one base folder (R5.4, D687).

The owner, 15 Nov 2026: "we just need to have a base folder's we put in then users can mount whatever they want if
they want for example DB wont live on NAS but logs or docuemnts may". So: EAX_DATA_ROOT in the config file names one
folder, and each kind of data has a fixed folder under it. What is mounted onto any of them (a NAS for the logs or the
documents, the local disk for the databases) is the organisation's choice; EA Explorer does not decide it.

- A folder setting of its own (EAX_DATA_DIR, EAX_DOCS_DIR, ...) that is a path is kept as it is; one left empty,
  naming a Docker volume (eax-...) or the laptop template's folder under work/ becomes <root>/<its folder>. Without EAX_DATA_ROOT nothing changes (a laptop's
  Docker volumes, as before).
- On Windows the databases stay in their Docker volume (PostgreSQL cannot run on an NTFS folder) unless EAX_DATA_DIR
  names a path itself.
- Before containers are made (eax up, run, create; all three forms), each folder is made if it is missing, checked
  (there, writable) and said: on this machine's own disk or a mount, and the space free. A missing base folder or one
  that cannot be written stops the start, with why; where a folder is never does.
- The values reach docker compose through eax's own environment (never written anywhere), and the containers through
  x-folders in docker-compose.yml.

`eax folders` shows the table; `eax folders env` prints the values for eax.ps1 and eax.sh (stdout) and the table
(stderr).
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "EAX_DATA_ROOT"

# (setting, folder under the base, what it holds); the order eax folders shows them in
KINDS: list[tuple[str, str, str]] = [
    ("EAX_DATA_DIR", "databases", "the databases (PostgreSQL)"),
    ("EAX_DOCS_DIR", "documents", "the documents' files"),
    ("EAX_LOGS_DIR", "logs", "every container's daily logs"),
    ("EAX_BACKUP_DIR", "backups", "the backups"),
    ("EAX_IMPORT_DIR", "imports", "files to import"),
    ("EAX_EXPORT_DIR", "exports", "files exported"),
    ("EAX_TLS_DIR", "certificates", "the certificate (tls.crt, tls.key)"),
    ("EAX_REPORTS_DIR", "reports", "Reports' own files (its secret key, uploads)"),
]


def _config(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = (root / "work" / "eaexplorer.env").read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip("'\"")
    return values


def _is_volume(value: str) -> bool:
    """A Docker volume's name (eax-pgdata) rather than a folder (./work/x, /srv/eax/x, D:\\eax)."""
    return bool(value) and "/" not in value and "\\" not in value and ":" not in value


def _is_default(value: str) -> bool:
    """A laptop template's own folder under work/ (./work/data/imports): the base folder replaces it when one is set."""
    return value.replace("\\", "/").lstrip("./").startswith("work/")


@dataclass
class Place:
    """One kind of data and where it goes under the base folder."""
    key: str
    folder: str          # under the base folder
    what: str
    value: str           # what docker compose gets ("" = its default, a Docker volume)
    source: str          # "base", "own" (its own setting), "volume" (a Docker volume, as before)
    note: str = ""


def resolve(get=None, windows: bool | None = None, root: Path | None = None) -> tuple[str, list[Place]]:
    """The base folder and where each kind of data goes. get(key) reads a setting (the environment first, then the
    config file)."""
    root = root or ROOT
    if get is None:
        cfg = _config(root)
        get = lambda k: os.environ.get(k) or cfg.get(k, "")   # noqa: E731
    windows = (os.name == "nt") if windows is None else windows
    base = (get(BASE) or "").strip()
    places: list[Place] = []
    for key, folder, what in KINDS:
        own = (get(key) or "").strip()
        if own and not _is_volume(own) and not (base and _is_default(own)):
            places.append(Place(key, folder, what, own, "own"))
        elif not base:
            places.append(Place(key, folder, what, own, "volume"))
        elif key == "EAX_DATA_DIR" and windows:
            places.append(Place(key, folder, what, own, "volume",
                                "kept in its Docker volume: PostgreSQL cannot run on a Windows folder"))
        else:
            places.append(Place(key, folder, what, _join(base, folder, windows), "base"))
    return base, places


def _join(base: str, folder: str, windows: bool) -> str:
    sep = "\\" if windows and ("\\" in base or ":" in base) else "/"
    return base.rstrip("/\\") + sep + folder


def _mount_of(p: Path) -> Path:
    p = p.resolve()
    while not os.path.ismount(p) and p.parent != p:
        p = p.parent
    return p


def where(p: Path) -> str:
    """On this machine's own disk, or the mount it is on."""
    if os.name == "nt":
        s = str(p.resolve())
        return "a network share" if s.startswith("\\\\") else f"this machine's drive {s[:2]}"
    m = _mount_of(p)
    return "this machine's own disk" if str(m) == "/" else f"mounted at {m}"


def _free(p: Path) -> str:
    try:
        u = shutil.disk_usage(p)
    except OSError:
        return "?"
    return f"{u.free / 1024 ** 3:,.0f} GB free of {u.total / 1024 ** 3:,.0f} GB"


@dataclass
class Check:
    """Whether one place is there and writable, in words."""
    place: Place
    ok: bool
    said: str


def check(base: str, places: list[Place], make: bool = True, root: Path | None = None) -> tuple[bool, list[Check]]:
    """Each folder made if missing, then checked: there and writable, where it is, the space free. False when the
    base folder is missing or a folder cannot be used: the start stops."""
    root = root or ROOT
    out: list[Check] = []
    ok = True
    if base:
        b = Path(base) if Path(base).is_absolute() else root / base
        if not b.is_dir():
            return False, [Check(Place(BASE, "", "the base folder", base, "base"), False,
                                 f"the base folder {base} is not there: make it (or mount it) first, then start again")]
    for p in places:
        if p.source == "volume":
            out.append(Check(p, True, p.note or f"Docker volume {p.value or '(its default)'}"))
            continue
        path = Path(p.value) if Path(p.value).is_absolute() else root / p.value
        try:
            if make:
                path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            ok = False
            out.append(Check(p, False, f"{p.value} could not be made: {exc.strerror or exc}"))
            continue
        if not path.is_dir() and not make:
            out.append(Check(p, True, f"{p.value}: not there yet (made at the next start)"))
            continue
        if not path.is_dir():
            ok = False
            out.append(Check(p, False, f"{p.value} is not there"))
            continue
        if not os.access(path, os.W_OK):
            ok = False
            out.append(Check(p, False, f"{p.value} cannot be written"))
            continue
        out.append(Check(p, True, f"{p.value}: {where(path)}, {_free(path)}"))
    return ok, out


def table(base: str, checks: list[Check]) -> str:
    """Where the data lives, as a table to print."""
    lines = [f"Where the data lives (EAX_DATA_ROOT={base or 'not set: Docker volumes and work/ as before'}):"]
    for c in checks:
        mark = "ok " if c.ok else "NO "
        own = " (its own setting)" if c.place.source == "own" else ""
        lines.append(f"  {mark} {c.place.what:<46} {c.said}{own}")
    return "\n".join(lines)


def env_lines(places: list[Place]) -> list[str]:
    """KEY=value for docker compose: only what the base folder decides (a setting of its own is already in the file)."""
    return [f"{p.key}={p.value}" for p in places if p.source == "base"]


def main(rest: list[str]) -> int:
    """eax folders: where the data lives (show), or the settings for the config file (env)."""
    base, places = resolve()
    if rest and rest[0] == "env":
        if not base:
            return 0
        ok, checks = check(base, places)
        print(table(base, checks), file=sys.stderr)
        if not ok:
            print("ERROR: a data folder cannot be used (above): nothing was started.", file=sys.stderr)
            return 1
        for line in env_lines(places):
            print(line)
        return 0
    if rest and rest[0] not in ("show",):
        print("eax folders [show|env]: where the data lives (R5.4).", file=sys.stderr)
        return 1
    ok, checks = check(base, places, make=False)
    print(table(base, checks))
    return 0 if ok else 1
