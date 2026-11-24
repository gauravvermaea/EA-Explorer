"""The eax commands (phase 13.9, D331): help, the dispatch, starting again, the console."""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from . import help as help_
from . import info, stack
from .core import (
    EAX,
    ENV_FILE,
    ENV_REL,
    ROOT,
    WINDOWS,
    WORK,
    Failure,
    assert_docker,
    attached,
    capture,
    compose,
    compose_args,
    diagnostics,
    docker_ok,
    kind,
    log_path,
    say,
    setting,
    start_log,
    stop_log,
    version,
)

DOCKER_COMMANDS = {"check", "up", "start-later", "debug", "status", "logs", "down", "backup", "backups", "restore", "restores", "databases", "footprint",
                   "restore-log", "delete-backup", "delete-restore", "app-backup", "restore-model", "restore-app",
                   "stop-backup", "services", "service", "import", "update", "rollback", "test", "standby"}
KEEP = ("tls",)                       # in work/data: the local certificate, kept by cleanup (D107)
KEEP_WORK = ("data", "tools")         # in work: data (its tls kept) and tools (uv and its Python, D331)


def _fill_config() -> None:
    """A newer release's new settings (and their passwords, made here) added before anything starts (R6)."""
    try:
        from . import secrets
        secrets.fill(say_=say)
    except Exception as exc:  # noqa: BLE001 - a start never fails because of it; eax secrets fill says why
        say(f"The config file could not be brought up to date ({exc}): {EAX} secrets fill", "yellow")


def _packs_auto() -> None:
    """Every full start copies what is new or changed in the pack sources first (owner, 11 Nov 2026, D584)."""
    try:
        from . import packs
        packs.auto()
    except Exception as exc:  # noqa: BLE001 - a start never fails because of the packs
        say(f"Industry packs: not copied ({exc}); the packs already in library/industry-packs are used.", "yellow")


def help_text(name: str = "") -> str:
    """The help from eaxcli/help.txt (the one source for every form, D331): the overview, one command, or --all."""
    return help_.render("py", EAX, WINDOWS, name)[0]


def show_help(name: str = "", arg: str = "") -> int:
    """eax help: one command's help, or all."""
    text, code = help_.render("py", EAX, WINDOWS, name, arg)
    print(text)
    return code


def document(options: list[str]) -> None:
    """eax document: every command in full, in the console (a menu, page by page) or as a web page (asks which)."""
    mode = "console" if "--console" in options else "web" if "--web" in options else ""
    if not mode:
        answer = input("Show the commands (1) here in the console or (2) as a web page in your browser? [1/2] ").strip()
        mode = "web" if answer in ("2", "w", "web") else "console"
    if mode == "web":
        import os
        import webbrowser
        out = WORK / "docs" / "eax-commands.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(help_.document_html("py", EAX, WINDOWS).encode("utf-8"))
        say(f"The commands as a web page: {out}")
        if not os.environ.get("EAX_NO_BROWSER"):
            webbrowser.open(out.resolve().as_uri())
        return
    while True:
        say("")
        say(f"EA Explorer commands ({EAX} document)", "cyan")
        print(help_.render("py", EAX, WINDOWS, "--groups")[0])
        try:
            answer = input("Number, s to search, q to quit: ").strip()
        except EOFError:
            return
        if answer in ("q", "Q"):
            return
        if answer in ("s", "S"):
            try:
                word = input("Search for: ").strip()
            except EOFError:
                return
            _paged(help_.render("py", EAX, WINDOWS, "--search", word)[0])
        elif answer.isdigit():
            _paged(help_.render("py", EAX, WINDOWS, "--group", answer)[0])
        elif answer:
            say("Choose a number, s or q.")


def _paged(text: str) -> None:
    rows = max(10, shutil.get_terminal_size((80, 24)).lines - 2)
    for i, line in enumerate(text.splitlines(), 1):
        print(line)
        if i % rows == 0 and sys.stdout.isatty():      # pages only on a terminal (piped or tested: all of it)
            try:
                if input("-- Enter for more, q to stop -- ").strip() == "q":
                    return
            except EOFError:
                return


# ---------------------------------------------------------------- the full test's steps (D823)
def dev_cli_main(args: list[str]) -> int:
    """eax dev check, as the full test's first step (imported only when it runs)."""
    from . import dev_cli
    return dev_cli.main(args)


def full_step(title: str, run) -> tuple[str, bool, str]:
    """One step of the full test: (title, passed, why not); a step that breaks never stops the next one."""
    say(f"\n=== the full test: {title}")
    try:
        code = run()
    except Failure as exc:
        return title, False, str(exc)
    except Exception as exc:  # noqa: BLE001 - said, and the next step runs
        return title, False, f"{type(exc).__name__}: {exc}"
    return title, code in (0, None), "" if code in (0, None) else f"ended with {code}"


def drill_folders(root: Path = ROOT) -> tuple[Path, Path]:
    """The DR drill's two folders in the full test (R9.10): beside the installation, never inside it, the same every time
    (the drill empties both at its start and keeps only its own leftovers in them)."""
    return root.parent / f"{root.name}-drill-dr", root.parent / f"{root.name}-drill-temp"


