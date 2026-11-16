"""The operations helper's part of the backup and restore test (R5.6-B1; owner, 16 Nov 2026, 15:36: "It needs to be
completly syncrhronous calling one comamnd after other within eax and calling the require apis. This will not be async").

`eax test backup-restore` (eaxcli/backup_restore.py) runs on the host and calls these one after another, each waited for
(`docker compose exec ops python3 /app/ops.py brtest <command> ...`); each prints one JSON line at the end, nothing in
the background:

  brtest quiet on|off                the maintenance page for everyone and every recurring job and schedule paused
                                     (work/quiet.json, eax/quiet.py), or both back (owner, 16 Nov 2026, 19:28)
  brtest ready                       the backup container runs; the disk the test needs and what is free (S12)
  brtest backup <tag>                an infrastructure backup now, pinned while the test runs (S14); its manifest and time
  brtest restore <name> [--what W]   an infrastructure restore of that backup (full unless said); its result, the backup it
                                     took first and the time (S15)
  brtest fingerprint                 every table of every database (rows and a checksum) and every file of every file set
                                     (its sha256), with the config file's: the backup container's fingerprint.sh
  brtest mark <sid> put|remove       a marker file in persist/ and in the import folder (a file changed between B1 and B2)
  brtest retention <name>...         the scheduled clean-up's choice: none of these would be removed (S14)
  brtest backups                     every infrastructure backup (name, tag, kind, pinned, created, bytes)
  brtest delete <name>...            unpinned and deleted (the test's own backups at its end)

Bound to ops.py's helpers with bind(globals()), as testruns.py is."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time

H: dict = {}
MARK_SETS = {"persist": "/persist", "imports": "/imports"}   # where the marker files go, in the backup container
NAME = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,120}$")
QUIET_WHAT = "Backup and restore test"
STALE_SECONDS = 8 * 3600          # a flag left by a test stopped hard is ignored after this (eax/quiet.py)


def quiet_path() -> str:
    """work/quiet.json: while it is there, recurring jobs and schedules wait (eax/quiet.py)."""
    return os.path.join(os.environ.get("EAX_WORK_MOUNT", "/eax-work"), "quiet.json")


def is_quiet(now: float | None = None) -> bool:
    """Whether the test's quiet is in force (a stale flag is not). The helper's own schedulers ask this."""
    try:
        return (now or time.time()) - os.path.getmtime(quiet_path()) <= STALE_SECONDS
    except OSError:
        return False


def _page(on: bool, what: str = QUIET_WHAT) -> None:
    """The proxy's maintenance page alone (the API stays writable for the test): on or off."""
    flag = H["PROXY_FLAG"]
    if on:
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        with open(flag, "w", encoding="utf-8") as f:
            f.write(f"{what}\n")
    elif os.path.exists(flag) and not H["maintenance"]():
        os.remove(flag)


def quiet(action: str, by: str, what: str = QUIET_WHAT) -> dict:
    """The maintenance page and the paused background on (the test, the drill, a DR pack or any infrastructure backup
    starts) or off (it ends)."""
    if action == "on":
        with open(quiet_path(), "w", encoding="utf-8") as f:
            json.dump({"since": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "by": by, "what": what}, f)
        _page(True, what)
        return {"quiet": True, "page": True}
    if action != "off":
        raise ValueError("quiet on or off")
    try:
        os.remove(quiet_path())
    except FileNotFoundError:
        pass
    _page(False)
    return {"quiet": False, "page": os.path.exists(H["PROXY_FLAG"])}


def bind(ns: dict) -> None:
    """Takes ops.py's helpers."""
    H.update(ns)


def _backup_container() -> dict:
    c = H["_container"]("backup")
    if not c or c["state"] != "running":
        raise RuntimeError("The backup container is not running: switch Backups on in Administration > Services.")
    return c


