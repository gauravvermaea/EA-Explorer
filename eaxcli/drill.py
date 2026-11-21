"""eax drill <step>: the steps the restore drill (dr/eax-drill) and the DR script (dr/eax-dr) ask of eax, each answering
one JSON line; nothing here asks a question (R5.6-B2).

The owner's design (16 Nov 2026, 21:40): "ea drill takes an install location as an input and a dr location as an input
and a temp location as an input; check if that install is running or not; if its not running stop; if its running
create a temp project model etc as needed; make backup ...; then shut down this install; then copy all the files to the
temp location - backups, env etc; then at dr location download the install from github; setup the files; restore; test
... ensure it doesnt override the current running folder. Always needs a new folder"; containers removed, images kept;
21:52: the DR copy gets its own Docker volumes (work/compose-project).

  eax drill info                       version, deployment kind, repository, where the backups, the config and persist/ are
  eax drill running                    whether this installation runs (the API and sign-in answer)
  eax drill preflight <temp> <dr>      before anything is touched, in seconds: free disk for the backup, its copy and the
                                       DR copy (too little fails); containers not healthy and the background busy (warnings)
  eax drill smoke-result               after a smoke test that failed (only with -Smoke): its findings, as warnings
                                       (then a warning, the drill carries on) or found a fault (a failure)
  eax drill diagnose <folder>          after a failure: every container's state and the last lines of its log, into <folder>
  eax drill quiet on|off               the maintenance page and the background paused, or back
  eax drill content <state file>       a test project, models and content of every kind (the backup and restore test's);
                                       the state (ids, its snapshot, the test accounts' tokens) written to the file; a kind
                                       that could not be made is a warning (it is then not checked after the restore)
  eax drill content-check <state file> the test's content read here and compared with its snapshot: exit 1 when it differs
  eax drill content-remove <state file> the test's content, accounts and record removed here
  eax drill idle                       waits until the background has finished what it was doing (at most half an hour)
  eax drill fingerprint <file>         every table and file, written to <file> (JSON)
  eax drill backup                     an infrastructure backup now: its name and folder
  eax drill shutdown                   every container of this installation stopped and removed (volumes and images kept)
  eax drill restore <name>             a full restore of a backup, then EA Explorer answering again
  eax drill compare <a> <b>            two fingerprints compared: the key items' counts (models, elements, relationships,
                                       projects, people, documents) and every table; a difference is a WARNING, never a
                                       failure (the owner, 18 Nov 2026, 07:12: "Key items, check is only a warning, unless
                                       the actual migration fails dont fail test")
  eax drill take <name> <folder>       the backup copied out of EA Explorer into <folder> while it still runs: from the
                                       backups folder on this machine when it is there, else straight out of the
                                       operations helper (docker compose cp), so no folder setting can send it astray
                                       (the owner's drill, 18 Nov 2026, 07:04: "Cannot find path ...\\infrastructure\\...")
  eax drill signin                     a real sign-in: Keycloak signs its admin in and counts the people of EA
                                       Explorer's realm, and the API answers: "If we can login into the new instance we
                                       are good" (07:12)
  eax drill remove-copy <name>         a DR copy's Docker containers, data (volumes) and networks removed, by its Docker
                                       name (eaexplorer-dr); never this installation's own; images kept (shared names)
  eax drill delete-backup <name>       one of this installation's backups unpinned and deleted (the drill's own)
  eax drill code <folder>              this installation's code copied into a new folder, with CODE.sha256 (a checksum
                                       of every file): eax-dr builds from it with no GitHub (the owner, 16 Nov 2026, 22:44)"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import backup_restore as BR
from .core import ROOT, WORK, Failure, compose_args, say, version


def config_values(path: Path) -> dict[str, str]:
    """The config file's settings (pure but for reading it)."""
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            name, eq, value = line.partition("=")      # NAME = value (D804: string work, not a regular expression)
            name = name.strip()
            if eq and name and not name.strip("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"):
                out[name] = value.strip().strip("'\"")
    except OSError:
        pass
    return out


def backups_folder(setting: str) -> Path:
    """Where the backups are on this machine: EAX_BACKUP_DIR when it names a folder, else work/backups (pure)."""
    s = (setting or "").strip()
    if s and (s.startswith(("/", "\\", "./", "~")) or re.match(r"^[A-Za-z]:", s)):
        p = Path(os.path.expanduser(s))
        return p if p.is_absolute() else ROOT / p
    return WORK / "backups"


