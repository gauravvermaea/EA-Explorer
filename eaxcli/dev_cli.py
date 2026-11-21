"""eax dev check (R5.16; owner, 13 Nov 2026: "what happens if I need another ai to work on this"): the first thing a
newcomer (a person or another AI) runs, before changing anything. On this machine, nothing installed and nothing
started: it runs what CI runs and the documents' cross-checks, and says what is wrong and where to look.

  eax dev check [--quick] [--web]

  1. lint        ruff over the Python (services/api's settings)
  2. tests       pytest in services/api (--quick: stops at the first failure)
  3. documents   the decisions numbered once each, in order; the help (eaxcli/help.txt) ASCII with short summaries;
                 docs/handover.md, AGENTS.md and CLAUDE.md there; every R5 story of docs/build-phases.md marked
  4. web         (--web) the screens build (npm run build in services/web)

What it needs (it says so when one is missing, and never installs it): Python 3.12 with services/api's
requirements-dev.txt, and Node 22 for --web. When this computer's Python has no ruff or pytest (eax's own Python in
work/tools has neither), lint and tests run in the test runner instead: its image has requirements-dev.txt, Docker
runs it with this folder mounted, nothing is installed here (owner's laptop, 19 Nov 2026, 06:41: "No module named
ruff", "No module named pytest"; D794).
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services" / "api"


LOG: list[str] = []      # everything this check printed, saved to work/tests/dev-check-<time>.log (D794)


def say(text: str = "") -> None:
    """Prints a line and keeps it for the log."""
    print(text, flush=True)
    LOG.append(text)


def _run(title: str, cmd: list[str], cwd: Path) -> tuple[str, bool, str]:
    """Runs one step in this terminal, its output kept for the log; (title, passed, why not)."""
    say(f"\n== {title}: {' '.join(cmd)}")
    try:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return title, False, f"{cmd[0]} is not on this machine (see eax help dev)"
    for line in p.stdout:
        say(line.rstrip("\n"))
    code = p.wait()
    return title, code == 0, "" if code == 0 else f"exit {code}"


def save_log(root: Path = ROOT, now: float | None = None) -> Path:
    """The whole check, in work/tests/dev-check-<date>-<time>.log (the baseline before and after a change)."""
    import time
    out = root / "work" / "tests" / f"dev-check-{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}.log"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    return out


def documents(root: Path = ROOT) -> list[str]:
    """The documents' cross-checks; each problem in words."""
    out = []
    dec = (root / "docs" / "decisions.md").read_text(encoding="utf-8")
    nums = [int(n) for n in re.findall(r"^\| D(\d+) \|", dec, re.M)]
    seen, dup = set(), set()
    for n in nums:
        (dup if n in seen else seen).add(n)
    if dup:
        out.append(f"docs/decisions.md: D{', D'.join(map(str, sorted(dup)))} recorded more than once")
    top = max(nums) if nums else 0
    gaps = sorted(set(range(1, top + 1)) - seen)
    if gaps and len(gaps) < 20:
        out.append(f"docs/decisions.md: no D{', D'.join(map(str, gaps))} (numbers are given in order)")
    help_text = (root / "eaxcli" / "help.txt").read_bytes()
    if any(b > 127 for b in help_text):
        out.append("eaxcli/help.txt: not ASCII only (eax.ps1 reads it on Windows PowerShell 5)")
    for name in ("docs/handover.md", "AGENTS.md", "CLAUDE.md", "docs/functional-description.md"):
        if not (root / name).is_file():
            out.append(f"{name} is missing")
    return out


def has_tools() -> bool:
    """Whether this computer's Python can lint and test (ruff and pytest there)."""
    return all(importlib.util.find_spec(m) is not None for m in ("ruff", "pytest"))


def in_runner(args: list[str], root: Path = ROOT) -> list[str]:
    """docker compose arguments that run python <args> in the test runner, in services/api of this folder (mounted at
    /repo, so the code checked is the code here, not the image's copy)."""
    repo = Path(root).resolve().as_posix()
    return ["--profile", "test", "run", "--rm", "--no-deps", "-v", f"{repo}:/repo", "-w", "/repo/services/api",
            "--entrypoint", "python", "testrunner", *args]