# ---------------------------------------------------------------- the disk (S12)
def need_bytes(backups: list[dict], databases_bytes: int = 0) -> int:
    """What the test needs on the backups' disk: four backups (B1, B2 and the backup each restore takes of the state
    before it), each the size of the newest good backup (or of the databases when there is none yet), and a tenth
    more (pure)."""
    good = [b for b in backups if b.get("status") in (None, "ok") and b.get("bytes")]
    one = int(good[0]["bytes"]) if good else int(databases_bytes or 0)
    return int(one * 4 * 1.1)


def ready() -> dict:
    """Whether the test can start: the backup container runs, and the disk has room (refused before anything is touched,
    saying how much is needed)."""
    _backup_container()
    rows = H["list_infra"]()
    fs = {f["label"]: f for f in H["filesystems"]() if not f.get("error")}
    free = int((fs.get("Backups folder") or fs.get("Docker's disk") or {}).get("free_bytes") or 0)
    need = need_bytes(rows)
    out = {"free_bytes": free, "need_bytes": need, "enough": free >= need or need == 0}
    if not out["enough"]:
        out["error"] = (f"Not enough disk for the test: it needs about {need / 1e9:.1f} GB in the backups folder (four "
                        f"backups the size of the newest), {free / 1e9:.1f} GB are free. Nothing was touched.")
    return out


# ---------------------------------------------------------------- backups and restores, one at a time
def backup(tag: str, by: str, version: str) -> dict:
    """An infrastructure backup now, pinned (the scheduled clean-up never removes it while the test runs)."""
    if not H["_block"].acquire(blocking=False):
        raise RuntimeError("Busy: another backup or restore is running.")
    t0 = time.time()
    try:
        m = H["_do_backup"](tag, by, "on-demand", version, pinned=True)
    finally:
        H["_block"].release()
    return {"name": m.get("name", ""), "status": m.get("status"), "error": m.get("error", ""),
            "seconds": round(time.time() - t0), "bytes": _size(m.get("name", "")), "version": m.get("version", ""),
            "parts": m.get("parts") or {}}


def restore(name: str, what: str, by: str, version: str) -> dict:
    """An infrastructure restore of a backup; its result (the backup it took first included) and how long it took."""
    if what not in H["RESTORE_WHAT"]:
        raise ValueError(f"--what is one of {', '.join(H['RESTORE_WHAT'])}")
    if not H["_block"].acquire(blocking=False):
        raise RuntimeError("Busy: another backup or restore is running.")
    t0 = time.time()
    try:
        rec, _ = H["new_restore"]("infrastructure", name, what, by)
        r = H["_do_restore"](name, what, by, version, False, rec)
    finally:
        H["_block"].release()
        if is_quiet():
            _page(True)              # a restore ends its own maintenance page: the test's stays up until the test ends
    return {"status": r.get("status"), "error": r.get("error", ""), "before": r.get("before", ""), "restore": r.get("restore", ""),
            "warnings": r.get("warnings", []), "seconds": round(time.time() - t0)}


def _size(name: str) -> int:
    try:
        folder = H["_infra_folder"](name)
    except (FileNotFoundError, ValueError):
        return 0
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(folder) for f in fs)


def backups() -> list[dict]:
    """Every infrastructure backup, newest first."""
    return [{k: b.get(k) for k in ("name", "tag", "kind", "status", "created", "pinned", "bytes", "version")}
            for b in H["list_infra"]()]


def retention(names: list[str]) -> dict:
    """S14: the backups the scheduled clean-up would remove now if it kept only one (the strictest), none of `names`
    among them (pinned ones are never removed nor counted). Nothing is removed."""
    unpinned = [m for m in H["list_infra"]() if not m.get("pinned") and m.get("status") != "running"]
    would = [m["name"] for m in unpinned[1:]]
    return {"would_remove": len(would), "kept": [n for n in names if n not in would], "lost": [n for n in names if n in would]}


def delete(names: list[str]) -> dict:
    """Unpins and deletes the test's own backups."""
    gone, left = [], []
    for n in names:
        try:
            H["pin_backup"](n, False)
            H["delete_infra_backup"](n)
            gone.append(n)
        except (FileNotFoundError, ValueError, OSError) as exc:
            left.append(f"{n}: {exc}")
    return {"deleted": gone, "left": left}