# not code: the installation's own data and what tools make (never in a DR pack or a drill's copy)
CODE_SKIP_DIRS = {"work", ".git", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv",
                  "venv", ".idea", ".vscode"}
# data and secrets kept beside the code (as .gitignore names them): never code. logs/ is every container's daily log
# (and open while they run), persist/ and data/ come back with the backup, testbench's credentials.json is filled in
# by hand, the web's dist/ is built; an env file holds passwords (deploy/templates' are blanks, and are code)
CODE_SKIP_PATHS = {"logs", "persist", "data", "testbench/reports", "testbench/data/credentials.json", "services/web/dist"}
CODE_SKIP_FILES = re.compile(r"\.(pyc|pyo|swp|tmp|log)$|^(\.DS_Store|Thumbs\.db|CODE\.sha256)$")


# the one part of work/ that goes with the code: work/tools, the helper's own uv and Python (eaxpy fetches them from
# GitHub when they are missing, so a DR copy without them would need GitHub after all); not its download cache
TOOLS_SKIP = {"cache"}


def code_files(root: Path, skip: Path | None = None) -> list[Path]:
    """The installation's code: every file under root but work/ (except work/tools, the helper's uv and Python), git's
    folder, packages and caches (and skip, a folder being written into), sorted; paths relative to root."""
    out = []
    for dirpath, dirs, files in os.walk(root):
        d = Path(dirpath)
        rel = d.relative_to(root).parts
        if rel[:1] == ("work",):
            if len(rel) == 1:
                dirs[:] = [x for x in dirs if x == "tools"]
                continue                                    # no file of work/ itself
            if len(rel) == 2:
                dirs[:] = sorted(x for x in dirs if x not in TOOLS_SKIP)
            else:
                dirs[:] = sorted(dirs)
            out += [(d / f).relative_to(root) for f in sorted(files)]
            continue
        here = "/".join(rel)
        dirs[:] = sorted(x for x in dirs if (x not in CODE_SKIP_DIRS or (not rel and x == "work"))
                         and f"{here}/{x}".lstrip("/") not in CODE_SKIP_PATHS
                         and (skip is None or (d / x).resolve() != skip))
        out += [(d / f).relative_to(root) for f in sorted(files) if not CODE_SKIP_FILES.search(f)
                and f"{here}/{f}".lstrip("/") not in CODE_SKIP_PATHS
                and not (f.endswith(".env") and here != "deploy/templates")]
    return out


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def copy_code(dest: Path, root: Path = ROOT) -> dict:
    """The code copied into dest (new or empty), CODE.sha256 written (sha256sum's format, paths with /) and checked, and
    its version read back: {"files", "version", "folder"}."""
    dest = Path(dest).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise Failure(f"{dest} is not empty: the code goes into a new or empty folder")
    files = code_files(root, dest)
    dest.mkdir(parents=True, exist_ok=True)
    lines = []
    for rel in files:
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, dest / rel)
        lines.append(f"{_sha(dest / rel)}  {rel.as_posix()}")
    (dest / "CODE.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    bad = check_code(dest)
    if bad:
        raise Failure("the code's copy is not whole: " + "; ".join(bad[:10]))
    ver = code_version(dest)
    if not ver:
        raise Failure(f"{dest} has no services/api/version.toml: not EA Explorer's code")
    return {"files": len(files), "version": ver, "folder": str(dest)}


def check_code(folder: Path) -> list[str]:
    """What does not match CODE.sha256 (missing or changed files); empty when the code is whole."""
    sums = Path(folder) / "CODE.sha256"
    if not sums.is_file():
        return ["CODE.sha256 is missing"]
    bad = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, _, rel = line.partition("  ")
        if rel and (not (Path(folder) / rel).is_file() or _sha(Path(folder) / rel) != digest):
            bad.append(f"{rel}: missing or changed")
    return bad


def code_version(folder: Path) -> str:
    """The version a copy of the code says (services/api/version.toml), or ""."""
    try:
        m = re.search(r'^version\s*=\s*"([^"]+)"', (Path(folder) / "services/api/version.toml").read_text(encoding="utf-8"), re.M)
    except OSError:
        return ""
    return m.group(1) if m else ""


def project() -> str:
    """This installation's Docker name: work/compose-project, else the compose file's (eaexplorer)."""
    return os.environ.get("COMPOSE_PROJECT_NAME") or "eaexplorer"


def info() -> dict:
    """What the outside scripts need to know before anything is touched."""
    from . import persist as P
    vals = config_values(WORK / "eaexplorer.env")
    return {"version": version(), "kind": vals.get("EAX_DEPLOYMENT", "laptop") or "laptop", "project": project(),
            "repo": vals.get("EAX_UPDATE_GIT_URL", "") or "https://github.com/gauravvermaea/EA-Explorer",
            "config": str(WORK / "eaexplorer.env"), "persist": str(P.folder()),
            "backups": str(backups_folder(vals.get("EAX_BACKUP_DIR", "")) / "infrastructure"),
            "root": str(ROOT), "shared": shared_folders(vals)}


FOLDER_SETTINGS = ("EAX_DATA_ROOT", "EAX_DATA_DIR", "EAX_DOCS_DIR", "EAX_LOGS_DIR", "EAX_BACKUP_DIR", "EAX_IMPORT_DIR",
                   "EAX_EXPORT_DIR", "EAX_TLS_DIR", "EAX_REPORTS_DIR", "EAX_PERSIST_DIR", "EAX_PACKS_DIR", "EAX_LIBRARY_DIR")


def shared_folders(vals: dict) -> list[str]:
    """The settings that put data in a folder of this machine by its full path (pure). A DR copy on the same machine,
    started with the same config file, would use those very folders: its restore would write over the installation's
    own data. The drill refuses then (a review of 17 Nov 2026, before the owner's next drill)."""
    out = []
    for k in FOLDER_SETTINGS:
        v = (vals.get(k) or "").strip().strip("'\"")
        if v and (v.startswith(("/", "\\", "~")) or re.match(r"^[A-Za-z]:", v)):
            out.append(f"{k}={v}")
    return out


def containers(state: str = "") -> list[str]:
    """This installation's containers (only the running ones with state="running")."""
    args = ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={project()}"]
    if state != "running":
        args.insert(2, "-a")
    return subprocess.run(args, capture_output=True, text=True).stdout.split()


def running() -> dict:
    """Whether the installation runs: its containers up and the API and sign-in answering."""
    up = containers("running")
    if not up:
        return {"running": False, "error": f"EA Explorer is not running here ({project()}): start it with eax up first"}
    from .stack import wait_core
    if not wait_core(2):
        return {"running": False, "error": "EA Explorer's containers run but the API or sign-in does not answer"}
    return {"running": True, "containers": len(up)}


def shutdown() -> dict:
    """Every container stopped and removed; the volumes (the data) and the images kept.

    The owner's drill, 17 Nov 2026, 11:13: "14 container(s) left" after docker compose down. Compose leaves the
    containers of services whose profile is not switched on (they are not orphans to it), and COMPOSE_PROFILES="*" is
    not understood by every compose. So every profile the compose files name is switched on by name, and any container
    of this installation still there afterwards is removed directly (its volumes stay)."""
    env = {**os.environ}
    r = subprocess.run(compose_args(["config", "--profiles"]), cwd=ROOT, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    profiles = [p for p in (r.stdout or "").split() if re.fullmatch(r"[A-Za-z0-9_.-]+", p)]
    if profiles:
        env["COMPOSE_PROFILES"] = ",".join(profiles)
    r = subprocess.run(compose_args(["down", "--remove-orphans"]), cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    left = containers()
    forced = 0
    if left:                                           # what compose did not take: removed directly, volumes kept
        subprocess.run(["docker", "rm", "-f", *left], capture_output=True, text=True, encoding="utf-8", errors="replace")
        forced = len(left)
        left = containers()
    out = {"containers_left": len(left), "removed_directly": forced, "profiles": profiles}
    if left:
        names = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}} ({{.Status}})", "--filter",
                                f"label=com.docker.compose.project={project()}"], capture_output=True, text=True).stdout.split("\n")
        out["error"] = (f"{len(left)} container(s) left: " + ", ".join(n for n in names if n)[:400]
                        + (f"; docker compose: {(r.stderr or r.stdout).strip().splitlines()[-1][:300]}"
                           if r.returncode and (r.stderr or r.stdout).strip() else ""))
    return out


