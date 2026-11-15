"""The security gate and trend (R5.17; owner, 14 Nov 2026: "In next release add Story for automated security test").

Every scanner's report in a run's folder is read into one list of findings, each with where it came from, its id, how
severe it is and whether a fix exists:

  zap.json         the OWASP ZAP baseline scan of the front door (not signed in)
  zap-api.json     the signed-in ZAP scan of the API (a test user's token, the run's own test data, reads only)
  trivy-*.json     Trivy on each of EA Explorer's images
  bandit.json      static analysis of the Python code (codescan.py)
  secrets.json     secrets committed by mistake (codescan.py)
  licences.json    the licences of the Python dependencies (codescan.py)

**The gate**: a high or critical finding fails the run (and so the CI job), unless it is accepted. Trivy's findings
with no fix released yet are listed, not failed: nothing can be done about them until the package's makers fix them
(R2.24 called these "watch"). **Accepted** findings are listed with their reason and an expiry date, in
`eax/testing/security_accepted.json` (kept with the code, reviewed like it) and, for one installation,
`persist/security-accepted.json`; past its date an accepted finding fails again. **The trend**: the findings per run
and kind (security-findings.json in each run's folder) for the Self-test page, and what is new since the run before.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCEPTED_FILES = (HERE / "security_accepted.json", Path("/persist/security-accepted.json"))
FINDINGS = "security-findings.json"
GATE = "security gate: no new high or critical finding"
SEVERE = ("critical", "high")
ZAP_RISK = {3: "high", 2: "medium", 1: "low", 0: "info"}


def finding(source: str, fid: str, severity: str, title: str, where: str = "", fix: bool = True) -> dict:
    """One finding in the gate's form."""
    return {"source": source, "id": str(fid), "severity": severity.lower(), "title": title[:300], "where": where, "fix": bool(fix)}


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return None


def from_zap(data: dict | None, source: str = "zap") -> list[dict]:
    """A ZAP report's alerts as findings."""
    out = []
    for s in (data or {}).get("site", []) or []:
        for a in s.get("alerts", []) or []:
            risk = int(str(a.get("riskcode", "0")) or 0)
            out.append(finding(source, f"zap:{a.get('pluginid', '?')}", ZAP_RISK.get(risk, "info"), a.get("alert", ""),
                               s.get("@name", "")))
    return out


def from_trivy(data: dict | None, image: str) -> list[dict]:
    """A Trivy report's vulnerabilities as findings (whether a fix exists kept)."""
    out = []
    for r in (data or {}).get("Results") or []:
        for v in r.get("Vulnerabilities") or []:
            out.append(finding("trivy", v.get("VulnerabilityID", "?"), v.get("Severity", "unknown"),
                               f"{v.get('PkgName')} {v.get('InstalledVersion')}" + (f" (fixed in {v['FixedVersion']})" if v.get("FixedVersion") else ""),
                               f"image {image}", fix=bool(v.get("FixedVersion"))))
    return out


def from_bandit(data: dict | None) -> list[dict]:
    """bandit's results of medium or high confidence as findings."""
    return [finding("code", f"bandit:{r.get('test_id')}", r.get("issue_severity", "low"), r.get("issue_text", ""),
                    f"{r.get('filename')}:{r.get('line_number')}") for r in (data or {}).get("results") or []
            if str(r.get("issue_confidence", "")).upper() in ("HIGH", "MEDIUM")]


def from_list(data, source: str) -> list[dict]:
    """secrets.json and licences.json: already in this module's form (codescan.py writes them)."""
    return [finding(source, f.get("id", "?"), f.get("severity", "high"), f.get("title", ""), f.get("where", ""), f.get("fix", True))
            for f in (data or []) if isinstance(f, dict)]


def collect(folder: Path) -> list[dict]:
    """Every finding of every scanner's report in a run's folder."""
    out = from_zap(_json(folder / "zap.json")) + from_zap(_json(folder / "zap-api.json"), "zap-api")
    for f in sorted(folder.glob("trivy-*.json")):
        out += from_trivy(_json(f), f.stem.removeprefix("trivy-"))
    out += from_bandit(_json(folder / "bandit.json"))
    out += from_list(_json(folder / "secrets.json"), "secrets") + from_list(_json(folder / "licences.json"), "licences")
    return out


