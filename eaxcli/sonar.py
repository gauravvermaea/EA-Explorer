"""eax test sonar (Release 8, R8; D740, D792): the whole repository scanned by SonarQube, every issue in a report.

  eax test sonar            pull the newest SonarQube and scanner (the last ones when offline), start SonarQube in the
                            test profile, scan, write work/tests/sonar-<time>/ (report.md, issues.json, hotspots.json,
                            summary.json), remove SonarQube (its data kept); fails when an issue is not accepted in
                            writing (services/api/eax/testing/sonar_accepted.json)
  eax test sonar --keep     the same, SonarQube left running afterwards (eax logs sonarqube)
  eax test sonar --reset    SonarQube's own data deleted first (a fresh SonarQube; nothing of EA Explorer is touched)

The SonarQube steps run in the test runner on the internal network (eax/testing/sonar.py); nothing gets a port. Every
fix made from a report is tested before and after (owner, 19 Nov 2026, 00:09: "For every fix you plan to make we need a
test case to ensure it works exactly as planned before and after"): run every test first, scan, fix, run every test
again and scan again."""

from __future__ import annotations

import os
import time

from .core import WORK, Failure, capture, compose, compose_args, docker_ok, heading, ok, say, warn

TOKEN = WORK / "tests" / "sonar" / "token"
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


def reset() -> None:
    """SonarQube's own data deleted (its volumes and the admin password's copy), so it starts afresh; nothing of EA
    Explorer is touched."""
    compose(["--profile", "test", "rm", "-sf", "sonarqube"], no_throw=True)
    for v in SONAR_VOLUMES:
        capture(["docker", "volume", "rm", "-f", f"{project_name()}_{v}"])
    (WORK / "tests" / "sonar" / "admin").unlink(missing_ok=True)
    say("SonarQube's own data deleted; it starts afresh.")


def main(rest: list[str]) -> int:
    """eax test sonar [--keep] [--reset]."""
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
    compose(["--profile", "test", "up", "-d", "--no-deps", "sonarqube"])
    folder = folder_name()
    try:
        say("Waiting for SonarQube (a few minutes the first time)...")
        got = compose(runner(["prepare"]), no_throw=True)
        if got == 3:      # its admin password's copy is gone (a cleanup deleted work/, e.g. clean-restart): afresh
            say("SonarQube's admin password was lost with the work folder (a cleanup): starting SonarQube afresh.")
            reset()
            compose(["--profile", "test", "up", "-d", "--no-deps", "sonarqube"])
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
        if "--keep" not in rest:
            compose(["--profile", "test", "rm", "-sf", "sonarqube"], no_throw=True)
    if code == 0:
        ok(f"No issue to fix. Report: work/tests/{folder}/report.md")
        return 0
    if code == 1:
        raise Failure(f"SonarQube found issues to fix: work/tests/{folder}/report.md (and issues.json beside it)")
    raise Failure(f"The report could not be made (exit {code}): eax logs sonarqube")
