"""The logs kept on disk, their backups and their cleaning (owner, 12 Nov 2026: R2.30 "backup and clean logs", R2.32
"logs to be written to a mounted disk", R2.31 "see on web per container").

  logs/containers/<service>/<YYYY-MM-DD>.log   every container's log, one file per day, secrets masked; written by the
                                               operations helper every minute (ship), so a container made again (a
                                               clean-restart, an update) loses nothing
  work/backups/logs/<when>-logs.zip            a log backup: the containers' daily files and eax's own logs (work/logs)

The logs folder is EAX_LOGS_DIR (in the config file: a mounted disk on a server), else logs/ beside work/; like
persist/, no cleanup, clean-run or clean-restart empties it. Used by eax (eax logs backup | clean) and by the operations
helper (the web), so both do exactly the same. Plain files, nothing in a database (D248).
"""

from __future__ import annotations

import json
import os
import re
import time
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import persist

ROOT = Path(__file__).resolve().parent.parent
# a day's file, or a part of it closed at its size (2026-11-15.1.log), compressed once closed (.log.gz) (R5.6)
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}(\.\d+)?\.log(\.gz)?$")
ZIP = re.compile(r"^\d{8}T\d{6}Z-logs(-[a-z0-9-]+)?\.zip$")
LEVELS = ("debug", "info", "warning", "error", "critical")
MAX_MB = 50                 # R5.6's size, kept only for a config file that still sets EAX_LOG_FILE_MB
# R5.26 (owner, 15 Nov 2026, 19:03: "The logs in the entire system should be configurable form a log page. Default being
# rolling with 100kb size"; 19:31: Docker's own copy included): every log file rolls at this size, set on System Admin >
# Logs and kept in the logs folder (.rolling.json), so it outlives a clean-restart like the logs themselves
FILE_KB = 100               # our log files: the containers', the web log and its debug lines
DOCKER_KB = 100             # Docker's own copy of each container's output (taken at the next eax up)
DOCKER_FILES = 5            # how many of Docker's files each container keeps
KB_RANGE = (10, 1024 * 1024)
ROLLING = ".rolling.json"
KEEP_DAYS = 7               # logs older than this are deleted every night (R5.6; System Admin > Settings)
_MASKS = [(re.compile(r"((?:PASSWORD|SECRET|TOKEN|_KEY|URLENC)[A-Za-z_]*\s*[:=]\s*)\S+", re.I), r"\1****"),
          (re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:/\s]+:)[^@\s]+@"), r"\1****@"),
          (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1****"),
          (re.compile(r'("(?:password|secret|token)"\s*:\s*")[^"]*"', re.I), r'\1****"')]


def mask(line: str) -> str:
    """A log line with what looks like a secret hidden (passwords, tokens, keys, a connection string's password)."""
    for rx, rep in _MASKS:
        line = rx.sub(rep, line)
    return line


def folder(root: Path | str | None = None) -> Path:
    """The logs folder: EAX_LOGS_DIR from the environment or the config file, else logs/ beside work/."""
    root = Path(root) if root else ROOT
    given = os.environ.get("EAX_LOGS_DIR") or persist._config_value(root, "EAX_LOGS_DIR")
    if not given:                                    # one base folder for the data (R5.4, D687): <base>/logs
        from . import datafolders
        given = next((p.value for p in datafolders.resolve(root=root)[1] if p.key == "EAX_LOGS_DIR" and p.source == "base"), "")
    p = Path(given) if given else root / "logs"
    return p if p.is_absolute() else root / p


def level_of(line: str) -> str:
    """debug, info, warning or error, from the words a line carries (info when it says none)."""
    low = line.lower()
    if re.search(r"\b(critical|fatal|panic|emerg(ency)?)\b", low):
        return "critical"
    if re.search(r"\b(error|exception|traceback|failed)\b", low):
        return "error"
    if re.search(r"\b(warn|warning)\b", low):
        return "warning"
    if re.search(r"\bdebug\b", low):
        return "debug"
    return "info"