def dr_drill(run=None) -> int:
    """The full test's last step (R9.10): the restore drill (dr/eax-drill) on this installation, the smoke test on the
    DR copy, then the DR copy stopped and kept and this installation started again and signed in to (--then-back)."""
    import subprocess

    from . import jenkins as J
    dr, temp = drill_folders()
    say(f"The restore drill: this installation backed up and shut down, a DR copy built in {dr} and restored, the smoke "
        "test on it, then the DR copy stopped (kept) and this installation started again. About 30 to 60 minutes.")
    argv = J.command_line(["eax-drill", "--install", str(ROOT), "--dr", str(dr), "--temp", str(temp),
                           "--smoke-after", "--then-back"])
    return (run or subprocess.run)(argv, cwd=ROOT, check=False).returncode


def full_summary(steps: list[tuple[str, bool, str]], began: float | None = None, keep=None, containers=None) -> int:
    """Every step of the full test in one list at the end; 1 when any failed. With began: the summary page too
    (work/tests/full-<time>/index.html, D825), kept in the database by keep(folder) (the api container's)."""
    if began is not None:                                 # every test container gone once the steps are done (14:40)
        left = (containers or stack.test_containers)()
        steps = [*steps, ("no test container left running", not left,
                          f"still there: {', '.join(left)} (eax down removes them)" if left else "")]
    say("\nThe full test, step by step:")
    for title, passed, why in steps:
        say(f"  {'ok    ' if passed else 'FAILED'} {title}" + (f": {why}" if why else ""))
    if began is not None:
        try:
            from . import fullreport
            who = os.environ.get("USERNAME") or os.environ.get("USER") or ""
            summary = fullreport.gather(WORK / "tests", began, steps, version=version(), by=who)
            folder = fullreport.write(WORK / "tests", summary)
            say(f"The summary page: {folder / 'index.html'} (System admin > Self-test > Summary)")
            (keep or (lambda f: stack.interactive(["api", "python", "-m", "eax.testing.cli", "full-save"], [f])))(folder.name)
        except Exception as exc:  # noqa: BLE001 - every step's own report is still there
            say(f"The summary page could not be made or kept: {exc}", "yellow")
    return 0 if all(p for _t, p, _w in steps) else 1


# ---------------------------------------------------------------- starting again (no log: the logs folder goes)
def cleanup(options: list[str]) -> None:
    """eax clean: removes the stack (and its data with --all, asked first)."""
    all_, yes, cert = "--all" in options, "--yes" in options or "-y" in options, "--certificate" in options
    unknown = [o for o in options if o not in ("--all", "--yes", "-y", "--certificate")]
    if unknown:
        raise Failure(f"Unknown option {unknown[0]}")
    say(f"This deletes everything in {WORK}: the config file, all logs, the laptop data folders, and every backup and "
        "restore log (work/backups).", "yellow")
    if all_:
        say("With --all it also deletes the Docker volumes: the databases and documents start empty.", "yellow")
    if not yes and input("Type yes to continue: ").strip() != "yes":
        say("Nothing deleted.")
        return
    if (WORK / "jenkins" / "agent.pid").exists():   # the Jenkins agent holds its log open in work/logs (18 Nov 2026)
        try:
            from . import jenkins
            say(jenkins.stop_agent())
        except Exception:  # noqa: BLE001 - never stops the cleanup
            pass
    try:                                   # the logs first, where no reset deletes them (R2.30)
        from . import logkeep
        base = logkeep.folder(WORK.parent)
        out = logkeep.backup(base, WORK / "logs", logkeep.kept_backups(base), "before-cleanup")
        say(f"Logs backed up first: {logkeep.kept_backups(base) / out['file']}")
        logkeep.clear(base)                # then cleaned too (R5.6: "Logs get cleaned in clean-run"); the backup stays
        say("The container logs and the web log are deleted (the backup above keeps them).")
    except Exception as exc:  # noqa: BLE001 - a log backup never stops the cleanup
        say(f"The logs could not be backed up first: {exc}", "yellow")
    if ENV_FILE.exists():
        attached(compose_args(["down", "-v", "--remove-orphans"] if all_ else ["down", "--remove-orphans"]))
    elif all_:
        say(f"No {ENV_REL}, so the Docker volumes cannot be found by name; list them with: docker volume ls")
    if WORK.exists():
        for p in WORK.iterdir():
            if p.name in KEEP_WORK and not (cert and p.name == "data"):
                if p.name == "data":
                    for q in p.iterdir():
                        if q.name not in KEEP:
                            _remove(q)
                continue
            _remove(p)
    for b in (WORK / "backups", WORK / "data" / "backups"):
        _remove(b)
    if not WINDOWS and ((WORK / "backups").exists() or (WORK / "data" / "backups").exists()) and docker_ok():
        # the backups are written by containers as root: removed by a container too (as eax.sh does)
        attached(["docker", "run", "--rm", "-v", f"{WORK}:/w", "--entrypoint", "sh",
                  setting("EAX_IMAGE_POSTGRES", "postgres:17-alpine"), "-c", "rm -rf /w/backups /w/data/backups"])
    if (WORK / "backups").exists():
        say("WARNING: work/backups could not be deleted completely (a file is in use?): delete it by hand.", "yellow")
    else:
        say("Every backup and restore log is deleted.")
    kept = "uv and its Python (work/tools)" + ("" if cert else " and the local certificate (work/data/tls)")
    say(f"The work folder is empty apart from {kept}. Run {EAX} init laptop to start again.")


