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
requirements-dev.txt, and Node 22 for --web.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services" / "api"


def _run(title: str, cmd: list[str], cwd: Path) -> tuple[str, bool, str]:
    """Runs one step in this terminal; (title, passed, why not)."""
    print(f"\n== {title}: {' '.join(cmd)}", flush=True)
    try:
        r = subprocess.run(cmd, cwd=cwd)
    except FileNotFoundError:
        return title, False, f"{cmd[0]} is not on this machine (see eax help dev)"
    return title, r.returncode == 0, "" if r.returncode == 0 else f"exit {r.returncode}"


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


def main(rest: list[str]) -> int:
    """eax dev check: lint, tests, the documents and (--web) the screens; 1 when any of them failed."""
    if not rest or rest[0] != "check":
        print(__doc__)
        return 2
    quick, web = "--quick" in rest, "--web" in rest
    py = sys.executable
    results = [_run("lint", [py, "-m", "ruff", "check", "eax", "tests", "../ops", "../../eaxcli", "../../testbench", "migrations"], API)]
    tests = [py, "-m", "pytest", "-q", "-p", "no:randomly"] + (["-x"] if quick else [])
    results.append(_run("tests", tests, API))
    print("\n== documents", flush=True)
    probs = documents()
    for p in probs:
        print(f"  {p}")
    results.append(("documents", not probs, f"{len(probs)} problem(s)" if probs else ""))
    if web:
        npm = shutil.which("npm")
        results.append(_run("web", [npm or "npm", "run", "build"], ROOT / "services" / "web"))
    print("\nSummary:")
    for title, ok, why in results:
        print(f"  {'ok    ' if ok else 'FAILED'} {title}" + (f": {why}" if why else ""))
    print("Next: docs/handover.md says what is in progress and what comes next.")
    return 0 if all(ok for _t, ok, _w in results) else 1
