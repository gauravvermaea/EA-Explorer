"""eax test commands (R9.14; owner, 22 Nov 2026, 09:51: "and then we have another eax test commands Which actually tests
the commands and ensure they are working"; D854).

Each eax command that is safe to run on a running installation is run for real, as a person would type it: through
this machine's own launcher (eax.ps1 on Windows, eax.sh elsewhere), with a time limit, checking its exit code and words
its output must hold. Commands that change everything, ask questions, open a screen, follow a log until stopped or run
for hours are not run here; each is in NOT_RUN with why, and a unit test fails when a command of the catalogue is in
neither list, so a new command is never missed. Their pipelines are checked by `eax test jenkins` (R9.13).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from .core import ROOT, WORK, Failure, say, setting

# (the command line after eax, words its output must hold (any case), seconds allowed, only on a laptop)
CASES: list[tuple[list[str], list[str], int, bool]] = [
    (["help"], ["status"], 60, False),
    (["help", "status"], ["lists every container"], 60, False),
    (["status"], ["ea explorer"], 180, False),
    (["status", "problems"], [], 180, False),
    (["errors", "EAX-AUTH-001"], ["eax-auth-001"], 60, False),
    (["errors", "backup"], [], 60, False),
    (["url"], ["https://"], 60, False),
    (["logins"], [], 60, True),
    (["check"], [], 120, False),
    (["databases"], [], 180, False),
    (["persist", "list"], [], 60, False),
    (["backups"], [], 120, False),
    (["restores"], [], 120, False),
    (["packs", "status"], [], 120, False),
    (["import"], [], 120, False),
    (["services"], ["reports"], 120, False),
    (["servers"], [], 120, False),
    (["secrets", "show"], [], 120, False),
    (["secrets", "schedule"], [], 120, False),
    (["schedule", "list"], [], 60, False),
    (["certs", "list"], [], 120, False),
    (["certs", "check"], [], 120, False),          # R11: each service can read its key (password mode: says so)
    (["jenkins", "status"], ["jenkins"], 120, False),
    (["setup"], [], 60, False),
    (["access", "admins"], [], 180, False),
    (["settings", "parts"], [], 120, False),
    (["allow", "show"], [], 120, False),
    (["hostname", "show"], [], 60, False),
    (["folders", "show"], [], 120, False),
    (["site", "check"], [], 300, False),
    (["jobs", "list"], [], 120, False),
    (["jobs", "history", "5"], [], 120, False),
    (["ticket", "list"], [], 120, False),
    (["estimate", "--users", "50", "--models", "10", "--projects", "5"], ["ram"], 120, False),
    (["optimise", "last"], [], 120, False),
    (["db", "check"], [], 300, False),
    (["footprint", "--history", "7"], [], 120, False),
    (["test", "summary"], [], 180, False),
    (["diag"], [], 600, False),
    (["images", "check", "--no-tell"], ["images"], 900, False),
]

# every other command of the catalogue, and why it is not run here
NOT_RUN: dict[str, str] = {
    "up": "starts everything (the test needs it running)",
    "stop": "stops EA Explorer",
    "restart": "restarts EA Explorer",
    "cleanup": "deletes everything",
    "clean-restart": "deletes everything and starts again",
    "clean-run": "deletes everything and starts again",
    "clean-debug": "deletes everything and starts in debug",
    "debug": "starts EA Explorer in debug mode",
    "maintenance": "puts the maintenance page up for everyone",
    "sonar": "starts SonarQube (eax test sonar covers the scan)",
    "logs": "follows the logs until stopped",
    "measure": "restarts and measures memory for twenty minutes or more",
    "dev": "the developer's check: lint and every unit test, run on its own (eax dev check)",
    "backup": "takes a backup (eax test backup-restore covers it)",
    "app-backup": "takes an application backup (eax test backup-restore covers it)",
    "restore": "restores everything",
    "restore-app": "restores the application",
    "restore-model": "asks which model to restore",
    "restore-log": "needs a restore's id",
    "delete-backup": "deletes a backup",
    "delete-restore": "deletes a restore's record",
    "stop-backup": "stops a running backup",
    "sign": "signs a release with the owner's key",
    "verify": "needs a release folder and its signature",
    "update": "updates EA Explorer",
    "rollback": "rolls an update back",
    "dr-pack": "writes a whole DR pack (eax test full and the drill cover it)",
    "drill": "shuts EA Explorer down for a restore drill",
    "service": "switches an optional service on or off",
    "standby": "changes the database's standby",
    "trust": "changes this machine's trusted certificates",
    "init": "makes the config file (it exists)",
    "deploy": "deploys another installation",
    "console": "a numbered menu that asks",
    "screen": "the full screen, which waits for keys",
    "menu": "a numbered menu that asks",
    "document": "opens a page in the browser",
}


def launcher() -> list[str]:
    """How a person runs eax on this machine."""
    if os.name == "nt":
        ps = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
        return [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "eax.ps1")]
    return ["bash", str(ROOT / "eax.sh")]


def check(argv: list[str], words: list[str], code: int, output: str, timed_out: bool) -> tuple[str, str]:
    """(passed or failed, why) for one run (pure)."""
    if timed_out:
        return "failed", "it did not end in time"
    if code != 0:
        last = " ".join(output.strip().splitlines()[-2:])[-300:]
        return "failed", f"it ended with {code}: {last}"
    low = output.lower()
    missing = [w for w in words if w.lower() not in low]
    if missing:
        return "failed", f"its output does not say {', '.join(missing)}"
    return "passed", ""


def run_one(argv: list[str], seconds: int, runner=subprocess.run) -> tuple[int, str, bool, float]:
    """One command run as a person would, asking nothing: its exit code, its output, whether it ran out of time, and
    how long it took."""
    began = time.time()
    env = {**os.environ, "EAX_NONINTERACTIVE": "1", "EAX_NO_BROWSER": "1", "EAX_RUN_BY": "eax test commands"}
    try:
        p = runner([*launcher(), *argv], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   stdin=subprocess.DEVNULL, env=env, timeout=seconds, check=False)
        return p.returncode, (p.stdout or "") + (p.stderr or ""), False, time.time() - began
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return -1, out, True, time.time() - began


def run(argv: list[str], runner=subprocess.run) -> int:
    """eax test commands [--only WORD,WORD]: each case run; the report in work/tests/commands-<time>/."""
    only = set()
    if "--only" in argv and argv.index("--only") + 1 < len(argv):
        only = {x for x in argv[argv.index("--only") + 1].split(",") if x}
    laptop = setting("EAX_DEPLOYMENT", "laptop") == "laptop"
    rows = []
    for args, words, seconds, laptop_only in CASES:
        if only and args[0] not in only:
            continue
        line = " ".join(["eax", *args])
        if laptop_only and not laptop:
            rows.append({"command": line, "outcome": "skipped", "why": "on a laptop only", "seconds": 0})
            continue
        say(f"  {line}")
        code, out, timed_out, took = run_one(args, seconds, runner)
        outcome, why = check(args, words, code, out, timed_out)
        rows.append({"command": line, "outcome": outcome, "why": why, "seconds": round(took, 1), "exit": code,
                     "output_tail": out.strip()[-2000:]})
    return report(rows, WORK / "tests" / f"commands-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")


def report(rows: list[dict], folder: Path) -> int:
    """report.json and report.md (the commands run, then the ones not run and why), the failures on screen; 1 when any
    failed."""
    folder.mkdir(parents=True, exist_ok=True)
    count = {k: sum(1 for r in rows if r["outcome"] == k) for k in ("passed", "failed", "skipped")}
    (folder / "report.json").write_text(json.dumps({"counts": count, "commands": rows,
                                                    "not_run": NOT_RUN}, indent=1), encoding="utf-8")
    md = ["# eax test commands", "", f"Passed {count['passed']}, failed {count['failed']}, skipped {count['skipped']} "
          f"of {len(rows)} commands, each run for real on this installation.", "",
          "| Command | Outcome | Seconds | Why |", "|---|---|---|---|"]
    md += [f"| `{r['command']}` | {r['outcome']} | {r['seconds']} | {r['why']} |" for r in rows]
    md += ["", "## Not run here", "", "| Command | Why |", "|---|---|"]
    md += [f"| `eax {k}` | {v} |" for k, v in sorted(NOT_RUN.items())]
    (folder / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for r in rows:
        if r["outcome"] == "failed":
            say(f"  FAILED  {r['command']}: {r['why']}", "red")
    say(f"eax commands: {count['passed']} passed, {count['failed']} failed, {count['skipped']} skipped "
        f"(the report: {folder / 'report.md'})", "green" if not count["failed"] else "red")
    if not rows:
        raise Failure("No command matched --only.")
    return 1 if count["failed"] else 0
