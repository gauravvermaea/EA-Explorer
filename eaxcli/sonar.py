"""eax test sonar (Release 8, R8; D740, D792): the whole repository scanned by SonarQube, every issue in a report.

  eax test sonar            pull the newest SonarQube and scanner (the last ones when offline), start SonarQube in the
                            test profile, scan, write work/tests/sonar-<time>/ (report.md, issues.json, hotspots.json,
                            summary.json), remove SonarQube (its data kept); fails when an issue is not accepted in
                            writing (services/api/eax/testing/sonar_accepted.json)
  eax test sonar --keep     the same, SonarQube left running afterwards (eax logs sonarqube)
  eax test sonar --open     the same, SonarQube left running with its own pages at http://localhost:9000 on this
                            computer only (EAX_SONAR_PORT to change the port), until eax down (D805)
  eax test sonar --reset    SonarQube's own data deleted first (a fresh SonarQube; nothing of EA Explorer is touched)

The SonarQube steps run in the test runner on the internal network (eax/testing/sonar.py); nothing gets a port but
SonarQube's own pages with --open, and those only on this computer. Every
fix made from a report is tested before and after (owner, 19 Nov 2026, 00:09: "For every fix you plan to make we need a
test case to ensure it works exactly as planned before and after"): run every test first, scan, fix, run every test
again and scan again."""

from __future__ import annotations

import os
import time

from .core import WORK, Failure, capture, compose, compose_args, docker_ok, heading, ok, say, warn

TOKEN = WORK / "tests" / "sonar" / "token"
OPEN_FILE = "deploy/compose/test/docker-compose.sonar-open.yml"     # --open: SonarQube's port, on 127.0.0.1 only
SONAR_VOLUMES = ("eax-sonar-data", "eax-sonar-extensions")


def folder_name(now: float | None = None) -> str:
    """The report's folder in work/tests: sonar-<date>-<time>."""
    return "sonar-" + time.strftime("%Y%m%d-%H%M%S", time.localtime(now))


def runner(args: list[str]) -> list[str]:
    """A step in the test runner: its own Python, on the internal network, nothing else started."""
    return ["--profile", "test", "run", "--rm", "--no-deps", "--entrypoint", "python", "testrunner", "-m", "eax.testing.sonar", *args]


def scanner_args() -> list[str]:
    """The scanner, with the token from the environment (never on the command line)."""
    return ["--profile", "test", "run", "--rm", "--no-deps", "-e", "SONAR_TOKEN", "sonar-scanner"]


def project_name() -> str:
    """This installation's Docker name, for its volumes."""
    f = WORK / "compose-project"
    return f.read_text(encoding="utf-8").strip() if f.is_file() else "eaexplorer"


def start_args(rest: list[str]) -> list[str]:
    """Starting SonarQube for the scan; with --open its pages on this computer too (the extra file gives the port)."""
    extra = ["-f", OPEN_FILE] if "--open" in rest else []
    return [*extra, "--profile", "test", "up", "-d", "--no-deps", "sonarqube"]


def open_address() -> str:
    """Where SonarQube's own pages are with --open."""
    return f"http://localhost:{os.environ.get('EAX_SONAR_PORT') or '9000'}"


def dashboard(rest: list[str]) -> int:
    """eax sonar open | close (owner, 19 Nov 2026, 21:28: "i wanna only execute it not run a test"; D805): SonarQube's
    own pages with the last scan's results, on this computer only, nothing scanned; close removes SonarQube again (its
    data kept, and eax down removes it too)."""
    what = rest[:1]
    if what not in (["open"], ["close"]):
        raise Failure("eax sonar open (SonarQube's pages with the last scan) or eax sonar close")
    if not docker_ok():
        raise Failure("Docker does not answer (EAX-STACK-003): start Docker Desktop, then eax sonar open again.")
    if what == ["close"]:
        compose(["--profile", "test", "rm", "-sf", "sonarqube"], no_throw=True)
        ok("SonarQube closed (its data and the last scan kept).")
        return 0
    heading("SonarQube's pages (the last scan's results; nothing is scanned)")
    say("The test runner (seconds when it is current)...")
    compose(["--profile", "test", "build", "testrunner"])     # its "ready" step is new in D805: an older runner lacks it
    compose(start_args(["--open"]))
    say("Waiting for SonarQube (a minute or two; longer the first time)...")
    got = compose(runner(["ready"]), no_throw=True)
    if got == 3:
        raise Failure("SonarQube's admin password is not the one kept in work/tests/sonar/admin: "
                      "eax test sonar --reset starts SonarQube afresh and scans")
    if got != 0:
        raise Failure("SonarQube did not start: eax logs sonarqube")
    where = published_port()
    if not where:
        raise Failure("SonarQube runs but Docker gave it no port, so the browser cannot reach it: eax sonar close, then "
                      f"eax sonar open again (the port comes from {OPEN_FILE})")
    ok(f"SonarQube is open at {open_address()} (Docker: {where}; this computer only). Sign in as admin; the password is in "
       "work/tests/sonar/admin. It shows the last scan (eax test sonar makes a new one). eax sonar close ends it.")
    return 0


