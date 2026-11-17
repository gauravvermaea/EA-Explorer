"""eax test backup-restore (and eax test restore; last in eax test full): the backup and restore test (R5.6-B1).

The owner's test (16 Nov 2026, 15:21): "1. do an infram backup enviornment lets call it B1 2. Create a project with some
models 3. Create content in model in project and documents + custom reports and custom views invarious states, tags and
all other kind of content 4. Do an Infra backup lets call it B2 5. Restore B1 6. The projects and models should be gone
7. Do a Restore of B2 8. All content should now be checked including files using checksum". How it runs (15:36): "a
seperate test style ... completly syncrhronous calling one comamnd after other within eax and calling the require apis.
This will not be async". On this installation (15:28; 15:36 "If the enviornment is lost thats upto the user"), asking
nothing (16:54: "backup and restore test should not ask me anything"). B1 and B2 get random names and are removed at the end (15:41).

First the maintenance page goes on for everyone and everything in the background stops (every recurring job and the
scheduled backups, commands and updates; owner, 16 Nov 2026, 19:28); both come back at the end, whatever happened.
Each step runs one command and waits for it to end before the next; nothing in the background, no job queue, no test
runner. The steps run in the operations helper (`ops.py brtest ...`: backups, restores, the fingerprint of every table and
file) and in the API container (`python -m eax.testing.backup_restore ...`: the content through the REST API and MCP, and
reading it back). A step that fails stops the test there and says which and why. When it fails after B1 was restored,
B2 is restored first, so the installation is as it was; the backups are then kept and named in the report.

The report: work/tests/backup-restore-<time>/report.md and report.json (every step, comparison and time; never a
password, key or token), and the same lines in the eax log.

Scenarios in this run (docs/build-phases.md, R5.6-B1): S1 people and roles; S2 files in persist/ and the import folder;
S3 Release 5.5's data; S4 search and KPIs from the restored data; S5 work goes on; S6 the jobs; S7 a document's record
and its file together; S8 the same backup restored twice gives the same fingerprint; S12 not enough disk refused before
anything is touched; S13 no secret in the report or the restores' logs; S14 the clean-up never removes B1, B2 or a
pinned backup; S15 the times and what would be lost. Not in this run, said in the report with how they are covered:
S7's writing during the backup, S9 (an application backup: the self-test's backup suite), S10 (a backup of the previous
release), S11 (a restore cut off half-way) and the drills on a new machine (the two drill documents)."""

from __future__ import annotations

import json
import re
import secrets as _secrets
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .core import EAX, ROOT, WORK, Failure, compose_args, log_only, say, version

OPS = ["exec", "-T", "ops", "python3", "/app/ops.py", "brtest"]
API = ["exec", "-T", "api", "python", "-m", "eax.testing.backup_restore"]
# tables and files the installation writes by itself while it runs (sessions, events, logs, jobs, heartbeats, caches):
# never compared, listed in the report; the test's own content is compared exactly by the snapshot
SYSTEM_TABLE = re.compile(r"(^|[ ._])(jobs|audit)\.|session|event|log|heartbeat|startup|notification|alert_check|alert_state|lock|"
                          r"cache|health|metric|sample|footprint|resource_|token|celery|kombu|key_value|django_admin", re.I)
# config_backup.yml: Documents (Mayan) saves a copy of its settings there at every start (the owner's run, 16 Nov 2026,
# 23:56: "documents/config_backup.yml: another checksum" after restoring B1)
SYSTEM_FILE = re.compile(r"(^|/)(\.?cache|logs?|tmp|whoosh|index|locks?)/|\.(lock|pid|log|tmp)$|celerybeat|"
                         r"(^|/)config_backup\.yml$", re.I)