def accepted(files=ACCEPTED_FILES) -> list[dict]:
    """The accepted findings: [{id, where (optional: a part of it), reason, until (YYYY-MM-DD), by}]."""
    out = []
    for f in files:
        got = _json(Path(f))
        for a in (got or {}).get("accepted", []) if isinstance(got, dict) else []:
            if a.get("id") and a.get("reason") and a.get("until"):
                out.append({"id": str(a["id"]), "where": str(a.get("where") or ""), "reason": str(a["reason"]),
                            "until": str(a["until"]), "by": str(a.get("by") or ""), "file": str(f)})
    return out


def _match(f: dict, a: dict) -> bool:
    """A finding is accepted by its own id, or (for Trivy) by "package:<name>": every finding in that package, kept to
    one image by `where` (a package the image's maker pins and a fix cannot be installed into, R5.23)."""
    if a["id"].startswith("package:"):
        pkg = a["id"].split(":", 1)[1].strip().lower()
        if f["source"] != "trivy" or not pkg or not a["where"]:
            return False
        name = (f.get("title") or "").split(" ", 1)[0].lower()
        return name == pkg and a["where"].lower() in f["where"].lower()
    return f["id"] == a["id"] and (not a["where"] or a["where"].lower() in f["where"].lower())


def gate(found: list[dict], accept: list[dict], today: date | None = None) -> dict:
    """Which findings fail the run: high or critical, a fix there (or not a package's), not accepted or accepted past its
    date. Returns {failing, accepted, expired, no_fix, counts}."""
    today = today or date.today()
    out = {"failing": [], "accepted": [], "expired": [], "no_fix": [], "counts": {}}
    for f in found:
        key = f"{f['source']} {f['severity']}"
        out["counts"][key] = out["counts"].get(key, 0) + 1
        if f["severity"] not in SEVERE:
            continue
        if f["source"] == "trivy" and not f["fix"]:
            out["no_fix"].append(f)
            continue
        a = next((a for a in accept if _match(f, a)), None)
        if a and a["until"] >= today.isoformat():
            out["accepted"].append({**f, "reason": a["reason"], "until": a["until"]})
        elif a:
            out["expired"].append({**f, "reason": a["reason"], "until": a["until"]})
            out["failing"].append(f)
        else:
            out["failing"].append(f)
    return out


def key_of(f: dict) -> str:
    """A finding's identity, to compare runs."""
    return f"{f['source']}|{f['id']}|{f['where']}"


def new_since(now: list[dict], before: list[dict] | None) -> list[dict]:
    """The severe findings not in the run before (all of them when there was none)."""
    old = {key_of(f) for f in before or []}
    return [f for f in now if f["severity"] in SEVERE and key_of(f) not in old]


def previous(folder: Path) -> list[dict] | None:
    """The findings of the newest earlier run that has them (folders are named by their start time)."""
    for other in sorted((p for p in folder.parent.iterdir() if p.is_dir() and p.name < folder.name), reverse=True):
        got = _json(other / FINDINGS)
        if isinstance(got, dict) and "findings" in got:
            return got["findings"]
    return None


def judge(folder: Path, record, today: date | None = None) -> dict:
    """The gate for a run: its findings kept (security-findings.json), one result that fails on what the gate fails."""
    found = collect(folder)
    g = gate(found, accepted(), today)
    fresh = new_since(found, previous(folder))
    folder.joinpath(FINDINGS).write_text(json.dumps({"findings": found, "gate": {k: v for k, v in g.items() if k != "counts"},
                                                     "counts": g["counts"], "new": fresh}, default=str), encoding="utf-8")
    show = lambda fs: "; ".join(f"{f['source']} {f['id']} {f['where']}".strip() for f in fs[:30])  # noqa: E731
    extra = (f" Accepted: {len(g['accepted'])}." if g["accepted"] else "") + \
        (f" No fix released yet (listed): {len(g['no_fix'])}." if g["no_fix"] else "") + \
        (f" New since the run before: {len(fresh)}." if fresh else "")
    if not found and not any(folder.glob("trivy-*.json")) and not (folder / "zap.json").exists():
        record(GATE, "skipped", "no scanner's report in this run (the scans run with a detailed run of the security suite)", 0)
    elif g["failing"]:
        exp = f" Accepted until a date now past: {show(g['expired'])}." if g["expired"] else ""
        record(GATE, "failed", f"{len(g['failing'])} high or critical: {show(g['failing'])}.{exp}{extra}", 0)
    else:
        record(GATE, "passed", f"{len(found)} findings, none that fails.{extra}", 0)
    return {**g, "new": fresh}


