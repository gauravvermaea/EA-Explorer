"""eax settings: the settings and admin configuration exported and imported, from the machine (Release 6.7, D755; the
owner, 17 Nov 2026, 22:06: "we need another release for import and export of settings and admin configs").

The same file as System Admin > Settings import and export (services/api/eax/settings_transfer.py, run in the api
container): every admin setting, in the parts chosen; never content, people, a password, key or certificate.

  eax settings parts                                    the parts a settings file carries
  eax settings export [--parts a,b] <file>              the settings file written
  eax settings import <file> [--parts a,b]              every difference shown; nothing changed
  eax settings import <file> [--parts a,b] --yes        a safety copy kept, then every difference in those parts taken
  eax settings copies                                   the safety copies kept before each import
  eax settings undo <copy>                              the settings that copy kept put back
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .core import EAX, ROOT, Failure, compose_args, say

PARTS = ("application", "system", "security", "branding", "alerts", "retention", "audiences", "webhooks", "pairings",
         "banner", "allow_lists", "schedules")


def _api(args: list[str], stdin: str = "", run=subprocess.run) -> dict:
    """python -m eax.settings_transfer in the api container: its one JSON line, or Failure in words."""
    p = run(compose_args(["exec", "-T", "api", "python", "-m", "eax.settings_transfer", *args]), cwd=ROOT, input=stdin,
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    lines = [ln for ln in (p.stdout or "").splitlines() if ln.strip().startswith("{")]
    if not lines:
        raise Failure(f"The API did not answer: {(p.stderr or p.stdout or f'exit {p.returncode}').strip()[-300:]} "
                      f"(is EA Explorer running? {EAX} status)")
    out = json.loads(lines[-1])
    if out.get("error"):
        raise Failure(out["error"])
    return out


def _parts(argv: list[str]) -> list[str]:
    if "--parts" not in argv:
        return []
    i = argv.index("--parts")
    if i + 1 >= len(argv):
        raise Failure(f"--parts needs the parts, for example --parts system,branding ({', '.join(PARTS)}).")
    bad = [p for p in argv[i + 1].split(",") if p and p not in PARTS]
    if bad:
        raise Failure(f"No part called {', '.join(bad)}: {', '.join(PARTS)}.")
    return ["--parts", argv[i + 1]]


def _file(argv: list[str]) -> str:
    skip = {i + 1 for i, a in enumerate(argv) if a == "--parts"}
    free = [a for i, a in enumerate(argv) if i not in skip and not a.startswith("--")]
    if not free:
        raise Failure("Give the settings file, for example work/exports/settings.json.")
    return free[0]


def show(preview: dict) -> int:
    """The preview in words; how many differences."""
    f = preview.get("file") or {}
    say(f"The file: made {f.get('made_at', '?')} by {f.get('made_by', '?')} on {f.get('site') or 'a site'}, "
        f"release {f.get('release', '?')}.")
    n = 0
    for part, d in (preview.get("differences") or {}).items():
        rows = d.get("differences") or []
        say(f"{d.get('title', part)}: {len(rows)} difference(s), {d.get('same', 0)} the same"
            + (f", {len(d['only_here'])} only here (kept)" if d.get("only_here") else ""))
        for r in rows:
            n += 1
            tag = "  CANNOT: " + r["cannot"] if r.get("cannot") else ("  MAINTENANCE PAGE: " + r["maintenance"] if r.get("maintenance") else "")
            say(f"  {r['change']:<8} {r['key']}{tag}")
            say(f"           here: {json.dumps(r.get('here'))[:150]}")
            say(f"           file: {json.dumps(r.get('file'))[:150]}")
    for part, why in (preview.get("not_read") or {}).items():
        say(f"{part}: not read here ({why})", "yellow")
    return n


def main(argv: list[str], run=subprocess.run) -> int:
    """eax settings parts | export [--parts a,b] <file> | import <file> [--parts a,b] [--yes] | copies | undo <copy>."""
    action, rest = (argv[0] if argv else "parts"), argv[1:]
    if action == "parts":
        say("The parts of a settings file (--parts a,b chooses some; all when none):")
        for p in PARTS:
            say(f"  {p}")
        say("Never content (models, projects), people, a password, key or certificate.")
        return 0
    if action == "export":
        target = Path(_file(rest))
        body = _api(["export", *_parts(rest), "--by", "eax settings"], run=run)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")
        say(f"Written: {target} ({', '.join(body.get('parts') or {}) or 'no parts'}).", "green")
        for part, why in (body.get("not_read") or {}).items():
            say(f"  {part} left out: {why}", "yellow")
        return 0
    if action == "import":
        source = Path(_file(rest))
        if not source.is_file():
            raise Failure(f"There is no file {source}.")
        text = source.read_text(encoding="utf-8-sig")
        if "--yes" not in rest:
            n = show(_api(["preview", *_parts(rest)], text, run=run))
            say(f"Nothing was changed. {n} difference(s). To take every one in these parts: {EAX} settings import "
                f"{source}{' ' + ' '.join(_parts(rest)) if _parts(rest) else ''} --yes (a safety copy is kept first; "
                f"the screen, System Admin > Settings import and export, lets you tick them one by one).")
            return 0
        out = _api(["import", *_parts(rest), "--yes", "--by", "eax settings"], text, run=run)
        taken = out.get("taken") or {}
        say(f"Taken: {sum(len(v) for v in taken.values())} difference(s) in {', '.join(taken) or 'no part'}.", "green")
        for line in (out.get("refused") or []) + (out.get("said") or []):
            say(f"  {line}")
        if out.get("copy"):
            say(f"Safety copy {out['copy']}: {EAX} settings undo {out['copy']} puts it back.")
        return 0
    if action == "copies":
        kept = _api(["copies"], run=run).get("copies") or []
        say("The safety copies kept before each import (newest first):" if kept else "No safety copies yet.")
        for c in kept:
            say(f"  {c['id']}  {str(c.get('made_at'))[:16]}  {c.get('made_by')}  {c.get('why')}  "
                f"{','.join(c.get('parts') or [])}{'  (undone)' if c.get('undone') else ''}")
        return 0
    if action == "undo":
        if not rest:
            raise Failure(f"Give the safety copy's id ({EAX} settings copies lists them).")
        out = _api(["undo", rest[0], "--by", "eax settings"], run=run)
        say(f"Put back: {', '.join(out.get('taken') or {}) or 'nothing was different'}.", "green")
        if out.get("copy"):
            say(f"The settings before this undo are kept too: {EAX} settings undo {out['copy']}.")
        return 0
    raise Failure(f"{EAX} settings parts | export [--parts a,b] <file> | import <file> [--parts a,b] [--yes] | copies | "
                  "undo <copy>")
