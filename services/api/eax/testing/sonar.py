"""SonarQube in the self-test (Release 8, R8; D740, D792): the steps that talk to SonarQube, run in the test runner on
the stack's internal network (`eax test sonar` on the machine starts SonarQube and the scanner, eaxcli/sonar.py).

  python -m eax.testing.sonar prepare            wait for SonarQube, set its admin password once (kept in
                                                 /results/sonar/admin, never shown), make an analysis token for this
                                                 scan (/results/sonar/token, deleted by report)
  python -m eax.testing.sonar report <folder>    wait for the analysis, read every open issue and security hotspot,
                                                 write the report into /results/<folder> (report.md, issues.json,
                                                 hotspots.json, summary.json), revoke the token; exit 1 when an issue
                                                 is not on the accepted list (eax/testing/sonar_accepted.json)

The rules are SonarQube's own default, "Sonar way" (owner, 19 Nov 2026, 00:07: "Newest + Sonar way"). Nothing leaves
the machine: SonarQube runs here, on the internal network, and its telemetry is off."""

from __future__ import annotations

import base64
import fnmatch
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

URL = os.environ.get("EAX_SONAR_URL", "http://sonarqube:9000")
PROJECT = "ea-explorer"
RESULTS = Path(os.environ.get("EAX_TEST_RESULTS", "/results"))
KEEP = RESULTS / "sonar"                      # the admin password and the scan's token: work/tests/sonar, never in git
ACCEPTED = Path(__file__).with_name("sonar_accepted.json")
SEVERITY_ORDER = ["BLOCKER", "CRITICAL", "HIGH", "MAJOR", "MEDIUM", "MINOR", "LOW", "INFO"]
TYPE_ORDER = ["BUG", "VULNERABILITY", "SECURITY_HOTSPOT", "CODE_SMELL"]


class SonarError(RuntimeError):
    """SonarQube did not answer as expected (the message says what to do)."""


class PasswordLost(SonarError):
    """SonarQube's admin password is not the first-start one and its copy is gone (a cleanup deleted work/, the volume
    stayed): eax test sonar then starts SonarQube afresh by itself."""


# ---------------------------------------------------------------- talking to SonarQube
def call(method: str, path: str, params: dict | None = None, auth: tuple[str, str] | None = None,
         token: str = "", timeout: int = 30) -> dict:
    """One call to SonarQube's web API; its JSON (an empty dict when it answers nothing)."""
    data = urllib.parse.urlencode(params or {}).encode() if method == "POST" else None
    url = URL + path + ("?" + urllib.parse.urlencode(params or {}) if method == "GET" and params else "")
    req = urllib.request.Request(url, data=data, method=method)
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode())
    elif token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310 - the stack's own SonarQube
        body = r.read()
    return json.loads(body) if body.strip() else {}


def refused(exc: urllib.error.HTTPError) -> str:
    """What SonarQube said when it refused a call: the call (without its token) and SonarQube's own messages, not a bare
    "HTTP Error 400" (D803)."""
    try:
        body = exc.read().decode("utf-8", "replace")
    except (OSError, AttributeError):
        body = ""
    try:
        msgs = "; ".join(e.get("msg", "") for e in json.loads(body).get("errors", [])) or body.strip()
    except ValueError:
        msgs = body.strip()
    where = urllib.parse.urlsplit(exc.geturl() or "").path or "?"
    return f"SonarQube refused {where} with {exc.code}: {msgs[:500] or exc.reason or 'no reason given'}"


def wait_up(minutes: float = 10, sleep=time.sleep, ask=call) -> str:
    """Waits until SonarQube says UP (its first start takes a few minutes); its version."""
    end = time.monotonic() + minutes * 60
    last = "not answering"
    while time.monotonic() < end:
        try:
            st = ask("GET", "/api/system/status")
            if st.get("status") == "UP":
                return str(st.get("version", ""))
            last = str(st.get("status"))
        except (OSError, urllib.error.URLError, ValueError) as exc:
            last = exc.__class__.__name__
        sleep(5)
    raise SonarError(f"SonarQube did not start in {minutes:.0f} minutes (last: {last}): eax logs sonarqube")


def admin_password(ask=call, keep: Path = KEEP) -> str:
    """The admin's password: set once from SonarQube's first-start default to a random one kept in work/tests/sonar."""
    keep.mkdir(parents=True, exist_ok=True)
    f = keep / "admin"
    if f.is_file():
        return f.read_text(encoding="utf-8").strip()
    new = secrets.token_urlsafe(24) + "aA1!"                         # SonarQube asks for upper, lower, digit, symbol
    try:
        ask("POST", "/api/users/change_password", {"login": "admin", "previousPassword": "admin", "password": new},
            auth=("admin", "admin"))
    except urllib.error.HTTPError as exc:
        raise PasswordLost("SonarQube's admin password is not the first-start one and work/tests/sonar/admin is missing: "
                         "eax test sonar --reset starts SonarQube afresh (its data only)") from exc
    f.write_text(new, encoding="utf-8")
    os.chmod(f, 0o600)
    return new