KINDS = (("OWASP ZAP signed-in", "zap-api"), ("OWASP ZAP", "zap"), ("(Trivy)", "trivy"), ("pip-audit", "python packages"),
         ("code:", "code"), ("secrets", "secrets"), ("licences", "licences"), ("attack:", "attacks"), ("security gate", "gate"))


def kind_of(name: str) -> str:
    """The kind of a security result, by its name, for the trend."""
    for marker, kind in KINDS:
        if marker in name:
            return kind
    return "headers and cookies"


def trend(rows: list[dict]) -> list[dict]:
    """[{run, at, name, outcome}] of the security suite's results, as per run and kind: failed and warnings."""
    by: dict[int, dict] = {}
    for r in rows:
        run = by.setdefault(r["run"], {"run": r["run"], "at": r.get("at"), "kinds": {}})
        k = run["kinds"].setdefault(kind_of(r["name"]), {"failed": 0, "warning": 0, "passed": 0})
        if r["outcome"] in k:
            k[r["outcome"]] += 1
    return sorted(by.values(), key=lambda x: x["run"])


def clean_accepted(data: dict) -> dict:
    """An accepted-findings file checked: every entry has an id, a reason and a date in YYYY-MM-DD form."""
    out = []
    for a in data.get("accepted") or []:
        if not (a.get("id") and str(a.get("reason") or "").strip()):
            raise ValueError("Every accepted finding has an id and a reason.")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(a.get("until") or "")):
            raise ValueError(f"{a.get('id')}: until is a date (YYYY-MM-DD) after which it fails again.")
        out.append({k: a[k] for k in ("id", "where", "reason", "until", "by") if a.get(k)})
    return {"accepted": out}


# ---------------------------------------------------------------- the signed-in ZAP scan (R5.17 (2))
ZAP_SPEC, ZAP_AUTH = "zap-openapi.json", "zap-auth.txt"
ZAP_LEAVE_OUT = re.compile(r"^/api/v1/(admin|operations|mcp|tests|updates|deploy|backups|restores)\b|/(download|export|zip|xlsx|csv|pdf)\b")


def zap_targets(spec: dict, ids: dict[str, str], fill) -> dict:
    """The API's own description cut down to what the signed-in scan may attack safely: reads (GET) only, every path in
    the run's own test data (its ids filled in), never the admin, operations or download paths. ZAP's active rules
    then try injections in the query strings of reads: nothing can be changed."""
    paths = {}
    for path, ops in (spec.get("paths") or {}).items():
        get = ops.get("get") if isinstance(ops, dict) else None
        if not isinstance(get, dict) or ZAP_LEAVE_OUT.search(path):
            continue
        real = fill(path, ids) if "{" in path else path
        if not real:
            continue
        op = {k: v for k, v in get.items() if k in ("summary", "responses", "tags")}
        op["parameters"] = [p for p in get.get("parameters") or [] if isinstance(p, dict) and p.get("in") == "query"]
        op.setdefault("responses", {"200": {"description": "ok"}})
        paths[real] = {"get": op}
    return {"openapi": spec.get("openapi", "3.0.3"), "info": {"title": "EA Explorer (self-test scope)", "version": "1"},
            "servers": [{"url": "https://proxy"}], "paths": paths}


def prepare_zap(folder: Path, spec: dict, ids: dict[str, str], token: str, fill) -> int:
    """The scope and the test user's token for the operations helper's signed-in scan; the token file is deleted by
    the helper as soon as the scan ends (and never outlives the run's test users)."""
    t = zap_targets(spec, ids, fill)
    (folder / ZAP_SPEC).write_text(json.dumps(t), encoding="utf-8")
    auth = folder / ZAP_AUTH
    auth.write_text(token, encoding="utf-8")
    auth.chmod(0o600)
    return len(t["paths"])