NOT_RUN = {
    "S7 (writing during the backup)": "this test is synchronous: nothing writes while B2 is taken; S7 checks instead that every "
                                      "document's record and file came back together",
    "S9 (an application backup of one model and one project)": "the self-test's backup suite takes an application backup and "
                                                               "restores a model from it (eax test full)",
    "S10 (an older backup onto newer code)": "needs a backup of the previous release: restore it with eax restore <name>; a "
                                             "newer backup onto older code is refused (tests/test_backups_infra.py)",
    "S11 (a restore cut off half-way)": "stopping a restore on purpose is left to a person: run eax restore again and it "
                                        "completes (docs/backup-drill-monthly.md)",
    "the restore onto a new machine": "a drill a person runs by hand: docs/backup-drill-new-machine.md (Documentation, with a PDF)",
}


def random_name() -> str:
    """A backup's random tag: brt-<8 letters and digits> (pure but for the randomness)."""
    return "brt-" + "".join(_secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))


def moved(a: dict, b: dict) -> set[str]:
    """Tables and files that differ between two fingerprints taken with nothing done in between: the installation
    changed them by itself (pure)."""
    out = {k for k in set(a.get("tables", {})) | set(b.get("tables", {})) if a.get("tables", {}).get(k) != b.get("tables", {}).get(k)}
    out |= {k for k in set(a.get("files", {})) | set(b.get("files", {})) if a.get("files", {}).get(k) != b.get("files", {}).get(k)}
    return out


# How the comparison decides (broad: the owner, 17 Nov 2026, 00:00: "make comparisons a bit loose, otherwise this will not
# work in every release"; 01:00: "this will never get fixed like this we need some broad level tests to check if backup
# is done"). The question is whether the backup gave its data back, not whether EA Explorer wrote nothing of its own
# after it started again:
#   failed (data lost): a table or a database gone, a table with fewer rows, a file gone
#   noted, never failed: a table with more rows or other content, a file new or with another checksum (EA Explorer, its
#             services and their start-up rewrite and add things of their own: dates, settings, roles, history)
#   not compared: what the installation writes all the time (SYSTEM_TABLE, SYSTEM_FILE, and what moved while idle)
# What the test made is checked exactly by its snapshot (gone after B1, back the same after B2), its document files by
# their checksums when downloaded (S7), and sign-in, search, KPIs, new work and the jobs after B2 (S1, S4 to S6).


def same(before: dict, after: dict, ignore: set[str]) -> dict:
    """Two fingerprints compared (pure): {"tables": n, "files": n compared, "differ": [...] (data lost: fails),
    "allowed": [...] (noted), "not_compared": [...]} (see above)."""
    differ, allowed, skipped = [], [], []
    nt = nf = 0
    for kind, rx in (("tables", SYSTEM_TABLE), ("files", SYSTEM_FILE)):
        b, a = before.get(kind, {}), after.get(kind, {})
        for k in sorted(set(b) | set(a)):
            if k in ignore or rx.search(k):
                if b.get(k) != a.get(k):
                    skipped.append(k)
                continue
            if kind == "tables":
                nt += 1
            else:
                nf += 1
            if b.get(k) == a.get(k):
                continue
            if k not in a:
                differ.append(f"{k}: missing after")
            elif k not in b:
                allowed.append(f"{k}: new after")
            elif kind == "tables":
                rb, ra = int(b[k][0]), int(a[k][0])
                if ra < rb:
                    differ.append(f"{k}: {rb} rows before, {ra} after ({rb - ra} lost)")
                elif ra > rb:
                    allowed.append(f"{k}: {ra - rb} more rows ({rb} before, {ra} after)")
                else:
                    allowed.append(f"{k}: same rows, other content")
            else:
                allowed.append(f"{k}: another checksum")
    return {"tables": nt, "files": nf, "differ": differ, "allowed": allowed, "not_compared": skipped}


NEEDED_DBS = ("eaexplorer", "keycloak", "mayan")