# ---------------------------------------------------------------- the fingerprint
def parse(text: str) -> dict:
    """fingerprint.sh's lines as {"tables": {"db schema.table": [rows, md5]}, "files": {"set/path": sha256}} (pure)."""
    tables: dict[str, list] = {}
    files: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("T "):
            parts = line.split(" ")
            if len(parts) >= 5 and parts[3].isdigit():
                tables[f"{parts[1]} {parts[2]}"] = [int(parts[3]), parts[4]]
        elif line.startswith("F "):
            head, _, rest = line[2:].partition(" ")
            path, _, digest = rest.rpartition(" ")
            if path and digest:
                files[f"{head}/{path}"] = digest
    return {"tables": tables, "files": files}


def fingerprint() -> dict:
    """Every table and file as fingerprint.sh sees them, and the config file's checksum."""
    c = _backup_container()
    r = subprocess.run(["docker", "exec", c["id"], "fingerprint.sh"], capture_output=True, text=True, timeout=3600)
    if r.returncode:
        raise RuntimeError(f"fingerprint.sh failed (exit {r.returncode}): "
                           + ((r.stderr.strip() or "no message; the last line it wrote: " + (r.stdout.strip().splitlines() or ["none"])[-1])[-300:]))
    out = parse(r.stdout)
    try:
        with open(H["CONFIG"], "rb") as f:
            out["files"]["config/eaexplorer.env"] = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        pass
    out["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return out


def mark(sid: str, action: str) -> dict:
    """A marker file in persist/ and the import folder (put), or taken away (remove)."""
    if not re.fullmatch(r"[0-9a-f]{6,32}", sid or ""):
        raise ValueError("the test's id")
    c = _backup_container()
    done = []
    for name, folder in MARK_SETS.items():
        path = f"{folder}/self_test_{sid}_backup_restore.txt"
        cmd = (f"printf '%s\\n' 'EA Explorer backup and restore test {sid}' > {path}" if action == "put" else f"rm -f {path}")
        r = subprocess.run(["docker", "exec", c["id"], "sh", "-c", cmd], capture_output=True, text=True, timeout=60)
        if r.returncode:
            raise RuntimeError(f"{name}: {(r.stderr or r.stdout).strip()[:200]}")
        done.append(f"{name}/self_test_{sid}_backup_restore.txt")
    return {"files": done, "action": action}


# ---------------------------------------------------------------- the command
def cli(args: list[str], version: str) -> int:
    """ops.py brtest <command>: one JSON line at the end ({"error": ...} and exit 1 when it fails)."""
    cmd, rest = (args[0] if args else ""), [a for a in args[1:] if a != version and a != "--version"]
    by = "eax test backup-restore"
    try:
        if cmd == "quiet" and rest:
            out = quiet(rest[0], by)
        elif cmd == "ready":
            out = ready()
        elif cmd == "backup":
            out = backup(rest[0] if rest else "backup-restore-test", by, version)
        elif cmd == "restore" and rest:
            what = rest[rest.index("--what") + 1] if "--what" in rest else "full"
            if not NAME.match(rest[0]):
                raise ValueError("a backup's name")
            out = restore(rest[0], what, by, version)
        elif cmd == "fingerprint":
            out = fingerprint()
        elif cmd == "mark" and len(rest) >= 2:
            out = mark(rest[0], rest[1])
        elif cmd == "retention":
            out = retention(rest)
        elif cmd == "backups":
            out = {"backups": backups()}
        elif cmd == "delete":
            out = delete([n for n in rest if NAME.match(n)])
        else:
            out = {"error": f"brtest: unknown command {cmd!r}: " + (__doc__ or "").split("\n\n")[1]}
    except Exception as exc:  # noqa: BLE001 - said in words to the test, which stops there
        out = {"error": str(exc)[:1000]}
    print(json.dumps(out), flush=True)
    return 1 if out.get("error") else 0
