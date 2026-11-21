"""Starting and stopping: the optional services (D191), the two-tier start (D255), the API servers (D249), disks."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from .core import (
    EAX,
    ROOT,
    WINDOWS,
    WORK,
    Failure,
    capture,
    compose,
    compose_args,
    compose_out,
    copy_config,
    say,
    setting,
    write_setting,
)

# name: setting, compose services in start order (mcp and change_log run inside the api container)
SERVICES = {
    "reports": ("EAX_SERVICE_REPORTS", ["reports-init", "reports"]),
    "documents": ("EAX_SERVICE_DOCUMENTS", ["dms-broker", "dms"]),
    "drawio": ("EAX_SERVICE_DRAWIO", ["drawio"]),
    "mcp": ("EAX_SERVICE_MCP", ["api"]),
    "change_log": ("EAX_SERVICE_CHANGE_LOG", ["api"]),
    "backups": ("EAX_SERVICE_BACKUPS", ["backup"]),
    "library": ("EAX_SERVICE_LIBRARY", ["library"]),
    "views": ("EAX_SERVICE_VIEWS", ["views"]),
}
CORE = ["db", "setup", "proxy", "web", "keycloak", "api"]
STARTUP_PY = ("import json,urllib.request as u; d=json.load(u.urlopen('http://localhost:8000/api/startup',timeout=20)); "
              "print(d['overall']+'|'+', '.join(p['key']+': '+p['status'] for p in d['parts']))")


def service_on(name: str) -> bool:
    """Whether an optional service is switched on in the config file."""
    default = setting("EAX_MCP_ENABLED", "on") if name == "mcp" else "on"
    return setting(SERVICES[name][0], default).lower() not in ("off", "false", "0", "no", "disabled")


def write_services_file() -> None:
    """work/services.env: the switches only (no secrets), read by the api container."""
    lines = ["# Written by EA Explorer from eaexplorer.env: the service switches only (D191). Do not edit; change eaexplorer.env."]
    lines += [f"{SERVICES[n][0]}={'on' if service_on(n) else 'off'}" for n in SERVICES]
    (WORK / "services.env").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def off_containers() -> list[str]:
    """The containers of the services switched off."""
    return [c for n, (_s, cs) in SERVICES.items() if not service_on(n) and cs[0] != "api" for c in cs]


def api_servers() -> int:
    """How many API and job servers to run (EAX_API_SERVERS)."""
    try:
        n = int(setting("EAX_API_SERVERS", "1"))
    except ValueError:
        n = 1
    return max(1, min(16, n))


def tiers() -> dict[str, list[str]]:
    """The containers to start first and those after."""
    off = off_containers()
    on = [s for s in compose_out(["config", "--services"]) if s not in off]
    return {"first": [s for s in on if s in CORE], "later": [s for s in on if s not in CORE], "off": off}


def wait_core(minutes: int = 15) -> bool:
    """Until the API (every copy) and Keycloak say healthy; each change shown; False when one stopped or too long."""
    until, last = time.time() + minutes * 60, ""
    while time.time() < until:
        rows = [r for r in compose_out(["ps", "-a", "--format", "{{.Name}}|{{.State}}|{{.Health}}", "api", "keycloak"]) if "|" in r]
        parts = [r.split("|") for r in rows]
        now = ", ".join(f"{p[0]}: {p[2] or p[1]}" for p in parts)
        if now and now != last:
            say(f"  {now}")
            last = now
        if len(parts) >= 2 and all(p[2] == "healthy" for p in parts):
            return True
        if any(p[1] in ("exited", "dead") for p in parts):
            say(f"A core container stopped; see {EAX} logs api (or keycloak).", "red")
            return False
        time.sleep(5)
    say(f"The API or sign-in was not ready after {minutes} minutes; see {EAX} logs api (or keycloak).", "yellow")
    return False


def wait_all(minutes: int = 30) -> None:
    """--wait-all: until every part is up (the API's start-up status, D255): Reports, Documents, Diagrams, sample data."""
    until, t0, last = time.time() + minutes * 60, time.time(), ""
    say(f"Waiting for everything: Reports, Documents, Diagrams and the sample data (up to {minutes} minutes)...")
    while time.time() < until:
        rows = [r for r in compose_out(["exec", "-T", "api", "python", "-c", STARTUP_PY]) if "|" in r]
        now = rows[-1] if rows else ""
        if now and now != last:
            say(f"  {now.split('|', 1)[1]}")
            last = now
        if now.startswith("up|"):
            say(f"Everything is up after {int(time.time() - t0)} s.", "green")
            return
        if now.startswith("down|") and "starting" not in now:
            say(f"Started, but not everything is up (see above): {EAX} logs <service>.", "yellow")
            return
        time.sleep(10)
    say(f"Not everything was up after {minutes} minutes (see above); EA Explorer is usable, the rest may still come.", "yellow")


def start_later() -> None:
    """The second tier in a process of its own, with its own log, so this window is free at once."""
    args = [sys.executable, str(ROOT / "eaxpy.py"), "start-later"]
    kw: dict = {"cwd": ROOT, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if WINDOWS:
        kw["creationflags"] = 0x00000008 | 0x08000000      # DETACHED_PROCESS | CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    subprocess.Popen(args, **kw)
    say("Reports, documents, draw.io, backups and the operations helper start now in the background "
        "(log: work/logs/eax-*-start-later.log).")


def up(names: list[str], wait_everything: bool, no_throw: bool = False) -> int:
    """Starts the stack (or some parts), first the core then the rest."""
    write_services_file()
    scale = ["--scale", f"api={api_servers()}"]
    if names:
        return compose(["up", "-d", "--build", *(scale if "api" in names else []), *names], no_throw=no_throw)
    if os.environ.get("EAX_BUILD_PULL") == "1":   # a clean rebuild: fresh base images, with their fixes (R3.12, D673)
        say("Fetching the current base images and building on them (a clean rebuild)...", "cyan")
        compose(["pull", "--ignore-buildable", "--quiet"], no_throw=True)
        code = compose(["build", "--pull"], no_throw=no_throw)
        if code != 0:
            return code
    t = tiers()
    if t["off"]:
        say(f"Switched off (D191): {', '.join(t['off'])}: created, not started.")
    say(f"Starting the core first (D255): {', '.join(t['first'])}", "cyan")
    code = compose(["up", "-d", "--build", *scale, *t["first"]], no_throw=no_throw)
    if code != 0:
        return code
    say("Waiting for the API and sign-in to be ready (the database upgrade and the built-in models come first)...")
    started = time.time()
    ready = wait_core()
    if wait_everything:
        later()
        wait_all()
        return 0
    start_later()
    say(f"(To wait for everything instead: {EAX} up --wait-all.)")
    if ready:
        say(f"EA Explorer is ready after {int(time.time() - started)} s: you can sign in.", "green")
        say("Still starting in the background: Reports, Documents, Diagrams and the sample data; the screens show each in "
            "red, amber or green (down, starting, up).", "green")
        hint = WORK / ".check-hint-shown"
        if not hint.exists():            # the first start: how to check it (D582)
            say("Check your installation: System admin > Self-test > Smoke test > Start (it prepares what it needs);")
            say(f"  or {EAX} test (smoke) or {EAX} test full.")
            say("  Results: Self-test > History and the report. Steps: docs/deployment.md, \"Check your installation\".")
            try:
                hint.touch()
            except OSError:
                pass
    return 0


# Containers that are not part of running EA Explorer (owner, 19 Nov 2026, 05:45: "ensure sonar and other non essential
# containers do not come up during regular operations"): SonarQube and its scanner (eax test sonar), k6 (the load test),
# the platform's always-on test runner (only for a managed platform) and a test run that has finished. A container of a
# profile that is not switched on is left alone by compose's own down and, with a restart policy, comes back whenever
# Docker starts; so up and down remove them (their data volumes kept). A running test is never stopped. In step with
# eax.ps1's Remove-Extras and eax.sh's remove_extras (D331).
EXTRA_CONTAINERS = ("sonarqube", "sonar-scanner", "k6", "testrunner-service")
ALL_PROFILES = ["--profile", "test", "--profile", "platform"]


def extras_to_remove(test_running: bool) -> list[str]:
    """The containers up and down remove: the extras, and the test runner when no test is running."""
    return [*EXTRA_CONTAINERS, *([] if test_running else ["testrunner"])]


TEST_LABEL = "eaexplorer.test"     # the containers a test starts (scanners, k6), its run's folder as the value
BEAT, BEAT_STALE = ".alive", 180   # a run being run touches work/tests/<folder>/.alive every 20 seconds


def stale_tests(listed: list[str], tests_dir, now: float | None = None) -> list[str]:
    """Of `docker ps -a` lines "<name> <folder>", the test containers whose run is no longer going (no heartbeat for
    three minutes): removed by up and down; a run in progress is never touched."""
    now = now or time.time()
    out = []
    for line in listed:
        name, _, folder = line.strip().partition(" ")
        if not name:
            continue
        beat = tests_dir / folder.strip() / BEAT if folder.strip() and "/" not in folder and ".." not in folder else None
        try:
            fresh = beat is not None and now - beat.stat().st_mtime < BEAT_STALE
        except OSError:
            fresh = False
        if not fresh:
            out.append(name)
    return out


def test_containers() -> list[str]:
    """The containers a test started that are still there (none after a run: the full test says so)."""
    try:
        out = subprocess.run(["docker", "ps", "-a", "--filter", f"label={TEST_LABEL}", "--format", "{{.Names}}"],
                             capture_output=True, text=True, timeout=60, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [n.strip() for n in out.splitlines() if n.strip()]


def remove_extras() -> None:
    """Removes the containers that are not part of running EA Explorer: the test and platform profiles' (but the test
    runner while a run uses it), and any container a test started that its run left behind (owner, 21 Nov 2026,
    14:40: "stray containers are hard on memory")."""
    running = bool(compose_out([*ALL_PROFILES, "ps", "--status", "running", "-q", "testrunner"]))
    compose([*ALL_PROFILES, "rm", "-s", "-f", *extras_to_remove(running)], no_throw=True, quiet=True)
    try:
        listed = subprocess.run(["docker", "ps", "-a", "--filter", f"label={TEST_LABEL}", "--format",
                                 '{{.Names}} {{.Label "' + TEST_LABEL + '"}}'], capture_output=True, text=True,
                                timeout=60, check=False).stdout.splitlines()
    except (OSError, subprocess.TimeoutExpired):
        return
    for name in stale_tests(listed, WORK / "tests"):
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=120, check=False)


def later() -> None:
    """start-later: the rest without touching the core, then the switched-off ones created (not started)."""
    t = tiers()
    if t["later"]:
        say(f"Starting after the core (D255): {', '.join(t['later'])}")
        compose(["up", "-d", "--build", "--no-deps", *t["later"]], no_throw=True)
    if t["off"]:
        compose(["create", "--build", *t["off"]], no_throw=True)
        compose(["stop", *t["off"]], no_throw=True, quiet=True)
    remove_extras()        # nothing that is not part of running EA Explorer (test, scan and platform containers)
    say("Everything is started.")


def show_filesystems() -> None:
    """The disks after the containers: Docker's and the work and backups folders (read by the operations helper), and
    this computer's disk the project sits on (read here, so it shows with the helper down too)."""
    say("")
    if compose_out(["ps", "--status", "running", "-q", "ops"]):
        for ln in compose_out(["exec", "-T", "ops", "python3", "/app/ops.py", "filesystems"]):
            say(ln)
    else:
        say("File systems: the operations helper is not running, so Docker's disk is not read (docker system df below).", "yellow")
        for ln in capture(["docker", "system", "df"])[1].splitlines():
            say(f"  {ln}")
    try:
        u = shutil.disk_usage(ROOT)
        pct = round(u.used / u.total * 100, 1)
        colour = "red" if pct >= 90 else "yellow" if pct >= 80 else ""
        say(f"  This computer's disk for the project folder: {u.total / 1e9:,.1f} GB, {u.used / 1e9:,.1f} GB used, "
            f"{u.free / 1e9:,.1f} GB free ({pct}% used)", colour)
    except OSError:
        pass


def show_services() -> None:
    """eax services: each optional service on or off, and the containers."""
    for n, (s, cs) in SERVICES.items():
        say(f"{n:<11} {'on ' if service_on(n) else 'off'}   {s} = {setting(s, 'on')}   containers: {', '.join(cs)}")
    compose(["ps", "-a"])


def set_service(name: str, value: str) -> None:
    """eax service <name> on|off."""
    if name not in SERVICES:
        raise Failure(f"Unknown service '{name}'. One of: {', '.join(SERVICES)}")
    if value not in ("on", "off"):
        raise Failure(f"Say on or off: {EAX} service {name} on")
    copy = copy_config(f"{name}-{value}")
    write_setting(SERVICES[name][0], value, drop="EAX_MCP_ENABLED" if name == "mcp" else "")
    write_services_file()
    say(f"{SERVICES[name][0]}={value} written (the config file before is kept as work/config-history/{copy}).")
    names = SERVICES[name][1]
    if names[0] == "api":
        compose(["restart", "api"])
    elif value == "on":
        compose(["up", "-d", *names])
    else:
        compose(["stop", *names])


def servers(args: list[str]) -> None:
    """eax servers: how many API servers run, or sets it."""
    if not args:
        say(f"API and job servers wanted: {api_servers()} (EAX_API_SERVERS). Running:")
        compose(["ps", "api"])
        return
    try:
        n = int(args[0])
    except ValueError:
        n = 0
    if not 1 <= n <= 16:
        raise Failure(f"Usage: {EAX} servers <1 to 16>")
    copy_config(f"servers-{n}")
    write_setting("EAX_API_SERVERS", str(n), section="# ---- API and job servers (D249)")
    say(f"Running {n} API and job server(s); stopping a server lets the jobs it runs finish first.")
    compose(["up", "-d", "--no-deps", "--no-recreate", "--scale", f"api={n}", "api"])


# what a backup, a restore, the backup and restore test, the drill or a DR pack leaves when it is cut off (R5.6; the
# owner, 17 Nov 2026, 11:19: "add another feature in eax that removes the mantainance page, just in case something
# crashed in backup or DR run")
LEFT_BEHIND = (("proxy/maintenance", "the maintenance page"),
               ("maintenance.json", "a restore's record that it is under way"),
               ("quiet.json", "the background paused (recurring jobs and schedules wait)"))
BUSY_IN_BACKUP = "backup.sh|restore.sh|fingerprint.sh|dumpdb.sh|pg_dump|pg_restore|pg_dumpall"


def _left_behind() -> list[tuple[str, str, str]]:
    """(file, what it is, what it says) for each one there."""
    out = []
    for rel, what in LEFT_BEHIND:
        f = WORK / rel
        if f.exists():
            try:
                said = f.read_text(encoding="utf-8").strip().replace("\n", " ")[:200]
            except OSError:
                said = ""
            out.append((rel, what, said))
    return out


def _backup_working() -> list[str]:
    """What the backup container is running now (a backup, a restore, a fingerprint), or [] (also when it is stopped)."""
    lines = compose_out(["exec", "-T", "backup", "sh", "-c", f"pgrep -af '{BUSY_IN_BACKUP}' | grep -v pgrep || true"])
    return [ln for ln in lines if ln.strip()]


def maintenance(arg: str, rest: list[str] | None = None) -> None:
    """eax maintenance on|off|status|clear: the maintenance page at the front door; status and clear also cover what a
    cut-off backup, restore, test, drill or DR pack leaves (the page, a restore's record, the paused background)."""
    flag = WORK / "proxy" / "maintenance"
    rest = rest or []
    if arg not in ("on", "off", "status", "clear"):
        raise Failure(f"Usage: {EAX} maintenance on|off|status|clear [--force]")
    if arg == "on":
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("maintenance\n", encoding="utf-8", newline="\n")
        say(f"The maintenance page is shown to everyone until: {EAX} maintenance off")
        return
    if arg == "off":
        if flag.exists():
            flag.unlink()
        say("The maintenance page is off." + ("" if not (WORK / "quiet.json").exists() and not (WORK / "maintenance.json").exists()
                                              else f" Something else is still left: {EAX} maintenance status"))
        return
    left = _left_behind()
    working = _backup_working()
    if not left:
        say("Nothing is left: no maintenance page, no restore under way, the background runs.", "green")
    for rel, what, said in left:
        say(f"  {what} (work/{rel})" + (f": {said}" if said else ""), "yellow")
    if working:
        say("The backup container is working now: " + "; ".join(w[:120] for w in working[:5]), "yellow")
    if arg == "status" or not left:
        if left and arg == "status":
            say(f"To clear it: {EAX} maintenance clear" + (" (after it has finished, or with --force)" if working else ""))
        return
    if working and "--force" not in rest:
        raise Failure("A backup or a restore is still running (above): nothing was cleared. Wait for it to finish, or, if "
                      f"you are sure it is stuck, {EAX} maintenance clear --force (nothing is stopped either way).")
    for rel, what, _ in left:
        (WORK / rel).unlink(missing_ok=True)
        say(f"  cleared: {what}", "green")
    say("EA Explorer is open again and the background runs; what was missed runs at its next turn.", "green")


def upgrade_page(all_services: bool) -> bool:
    """While up rebuilds a running installation (D230) the proxy shows the maintenance page; True when switched on here."""
    flag = WORK / "proxy" / "maintenance"
    if not all_services or flag.exists() or not compose_out(["ps", "--status", "running", "-q", "proxy"]):
        return False
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("upgrade\n", encoding="utf-8", newline="\n")
    say("Everyone sees the maintenance page until this has finished.")
    return True


def backup_helpers() -> None:
    """Backups and restores talk to the operations helper and the backup container: started first (with the database)."""
    compose(["up", "-d", "db", "backup", "ops"], quiet=True)


def compose_attached(args: list[str]) -> int:
    """docker compose in this terminal."""
    from .core import attached
    return attached(compose_args(args))


def interactive(target: list[str], args: list[str]) -> None:
    """A command in a container with this console attached, so it can ask and show progress."""
    code = compose_attached(["exec", *target, *[a for a in args if a]])
    if code != 0:
        raise Failure(f"{target[0]} {' '.join(target[2:])} ended with exit {code}")