def remove_copy(name: str) -> dict:
    """A DR copy gone from Docker: its containers, volumes (its data) and networks, found by the Docker name compose
    gives them (com.docker.compose.project). Not its images: they carry the same names as the installation's
    (eaexplorer/api:dev and the rest), so removing them would remove the installation's too. The owner, 17 Nov 2026, 09:03: "For testing auto remove and create destination
    folders. Expect them to be cleaned and deleted". Never this installation's own name."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name or ""):
        return {"error": f"{name!r} is not a Docker name"}
    if name == project():
        return {"error": f"{name} is this installation's own Docker name: never removed this way"}
    label = f"label=com.docker.compose.project={name}"

    def ids(*what: str) -> list[str]:
        r = subprocess.run(["docker", *what, "--filter", label], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.stdout.split()

    out = {}
    for kind, listing, removing in (("containers", ("ps", "-aq"), ("rm", "-f")),
                                    ("volumes", ("volume", "ls", "-q"), ("volume", "rm", "-f")),
                                    ("networks", ("network", "ls", "-q"), ("network", "rm"))):
        found = sorted(set(ids(*listing)))
        if found:
            subprocess.run(["docker", *removing, *found], capture_output=True, text=True, encoding="utf-8", errors="replace")
        left = ids(*listing)
        out[kind] = len(found)
        if left:
            out["error"] = f"{len(set(left))} {kind} of {name} could not be removed"
    return out


def compare_warnings(c: dict) -> list[str]:
    """What a comparison found, as warnings only (pure): each key item with fewer rows after, then the other tables that
    lost rows (the first ten). Never a failure: the drill fails only when the restore itself fails or nobody can sign in
    (the owner, 18 Nov 2026, 07:12)."""
    out = [f"{k['what']}: {k['before']} before, {k['after']} after" for k in c.get("keys") or [] if k.get("lost")]
    rest = c.get("differ") or []
    if rest:
        out.append(f"{len(rest)} table(s) or file(s) differ: " + "; ".join(rest[:10]) + (" ..." if len(rest) > 10 else ""))
    return out


BACKUP_NAME = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[A-Za-z0-9._-]+$")


def take(name: str, dest: str, run=subprocess.run) -> dict:
    """The backup copied out of EA Explorer into dest while it still runs (see the module): the folder on this machine
    when it holds it, else out of the operations helper. Checked to hold its SHA256SUMS."""
    if not BACKUP_NAME.match(name or ""):
        return {"error": f"{name} is not a backup's name"}
    target = Path(dest).expanduser()
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    src = Path(info()["backups"]) / name
    if (src / "SHA256SUMS").exists():
        shutil.copytree(src, target)
        how = f"from {src}"
    else:
        p = run(compose_args(["cp", f"ops:/backups/infrastructure/{name}", str(target)]), cwd=ROOT, capture_output=True,
                text=True, encoding="utf-8", errors="replace", check=False)
        if p.returncode != 0:
            return {"error": f"the backup could not be copied out of EA Explorer: {(p.stderr or p.stdout).strip()[-300:]}"}
        how = "out of EA Explorer's operations helper"
    if not (target / "SHA256SUMS").exists():
        return {"error": f"the copy of {name} has no SHA256SUMS: not a whole backup"}
    return {"folder": str(target), "files": sum(1 for f in target.rglob("*") if f.is_file()), "how": how}


SIGNIN_KC = ('set -e; K=/opt/keycloak/bin/kcadm.sh; C=/tmp/eax-drill-kcadm.config; '
             '$K config credentials --config $C --server http://localhost:8080/auth --realm master --user "$1" '
             '--password "$(cat /run/secrets/EAX_KC_ADMIN_PASSWORD)" >/dev/null; '
             '$K get users/count --config $C -r "$2"; rm -f $C')
SIGNIN_API = ("import urllib.request,sys; r=urllib.request.urlopen('http://localhost:8000/api/health', timeout=20); "
              "print(r.status)")


def signin(minutes: int = 10, run=subprocess.run, sleep=None) -> dict:
    """A real sign-in to this installation (see the module), tried for up to `minutes` while it finishes starting."""
    import time

    from .core import setting
    sleep = sleep or time.sleep
    realm, admin = setting("EAX_KEYCLOAK_REALM", "eaexplorer"), setting("EAX_KC_ADMIN", "kcadmin")
    why, end = "", time.time() + minutes * 60
    while True:
        kc = run(compose_args(["exec", "-T", "keycloak", "bash", "-c", SIGNIN_KC, "kc", admin, realm]), cwd=ROOT,
                 capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        api = run(compose_args(["exec", "-T", "api", "python", "-c", SIGNIN_API]), cwd=ROOT, capture_output=True, text=True,
                  encoding="utf-8", errors="replace", check=False)
        people = (kc.stdout or "").strip().splitlines()[-1:] if kc.returncode == 0 else []
        if people and people[0].strip().isdigit() and api.returncode == 0 and "200" in (api.stdout or ""):
            n = int(people[0].strip())
            out = {"people": n, "realm": realm, "api": "answers"}
            if n == 0:
                out["warnings"] = [f"signed in, but the realm {realm} has no people: were they restored?"]
            return out
        why = ("Keycloak: " + (kc.stderr or kc.stdout or "").strip()[-200:]) if kc.returncode or not people else \
              ("the API: " + (api.stderr or api.stdout or "").strip()[-200:])
        if time.time() >= end:
            return {"error": f"nobody can sign in after {minutes} minutes ({why})"}
        sleep(15)


def _ops(*args: str) -> dict:
    return BR.run_in(BR.OPS, [*args, "--version", version()])


def _api(cmd: str, state: dict) -> dict:
    return BR.run_in(BR.API, [cmd], state)


def _state(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def content(path: str) -> dict:
    """The test's content made here, its snapshot taken; the state written to the file (never printed: it holds the test
    accounts' tokens)."""
    st = _api("start", {"by": "eax-drill", "folder": "drill", "version": version()})
    if st.get("error"):
        return {"error": st["error"]}
    bad = [m["what"] + (f": {m['detail']}" if m.get("detail") else "") for m in st.get("made") or [] if not m.get("ok")]
    st.pop("calls", None)
    snap = _api("snapshot", st)
    st["snapshot"] = snap
    Path(path).write_text(json.dumps(st), encoding="utf-8")
    out = {"made": len(st.get("made") or []) - len(bad), "sid": st.get("sid"), "file": path}
    if snap.get("error"):
        out["error"] = f"its snapshot: {snap['error']}"
    elif bad:
        # a kind that could not be made is a warning: the drill carries on and that kind is not checked after the restore
        # (it is in neither snapshot); the test's accounts, models and project not made stop start() itself (the owner,
        # 17 Nov 2026, 19:05: "have make things warning and fail and can we continue with it")
        out["warnings"] = [f"not made (not checked after the restore): {b}" for b in bad[:20]]
    return out