def _remove(p: Path) -> None:
    try:
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    except OSError:
        pass


def clean(command: str, rest: list[str], wait_all: bool) -> int:
    """clean-run, clean-debug, clean-restart: cleanup --all --yes, init, then up or debug, each a run of its own."""
    words = [w for w in rest if not w.startswith("--")]
    kind_ = words[0] if words else "laptop"
    # --certificate or --password passed on to init (R11.2): without either, init keeps the choice made before
    modes = [m for m in ("--certificate", "--password") if m in rest]
    last = ["debug" if command == "clean-debug" else "up", *(["--wait-all"] if wait_all else [])]
    steps = [["cleanup", "--all", "--yes"], ["init", kind_, *modes], last]
    if command == "clean-restart":
        if ENV_FILE.exists():
            steps.insert(0, ["down"])
        else:
            say(f"No {ENV_REL} yet: nothing running to bring down; going straight to clean-run.", "yellow")
    os.environ["EAX_BUILD_PULL"] = "1"         # the last step builds on fresh base images (R3.12, D673)
    for step in steps:
        say("")
        say(f"=== {EAX} {' '.join(step)}", "cyan")
        code = run_self(step)
        if code != 0:
            say(f"ERROR: {EAX} {' '.join(step)} failed (exit {code}); {command} stopped there.", "red")
            return code
    return 0


def restart(wait_all: bool) -> int:
    """restart: down, then up, each a run of its own (its own log). The data is kept."""
    for step in (["down"], ["up", *(["--wait-all"] if wait_all else [])]):
        say("")
        say(f"=== {EAX} {' '.join(step)}", "cyan")
        code = run_self(step)
        if code != 0:
            say(f"ERROR: {EAX} {' '.join(step)} failed (exit {code}); restart stopped there.", "red")
            return code
        if step == ["down"]:   # nothing runs now: a maintenance page or a paused background left behind is stale (18 Nov 2026)
            for f in (WORK / "proxy" / "maintenance", WORK / "quiet.json"):
                if f.exists():
                    f.unlink()
                    say(f"Removed what was left: {f.relative_to(ROOT)} (the maintenance page and the paused background).", "yellow")
    return 0


def run_self(args: list[str]) -> int:
    """This program again, as its own run (its own log), like typing the command."""
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / "eaxpy.py"), *args], cwd=ROOT, check=False).returncode


# ---------------------------------------------------------------- the console (phase 13.5, D330)
def console(options: list[str]) -> None:
    """A numbered menu for getting a system that is down back up. It runs in the operations helper; what needs this
    machine (start, stop, diagnostics, any eax command) it hands back here by its exit code. No sign-in on the machine.
    With --server: another installation, through its API."""
    if "--server" in options:
        assert_docker()
        attached(compose_args(["run", "--rm", "--no-deps", "api", "python", "-m", "eax.console_cli", "remote", *options]))
        return
    stopped = False                   # after Stop everything, nothing is started again until asked
    while True:
        ok = docker_ok()
        code = 99
        if ok and ENV_FILE.exists() and not stopped:
            # built first: an ops image from before the console has no console.py (seconds when nothing changed)
            print("Starting the console (the operations helper; the first time it is built, a minute)...", flush=True)
            if capture(compose_args(["up", "-d", "--build", "--no-deps", "ops"]))[0] == 0:
                code = attached(compose_args(["exec", "ops", "python3", "/app/console.py", "--version", version()]))
                if code not in (0, 20, 21, 23, 25):      # it failed: the basic menu, not the same failure again
                    say(f"The console stopped with an error (exit {code}); the basic menu follows. Its log: work/logs/console-*.log", "yellow")
                    code = 99
        if code == 99:                # the helper could not start: only what this machine can do
            say("")
            say(f"EA Explorer console (basic: {'everything is stopped' if stopped else 'the operations helper is not running'})", "cyan")
            if not ok:
                say("Docker is not running: start it, wait for 'Engine running', then choose 1.", "yellow")
            elif not ENV_FILE.exists():
                say(f"Not set up yet: there is no {ENV_REL}. Run {EAX} init laptop first.", "yellow")
            print("  1  Start everything\n  2  Save a diagnostics file for support\n  c  Command prompt (every eax command)\n  q  Quit")
            try:
                a = input("Choose: ").strip().lower()
            except EOFError:
                a = "q"
            code = {"1": 20, "2": 23, "c": 25, "q": 0}.get(a, 98)
        if code == 0:
            return
        if code == 20:
            stopped = False
            run_self(["up"])
        elif code == 21:
            run_self(["down"])
            stopped = True
        elif code == 23:
            run_self(["diag"])
        elif code == 25:
            print("Type an eax command (for example: logs api, services, backups). Empty or back: the menu.")
            while True:
                try:
                    line = input("eax> ").strip()
                except EOFError:
                    break
                if line in ("", "back", "b", "menu"):
                    break
                words = line.split()
                if words[0] == "console":
                    print("You are in the console already.")
                    continue
                run_self(words)