def whole(r: dict) -> tuple[bool, str]:
    """A broad check of a backup just taken (pure): good, and holding the main databases and Documents' files."""
    p = r.get("parts") or {}
    dbs, files = p.get("databases") or [], p.get("files") or []
    missing = [d for d in NEEDED_DBS if d not in dbs] + ([] if "documents" in files else ["Documents' files"])
    ok = r.get("status") in (None, "ok") and not missing
    return ok, (f"{len(dbs)} databases ({', '.join(dbs)}), files: {', '.join(files) or 'none'}"
                + (f"; missing: {', '.join(missing)}" if missing else ""))


def said(c: dict, ok_text: str = "nothing lost") -> str:
    """A comparison in words, for the report (pure)."""
    out = f"{c['tables']} tables and {c['files']} files compared; " + ("; ".join(c["differ"][:20]) or ok_text)
    if c.get("allowed"):
        out += f". Noted, not failed (written by EA Explorer itself after it started, {len(c['allowed'])}): " + "; ".join(c["allowed"][:10])
    return out


def secrets_in(text: str, values: list[str]) -> list[str]:
    """Which of the secret values appear in a text (pure); returns their names' positions, never the values."""
    return [f"secret #{i + 1}" for i, v in enumerate(values) if len(v) >= 8 and v in text]


def config_secrets(path: Path) -> list[str]:
    """The passwords, keys and tokens of the config file (their values, only to look for them)."""
    out = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            # a password, secret or token, or a key (a name ending in _KEY): not EAX_KEYCLOAK_REALM, whose value
            # "eaexplorer" is in every report (the owner's run, 16 Nov 2026, 22:21: "secret #15")
            m = re.match(r"^\s*([A-Z0-9_]*(PASSWORD|SECRET|TOKEN)[A-Z0-9_]*|[A-Z0-9_]*_KEY)\s*=\s*(.+?)\s*$", line)
            if m and not m.group(3).startswith("change-me") and m.group(3).strip("'\"").lower() not in ("true", "false"):
                out.append(m.group(3).strip("'\""))
    except OSError:
        pass
    return out


# ---------------------------------------------------------------- one command at a time
def _json_line(stdout: str) -> dict:
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                break
    return {"error": "no answer: " + ((stdout or "").strip().splitlines() or ["nothing printed"])[-1][:300]}


SERVICE_WAIT = 20 * 60        # how long a command waits for its container to be running (the later part may be building it)


