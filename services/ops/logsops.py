"""The logs on disk, for the web (R2.30, R2.31, R2.32): the operations helper writes every container's new log lines to
its file of the day every minute, and lists, reads, backs up and cleans them for System Admin. The work is in
eaxcli/logkeep.py, shared with `eax logs backup | clean`.

  GET  /logs/files?service=       the daily files kept
  GET  /logs/own?name=|backup=&member=&q=&page=   eax's own logs (work/logs) and the log backups: listed, or one read
  GET  /logs/read?services=a,b&day=YYYY-MM-DD&level=&q=&since=HH:MM&until=HH:MM&page=N   their lines, merged by time
  POST /logs/backup {tag, by}     one zip of them and eax's own logs in work/backups/logs
  POST /logs/clean {days, by}     delete them and the log backups older than `days`
  GET  /logs/web?day=&since=&until=&who=&path=&status=&sort=&page=   the web log of a day, filtered, with what is
                                  slowest and most failing (R5.6); /logs/web/files the days kept; /logs/web/csv?day=
                                  (with the same filters) as CSV; /logs/web/zip?start=&end= the raw files (base64)
  POST /logs/clean-range {what: period|before|all, start, end, by}   a log backup first, then delete (R5.6)
  GET  /logs/rolling              the sizes the logs roll at {file_kb, docker_kb, docker_files} (R5.26)
  POST /logs/rolling {file_kb, docker_kb, by}   saved in the logs folder; Docker's into the config file (EAX_DOCKER_LOG_KB,
                                  a dated copy first), taken by every container at the next eax up
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = os.environ.get("EAX_REPO_MOUNT", "/eax-repo")
WORK = Path(os.environ.get("EAX_WORK_MOUNT", "/eax-work"))
LOGS = Path(os.environ.get("EAX_LOGS_MOUNT", "/eax-logs"))
BACKUPS = Path(os.environ.get("EAX_BACKUPS_MOUNT", "/backups"))
sys.path.insert(0, REPO)
try:
    from eaxcli import logkeep as K
except Exception:  # noqa: BLE001 - an older compose file without the eaxcli mount
    K = None

hooks: dict = {}       # set by ops.py: containers


def _need() -> None:
    if K is None:
        raise RuntimeError("The logs need eaxcli mounted into the operations helper (docker-compose.yml).")


def read_since(cid: str, since: str) -> list[str]:
    """A container's log lines since a time."""
    r = subprocess.run(["docker", "logs", "--timestamps", "--since", since, cid], capture_output=True, text=True,
                       errors="replace", timeout=60)
    return (r.stdout + r.stderr).splitlines()


def ship_once() -> dict:
    """Copies every container's new log lines into the day files."""
    _need()
    if not LOGS.is_dir():
        return {}
    running = [c for c in hooks["containers"]() if c.get("state") == "running"]
    return K.ship(LOGS, [{"id": c["id"], "service": c["key"]} for c in running], read_since)


def shipper(pause: float = 60) -> None:
    """Every minute, for as long as the helper runs: the new lines of every running container to its file of the day."""
    while True:
        try:
            ship_once()
        except Exception as exc:  # noqa: BLE001 - a disk full or Docker busy: logged, tried again next minute
            print(f"logs: could not write the containers' logs to {LOGS}: {exc}", flush=True)
        time.sleep(pause)


def start() -> None:
    """Starts copying the logs in the background."""
    threading.Thread(target=shipper, daemon=True).start()


def files(service: str = "") -> dict:
    """The kept log files (one container's)."""
    _need()
    return {"files": K.files(LOGS, service), "folder": os.environ.get("EAX_LOGS_DIR_HOST", "logs/")}


def read(args: dict) -> dict:
    """A day of some containers' logs, merged."""
    _need()
    services = [s for s in str(args.get("services") or "").split(",") if s]
    if not services:
        raise ValueError("Choose one or more containers.")
    return K.read(LOGS, services, str(args.get("day") or ""), str(args.get("level") or ""), str(args.get("q") or ""),
                  str(args.get("since") or ""), str(args.get("until") or ""), int(args.get("page") or 0))