def prepare(ask=call, keep: Path = KEEP) -> str:
    """SonarQube up, the admin password set, a token for this scan written to work/tests/sonar/token."""
    version = wait_up(ask=ask)
    pw = admin_password(ask=ask, keep=keep)
    name = "eax-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    got = ask("POST", "/api/user_tokens/generate", {"name": name}, auth=("admin", pw))
    (keep / "token").write_text(got["token"], encoding="utf-8")
    os.chmod(keep / "token", 0o600)
    (keep / "token-name").write_text(name, encoding="utf-8")
    (keep / "version").write_text(version, encoding="utf-8")
    return version


def wait_analysis(token: str, minutes: float = 30, sleep=time.sleep, ask=call) -> dict:
    """Waits until SonarQube has worked through the analysis the scanner sent; the task (status SUCCESS) or SonarError."""
    end = time.monotonic() + minutes * 60
    while time.monotonic() < end:
        st = ask("GET", "/api/ce/component", {"component": PROJECT}, token=token)
        if not st.get("queue"):
            cur = st.get("current") or {}
            if cur.get("status") == "SUCCESS":
                return cur
            if cur.get("status") in ("FAILED", "CANCELED"):
                raise SonarError(f"SonarQube could not process the analysis: {cur.get('errorMessage', cur.get('status'))}")
        sleep(5)
    raise SonarError(f"the analysis was not processed in {minutes:.0f} minutes")


def pages(path: str, key: str, params: dict, token: str, ask=call, size: int = 500) -> list[dict]:
    """Every item of a paged list (issues: SonarQube gives at most 10,000 for one search)."""
    out, p = [], 1
    while True:
        got = ask("GET", path, {**params, "ps": size, "p": p}, token=token)
        items = got.get(key) or []
        out += items
        total = (got.get("paging") or {}).get("total", got.get("total", len(out)))
        if not items or len(out) >= total or len(out) >= 10000:
            return out
        p += 1


# ---------------------------------------------------------------- reading the results
def kind_of(issue: dict) -> str:
    """An issue's kind: BUG, VULNERABILITY or CODE_SMELL (from its software quality when the old type is gone)."""
    if issue.get("type"):
        return issue["type"]
    qualities = {i.get("softwareQuality") for i in issue.get("impacts") or []}
    return "VULNERABILITY" if "SECURITY" in qualities else "BUG" if "RELIABILITY" in qualities else "CODE_SMELL"


def severity_of(issue: dict) -> str:
    """An issue's severity: the old one, or the worst of its impacts'."""
    if issue.get("severity"):
        return issue["severity"]
    sev = [i.get("severity", "INFO") for i in issue.get("impacts") or []]
    return min(sev, key=lambda s: SEVERITY_ORDER.index(s) if s in SEVERITY_ORDER else 99) if sev else "INFO"


def file_of(item: dict) -> str:
    """The file an issue or hotspot is in, from the repository's top folder."""
    comp = item.get("component", "")
    return comp.split(":", 1)[1] if ":" in comp else comp


def accepted_list(path: Path = ACCEPTED) -> list[dict]:
    """The issues accepted in writing with the owner's approval (rule, file pattern, why, by whom)."""
    return json.loads(path.read_text(encoding="utf-8")).get("accepted", []) if path.is_file() else []


def is_accepted(item: dict, accepted: list[dict]) -> dict | None:
    """The acceptance that covers an issue or hotspot (same rule, its file matching the pattern), or None."""
    rule, f = item.get("rule") or item.get("ruleKey", ""), file_of(item)
    for a in accepted:
        if a.get("rule") == rule and fnmatch.fnmatch(f, a.get("file", "*")) and \
                (not a.get("line") or a["line"] == item.get("line")):
            return a
    return None


def summarise(issues: list[dict], hotspots: list[dict], accepted: list[dict]) -> dict:
    """The counts the report and the exit code are made from."""
    open_issues = [i for i in issues if not is_accepted(i, accepted)]
    open_hot = [h for h in hotspots if not is_accepted(h, accepted)]
    return {
        "issues": len(issues), "hotspots": len(hotspots),
        "accepted": len(issues) + len(hotspots) - len(open_issues) - len(open_hot),
        "to_fix": len(open_issues) + len(open_hot),
        "by_kind": dict(Counter(kind_of(i) for i in open_issues)) | ({"SECURITY_HOTSPOT": len(open_hot)} if open_hot else {}),
        "by_severity": dict(Counter(severity_of(i) for i in open_issues)),
        "by_rule": dict(Counter(i.get("rule", "") for i in open_issues).most_common()),
        "by_file": dict(Counter(file_of(i) for i in [*open_issues, *open_hot]).most_common()),
        "passed": not open_issues and not open_hot,
    }


