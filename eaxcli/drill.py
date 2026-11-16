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
  eax drill quiet on|off               the maintenance page and the background paused, or back
  eax drill content <state file>       a test project, models and content of every kind (the backup and restore test's);
                                       the state (ids, its snapshot, the test accounts' tokens) written to the file
  eax drill content-check <state file> the test's content read here and compared with its snapshot: exit 1 when it differs
  eax drill content-remove <state file> the test's content, accounts and record removed here
  eax drill fingerprint <file>         every table and file, written to <file> (JSON)
  eax drill backup                     an infrastructure backup now: its name and folder
  eax drill shutdown                   every container of this installation stopped and removed (volumes and images kept)
  eax drill restore <name>             a full restore of a backup, then EA Explorer answering again
  eax drill compare <a> <b>            two fingerprints compared (what the installation writes by itself is not): exit 1
                                       when anything differs
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
            m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$", line)
            if m:
                out[m.group(1)] = m.group(2).strip("'\"")
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
CODE_SKIP_FILES = re.compile(r"\.(pyc|pyo|swp|tmp|log)$|^(\.DS_Store|Thumbs\.db|CODE\.sha256)$")


def code_files(root: Path, skip: Path | None = None) -> list[Path]:
    """The installation's code: every file under root but work/, git's folder, packages and caches (and skip, a folder
    being written into), sorted; paths relative to root."""
    out = []
    for dirpath, dirs, files in os.walk(root):
        d = Path(dirpath)
        dirs[:] = sorted(x for x in dirs if x not in CODE_SKIP_DIRS and (skip is None or (d / x).resolve() != skip))
        out += [(d / f).relative_to(root) for f in sorted(files) if not CODE_SKIP_FILES.search(f)]
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
            "root": str(ROOT)}


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
    """Every container stopped and removed; the volumes (the data) and the images kept."""
    r = subprocess.run(compose_args(["down", "--remove-orphans"]), cwd=ROOT, env={**os.environ, "COMPOSE_PROFILES": "*"},
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    left = containers()
    out = {"containers_left": len(left)}
    if r.returncode or left:
        out["error"] = (f"{len(left)} container(s) left" + (f"; docker compose: {(r.stderr or r.stdout).strip().splitlines()[-1][:300]}"
                                                            if r.returncode and (r.stderr or r.stdout).strip() else ""))
    return out


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
    out = {"made": len(st.get("made") or []), "sid": st.get("sid"), "file": path}
    if bad:
        out["error"] = "not made: " + "; ".join(bad[:10])
    elif snap.get("error"):
        out["error"] = f"its snapshot: {snap['error']}"
    return out


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
        elif cmd == "quiet" and rest[:1] in (["on"], ["off"]):
            out = _ops("quiet", rest[0])
        elif cmd == "content" and rest:
            out = content(rest[0])
        elif cmd == "content-check" and rest:
            out = content_check(rest[0])
        elif cmd == "content-remove" and rest:
            st = _state(rest[0])
            out = _api("finish", {**st, "results": [], "keep": False})
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
            if out["differ"]:
                out["error"] = f"{len(out['differ'])} differ: " + "; ".join(out["differ"][:20])
        elif cmd == "code" and rest:
            out = copy_code(Path(rest[0]).expanduser())
            if out["version"] != version():
                out["error"] = f"the code copied says version {out['version']}, the installation {version()}"
        else:
            out = {"error": "eax drill info | running | quiet on|off | content|content-check|content-remove <state file> | "
                            "fingerprint <file> | backup | shutdown | restore <name> | compare <a> <b> | code <folder>"}
    except (Failure, OSError, ValueError) as exc:
        out = {"error": str(exc)[:1000]}
    print(json.dumps(out, default=str), flush=True)
    if out.get("error"):
        say(f"eax drill {cmd}: {out['error']}", "red")
    return 1 if out.get("error") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