def own(args: dict) -> dict:
    """eax's own logs and the log backups: the list, or one of them read (R2.31)."""
    _need()
    if args.get("backup"):
        name = str(args["backup"])
        where = K.kept_backups(LOGS) if (K.kept_backups(LOGS) / name).is_file() else BACKUPS / "logs"
        return K.read_backup(where, name, str(args.get("member") or ""), str(args.get("q") or ""), int(args.get("page") or 0))
    if args.get("name"):
        return K.read_own(WORK / "logs", str(args["name"]), str(args.get("q") or ""), int(args.get("page") or 0))
    got = K.own_files(WORK / "logs", BACKUPS / "logs")
    got["backups"] += K.own_files(WORK / "logs", K.kept_backups(LOGS))["backups"]   # those taken before a reset
    return got


def backup(body: dict) -> dict:
    """Backs the logs up in one zip."""
    _need()
    return K.backup(LOGS, WORK / "logs", BACKUPS / "logs", str(body.get("tag") or ""))


def rolling() -> dict:
    """The sizes the logs roll at, and whether Docker's has still to be taken (the config file changed, not yet up)."""
    _need()
    out = K.rolling(LOGS)
    out["docker_kb_running"] = _docker_kb_running()
    return out


def _docker_kb_running() -> int | None:
    """Docker's size for the containers as they run now (the api's), in KB; None when unknown."""
    try:
        api = next((c for c in hooks["containers"]() if c.get("key") == "api"), None)
        if not api:
            return None
        r = subprocess.run(["docker", "inspect", "--format", "{{index .HostConfig.LogConfig.Config \"max-size\"}}", api["id"]],
                           capture_output=True, text=True, timeout=20)
        v = r.stdout.strip().lower()
        n = float(v[:-1]) if v[-1:] in "kmg" else float(v)
        return int(n * {"k": 1, "m": 1024, "g": 1024 * 1024}.get(v[-1:], 1 / 1024))
    except Exception:  # noqa: BLE001 - shown as unknown
        return None


def set_rolling(body: dict) -> dict:
    """Saves the sizes (System Admin > Logs, R5.26): ours at once; Docker's in the config file, for the next eax up."""
    _need()
    by = str(body.get("by") or "")
    before = K.rolling(LOGS)
    out = K.set_rolling(LOGS, body.get("file_kb"), body.get("docker_kb"), by)
    if out["docker_kb"] != before["docker_kb"] or not (WORK / "eaexplorer.env").exists() \
            or f"EAX_DOCKER_LOG_KB={out['docker_kb']}" not in (WORK / "eaexplorer.env").read_text(encoding="utf-8", errors="replace"):
        hooks["set_config"]("EAX_DOCKER_LOG_KB", str(out["docker_kb"]), by or "logs-page", "log-sizes")
    out["docker_kb_running"] = _docker_kb_running()
    return out


def clean(body: dict) -> dict:
    """Deletes logs and log backups older than some days."""
    _need()
    out = K.clean(LOGS, WORK / "logs", BACKUPS / "logs", int(body.get("days") or 0))
    out["deleted"] += K.clean(LOGS, WORK / "logs", K.kept_backups(LOGS), int(body.get("days") or 0))["deleted"]
    return out


def web(path: str, q: dict) -> dict:
    """The web log (R5.6): read, its files, a CSV of a filtered day, or the raw files of a period zipped (base64)."""
    _need()
    if path == "/logs/web/files":
        return {"files": K.web_files(LOGS)}
    if path == "/logs/web/zip":
        import base64
        data = K.web_zip(LOGS, str(q.get("start") or ""), str(q.get("end") or q.get("start") or ""))
        return {"name": f"web-log-{q.get('start')}-{q.get('end') or q.get('start')}.zip", "zip": base64.b64encode(data).decode()}
    out = K.web_read(LOGS, str(q.get("day") or ""), str(q.get("since") or ""), str(q.get("until") or ""),
                     str(q.get("who") or ""), str(q.get("path") or ""), str(q.get("status") or ""),
                     str(q.get("sort") or "time"), int(q.get("page") or 0), size=10 ** 9 if path == "/logs/web/csv" else 500)
    if path == "/logs/web/csv":
        return {"name": f"web-log-{out['day']}.csv", "csv": K.web_csv(out["rows"])}
    return out


def clean_range(body: dict) -> dict:
    """Delete from the page (R5.6): a log backup first (D625), then a period, everything before a day, or all."""
    _need()
    taken = K.backup(LOGS, WORK / "logs", BACKUPS / "logs", "before-delete")
    out = K.clean_range(LOGS, str(body.get("what") or ""), str(body.get("start") or ""), str(body.get("end") or ""))
    return out | {"backup": taken["file"]}