UNIT_COVERAGE = "work/tests/unit-coverage.json"     # the unit tests' coverage, which lines ran (R8.1, D807)


def cover(where: str) -> list[str]:
    """pytest --cov over the code the live run measures (pyproject's [tool.coverage.run]), its lines kept in a JSON report
    (D807: eax test full joins it with the live run's)."""
    return ["--cov", "--cov-report", f"json:{where}"]


def unit_coverage(path: Path) -> str:
    """The unit tests' share of lines from their JSON report, for the summary ("" when there is none)."""
    try:
        t = json.loads(path.read_text(encoding="utf-8")).get("totals") or {}
        return f"{t['percent_covered']:.1f}% of {t['num_statements']} lines (unit tests; eax test full joins the live run's)"
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def commands(quick: bool, local: bool, py: str = sys.executable, compose_args=None) -> list[tuple[str, list[str], Path]]:
    """The lint and test steps: here when this Python has the tools, else in the test runner (D794); the tests measured
    (D807) when pytest-cov is there (always in the test runner)."""
    lint = ["-m", "ruff", "check", "eax", "tests", "../ops", "../../eaxcli", "../../testbench", "migrations"]
    # every test file collected even when one cannot be (owner's laptop, 07:09: one stale import stopped them all)
    tests = ["-m", "pytest", "-q", "-p", "no:randomly", "--continue-on-collection-errors", "-rfE"] + (["-x"] if quick else [])
    if local:
        measured = cover(str(ROOT / UNIT_COVERAGE)) if importlib.util.find_spec("pytest_cov") else []
        return [("lint", [py, *lint], API), ("tests", [py, *tests, *measured], API)]
    # compose_args gives the whole command, docker compose included (owner's laptop, 06:45: "docker docker" refused)
    return [("lint", compose_args(in_runner([*lint, "--no-cache"])), ROOT),
            ("tests", compose_args(in_runner([*tests, "-p", "no:cacheprovider", *cover(f"/repo/{UNIT_COVERAGE}")])), ROOT)]


def main(rest: list[str]) -> int:
    """eax dev check: lint, tests, the documents and (--web) the screens; 1 when any of them failed."""
    if not rest or rest[0] != "check":
        print(__doc__)
        return 2
    quick, web = "--quick" in rest, "--web" in rest
    local = has_tools()
    results = []
    if local:
        steps = commands(quick, True)
    else:
        say("This computer's Python has no ruff or pytest: lint and tests run in the test runner (Docker), with this "
              "folder mounted; nothing is installed here.")
        try:
            from .core import compose, compose_args
            compose(["--profile", "test", "build", "testrunner"])
            steps = commands(quick, False, compose_args=compose_args)
        except Exception as exc:  # noqa: BLE001 - no config file or no Docker: said, and the documents still checked
            steps = []
            results += [("lint", False, f"no ruff here and the test runner could not start: {exc}"),
                        ("tests", False, "no pytest here and the test runner could not start (eax up first?)")]
    (ROOT / UNIT_COVERAGE).unlink(missing_ok=True)        # never last time's figure shown as this one's
    for title, cmd, cwd in steps:
        results.append(_run(title, cmd, cwd))
    measured = unit_coverage(ROOT / UNIT_COVERAGE)
    if measured and any(t == "tests" for t, _c, _w in steps):
        results.append(("coverage", True, measured))
    say("\n== documents")
    probs = documents()
    for p in probs:
        say(f"  {p}")
    results.append(("documents", not probs, f"{len(probs)} problem(s)" if probs else ""))
    if web:
        npm = shutil.which("npm")
        results.append(_run("web", [npm or "npm", "run", "build"], ROOT / "services" / "web"))
    say("\nSummary:")
    for title, ok, why in results:
        say(f"  {'ok    ' if ok else 'FAILED'} {title}" + (f": {why}" if why else ""))
    say(f"Saved: {save_log().relative_to(ROOT)}")
    say("Next: docs/handover.md says what is in progress and what comes next.")
    return 0 if all(ok for _t, ok, _w in results) else 1