# ---------------------------------------------------------------- written every minute (the operations helper)
def ship(base: Path, containers: list[dict], read_since, now: float | None = None) -> dict[str, int]:
    """Appends each container's new log lines to its file of the day. containers: {id, service}; read_since(id, since)
    gives its lines with their timestamps ("2026-11-13T05:00:01.123456789Z text") since an RFC 3339 time. Where each
    container got to is kept in .shipped.json, so nothing is written twice."""
    state_file = base / ".shipped.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    now = now or time.time()
    limit = max_bytes(base)
    out: dict[str, int] = {}
    for c in containers:
        last = state.get(c["id"]) or datetime.fromtimestamp(now - 600, UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        lines = [ln for ln in read_since(c["id"], last) if ln[:30] > last]
        n = 0
        for ln in sorted(lines):
            day = ln[:10] if re.match(r"^\d{4}-\d{2}-\d{2}T", ln) else datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%d")
            f = base / "containers" / c["service"] / f"{day}.log"
            f.parent.mkdir(parents=True, exist_ok=True)
            rotate(f, limit)
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(mask(ln.rstrip("\n")) + "\n")
            n += 1
            state[c["id"]] = ln.split(" ", 1)[0][:30]
        out[c["service"]] = out.get(c["service"], 0) + n
    base.mkdir(parents=True, exist_ok=True)
    roll_web(base, now)
    compress_closed(base, now)
    tmp = state_file.with_name(".shipped.json.tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, state_file)
    return out


def _kb(value, default: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(v, KB_RANGE[0]), KB_RANGE[1])


def rolling(base: Path | None = None) -> dict:
    """The sizes the logs roll at: {file_kb, docker_kb, docker_files, set_by, set_at}. The logs folder's .rolling.json
    (the Logs page) wins; else the config file (EAX_LOG_FILE_KB, or R5.6's EAX_LOG_FILE_MB); else 100 KB (R5.26)."""
    out = {"file_kb": FILE_KB, "docker_kb": DOCKER_KB, "docker_files": DOCKER_FILES, "set_by": "", "set_at": ""}
    if os.environ.get("EAX_LOG_FILE_KB"):
        out["file_kb"] = _kb(os.environ["EAX_LOG_FILE_KB"], FILE_KB)
    elif os.environ.get("EAX_LOG_FILE_MB"):
        out["file_kb"] = _kb(_kb(os.environ["EAX_LOG_FILE_MB"], 0) and int(os.environ["EAX_LOG_FILE_MB"]) * 1024, FILE_KB)
    if os.environ.get("EAX_DOCKER_LOG_KB"):
        out["docker_kb"] = _kb(os.environ["EAX_DOCKER_LOG_KB"], DOCKER_KB)
    if base is not None:
        try:
            got = json.loads((Path(base) / ROLLING).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            got = {}
        if isinstance(got, dict):
            for k, d in (("file_kb", out["file_kb"]), ("docker_kb", out["docker_kb"])):
                if k in got:
                    out[k] = _kb(got[k], d)
            out["set_by"], out["set_at"] = str(got.get("set_by") or ""), str(got.get("set_at") or "")
    return out


def set_rolling(base: Path, file_kb, docker_kb, by: str) -> dict:
    """Saves the sizes the logs roll at (System Admin > Logs, R5.26): KB, 10 to 1,048,576 (1 GB)."""
    clean = {}
    for k, v in (("file_kb", file_kb), ("docker_kb", docker_kb)):
        try:
            n = int(v)
        except (TypeError, ValueError):
            raise ValueError(f"{k}: a whole number of KB.") from None
        if not KB_RANGE[0] <= n <= KB_RANGE[1]:
            raise ValueError(f"{k}: {KB_RANGE[0]} KB to {KB_RANGE[1]:,} KB (1 GB).")
        clean[k] = n
    Path(base).mkdir(parents=True, exist_ok=True)
    body = {**clean, "set_by": by, "set_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    tmp = Path(base) / (ROLLING + ".tmp")
    tmp.write_text(json.dumps(body), encoding="utf-8")
    os.replace(tmp, Path(base) / ROLLING)
    return rolling(base)


def max_bytes(base: Path | None = None) -> int:
    """How large a log file grows before it is rolled over (R5.26: 100 KB unless set)."""
    return rolling(base)["file_kb"] * 1024


def rotate(f: Path, limit: int | None = None, compress: bool = True) -> Path | None:
    """A day's file past its size is closed (renamed <day>.<n>.log, or debug-<day>.<n>.log, and compressed) and a new
    one begun (R5.6). compress=False for a file another program writes (the front door's web log): it may still write a
    line or two to the renamed file, so that one is compressed when the day ends."""
    limit = limit or max_bytes()
    if not f.is_file() or f.stat().st_size < limit:
        return None
    stem = f.name[:-len(".log")]                                    # 2026-11-15 or debug-2026-11-15
    n = 1
    while (f.parent / f"{stem}.{n}.log.gz").exists() or (f.parent / f"{stem}.{n}.log").exists():
        n += 1
    closed = f.with_name(f"{stem}.{n}.log")
    os.replace(f, closed)
    return _gzip(closed) if compress else closed


def roll_web(base: Path, now: float | None = None) -> int:
    """The web log of today and its debug lines rolled at the size (R5.26); the operations helper does it every
    minute. The front door reopens its file by name within a minute (open_log_file_cache valid=60s)."""
    root = base / "web"
    if not root.is_dir():
        return 0
    today = datetime.fromtimestamp(now or time.time(), UTC).strftime("%Y-%m-%d")
    limit, n = max_bytes(base), 0
    for name in (f"{today}.log", f"debug-{today}.log"):
        if rotate(root / name, limit, compress=False):
            n += 1
    return n


def _gzip(f: Path) -> Path:
    import gzip
    import shutil
    out = f.with_name(f.name + ".gz")
    with open(f, "rb") as src, gzip.open(out, "wb") as dst:
        shutil.copyfileobj(src, dst)
    f.unlink()
    return out


def compress_closed(base: Path, now: float | None = None) -> int:
    """Every file of a day before today compressed (R5.6: "compressed when closed"); the web log's too."""
    today = datetime.fromtimestamp(now or time.time(), UTC).strftime("%Y-%m-%d")
    n = 0
    for sub in ("containers", "web"):
        root = base / sub
        if not root.is_dir():
            continue
        for f in root.rglob("*.log"):
            if DAY.match(f.name) and f.name[:10] < today:
                try:
                    _gzip(f)
                    n += 1
                except OSError:
                    pass
    return n


def _lines(f: Path):
    import gzip
    if not f.name.endswith(".gz") and not f.exists() and f.with_name(f.name + ".gz").exists():
        f = f.with_name(f.name + ".gz")             # compressed since it was listed (D939)
    opener = gzip.open if f.name.endswith(".gz") else open
    try:
        with opener(f, "rt", encoding="utf-8", errors="replace") as fh:
            yield from fh
    except FileNotFoundError:
        return                                      # closed and renamed since it was listed: its new name is read too


def _day_files(folder: Path, day: str) -> list[Path]:
    """A day's files in order: its closed parts, then the open one."""
    if not folder.is_dir():
        return []
    found = [f for f in folder.iterdir() if DAY.match(f.name) and f.name[:10] == day]
    return sorted(found, key=lambda f: (0, int(f.name.split(".")[1])) if f.name.split(".")[1].isdigit() else (1, 0))


# ---------------------------------------------------------------- reading (the web, R2.31)
# the sizes of the compressed files, which never change once made (D948): a file's size is read once, not at every
# listing. At 100 KB a file (R5.26) the laptop kept over 5,000 of them, and reading each one's size through Docker
# Desktop's folder sharing took over 30 s: the Logs page's list, and the self-test's call of it, timed out (runs 20, 21)
_GZ_SIZES: dict[str, int] = {}


def files(base: Path, service: str = "") -> list[dict]:
    """The daily files kept: service, day, size; the newest first."""
    out = []
    root = base / "containers"
    if not root.is_dir():
        return out
    seen: set[str] = set()
    for d in sorted(root.iterdir()):
        if not d.is_dir() or (service and d.name != service):
            continue
        sizes: dict[str, int] = {}
        for f in d.iterdir():
            if DAY.match(f.name):
                key = f"{d.name}/{f.name}"
                seen.add(key)
                try:
                    size = _GZ_SIZES.get(key) if f.name.endswith(".gz") else None
                    if size is None:
                        size = f.stat().st_size
                        if f.name.endswith(".gz"):
                            _GZ_SIZES[key] = size
                except FileNotFoundError:
                    # closed and compressed between the listing and here (its .log.gz is listed or comes next):
                    # self-test 18's IT Admin read the files list at that instant and got a server error (D939)
                    continue
                sizes[f.name[:10]] = sizes.get(f.name[:10], 0) + size
        out += [{"service": d.name, "day": day, "size": size} for day, size in sizes.items()]
    if not service:                                  # files deleted (kept days passed) leave the memory too
        for gone in [k for k in _GZ_SIZES if k not in seen]:
            _GZ_SIZES.pop(gone, None)
    return sorted(out, key=lambda x: (x["day"], x["service"]), reverse=True)


def read(base: Path, services: list[str], day: str, level: str = "", q: str = "", since: str = "", until: str = "",
         page: int = 0, size: int = 1000) -> dict:
    """The lines of one day of one or several containers, merged by time, filtered by level (that level and worse),
    words and time (HH:MM), a page at a time (never the whole file at once in the answer)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", day or ""):
        raise ValueError("Give the day as YYYY-MM-DD.")
    worse = LEVELS[LEVELS.index(level):] if level in LEVELS else LEVELS
    rows = []
    for s in services:
        if not re.match(r"^[a-z0-9_-]+$", s):
            raise ValueError(f"No container {s!r}.")
        for ln in (x for f in _day_files(base / "containers" / s, day) for x in _lines(f)):
            ln = ln.rstrip("\n")
            t = ln[11:16]
            if (since and t < since) or (until and t > until):
                continue
            lv = level_of(ln)
            if lv not in worse or (q and q.lower() not in ln.lower()):
                continue
            rows.append({"service": s, "line": ln, "level": lv})
    rows.sort(key=lambda r: r["line"][:30])
    total = len(rows)
    start = max(0, int(page)) * size
    return {"day": day, "services": services, "total": total, "page": int(page), "pages": (total + size - 1) // size,
            "lines": rows[start:start + size]}


# ---------------------------------------------------------------- backing up and cleaning (R2.30)
def backup(base: Path, own_logs: Path, dest: Path, tag: str = "") -> dict:
    """One zip of every container's daily files and eax's own logs, in dest (work/backups/logs)."""
    dest.mkdir(parents=True, exist_ok=True)
    name = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-logs" + (f"-{re.sub(r'[^a-z0-9-]', '', tag.lower())}" if tag else "") + ".zip"
    n = 0
    with zipfile.ZipFile(dest / name, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in ((base / "containers", "containers"), (base / "web", "web"), (own_logs, "eax")):
            if not src.is_dir():
                continue
            for f in sorted(src.rglob("*")):
                if f.is_file() and not f.name.startswith("."):
                    z.write(f, f"{arc}/{f.relative_to(src)}")
                    n += 1
    return {"file": name, "files": n, "size": (dest / name).stat().st_size}


def clean(base: Path, own_logs: Path, zips: Path, days: int, now: float | None = None) -> dict:
    """Deletes the daily files, eax's own logs and the log backups older than `days` (0 keeps them); returns what went."""
    if int(days) <= 0:
        return {"deleted": [], "kept_days": 0}
    cut = (now or time.time()) - int(days) * 86400
    cut_day = datetime.fromtimestamp(cut, UTC).strftime("%Y-%m-%d")
    gone: list[str] = []
    for sub in ("containers", "web"):
        for f in (base / sub).rglob("*.log*") if (base / sub).is_dir() else []:
            if (DAY.match(f.name) or WEB_DAY.match(f.name)) and f.name.removeprefix("debug-")[:10] < cut_day:
                f.unlink()
                gone.append(f"{sub}/{f.relative_to(base / sub).as_posix()}")
    for d, label in ((own_logs, "work/logs"), (zips, "backups/logs")):
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.is_file() and f.stat().st_mtime < cut and (d is not zips or ZIP.match(f.name)):
                f.unlink()
                gone.append(f"{label}/{f.name}")
    return {"deleted": sorted(gone), "kept_days": int(days)}


def kept_backups(base: Path) -> Path:
    """Where the log backups taken before a reset go: inside the logs folder, which no reset empties (R2.30)."""
    return base / "backups"


def default_keep_days(deployment: str) -> int:
    """7 days, laptop and server alike (R5.6; owner, 14 Nov 2026: "Logs are deleted once every 7 days in schedule";
    R2.30 had 14 on a laptop and 90 on a server)."""
    return KEEP_DAYS


def clear(base: Path) -> list[str]:
    """Every container log and web log deleted (clean-run and clean-restart, R5.6: "Logs get cleaned in clean-run"),
    after a log backup into the logs folder's own backups/ (which stays)."""
    import shutil
    gone = []
    for sub in ("containers", "web"):
        if (base / sub).is_dir():
            shutil.rmtree(base / sub, ignore_errors=True)
            gone.append(sub)
    (base / ".shipped.json").unlink(missing_ok=True)
    return gone


def clean_range(base: Path, what: str, start: str = "", end: str = "") -> dict:
    """Deleted from the page (R5.6): a period of days (start to end, inclusive), everything before a day, or all; the
    container logs and the web log alike. A log backup is taken first by the caller."""
    if what not in ("period", "before", "all"):
        raise ValueError("what: period, before or all.")
    for d in ([start, end] if what == "period" else [start] if what == "before" else []):
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d or ""):
            raise ValueError("Give the days as YYYY-MM-DD.")
    gone: list[str] = []
    for sub in ("containers", "web"):
        for f in (base / sub).rglob("*.log*") if (base / sub).is_dir() else []:
            if not (DAY.match(f.name) or WEB_DAY.match(f.name)):
                continue
            day = f.name.removeprefix("debug-")[:10]
            if what == "all" or (what == "before" and day < start) or (what == "period" and start <= day <= end):
                f.unlink()
                gone.append(f"{sub}/{f.relative_to(base / sub).as_posix()}")
    return {"deleted": sorted(gone), "what": what, "start": start, "end": end}


# ---------------------------------------------------------------- the web log (R5.6)
# logs/web/<YYYY-MM-DD>.log: one JSON line for every call to the API and MCP, written by the front door (nginx):
#   {time, address, who, method, path, status, seconds, bytes, request_id, host}
# logs/web/debug-<YYYY-MM-DD>.log: with web log debug on (off by default, for a time), the API's input and answer too,
# every password, secret, token, key and personal field masked.
WEB_DAY = re.compile(r"^(debug-)?\d{4}-\d{2}-\d{2}(\.\d+)?\.log(\.gz)?$")
WEB_FIELDS = ("time", "address", "who", "method", "path", "status", "seconds", "bytes", "request_id", "host")


def web_files(base: Path) -> list[dict]:
    """The web log's days, with their sizes."""
    root = base / "web"
    if not root.is_dir():
        return []
    sizes: dict[tuple[str, bool], int] = {}
    for f in root.iterdir():
        if WEB_DAY.match(f.name):
            debug = f.name.startswith("debug-")
            day = f.name.removeprefix("debug-")[:10]
            sizes[(day, debug)] = sizes.get((day, debug), 0) + f.stat().st_size
    return sorted(({"day": d, "debug": dbg, "size": s} for (d, dbg), s in sizes.items()),
                  key=lambda x: (x["day"], x["debug"]), reverse=True)


def web_rows(base: Path, day: str) -> list[dict]:
    """A day of the web log as rows."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", day or ""):
        raise ValueError("Give the day as YYYY-MM-DD.")
    rows = []
    for f in _day_files(base / "web", day):
        for ln in _lines(f):
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            try:
                r["status"] = int(r.get("status") or 0)
                r["seconds"] = float(r.get("seconds") or 0)
            except (TypeError, ValueError):
                continue
            rows.append({k: r.get(k, "") for k in WEB_FIELDS})
    return rows


def web_read(base: Path, day: str, since: str = "", until: str = "", who: str = "", path: str = "", status: str = "",
             sort: str = "time", page: int = 0, size: int = 500) -> dict:
    """The web log of a day, filtered by time (HH:MM), person, path (words), status (a code, 4xx, 5xx or errors) and
    sorted by time or slowest first; with what is slowest and most failing summed."""
    rows = web_rows(base, day)
    out = []
    for r in rows:
        t = str(r["time"])[11:16]
        if (since and t < since) or (until and t > until):
            continue
        if who and who.lower() not in str(r["who"]).lower():
            continue
        if path and path.lower() not in str(r["path"]).lower():
            continue
        s = r["status"]
        if status == "errors" and s < 400 or status in ("4xx", "5xx") and s // 100 != int(status[0]) \
                or status.isdigit() and s != int(status):
            continue
        out.append(r)
    out.sort(key=(lambda r: -r["seconds"]) if sort == "slowest" else (lambda r: str(r["time"])))
    start = max(0, int(page)) * size
    return {"day": day, "total": len(out), "page": int(page), "pages": (len(out) + size - 1) // size,
            "rows": out[start:start + size], "summary": web_summary(out)}


def _route(path: str) -> str:
    """A path with its ids made general, so calls to the same route add up (/api/v1/models/<id>/entities)."""
    return re.sub(r"/([0-9a-f]{8}-[0-9a-f-]{27,}|\d+|[0-9a-f]{24,})(?=/|$)", "/<id>", str(path))


def web_summary(rows: list[dict]) -> dict:
    """The web log's rows by route: calls, errors and times."""
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(f"{r['method']} {_route(r['path'])}", []).append(r)
    stats = []
    for route, rs in by.items():
        times = sorted(x["seconds"] for x in rs)
        p95 = times[min(len(times) - 1, int(len(times) * 0.95))]
        stats.append({"route": route, "calls": len(rs), "average": round(sum(times) / len(times), 3), "p95": p95,
                      "errors": sum(1 for x in rs if x["status"] >= 500), "refused": sum(1 for x in rs if 400 <= x["status"] < 500)})
    return {"calls": len(rows), "errors": sum(1 for r in rows if r["status"] >= 500),
            "slowest": sorted(stats, key=lambda x: -x["p95"])[:10],
            "failing": sorted((x for x in stats if x["errors"]), key=lambda x: -x["errors"])[:10]}


def web_csv(rows: list[dict]) -> str:
    """Web log rows as CSV."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(WEB_FIELDS))
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in WEB_FIELDS})
    return buf.getvalue()


def web_zip(base: Path, start: str, end: str) -> bytes:
    """The raw web log files of a period, zipped."""
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((base / "web").iterdir()) if (base / "web").is_dir() else []:
            if WEB_DAY.match(f.name) and start <= f.name.removeprefix("debug-")[:10] <= end:
                z.write(f, f"web/{f.name}")
    return buf.getvalue()


def older_than(days: int) -> str:
    """The day `days` days ago."""
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- eax's own logs and the log backups, read (R2.31)
SAFE = re.compile(r"^[A-Za-z0-9._ -]{1,120}$")


def own_files(own_logs: Path, zips: Path) -> dict:
    """eax's own logs (work/logs: up, start-later, test, ...) and the log backups (work/backups/logs), newest first."""
    def listing(d: Path, pat: str) -> list[dict]:
        if not d.is_dir():
            return []
        return sorted(({"name": f.name, "size": f.stat().st_size, "changed": f.stat().st_mtime}
                       for f in d.glob(pat) if f.is_file()), key=lambda x: x["changed"], reverse=True)
    return {"own": listing(own_logs, "*.log"), "backups": listing(zips, "*-logs*.zip")}


def _page(lines: list[str], q: str, page: int, size: int) -> dict:
    rows = [{"line": mask(ln), "level": level_of(ln)} for ln in lines if not q or q.lower() in ln.lower()]
    start = max(0, int(page)) * size
    return {"total": len(rows), "page": int(page), "pages": (len(rows) + size - 1) // size, "lines": rows[start:start + size]}


def read_own(own_logs: Path, name: str, q: str = "", page: int = 0, size: int = 1000) -> dict:
    """One of eax's own logs, a page at a time, secrets masked."""
    if not SAFE.match(name or "") or not name.endswith(".log"):
        raise ValueError("Choose one of eax's logs.")
    f = own_logs / name
    if not f.is_file():
        raise ValueError(f"No log {name}.")
    return {"name": name, **_page(f.read_text(encoding="utf-8", errors="replace").splitlines(), q, page, size)}


def read_backup(zips: Path, name: str, member: str = "", q: str = "", page: int = 0, size: int = 1000) -> dict:
    """A log backup: its files, or one of them read a page at a time."""
    if not ZIP.match(name or ""):
        raise ValueError("Choose one of the log backups.")
    f = zips / name
    if not f.is_file():
        raise ValueError(f"No log backup {name}.")
    with zipfile.ZipFile(f) as z:
        members = [i.filename for i in z.infolist() if not i.is_dir()]
        if not member:
            return {"name": name, "members": members}
        if member not in members:
            raise ValueError(f"{name} has no {member}.")
        text = z.read(member).decode("utf-8", errors="replace")
    return {"name": name, "member": member, "members": members, **_page(text.splitlines(), q, page, size)}