# ---------------------------------------------------------------- init, check, the dispatch
AUTH_MODES = {"certificate": "Certificates: EA Explorer's own, renewed by themselves; no internal passwords (R6-C1)",
              "password": "Passwords: as before, rotated by themselves every 90 days (R6-R1)"}


def auth_mode(rest: list[str], kind_: str, ask=input, tty: bool | None = None) -> tuple[str, str]:
    """How the services sign in to each other (R6-C1, D743): --certificate or --password; with neither, the choice made
    the last time on this machine (persist/, so a clean restart does not ask again), else asked when a person is at the
    keyboard, else password on a laptop and certificate on a server. Returns (mode, how it was decided)."""
    import sys

    from . import persist as P
    if "--certificate" in rest and "--password" in rest:
        raise Failure("--certificate or --password, not both.")
    if "--certificate" in rest or "--password" in rest:
        return ("certificate" if "--certificate" in rest else "password"), "given"
    kept = P.read_json(P.folder() / "auth.json", {})[0].get("mode")
    if kept in AUTH_MODES:
        return kept, "as chosen before"
    if tty if tty is not None else sys.stdin.isatty():
        say("How should EA Explorer's services sign in to each other?")
        for i, v in enumerate(AUTH_MODES.values(), 1):
            say(f"  {i}  {v}")
        default = "2" if kind_ == "laptop" else "1"
        got = (ask(f"Choose 1 or 2 [{default}]: ").strip() or default)
        return ("certificate" if got in ("1", "certificate") else "password"), "asked"
    return ("password" if kind_ == "laptop" else "certificate"), "the default"