def service_running(service: str) -> bool:
    """Whether the service's container is running now (docker compose ps)."""
    try:
        r = subprocess.run(compose_args(["ps", "--status", "running", "--services"]), cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return service in (r.stdout or "").split()


def wait_for_service(service: str, limit: int = SERVICE_WAIT, running=service_running, sleep=time.sleep, clock=time.monotonic) -> bool:
    """Waits until the service's container runs, up to limit seconds. `eax up` starts the core and builds the rest (the
    operations helper among it) in the background (D255), so a command needing the operations helper right after an
    `eax up` waited for nothing and failed with "service ops is not running" (the owner's drill, 17 Nov 2026, 21:09)."""
    if running(service):
        return True
    say(f"    waiting for {service} to be running (the rest of EA Explorer is still starting; up to {limit // 60} minutes)")
    end = clock() + limit
    while clock() < end:
        sleep(5)
        if running(service):
            say(f"    {service} is running")
            return True
    return False


def run_in(target: list[str], args: list[str], state: dict | None = None, timeout: int = 6 * 3600, wait=wait_for_service) -> dict:
    """One command in a container, waited for: its progress shown as it comes (standard error), its JSON answer kept.
    The container is waited for first when it is not running yet."""
    if target[:2] == ["exec", "-T"] and not wait(target[2]):
        return {"error": f"{target[2]} did not start within {SERVICE_WAIT // 60} minutes: eax status, eax logs {target[2]}"}
    cmd = compose_args([*target, *args])
    log_only("> " + " ".join([*target[1:4], *target[4:], *args]))
    try:
        r = subprocess.run(cmd, cwd=ROOT, input=json.dumps(state) if state is not None else "", capture_output=False,
                           stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"error": f"no answer after {timeout // 60} minutes"}
    except FileNotFoundError:
        return {"error": "docker is not installed or not on the PATH"}
    out = _json_line(r.stdout)
    if r.returncode and not out.get("error"):
        out["error"] = f"exit {r.returncode}"
    return out


class Test:
    """The steps, their results and the report."""

    def __init__(self, folder: Path, ops=None, api=None, wait=None, clock=time.time):
        self.folder, self.clock = folder, clock
        self.ops = ops or (lambda *a, state=None: run_in(OPS, [*a, "--version", version()], state))
        self.api = api or (lambda cmd, state: run_in(API, [cmd], state))
        self.wait = wait or _wait_core
        self.results: list[dict] = []
        self.times: dict[str, float] = {}
        self.names: dict[str, str] = {}
        self.restored_b1 = self.restored_b2 = self.quiet = False
        self.started = clock()

    def check(self, name: str, ok: bool | None, detail: str = "", ms: int = 0, scenario: str = "") -> bool:
        """A result, printed and kept."""
        self.results.append({"name": name, "ok": ok, "detail": str(detail)[:2000], "ms": ms, "scenario": scenario})
        mark = "ok  " if ok else "skip" if ok is None else "FAIL"
        say(f"  {mark} {name}{': ' + str(detail)[:300] if detail else ''}", "green" if ok else "yellow" if ok is None else "red")
        log_only(f"backup-restore: {mark} {name}: {detail}")
        return bool(ok) or ok is None

    def step(self, name: str, fn):
        """One step: shown, timed, its answer returned; a step that fails raises (the test stops there)."""
        say(f"\n> {name}", "cyan")
        t0 = self.clock()
        out = fn()
        ms = int((self.clock() - t0) * 1000)
        err = out.get("error") if isinstance(out, dict) else ""
        self.check(name, not err, err or f"{ms / 1000:.0f} s", ms)
        if err:
            raise Failure(f"{name}: {err}")
        return out


def _wait_core() -> bool:
    from .stack import wait_core
    return wait_core(30)


def warn() -> None:
    """Said plainly before it starts what is lost until B2 is restored; nothing is asked (owner, 16 Nov 2026, 16:54: "backup
    and restore test should not ask me anything")."""
    say("\nThe backup and restore test runs on THIS installation:", "yellow")
    say("  1. a backup (B1); 2. a test project and models with content of every kind; 3. a second backup (B2);")
    say("  4. B1 is restored: everything made since B1 - the test's content AND ANY REAL WORK done meanwhile - is gone;")
    say("  5. B2 is restored: everything comes back and every table and file is compared; then the test's data and both")
    say("     backups are removed. The maintenance page is on for everyone and everything in the background is stopped")
    say("     (recurring jobs, scheduled backups, commands and updates) until it ends, about an hour.")


def run(t: Test) -> dict:
    """The test, step by step (see the module). Returns the report's data."""
    st: dict = {}
    b1 = b2 = ""
    made_backups: list[str] = []
    try:
        # owner, 16 Nov 2026, 19:28: "put mantainance page and stop everything in background" before the test
        t.step("the maintenance page on and everything in the background stopped", lambda: t.ops("quiet", "on"))
        t.quiet = True
        ready = t.step("the backup container runs and the disk has room (S12)", lambda: t.ops("ready"))
        t.check("S12: the disk needed is free", True, f"{ready.get('need_bytes', 0) / 1e9:.1f} GB needed, "
                f"{ready.get('free_bytes', 0) / 1e9:.1f} GB free", scenario="S12")
        # nothing half done under a backup (the owner's run, 16 Nov 2026, 23:09: B2 caught a project's documents being made)
        t.step("the background finished what it was doing (before B1)", lambda: t.api("idle", {}))
        f0 = t.step("fingerprint before B1 (every table and file)", lambda: t.ops("fingerprint"))
        r = t.step("B1: an infrastructure backup", lambda: t.ops("backup", random_name()))
        b1 = t.names["B1"] = r["name"]
        t.check("B1 holds every database and all of Documents", *whole(r))
        made_backups.append(b1)
        t.times["B1 backup"] = r.get("seconds", 0)
        f1 = t.step("fingerprint after B1", lambda: t.ops("fingerprint"))
        moving = moved(f0, f1)
        st = t.step("the test's content: a project, models and content of every kind (REST and MCP)",
                    lambda: t.api("start", {"by": "eax test backup-restore", "folder": t.folder.name, "version": version()}))
        for m in st.get("made") or []:
            t.check(f"made: {m['what']}", m["ok"], m.get("detail", ""), scenario="content")
        if not all(m["ok"] for m in st.get("made") or []):
            raise Failure("part of the content could not be made (above)")
        t.step("S2: a file in persist/ and in the import folder", lambda: t.ops("mark", st["sid"], "put"))
        t.step("the background finished what it was doing (the test's project's documents and the rest, before B2)",
               lambda: t.api("idle", {}))
        snap2 = t.step("what the test made, read back", lambda: t.api("snapshot", st))
        f2a = t.step("fingerprint before B2", lambda: t.ops("fingerprint"))
        t2 = t.clock()
        r = t.step("B2: an infrastructure backup", lambda: t.ops("backup", random_name()))
        b2 = t.names["B2"] = r["name"]
        t.check("B2 holds every database and all of Documents", *whole(r))
        made_backups.append(b2)
        t.times["B2 backup"] = r.get("seconds", 0)
        f2b = t.step("fingerprint after B2", lambda: t.ops("fingerprint"))
        moving |= moved(f2a, f2b)
        ret = t.step("S14: the scheduled clean-up keeps B1, B2 and the pinned backups", lambda: t.ops("retention", b1, b2))
        t.check("S14: B1 and B2 are never removed by the clean-up", not ret.get("lost"), f"would remove {ret.get('would_remove')} "
                f"others; B1 and B2 kept: {not ret.get('lost')}", scenario="S14")

        r = t.step("restore B1 (full)", lambda: t.ops("restore", b1, "--what", "full"))
        t.restored_b1 = True
        made_backups.append(r.get("before", ""))
        t.times["B1 restore"] = r.get("seconds", 0)
        t.check("EA Explorer answers again after restoring B1", t.wait(), "the API and sign-in are healthy")
        snap3 = t.step("what the test made, after restoring B1", lambda: t.api("snapshot", st))
        left = _present(snap3)
        t.check("everything the test made is gone (the project, its models and the rest)", not left, ", ".join(left) or "gone")
        f3 = t.step("fingerprint after restoring B1", lambda: t.ops("fingerprint"))
        c = same(f1, f3, moving)
        t.check("nothing of B1 lost: every database's tables and rows and every file there", not c["differ"], said(c))
        marks = [k for k in f3.get("files", {}) if f"self_test_{st['sid']}_backup_restore" in k]
        t.check("S2: the files made after B1 are gone from persist/ and the import folder", not marks, ", ".join(marks) or "gone",
                scenario="S2")
        if any(x["ok"] is False for x in t.results):
            raise Failure("restoring B1 did not give B1 back")

        r = t.step("S8: restore B1 again (the same backup twice)", lambda: t.ops("restore", b1, "--what", "full"))
        made_backups.append(r.get("before", ""))
        t.check("EA Explorer answers again", t.wait(), "the API and sign-in are healthy")
        f3b = t.step("fingerprint after restoring B1 again", lambda: t.ops("fingerprint"))
        c = same(f3, f3b, moving)
        t.check("S8: the same backup restored twice loses nothing", not c["differ"], said(c), scenario="S8")

        r = t.step("restore B2 (full)", lambda: t.ops("restore", b2, "--what", "full"))
        t.restored_b2 = True
        made_backups.append(r.get("before", ""))
        t.times["B2 restore"] = r.get("seconds", 0)
        t.check("EA Explorer answers again after restoring B2", t.wait(), "the API and sign-in are healthy")
        snap4 = t.step("what the test made, after restoring B2", lambda: t.api("snapshot", st))
        diffs = _differences(snap2, snap4)
        t.check("everything the test made is back, row for row", not diffs, "; ".join(diffs[:20]) or
                f"{len(_present(snap4))} kinds of content, the same")
        f4 = t.step("fingerprint after restoring B2", lambda: t.ops("fingerprint"))
        c = same(f2b, f4, moving)
        t.check("nothing of B2 lost: every database's tables and rows and every file there", not c["differ"], said(c))
        marks = [k for k in f4.get("files", {}) if f"self_test_{st['sid']}_backup_restore" in k]
        t.check("S2: the files in persist/ and the import folder are back", len(marks) == 2, ", ".join(marks), scenario="S2")
        t.check("S13: the config file and the certificate came back", f4.get("files", {}).get("config/eaexplorer.env")
                == f2b.get("files", {}).get("config/eaexplorer.env") and any(k.startswith("tls/") for k in f4.get("files", {})),
                "the config file's checksum and the certificate's files", scenario="S13")

        aft = t.step("after B2: sign-in, search, KPIs, new work, the jobs, the documents", lambda: t.api("after", st))
        for x in aft.get("checks") or []:
            t.check(f"{x['scenario']}: {x['check']}", x["ok"], x.get("detail", ""), scenario=x["scenario"])
        t.times["recovery point"] = round(t.clock() - t2)
    except Failure as exc:
        t.check("the test stopped", False, str(exc))
        if t.restored_b1 and not t.restored_b2 and b2:
            say("\nB1 was restored: B2 is restored now, so the installation is as it was before the test.", "yellow")
            r = t.ops("restore", b2, "--what", "full")
            made_backups.append(r.get("before", ""))
            t.check("B2 restored after the failure (the installation as it was)", not r.get("error") and t.wait(), r.get("error", ""))
    return _finish(t, st, b1, b2, [b for b in made_backups if b])


def _present(snap: dict) -> list[str]:
    out = [k for k, v in snap.items() if isinstance(v, dict) and v.get("rows")]
    out += [v.get("name") or k for k, v in (snap.get("models") or {}).items()
            if isinstance(v, dict) and not v.get("missing") and not v.get("skipped")]
    return out


def _differences(before: dict, after: dict) -> list[str]:
    diffs = []
    for k in sorted(set(before) | set(after)):
        if k == "at":
            continue
        b, a = before.get(k), after.get(k)
        if k == "models":
            for g in sorted(set(b or {}) | set(a or {})):
                if (b or {}).get(g) != (a or {}).get(g):
                    diffs.append(f"{((b or {}).get(g) or {}).get('name') or g}: {(b or {}).get(g)} before, {(a or {}).get(g)} after")
        elif b != a:
            diffs.append(f"{k}: {b} before, {a} after")
    return diffs


def _finish(t: Test, st: dict, b1: str, b2: str, backups: list[str]) -> dict:
    """The secrets check, the test's data and backups removed when all passed, the report."""
    passed = all(r["ok"] is not False for r in t.results)
    report = {"started": datetime.fromtimestamp(t.started, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "minutes": round((t.clock() - t.started) / 60, 1),
              "B1": b1, "B2": b2, "passed": passed, "times_seconds": t.times, "results": t.results,
              "not_in_this_run": NOT_RUN, "content": [m["what"] for m in st.get("made") or []]}
    found = secrets_in(json.dumps(report) + json.dumps(st.get("calls") or []), config_secrets(WORK / "eaexplorer.env")
                       + [x for x in (st.get("token"), st.get("architect")) if x])
    logs = ""
    for d in sorted((WORK / "backups" / "restores").glob("*/restore.log"))[-6:]:
        try:
            logs += d.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    found += [f"a restore's log: {x}" for x in secrets_in(logs, config_secrets(WORK / "eaexplorer.env"))]
    t.check("S13: no password, key or token in the report or the restores' logs", not found, ", ".join(found) or "none", scenario="S13")
    if st.get("run_id"):
        fin = t.api("finish", {**st, "results": t.results, "keep": not passed, "error": "" if passed else "failed"})
        t.check("the test's project, models, accounts and records removed" if passed else "the test's record closed (its data kept)",
                not fin.get("error"), json.dumps(fin.get("removed", {}))[:300] if not fin.get("error") else fin["error"])
        if st.get("sid"):
            t.ops("mark", st["sid"], "remove")
    if passed and backups:
        d = t.ops("delete", *backups)
        t.check("B1, B2 and the backups the restores took first removed", not d.get("left") and not d.get("error"),
                ", ".join(d.get("left") or []) or f"{len(d.get('deleted') or [])} removed")
    elif backups:
        t.check("the backups kept (the test failed): delete them with eax delete-backup when done", None, ", ".join(backups))
    if t.quiet:
        q = t.ops("quiet", "off")
        t.quiet = bool(q.get("error"))
        t.check("the maintenance page off and the background started again", not q.get("error"),
                q.get("error") or "recurring jobs and schedules run again (what was missed runs at its next turn)")
    report.update(passed=all(r["ok"] is not False for r in t.results), results=t.results)
    t.folder.mkdir(parents=True, exist_ok=True)
    (t.folder / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (t.folder / "report.md").write_text(to_markdown(report), encoding="utf-8")
    return report


def to_markdown(rep: dict) -> str:
    """The report as Markdown (pure)."""
    lines = [f"# Backup and restore test, {rep['started']}", "",
             f"**{'Passed' if rep['passed'] else 'Failed'}** in {rep['minutes']} minutes. B1 was `{rep['B1'] or '-'}`, "
             f"B2 `{rep['B2'] or '-'}` (random names).", "", "## Times (S15)", ""]
    tm = rep.get("times_seconds") or {}
    for k, v in tm.items():
        if k != "recovery point":
            lines.append(f"- {k}: {v / 60:.1f} minutes")
    if "B2 restore" in tm:
        lines.append(f"- recovery time (restoring B2): {tm['B2 restore'] / 60:.1f} minutes")
    if "recovery point" in tm:
        lines.append(f"- recovery point: restoring B2 now would lose what was done in the {tm['recovery point'] / 60:.0f} minutes "
                     "since B2 was taken")
    lines += ["", "## Steps and checks", "", "| | Check | Detail |", "| --- | --- | --- |"]
    for r in rep["results"]:
        mark = "ok" if r["ok"] else "skipped" if r["ok"] is None else "FAILED"
        lines.append(f"| {mark} | {r['name']} | {str(r.get('detail', '')).replace('|', '/')[:500]} |")
    lines += ["", "## Not in this run", ""] + [f"- **{k}**: {v}" for k, v in rep.get("not_in_this_run", {}).items()]
    return "\n".join(lines) + "\n"


def main(args: list[str]) -> int:
    """eax test backup-restore: says what it does, then runs; it asks nothing."""
    warn()
    folder = WORK / "tests" / f"backup-restore-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    say(f"Backup and restore test: one step after another; the report goes to {folder.relative_to(ROOT)}.", "cyan")
    t = Test(folder)
    try:
        rep = run(t)
    finally:
        if t.quiet:                                   # stopped hard (Ctrl+C): the installation is not left paused
            t.ops("quiet", "off")
    say("")
    say(f"Backup and restore test {'PASSED' if rep['passed'] else 'FAILED'} in {rep['minutes']} minutes. "
        f"Report: {(folder / 'report.md').relative_to(ROOT)}", "green" if rep["passed"] else "red")
    if not rep["passed"]:
        say(f"Look at the first FAIL above; {EAX} logs api and {EAX} restores say more.", "yellow")
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