def report_md(summary: dict, issues: list[dict], hotspots: list[dict], accepted: list[dict], version: str = "") -> str:
    """report.md: the counts, then every issue still to fix by file and line (the list the fixes are made from)."""
    def order(i):
        return (TYPE_ORDER.index(kind_of(i)) if kind_of(i) in TYPE_ORDER else 9,
                SEVERITY_ORDER.index(severity_of(i)) if severity_of(i) in SEVERITY_ORDER else 9, file_of(i), i.get("line") or 0)
    lines = [f"# SonarQube scan of EA Explorer, {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
             "", f"SonarQube {version or '?'}, rules: Sonar way. "
             f"**{'PASSED' if summary['passed'] else 'FAILED'}**: {summary['to_fix']} to fix "
             f"({summary['issues']} issues, {summary['hotspots']} security hotspots, {summary['accepted']} accepted in writing).",
             "", "| Kind | Count |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(summary["by_kind"].items(), key=lambda x: TYPE_ORDER.index(x[0]) if x[0] in TYPE_ORDER else 9)]
    lines += ["", "| Severity | Count |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(summary["by_severity"].items(), key=lambda x: SEVERITY_ORDER.index(x[0]) if x[0] in SEVERITY_ORDER else 9)]
    lines += ["", "## The rules found most", "", "| Rule | Count |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in list(summary["by_rule"].items())[:40]]
    lines += ["", "## Every issue to fix", ""]
    for i in sorted((x for x in issues if not is_accepted(x, accepted)), key=order):
        lines.append(f"- `{file_of(i)}:{i.get('line') or '-'}` {kind_of(i)} {severity_of(i)} {i.get('rule')}: {i.get('message', '')}")
    hot = [h for h in hotspots if not is_accepted(h, accepted)]
    if hot:
        lines += ["", "## Security hotspots to review", ""]
        lines += [f"- `{file_of(h)}:{h.get('line') or '-'}` {h.get('vulnerabilityProbability', '')} {h.get('ruleKey', '')}: "
                  f"{h.get('message', '')}" for h in sorted(hot, key=lambda h: (file_of(h), h.get("line") or 0))]
    return "\n".join(lines) + "\n"


def report(folder: str, ask=call, keep: Path = KEEP, results: Path = RESULTS) -> bool:
    """The analysis read and written into work/tests/<folder>; the scan's token revoked. True when nothing is to fix."""
    token = (keep / "token").read_text(encoding="utf-8").strip()
    out = results / folder
    out.mkdir(parents=True, exist_ok=True)
    try:
        version = (keep / "version").read_text(encoding="utf-8").strip() if (keep / "version").is_file() else ""
        wait_analysis(token, ask=ask)
        issues = pages("/api/issues/search", "issues", {"components": PROJECT, "resolved": "false"}, token, ask=ask)
        hotspots = pages("/api/hotspots/search", "hotspots", {"project": PROJECT, "status": "TO_REVIEW"}, token, ask=ask)
    finally:
        try:
            pw = (keep / "admin").read_text(encoding="utf-8").strip()
            name = (keep / "token-name").read_text(encoding="utf-8").strip()
            ask("POST", "/api/user_tokens/revoke", {"name": name}, auth=("admin", pw))
        except (OSError, urllib.error.URLError, ValueError):
            pass
        for f in ("token", "token-name"):
            (keep / f).unlink(missing_ok=True)
    accepted = accepted_list()
    summary = summarise(issues, hotspots, accepted)
    (out / "issues.json").write_text(json.dumps(issues, indent=1), encoding="utf-8")
    (out / "hotspots.json").write_text(json.dumps(hotspots, indent=1), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (out / "report.md").write_text(report_md(summary, issues, hotspots, accepted, version), encoding="utf-8")
    print(f"{'PASSED' if summary['passed'] else 'FAILED'}: {summary['to_fix']} to fix "
          f"({summary['issues']} issues, {summary['hotspots']} hotspots, {summary['accepted']} accepted). "
          f"Report: work/tests/{folder}/report.md")
    for k, v in summary["by_kind"].items():
        print(f"  {k:<18} {v}")
    return summary["passed"]


def main(argv: list[str]) -> int:
    """prepare or report <folder>: 0 when done (and, for report, nothing to fix), 1 issues to fix, 2 an error, 3 the
    admin password lost (eax test sonar then starts SonarQube afresh)."""
    try:
        if argv[:1] == ["ready"]:            # eax sonar open (D805): SonarQube up and its admin password ours, no token
            try:
                print(f"SonarQube {wait_up()} is ready.")
                admin_password()
            except PasswordLost as exc:
                print(f"ERROR: {exc}")
                return 3
            return 0
        if argv[:1] == ["prepare"]:
            try:
                print(f"SonarQube {prepare()} is ready.")
            except PasswordLost as exc:
                print(f"ERROR: {exc}")
                return 3                       # eax test sonar starts SonarQube afresh and tries once more
            return 0
        if argv[:1] == ["report"] and len(argv) > 1:
            return 0 if report(argv[1]) else 1
    except urllib.error.HTTPError as exc:
        print(f"ERROR: {refused(exc)}")
        return 2
    except (SonarError, urllib.error.URLError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
