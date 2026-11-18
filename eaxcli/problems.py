"""`eax status`'s problems (Release 7.9, D787): every problem now with its error code (EAX-AREA-NNN) and what to do.

The containers are read here (so a stopped API still shows); the services' health and the open alerts are read inside
the api container (python -m eax.errors). The codes come from the one list, services/api/eax/errors.json."""

from __future__ import annotations

import json

from .core import ROOT, compose_out, docker_ok, heading, ok, say

LIST = ROOT / "services" / "api" / "eax" / "errors.json"
ONE_SHOT = {"setup", "reports-init"}          # containers that run once and stop when done


def _errors() -> list[dict]:
    try:
        return json.loads(LIST.read_text(encoding="utf-8"))["errors"]
    except (OSError, ValueError, KeyError):
        return []


def to_do(code: str) -> str:
    """What to do about a code, from the list."""
    return next((e.get("to_do", "") for e in _errors() if e["code"] == code), "")


def container_code(service: str, state: str) -> str:
    """A container's code: its part's own when the list has one, else a stopped or an unhealthy container."""
    if "unhealthy" in state:
        return "EAX-STACK-002"
    return next((e["code"] for e in _errors() if e.get("stack") == service), "EAX-STACK-001")


def containers(lines: list[str]) -> list[dict]:
    """The containers from `docker compose ps -a --format json` (one JSON object per line, or one JSON list)."""
    rows: list[dict] = []
    for line in lines:
        try:
            got = json.loads(line)
        except ValueError:
            continue
        rows += got if isinstance(got, list) else [got]
    return rows


def container_problems(rows: list[dict], switched_off: set[str] = frozenset()) -> list[dict]:
    """The containers not running well: stopped (a one-shot container that ended well is fine) or unhealthy."""
    out = []
    for r in rows:
        service = r.get("Service") or r.get("Name") or "?"
        state, status = (r.get("State") or "").lower(), (r.get("Status") or "")
        if service in switched_off:
            continue
        if service in ONE_SHOT and state == "exited" and r.get("ExitCode") in (0, None):
            continue
        if state == "running" and "unhealthy" not in status:
            continue
        code = container_code(service, f"{state} {status}")
        out.append({"code": code, "level": "warning" if code == "EAX-STACK-002" else "critical", "what": f"container {service}", "detail": status or state,
                    "to_do": to_do(code).replace("<container>", service)})
    return out


def merge(*lists: list[dict]) -> list[dict]:
    """Every problem once by its code and what it is about, the critical ones first."""
    seen, out = set(), []
    for p in [p for ps in lists for p in ps]:
        key = (p["code"], p["what"])
        if key not in seen:
            seen.add(key)
            out.append(p)
    return sorted(out, key=lambda p: (p["level"] != "critical", p["code"]))


def show(switched_off: set[str] = frozenset()) -> int:
    """Says every problem with its code and what to do. Returns how many there are."""
    say("")
    heading("Problems (error codes: Documentation > Printed guides > Troubleshooting, or the error guide on the site)")
    if not docker_ok():
        say("  EAX-STACK-003  critical  Docker does not answer", "red")
        say(f"      To do: {to_do('EAX-STACK-003')}")
        return 1
    rows = containers(compose_out(["ps", "-a", "--format", "json"]))
    found = container_problems(rows, switched_off)
    api_up = any((r.get("Service") == "api") and (r.get("State") or "").lower() == "running" for r in rows)
    inside: list[dict] = []
    if api_up:
        lines = compose_out(["exec", "-T", "api", "python", "-m", "eax.errors"])
        try:
            inside = json.loads(lines[-1])["problems"] if lines else []
        except (ValueError, KeyError, TypeError):
            say("  (the API did not say its health: run eax logs api)", "yellow")
    problems = merge(found, inside)
    if not problems:
        ok("  No problems found.")
        return 0
    for p in problems:
        say(f"  {p['code']:<14} {p['level']:<9} {p['what']}: {p['detail']}"[:240], "red" if p["level"] == "critical" else "yellow")
        say(f"      To do: {p['to_do']}")
    return len(problems)


def find(words: str) -> list[dict]:
    """The codes a person asks for: one code exactly, every code of an area (AUTH, or EAX-AUTH), or every code whose
    words hold all the words given."""
    items = _errors()
    w = words.strip()
    if not w:
        return items
    up = w.upper()
    exact = [e for e in items if e["code"] == up]
    if exact:
        return exact
    area = up.removeprefix("EAX-").rstrip("-")
    by_area = [e for e in items if e["area"] == area]
    if by_area:
        return by_area
    terms = w.lower().split()
    return [e for e in items if all(t in " ".join(str(e.get(k, "")) for k in ("code", "title", "meaning", "cause", "to_do")).lower()
                                    for t in terms)]


def errors_main(rest: list[str]) -> int:
    """eax errors [code|area|words]: what an error code means and what to do (R7.9, D787). No words: every code."""
    found = find(" ".join(rest))
    if not found:
        say(f"No error code matches '{' '.join(rest)}'. Run eax errors for the whole list.", "yellow")
        return 1
    if len(found) == 1 or (rest and len(found) <= 3):
        for e in found:
            heading(f"{e['code']}: {e['title']}")
            say(f"  What it means: {e['meaning']}")
            say(f"  Usual cause:   {e['cause']}")
            say(f"  What to do:    {e['to_do']}")
            say("")
        return 0
    for e in found:
        say(f"  {e['code']:<14} {e['title']}")
    say("")
    say("Run eax errors <code> for what one means and what to do; the error guide on the website lists them all.")
    return 0