def published_port() -> str:
    """Where Docker publishes SonarQube's pages ("127.0.0.1:9000"), or "" when the container has no port (D805: on 20 Nov
    eax sonar open said "open" while the browser showed nothing; it now checks before saying so)."""
    code, out = capture(["docker", "port", f"{project_name()}-sonarqube-1", "9000"])
    return out.strip().splitlines()[0].strip() if code == 0 and out.strip() else ""


def reset() -> None:
    """SonarQube's own data deleted (its volumes and the admin password's copy), so it starts afresh; nothing of EA
    Explorer is touched."""
    compose(["--profile", "test", "rm", "-sf", "sonarqube"], no_throw=True)
    for v in SONAR_VOLUMES:
        capture(["docker", "volume", "rm", "-f", f"{project_name()}_{v}"])
    (WORK / "tests" / "sonar" / "admin").unlink(missing_ok=True)
    say("SonarQube's own data deleted; it starts afresh.")


def main(rest: list[str]) -> int:
    """eax test sonar [--keep] [--open] [--reset]."""
    if not docker_ok():
        raise Failure("Docker does not answer (EAX-STACK-003): start Docker Desktop, then eax test sonar again.")
    heading("SonarQube scan of the whole repository (Release 8)")
    if "--reset" in rest:
        reset()
    say("The newest SonarQube and scanner (the last ones pulled when offline)...")
    if capture(compose_args(["--profile", "test", "pull", "sonarqube", "sonar-scanner"]))[0] != 0:
        warn("Could not pull (offline?): using the images pulled last time.")
    say("The test runner (seconds when it is current)...")
    compose(["--profile", "test", "build", "testrunner"])
    compose(start_args(rest))
    folder = folder_name()
    try:
        say("Waiting for SonarQube (a few minutes the first time)...")
        got = compose(runner(["prepare"]), no_throw=True)
        if got == 3:      # its admin password's copy is gone (a cleanup deleted work/, e.g. clean-restart): afresh
            say("SonarQube's admin password was lost with the work folder (a cleanup): starting SonarQube afresh.")
            reset()
            compose(start_args(rest))
            got = compose(runner(["prepare"]), no_throw=True)
        if got != 0:
            raise Failure("SonarQube is not ready: eax logs sonarqube (eax test sonar --reset starts it afresh)")
        os.environ["SONAR_TOKEN"] = TOKEN.read_text(encoding="utf-8").strip()
        say("Scanning (several minutes)...")
        if compose(scanner_args(), no_throw=True) != 0:
            raise Failure("The scanner stopped: see its output above")
        code = compose(runner(["report", folder]), no_throw=True)
    finally:
        os.environ.pop("SONAR_TOKEN", None)
        TOKEN.unlink(missing_ok=True)
        if "--keep" not in rest and "--open" not in rest:
            compose(["--profile", "test", "rm", "-sf", "sonarqube"], no_throw=True)
        if "--open" in rest:
            ok(f"SonarQube is open at {open_address()} (this computer only) until eax down. Sign in as admin; "
               "the password is in work/tests/sonar/admin.")
    if code == 0:
        ok(f"No issue to fix. Report: work/tests/{folder}/report.md")
        return 0
    if code == 1:
        raise Failure(f"SonarQube found issues to fix: work/tests/{folder}/report.md (and issues.json beside it)")
    raise Failure(f"The report could not be made (exit {code}): eax logs sonarqube")