def init(rest: list[str]) -> None:
    """eax init [laptop|server] [--certificate|--password] [--hostname NAME]: the config file from the laptop or server template. A server
    gets strong random passwords made here (R6-C1); a laptop keeps the template's (laptop users carry on as before)."""
    import re

    from . import persist as P
    from .secrets import generate
    words = [w for w in rest if not w.startswith("--")]
    kind_ = words[0] if words else "laptop"
    template = ROOT / "deploy" / "templates" / f"eaexplorer.{kind_}.env"
    if ENV_FILE.exists():
        raise Failure(f"{ENV_REL} already exists; not overwriting. Use {EAX} cleanup to start again.")
    if not template.exists():
        raise Failure(f"Unknown deployment kind: {kind_}")
    mode, how = auth_mode(rest, kind_)
    for d in ("logs", "backups", "proxy", "data/imports", "data/exports", "data/tls"):
        (WORK / d).mkdir(parents=True, exist_ok=True)
    # UTF-8 without BOM and LF endings (Docker Compose reads it cleanly)
    text = "\n".join(template.read_text(encoding="utf-8").splitlines()) + "\n"
    made = 0
    if kind_ != "laptop":                   # every change-me password made here, strong and random (R6-C1)
        keys = [m.group(1) for m in re.finditer(r"^([A-Z0-9_]+)=change-me", text, re.MULTILINE)]
        values = generate(keys)
        text = re.sub(r"^([A-Z0-9_]+)=change-me.*$", lambda m: f"{m.group(1)}={values.get(m.group(1), m.group(0))}", text,
                      flags=re.MULTILINE)
        made = len(values)
    # the name people open it at (D765): --hostname, else asked on a server when someone is at the keyboard
    from . import hostname as H
    given = rest[rest.index("--hostname") + 1] if "--hostname" in rest and rest.index("--hostname") + 1 < len(rest) else ""
    if not given and kind_ != "laptop" and sys.stdin.isatty() and not os.environ.get("EAX_NONINTERACTIVE"):
        given = input("The name people will open EA Explorer at (e.g. ea.example.org; Enter to set it later with eax hostname set): ").strip()
    if given:
        text = re.sub(r"^EAX_HOSTNAME=.*$", f"EAX_HOSTNAME={H.valid(given)}", text, flags=re.MULTILINE)
    if re.search(r"^EAX_AUTH_MODE=", text, re.MULTILINE):
        text = re.sub(r"^EAX_AUTH_MODE=.*$", f"EAX_AUTH_MODE={mode}", text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n\n# How the services sign in to each other (R6-C1)\nEAX_AUTH_MODE={mode}\n"
    ENV_FILE.write_text(text, encoding="utf-8", newline="\n")
    try:
        ENV_FILE.chmod(0o600)
    except OSError:
        pass
    try:
        P.write_json(P.folder() / "auth.json", {"mode": mode})
    except Exception:  # noqa: BLE001 - remembering the choice is a convenience
        pass
    say(f"Created {ENV_REL} ({kind_}) from deploy/templates/eaexplorer.{kind_}.env; the services sign in with "
        f"{'certificates' if mode == 'certificate' else 'passwords'} ({how}; {EAX} init --certificate or --password to choose).")
    if kind_ != "laptop":
        say(f"{made} passwords and keys were made, strong and random; {EAX} secrets shows them by name, never their values.")
        _ask_base_folder()
    else:
        info.show_logins()


BASE_ASK = ("Base folder for all the data (databases, documents, logs, backups, imports, exports, certificates, "
            "reports); mount what you want onto its folders later")


def _ask_base_folder() -> None:
    """A server or platform keeps all its data under one base folder (R5.4, D687; it replaced the backups folder's
    question, R2.44): asked here, kept as EAX_DATA_ROOT (the template's /srv/eax when nothing is typed)."""
    import re
    import sys
    text_ = ENV_FILE.read_text(encoding="utf-8")
    m = re.search(r"(?m)^EAX_DATA_ROOT=(.*)$", text_)
    default = m.group(1).strip() if m else "/srv/eax"
    folder = input(f"{BASE_ASK} [{default}]: ").strip() if sys.stdin.isatty() else ""
    folder = folder or default
    if m:
        text_ = text_[:m.start()] + f"EAX_DATA_ROOT={folder}" + text_[m.end():]
    else:
        text_ = text_.rstrip("\n") + f"\nEAX_DATA_ROOT={folder}\n"
    ENV_FILE.write_text(text_, encoding="utf-8", newline="\n")
    say(f"All the data goes under {folder} (EAX_DATA_ROOT), a folder for each kind, made at the first {EAX} up; "
        f"{EAX} folders shows them.")


def check() -> None:
    """eax check: Docker and Docker Compose are there."""
    if attached(["docker", "version", "--format", "Docker {{.Server.Version}}"]) != 0:
        raise Failure("Docker is not running.")
    attached(["docker", "compose", "version"])
    if not ENV_FILE.exists():
        raise Failure(f"No {ENV_REL} yet: run {EAX} init")
    say(f"Config: {ENV_REL} ({kind()})")
    compose(["config", "--quiet"])
    say("Compose configuration is valid.")


def need_backups() -> None:
    """Stops when backups are switched off."""
    if not stack.service_on("backups"):
        raise Failure(f"Backups are switched off: {EAX} service backups on")


def dispatch(command: str, rest: list[str], wait_all: bool) -> None:
    """Runs one eax command."""
    ops = ["ops", "python3", "/app/ops.py"]
    api = ["api", "python", "-m", "eax.backups_cli"]
    if command in DOCKER_COMMANDS:
        assert_docker()
    if command == "init":
        init(rest)
    elif command == "check":
        check()
    elif command == "up":
        if not rest:                               # the industry packs first (D584); never fatal
            _fill_config()
            _packs_auto()
        page = stack.upgrade_page(not rest)        # an upgrade (D230): the maintenance page while it rebuilds
        try:
            stack.up(rest, wait_all)
        finally:
            if page:
                _remove(WORK / "proxy" / "maintenance")
        if rest:
            info.show_part_urls(rest)
        else:
            info.show_urls()
            info.show_logins()
    elif command == "start-later":
        stack.later()
    elif command == "debug":
        if not rest:
            _fill_config()
            _packs_auto()
        code = stack.up(rest, wait_all, no_throw=True)
        if code != 0:
            say(f"docker compose up failed (exit {code}); recording what is running anyway.", "red")
        diagnostics()
        if rest:
            info.show_part_urls(rest)
        else:
            info.show_urls()
            info.show_logins()
        info.watch_containers(rest)
    elif command == "diag":
        diagnostics()
    elif command == "status" and rest[:1] == ["problems"]:    # the problems only, with their codes (R7.9, D787)
        from . import problems
        problems.show(set(stack.off_containers()))
    elif command == "status":
        from . import core as _core
        _core.heading(f"EA Explorer {_core.release()}, build {_core.build_id()}")
        _core.say_status_lines(_core.compose_out(["ps", "-a"]))    # each container in its state's colour (R2.10)
        stack.show_filesystems()
        from . import problems  # every problem with its code and what to do (R7.9)
        problems.show(set(stack.off_containers()))
    elif command == "logs" and rest[:1] in (["backup"], ["clean"]):   # back up and clean the logs (R2.30)
        from . import logs_cli
        return logs_cli.main(rest)
    elif command == "logs":
        attached(compose_args(["logs", "-f", "--tail=100", *rest]))
    elif command == "down":
        compose(["down"])
        stack.remove_extras()        # the test, scan and platform containers too (owner, 19 Nov 2026, 05:45)
    elif command == "backup":
        need_backups()
        stack.backup_helpers()
        stack.interactive([*ops, "backup"], rest)
    elif command == "backups":
        stack.backup_helpers()
        stack.interactive([*ops, "list"], rest)
    elif command == "footprint" and rest[:1] == ["--history"]:     # the resource history (R3.5-M8), kept by the API
        stack.interactive(["api", "python", "-m", "eax.resources", "history"], rest[1:])
    elif command == "footprint":        # how much each container takes (R2.22): kept in work/footprint
        stack.interactive([*ops, "footprint"], rest)
    elif command == "stop-backup":
        stack.backup_helpers()
        stack.interactive([*ops, "stop-backup"], [])
    elif command == "restore-app":
        stack.interactive([*api, "restore-all"], rest)
    elif command == "maintenance":
        stack.maintenance(rest[0] if rest else "", rest[1:])
    elif command == "restore":
        need_backups()
        stack.backup_helpers()
        stack.interactive([*ops, "restore"], [*rest, "--version", version()])
    elif command == "restores":
        stack.backup_helpers()
        stack.interactive([*ops, "restores"], [])
    elif command == "databases":       # where each database lives and whether it answers (R2.50)
        stack.interactive(["api", "python", "-m", "eax.databases"], rest)
    elif command in ("restore-log", "delete-backup", "delete-restore"):
        stack.backup_helpers()
        stack.interactive([*ops, command], rest)
    elif command == "app-backup":
        stack.interactive([*api, "backup"], rest)
    elif command == "import":           # deliveries dropped in the import folder (phase 34, D466)
        stack.interactive(["api", "python", "-m", "eax.deliveries_cli"], rest)
    elif command in ("update", "rollback"):   # updating to a new release from git (phase 36, D417)
        stack.backup_helpers()
        stack.interactive([*ops, command], rest)
    elif command == "restore-model":
        stack.interactive([*api, "restore"], rest)
    elif command == "test" and "--build" in rest:   # only build the test runner image (D570; the Self-test page's button)
        say("Building the test runner (about 1.5 GB, 5 to 15 minutes the first time): base image, Python packages, "
            "Chromium, scanners.")
        compose(["--profile", "test", "build", "testrunner"])
        say("The test runner is built.")
    elif command == "test" and rest[:1] == ["jenkins"]:   # every Jenkins pipeline probed, nothing run (R9.13, D854)
        from . import jenkins_test
        return jenkins_test.run(rest[1:])
    elif command == "test" and rest[:1] == ["commands"]:  # each safe eax command run and checked (R9.14, D854)
        from . import command_tests
        return command_tests.run(rest[1:])
    elif command == "test" and rest[:1] == ["sonar"]:   # the SonarQube scan of the whole repository (Release 8, D792)
        from . import sonar
        sonar.main(rest[1:])
    elif command == "test" and rest[:1] == ["clean"]:   # delete every test run's data, for good (R2.0.1, D593)
        stack.interactive(["api", "python", "-m", "eax.testing.cli", "clean", "all"], rest[1:])
    elif command == "test" and rest[:1] == ["delete"]:  # delete test results for good (R2.43)
        stack.interactive(["api", "python", "-m", "eax.testing.cli", "delete"], rest[1:])
    elif command == "test" and rest[:1] in (["prune"], ["summary"]):   # only the detailed files; the summaries (D825)
        stack.interactive(["api", "python", "-m", "eax.testing.cli", rest[0]], rest[1:])
    elif command == "test" and rest[:1] == ["api"]:     # the API test harness: one call (R3.16)
        stack.interactive(["api", "python", "-m", "eax.testing.cli", "api"], rest[1:])
    elif command == "test" and rest[:1] == ["watch"] and "--browser" in rest:   # the live view in a browser (R5.20)
        import webbrowser
        run = next((a for a in rest[1:] if a.isdigit()), "")
        port = setting("EAX_HTTPS_PORT", "443")
        url = f"https://{setting('EAX_HOSTNAME', 'localhost')}{'' if port == '443' else ':' + port}/#/admin/self-test/watch" \
            + (f"/{run}" if run else "")
        say(f"The live view of the {'run ' + run if run else 'run going on'}: {url}")
        if not os.environ.get("EAX_NO_BROWSER"):
            webbrowser.open(url)
    elif command == "test" and rest[:1] in (["watch"], ["stop"]):   # follow a run live, or stop it (R3.2)
        stack.interactive(["api", "python", "-m", "eax.testing.cli", rest[0]], rest[1:])
    elif command == "dr-pack":          # a DR pack in one command, with its checksums and fingerprint (R5.6-B2)
        from . import drpack
        return drpack.main(rest)
    elif command == "drill":            # the steps of the automated restore drill, run from outside (R5.6-B2)
        from . import drill
        if rest[:1] == ["restore"]:     # the others never start anything: "running" must see a stopped installation
            stack.backup_helpers()
        return drill.main(rest)
    elif command == "test" and rest[:1] in (["backup-restore"], ["restore"]):   # the backup and restore test (R5.6-B1)
        from . import backup_restore
        stack.backup_helpers()
        return backup_restore.main(rest[1:])
    elif command == "test":             # the self-test (phase 36.1, D367, D529): results read in the api container, a
        read = [a for a in rest if a in ("--status", "--last", "--report", "--fixtures", "--clean")]   # run through ops
        if read:
            stack.interactive(["api", "python", "-m", "eax.testing.cli", read[0].removeprefix("--")],
                              [a for a in rest if a != read[0]])
        else:
            # the full test ends with the backup and restore test, which asks nothing (owner, 16 Nov 2026, 16:54: "backup
            # and restore test should not ask me anything"); it runs from eax itself, one command after another
            from . import backup_restore
            last = "full" in rest and "--ci" not in rest
            # the full test from the command line does everything but the benchmark (owner, 21 Nov 2026, 13:06: "can dev
            # check be part pf full test along with sonar this way one full test will do everything excpt performance
            # ttest. Its ok if we can only do this from command line"; D823): the dev check first (its unit tests'
            # coverage joins the run's own, D807), the self-test with the attack test, the backup and restore test,
            # SonarQube; --no-dev-check and --no-sonar leave one out; then the DR drill (R9.10), --no-dr leaves it out
            steps: list[tuple[str, bool, str]] = []
            began = time.time()                       # each step's files made since then go on the summary page (D825)
            no_sonar, no_dr = "--no-sonar" in rest, "--no-dr" in rest
            if last:                                  # what would slow it down, said first (R14.27, R14.33)
                from . import preflight
                preflight.check()
            if last and "--no-dev-check" not in rest:
                steps.append(full_step("dev check", lambda: dev_cli_main(["check"])))
            rest = [a for a in rest if a not in ("--no-dev-check", "--no-sonar", "--no-dr")]
            # always prepare the runner first (D584): seconds when it is current, rebuilt when the code or version changed
            say("Preparing the test runner... (the first time about 5 to 15 minutes; seconds when it is current)")
            compose(["--profile", "test", "build", "testrunner"])
            stack.backup_helpers()
            failed = None
            try:
                stack.interactive([*ops, "test"], [*rest, "--version", version()])
            except Failure as exc:
                failed = exc
            if last:
                steps.append(("self-test", failed is None, str(failed or "")))
                steps.append(full_step("backup and restore test", lambda: backup_restore.main([])))
                if not no_sonar:
                    from . import sonar as sonar_
                    steps.append(full_step("SonarQube scan", lambda: sonar_.main([])))
                if not no_dr:
                    steps.append(full_step("DR drill", dr_drill))
                return full_summary(steps, began)
            if failed:
                raise failed
    elif command == "standby":          # the database standby (phase 36.3, D527; EAX_COMPOSE_EXTRA=standby)
        what = rest[0] if rest else "status"
        if what == "status":
            stack.interactive(["db", "psql", "-U", "postgres", "-c"],
                              ["SELECT client_addr, state, sync_state, replay_lag FROM pg_stat_replication"])
            stack.interactive(["db-standby", "psql", "-U", "postgres", "-c"],
                              ["SELECT pg_is_in_recovery() AS following_the_primary, now() - pg_last_xact_replay_timestamp() AS behind_by"])
        elif what == "promote":
            say("The standby becomes the primary: it stops following and accepts changes. Then set EAX_DB_HOST=db-standby "
                f"(or the standby's host) and run {EAX} up.")
            if input("Type PROMOTE to go on: ").strip() != "PROMOTE":
                say("Nothing changed.")
                return
            stack.interactive(["-u", "postgres", "db-standby", "pg_ctl", "promote", "-D"], ["/var/lib/postgresql/data"])
        else:
            raise Failure(f"Usage: {EAX} standby status|promote")
    elif command == "services":
        stack.show_services()
    elif command == "servers":
        stack.servers(rest)
    elif command == "service":
        if len(rest) < 2:
            raise Failure(f"Usage: {EAX} service <name> on|off   (names: {', '.join(stack.SERVICES)})")
        stack.set_service(rest[0], rest[1].lower())
    elif command == "url":
        info.show_urls()
        info.show_logins()
    elif command == "logins":
        if not ENV_FILE.exists():
            raise Failure(f"No {ENV_REL} yet: run {EAX} init first.")
        info.show_logins()
    elif command == "trust":
        if not ENV_FILE.exists():
            raise Failure(f"No {ENV_REL} yet: run {EAX} init first.")
        info.trust(rest)
    else:
        raise Failure(help_.unknown(command, EAX))


def main(argv: list[str]) -> int:
    """eax: the command line's entry point."""
    if "--no-color" in argv:                  # plain text, wherever it is typed (R2.10)
        from . import core as _core
        _core.no_colour()
        argv = [a for a in argv if a != "--no-color"]
    command = argv[0] if argv else ""
    if command == "screen" or (not command and sys.stdin.isatty()):   # the full screen (R3.1); the numbered menu without it
        from . import screen
        return screen.main(argv[1:])
    if command == "measure":                  # how much memory it needs, measured in one go (R3.5-M1)
        from . import measure
        return measure.main(argv[1:])
    if command == "menu":                     # the numbered menu (R2.29), kept as it is (owner: "keep both kinds of menus")
        from . import menu
        return menu.main(argv[1:])
    command = command or "help"
    rest = [a for a in argv[1:] if a]
    if command in ("help", "-h", "--help", "/?"):
        return show_help(rest[0] if rest else "", rest[1] if len(rest) > 1 else "")
    if any(a in ("--help", "-h", "/?") for a in rest):
        return show_help(command)     # <command> --help: the help of that command
    if command == "run":
        command = "up"                # run: the everyday start, the same as up
    elif command == "stop":
        command = "down"              # stop: the same as down (the data is kept)
    wait_all = "--wait-all" in rest
    rest = [a for a in rest if a != "--wait-all"]
    try:
        if command in ("clean-run", "clean-debug", "clean-restart"):
            return clean(command, rest, wait_all)
        if command == "restart":
            return restart(wait_all)
        if command == "cleanup":
            cleanup(rest)
            return 0
        if command == "console":
            console(rest)
            return 0
        if command == "document":
            document(rest)
            return 0
        if command == "jobs":                   # the background job queue (R5.30 to R5.34): every form
            from . import jobs_cli
            return jobs_cli.main(rest)
        if command == "ticket":                 # the service desk's requests (R5.11, D692): every form
            from . import ticket_cli
            return ticket_cli.main(rest)
        if command == "dev":                    # the newcomer's first check (R5.16): every form, nothing running
            from . import dev_cli
            return dev_cli.main(rest)
        if command == "estimate":               # the server sizing estimate (R5.19): every form, nothing running
            from . import estimate_cli
            return estimate_cli.main(rest)
        if command == "optimise":               # the optimisation report (R5.1, D697): every form
            from . import optimise_cli
            return optimise_cli.main(rest)
        if command == "db":                     # database maintenance (R5.12, D691): every form
            from . import db_cli
            return db_cli.main(rest)
        if command in ("sign", "verify"):       # signed deployments, the organisation's own (R5.10, D685): every form
            from . import signing
            return signing.main(command, rest)
        if command == "allow":                  # the IP allow lists from the machine (R5.2, D686): every form
            from . import allow_cli
            return allow_cli.main(rest)
        if command == "folders":                # where the data lives (R5.4, D687): every form
            from . import datafolders
            return datafolders.main(rest)
        if command == "persist":                # what persist/ holds, and deleting it (R2.26): every form
            from . import persist_cli
            return persist_cli.main(rest)
        if command == "schedule":               # scheduled eax commands (D559): persist/schedules.json, every form
            from . import schedule_cli
            return schedule_cli.main(rest)
        if command == "test" and "--reset-survival" in rest:   # settings outlive a real reset (D561): runs here
            from . import reset_survival
            return reset_survival.main(ROOT, rest)
        if command == "packs":                  # the industry packs (phase 39, D546): one Python program for every form
            from . import packs
            return packs.main(rest)
        if command == "certs":                  # certificate mode (R6-C1, D743)
            from . import certs
            return certs.main(rest)
        if command == "jenkins":                # Jenkins, a pipeline per command (R6.6-J1, D750)
            from . import jenkins
            return jenkins.main(rest)
        if command == "hostname":               # the name people open EA Explorer at (D765)
            from . import hostname
            return hostname.main(rest)
        if command == "settings":               # the settings exported and imported (Release 6.7, D755)
            from . import settings_cli
            return settings_cli.main(rest)
        if command == "sonar":                  # SonarQube's own pages, the last scan's results, nothing scanned (D805)
            from . import sonar
            return sonar.dashboard(rest)
        if command == "images":                 # the images in use and the ones published, every 3 months (R9.12, D841)
            from . import images
            return images.main(rest)
        if command == "errors":                 # what an error code means and what to do (Release 7.9, D787)
            from . import problems
            return problems.errors_main(rest)
        if command == "site":                   # the website: made, checked, its pictures taken (Release 7.1, D776, D777)
            from . import site_cli
            return site_cli.main(rest)
        if command == "access":                 # an administrator back in, from the machine (R6.6-J1, D762)
            from . import access
            return access.main(rest)
        if command == "setup":                  # the guides, guided (R6.6, D750)
            from . import setup
            return setup.main(rest)
        if command in ("deploy", "secrets"):    # phase 36 (D498, D504): one Python program for every form (D500)
            if command == "deploy":
                from . import deploy
                return deploy.main(rest)
            from . import secrets
            return secrets.main(rest)
    except (Failure, KeyboardInterrupt) as exc:
        say(f"ERROR: {exc}" if isinstance(exc, Failure) else "Stopped.", "red")
        return 1
    start_log(command, rest)
    if Path(ROOT / "eaexplorer.env").exists() and not ENV_FILE.exists():
        say(f"Found eaexplorer.env in the main folder: it is no longer used. The config now lives in {ENV_REL}.", "yellow")
        say(f"Delete the old file and run {EAX} init laptop (or copy your changes into {ENV_REL}).", "yellow")
    failed = False
    try:
        dispatch(command, rest, wait_all)
    except Failure as exc:
        failed = True
        say(f"ERROR: {exc}", "red")
    except KeyboardInterrupt:
        failed = True
        say("Stopped (Ctrl+C).", "yellow")
    finally:
        if log_path():
            print(f"Log: {log_path()}")
        stop_log()
    return 1 if failed else 0


