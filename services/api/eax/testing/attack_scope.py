"""What the attack test may fuzz, and as whom (R8.2, D817): the API's own description cut down to calls that can only
touch the run's own test data, and the run's Architect's token for the operations helper's Schemathesis container.

  reads    every GET, its ids filled with the run's own (the same paths as the signed-in ZAP scan)
  writes   POST, PUT and PATCH only on a path that names one of the run's own models, projects or entities (an id the
           run filled in): never on a bare collection (that would make things outside the test data), never DELETE
  never    the admin, operations, MCP, tests, updates, deploy, backup, restore and download paths (security_gate's
           ZAP_LEAVE_OUT), whatever the method

Signed in as the run's Architect, who has roles only on the run's own models and project: a call the scope lets
through is still refused by EA Explorer itself for anything else, and that refusal is part of what is tested."""

from __future__ import annotations

import json
from pathlib import Path

from .security_gate import ZAP_LEAVE_OUT

SPEC, AUTH = "attack-openapi.json", "attack-auth.txt"       # read by services/ops/attackscans.py
WRITES = ("post", "put", "patch")
KEEP = ("summary", "responses", "tags", "requestBody", "operationId")


def _op(op: dict, keep_body: bool) -> dict:
    out = {k: v for k, v in op.items() if k in KEEP and (keep_body or k != "requestBody")}
    out["parameters"] = [p for p in op.get("parameters") or [] if isinstance(p, dict) and p.get("in") in ("query", "header")
                         and str(p.get("name", "")).lower() != "authorization"]
    out.setdefault("responses", {"200": {"description": "ok"}})
    return out


def targets(spec: dict, ids: dict[str, str], fill) -> dict:
    """The description the fuzzer gets: see the module's note. `fill(path, ids)` gives the path with the run's ids, or
    "" when it cannot fill every one of them."""
    paths: dict[str, dict] = {}
    for path, ops in (spec.get("paths") or {}).items():
        if not isinstance(ops, dict) or ZAP_LEAVE_OUT.search(path):
            continue
        has_ids = "{" in path
        real = fill(path, ids) if has_ids else path
        if not real:
            continue
        kept = {}
        if isinstance(ops.get("get"), dict):
            kept["get"] = _op(ops["get"], keep_body=False)
        if has_ids:                                    # writes only where the path is the run's own thing
            for m in WRITES:
                if isinstance(ops.get(m), dict):
                    kept[m] = _op(ops[m], keep_body=True)
        if kept:
            paths[real] = kept
    out = {"openapi": spec.get("openapi", "3.0.3"), "info": {"title": "EA Explorer (attack test scope)", "version": "1"},
           "servers": [{"url": "https://proxy"}], "paths": paths}
    if isinstance(spec.get("components"), dict):        # the bodies' schemas the writes refer to
        out["components"] = {k: v for k, v in spec["components"].items() if k == "schemas"}
    return out


def counts(t: dict) -> dict[str, int]:
    """How many calls of each method the scope holds."""
    out: dict[str, int] = {}
    for ops in (t.get("paths") or {}).values():
        for m in ops:
            out[m] = out.get(m, 0) + 1
    return out


def prepare(folder: Path, spec: dict, ids: dict[str, str], token: str, fill) -> dict[str, int]:
    """The scope and the token for the helper; the helper deletes the token file the moment it has read it."""
    t = targets(spec, ids, fill)
    (folder / SPEC).write_text(json.dumps(t), encoding="utf-8")
    auth = folder / AUTH
    auth.write_text(token, encoding="utf-8")
    auth.chmod(0o600)
    return counts(t)


def forget_token(folder: Path) -> None:
    """The token file never outlives the run (the helper normally deletes it first)."""
    try:
        (folder / AUTH).unlink()
    except OSError:
        pass


# ---------------------------------------------------------------- the results (collect)
TOOLS = "attack-tools.json"
REPORTS = (   # (name in the results, the tool's key in attack-tools.json, its report, the findings' source)
    ("attack test: OWASP ZAP full scan of the front door (as no one)", "zap", "zap-full.json", "zap-full"),
    ("attack test: Schemathesis fuzzing of the API, signed in, in the run's test data", "schemathesis", "schemathesis", "schemathesis"),
    ("attack test: Nuclei's templates against every container's ports", "nuclei", "nuclei.jsonl", "nuclei"),
    ("attack test: Semgrep on the source", "semgrep", "semgrep.json", "semgrep"),
    ("attack test: Gitleaks on the git history", "gitleaks", "gitleaks.json", "gitleaks"),
)


def judge(folder: Path, record, found: list[dict]) -> None:
    """One result for the tools' versions and one a tool: how many findings of each severity, or why it did not run.
    Whether a finding fails the run is the security gate's (security_gate.judge), as for every other scanner."""
    try:
        tools = json.loads((folder / TOOLS).read_text(encoding="utf-8")).get("tools") or {}
    except (OSError, ValueError):
        tools = {}
    if not tools:
        record("attack test: the scanners brought up to date", "warning", "no list of the scanners from the helper: an "
               "older operations helper, or the scans did not start", 0)
    else:
        offline = [k for k, v in tools.items() if v.get("present") and not v.get("pulled")]
        missing = [k for k, v in tools.items() if not v.get("present")]
        said = "; ".join(f"{k} {str(v.get('digest') or '').rsplit(':', 1)[-1][:12] or '?'} ({v.get('note', '')})"
                         for k, v in sorted(tools.items()))
        record("attack test: the scanners brought up to date", "warning" if offline or missing else "passed", said[:1500], 0)
    for name, key, report, source in REPORTS:
        mine = [f for f in found if f["source"] == source]
        there = (folder / report).exists()
        if not there and not mine:
            why = "not there and could not be pulled" if tools.get(key, {}).get("present") is False else "it left no report"
            record(name, "warning", f"did not run: {why} (see runner-output.log and the helper's lines)", 0)
            continue
        by = {s: sum(1 for f in mine if f["severity"] == s) for s in ("critical", "high", "medium", "low", "info")}
        record(name, "passed", ", ".join(f"{n} {s}" for s, n in by.items() if n) or "nothing found", 0)