# ---------------------------------------------------------------- warnings and failures (the owner, 17 Nov 2026, 19:05)
GB = 1 << 30
MIN_BACKUP = 5 * GB       # what a backup is taken to need when there is none yet to measure


def _nearest(path: str) -> Path:
    """The folder itself, or its nearest parent that exists (the DR and temp folders may not be made yet)."""
    p = Path(path).expanduser().resolve()
    while not p.exists() and p != p.parent:
        p = p.parent
    return p


def _size(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


def last_backup_bytes(backups: Path) -> int:
    """The size of the newest infrastructure backup here (0 when there is none)."""
    try:
        folders = sorted((d for d in Path(backups).iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime)
    except OSError:
        return 0
    return _size(folders[-1]) if folders else 0


def disk_needs(backup: int, backups: str, temp: str, dr: str, free=lambda p: shutil.disk_usage(p).free, device=None) -> list[str]:
    """What each disk lacks (pure but for free): the backup (one and a half times the last), its copy in the temp folder
    (the same again), and the DR copy (its code and work folders, half of it). Folders on the same disk add up."""
    need: dict[object, int] = {}
    where: dict[object, list[str]] = {}
    path: dict[object, Path] = {}
    for label, folder, n in (("the backup", backups, backup * 3 // 2), ("its copy in the temp folder", temp, backup * 6 // 5),
                             ("the DR copy's folder", dr, backup // 2)):
        p = _nearest(folder)
        disk = (device or _device)(p)          # the same disk (or mount) adds up, whatever the folder
        need[disk] = need.get(disk, 0) + n
        where.setdefault(disk, []).append(label)
        path.setdefault(disk, p)
    out = []
    for disk, n in need.items():
        have = free(path[disk])
        if have < n:
            out.append(f"{path[disk]}: {have / GB:.1f} GB free, {n / GB:.1f} GB needed for {', '.join(where[disk])}")
    return out


def _device(p: Path) -> object:
    """Which disk or mount a folder is on (its device number; the drive on Windows)."""
    try:
        return os.stat(p).st_dev
    except OSError:
        return p.anchor or str(p)


def container_states() -> list[dict]:
    """This installation's containers: name, state and health."""
    r = subprocess.run(["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={project()}",
                        "--format", "{{.Names}}|{{.State}}|{{.Status}}"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = []
    for line in (r.stdout or "").splitlines():
        name, _, rest = line.partition("|")
        state, _, status = rest.partition("|")
        health = "unhealthy" if "(unhealthy)" in status else "starting" if "(health: starting)" in status else \
            "healthy" if "(healthy)" in status else ""
        out.append({"name": name, "state": state, "status": status, "health": health})
    return out


def not_well(c: dict) -> bool:
    """A container that should be running and is not, or is not healthy (pure). One that runs once at start and ends
    well (setup, reports-init: "Exited (0)") is as it should be (the owner's drill, 17 Nov 2026, 19:45)."""
    if c["state"] == "exited" and re.search(r"Exited \(0\)", c.get("status") or ""):
        return False
    return c["state"] != "running" or c["health"] in ("unhealthy", "starting")


def preflight(temp: str, dr: str) -> dict:
    """Before anything is touched, in seconds: the disks (too little fails), the containers and the background (warnings)."""
    inf = info()
    size = last_backup_bytes(Path(inf["backups"]))
    warnings = []
    if not size:
        warnings.append(f"no earlier backup to measure: a backup is taken to need {MIN_BACKUP // GB} GB")
    lacking = disk_needs(size or MIN_BACKUP, inf["backups"], temp, dr)
    for c in container_states():
        if not_well(c):
            warnings.append(f"container {c['name']}: {c['status']}")
    bz = _api("busy", {})
    if bz.get("error"):
        warnings.append(f"the background could not be asked: {bz['error']}")
    warnings += [f"the background is busy: {b}" for b in bz.get("busy") or []]
    out = {"backup_gb": round((size or MIN_BACKUP) / GB, 2), "warnings": warnings}
    if lacking:
        out["error"] = "too little disk: " + "; ".join(lacking)
    return out


# a failed check that says only that something was slow (the owner's full test, 17 Nov 2026: "VP-25 ... not loaded after
# 60 seconds"): a warning in the drill, not a failure
TIMING = re.compile(r"not loaded after \d+ seconds|timed? ?out|no answer after|took (longer|over|more)|slower than|"
                    r"too slow|still loading|did not answer within", re.I)


def timing_only(failed: list[dict]) -> bool:
    """Whether every failed check failed only on timing (pure)."""
    return bool(failed) and all(TIMING.search(f"{f.get('name', '')} {f.get('detail', '')}") for f in failed)


def smoke_result() -> dict:
    """After `eax test smoke` failed (it runs only when asked: -Smoke): its findings as warnings. Whether the backup and
    the restore work is judged on the row counts, the key items and the test content (owner, 18 Nov 2026, 06:39: "Can
    the testing be not exhasutive and just check number of rows or some ket items"), not on the installation's own
    faults the smoke test finds."""
    r = _api("failed", {})
    if r.get("error"):
        return {"warnings": [f"the smoke test failed, and its checks could not be read: {r['error']}"]}
    failed = r.get("failed") or []
    lines = [f"{f['suite']} {f['name']}: {f['detail'][:200]}" for f in failed]
    if timing_only(failed):
        return {"run": r.get("run"), "warnings": [f"smoke test, only slow (run {r.get('run')}): {x}" for x in lines[:20]]}
    if not failed:
        return {"warnings": [f"the smoke test failed (run {r.get('run')}, {r.get('state')}) with no failed check recorded"]}
    return {"run": r.get("run"), "warnings": [f"smoke test found (run {r.get('run')}): {x}" for x in lines[:20]]}


LOG_LINES = 200


def diagnose(folder: str) -> dict:
    """After a failure: every container's state (containers.txt) and the last LOG_LINES lines of each one's log
    (logs/<name>.log) written into folder, so a failure explains itself without running the drill again."""
    dest = Path(folder).expanduser()
    (dest / "logs").mkdir(parents=True, exist_ok=True)
    states = container_states()
    (dest / "containers.txt").write_text("\n".join(f"{c['name']}  {c['state']}  {c['status']}" for c in states) + "\n",
                                         encoding="utf-8")
    for c in states:
        r = subprocess.run(["docker", "logs", "--tail", str(LOG_LINES), "--timestamps", c["name"]], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        (dest / "logs" / f"{c['name']}.log").write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
    bad = [f"{c['name']} ({c['status']})" for c in states if not_well(c)]
    return {"folder": str(dest), "containers": len(states), "not_well": bad}


def content_check(path: str) -> dict:
    """The test's content read here and compared with the snapshot taken where it was made."""
    st = _state(path)
    now = _api("snapshot", st)
    if now.get("error"):
        return {"error": now["error"]}
    diffs = BR._differences(st.get("snapshot") or {}, now)
    present = BR._present(now)
    out = {"kinds": len(present), "same": not diffs}
    if diffs:
        out["error"] = "differs: " + "; ".join(diffs[:20])
    elif not present:
        out["error"] = "none of the test's content is here"
    return out


def main(args: list[str]) -> int:
    """eax drill <step> (see the module): one JSON line."""
    cmd, rest = (args[0] if args else ""), args[1:]
    try:
        if cmd == "info":
            out = info()
        elif cmd == "running":
            out = running()
        elif cmd == "preflight" and len(rest) >= 2:
            out = preflight(rest[0], rest[1])
        elif cmd == "smoke-result":
            out = smoke_result()
        elif cmd == "diagnose" and rest:
            out = diagnose(rest[0])
        elif cmd == "quiet" and rest[:1] in (["on"], ["off"]):
            out = _ops("quiet", rest[0])
        elif cmd == "content" and rest:
            out = content(rest[0])
        elif cmd == "content-check" and rest:
            out = content_check(rest[0])
        elif cmd == "content-remove" and rest:
            st = _state(rest[0])
            out = _api("finish", {**st, "results": [], "keep": False})
        elif cmd == "remove-copy" and rest:
            out = remove_copy(rest[0])
        elif cmd == "delete-backup" and rest:
            out = _ops("delete", rest[0])
            if out.get("left"):
                out["error"] = f"{rest[0]} could not be deleted"
        elif cmd == "idle":
            out = _api("idle", {})
        elif cmd == "fingerprint" and rest:
            out = _ops("fingerprint")
            if not out.get("error"):
                Path(rest[0]).write_text(json.dumps(out), encoding="utf-8")
                out = {"file": rest[0], "tables": len(out.get("tables", {})), "files": len(out.get("files", {}))}
        elif cmd == "backup":
            out = _ops("backup", "drill-" + BR.random_name()[4:])
            if not out.get("error"):
                out["folder"] = str(Path(info()["backups"]) / out["name"])
        elif cmd == "shutdown":
            out = shutdown()
        elif cmd == "restore" and rest:
            out = _ops("restore", rest[0], "--what", "full")
            if not out.get("error") and not BR._wait_core():
                out["error"] = "EA Explorer did not answer again within 30 minutes after the restore"
        elif cmd == "compare" and len(rest) >= 2:
            a, b = (json.loads(Path(p).read_text(encoding="utf-8")) for p in rest[:2])
            out = BR.same(a, b, set())
            out["keys"] = BR.key_counts(a, b)
            out["keys_said"] = ", ".join(f"{k['what']} {k['before']}->{k['after']}" for k in out["keys"])
            out["warnings"] = compare_warnings(out)
        elif cmd == "take" and len(rest) >= 2:
            out = take(rest[0], rest[1])
        elif cmd == "signin":
            out = signin()
        elif cmd == "code" and rest:
            out = copy_code(Path(rest[0]).expanduser())
            if out["version"] != version():
                out["error"] = f"the code copied says version {out['version']}, the installation {version()}"
        else:
            out = {"error": "eax drill info | running | preflight <temp> <dr> | smoke-result | diagnose <folder> | quiet on|off | content|content-check|content-remove <state file> | "
                            "idle | remove-copy <name> | delete-backup <name> | fingerprint <file> | backup | take <name> <folder> | shutdown | restore <name> | signin | compare <a> <b> | code <folder>"}
    except (Failure, OSError, ValueError) as exc:
        out = {"error": str(exc)[:1000]}
    print(json.dumps(out, default=str), flush=True)
    for w in out.get("warnings") or []:
        say(f"eax drill {cmd}: warning: {w}", "yellow")
    if out.get("error"):
        say(f"eax drill {cmd}: {out['error']}", "red")
    return 1 if out.get("error") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
