"""eax test jenkins (R9.13; owner, 22 Nov 2026, 09:51: "Can we have eax test jenkins which using api of jenkins calls
jenkins pipelines and we can ensure its actually happening by checking right command or something is triggered from
logs, testing the command result is out of scope"; D854).

Every pipeline is started through Jenkins' own REST API, as a person's click would start it, with its field EAX_PROBE
set to an id of this run. The pipeline sends its fields to the agent as always; the agent checks them as it checks a
real run (the catalogue, the options, the installation's name for a pipeline that changes everything) and records the
command in work/jenkins/runs.log with the probe's id, but runs nothing. This test then reads runs.log and compares the
command each pipeline started with the one it should start (argv_for, for the same fields). So no pipeline is run for
real, a restore or a wipe included; what the command itself then does is out of scope (eax test commands, R9.14).

Before anything is started it makes sure nothing can run for real by mistake: the agent must say it knows probes, and
every pipeline must have the EAX_PROBE field (an older pipeline would ignore it and run the command). If either is
missing it stops and says to run `eax jenkins up` (which writes the pipelines again and restarts the agent).
"""

from __future__ import annotations

import base64
import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import commands as C
from . import jenkins as J
from .core import EAX, WORK, Failure, say, setting

SAMPLE = "probe"                     # what a required field that takes a word gets


def jenkins_key(key: str) -> str:
    """A field's name in Jenkins, as deploy/jenkins/seed.groovy makes it from the option."""
    out = key[2:] if key.startswith("--") else key
    return out.replace("/", "_or_").replace("-", "_")


def sample_values(p: dict) -> tuple[dict[str, str], dict[str, str]]:
    """The fields a probe of one pipeline is started with: (Jenkins' names -> value, the options -> value as the agent
    gets them). Required words get SAMPLE, required choices their first choice; the rest is left empty, ticks unticked.
    A pipeline that changes everything gets the installation's name in CONFIRM."""
    jk: dict[str, str] = {}
    original: dict[str, str] = {}
    for f in p.get("params") or []:
        name = jenkins_key(f["key"])
        if f.get("type") == "flag":
            jk[name] = "false"
            continue
        value = ""
        if f.get("required"):
            choices = [c for c in (f.get("choices") or []) if c]
            if f["key"] == "COMMAND":       # the menus' and screens' pipelines: a command that needs no typed name
                choices = [c for c in choices if C.kind_of(c) == "run"] or choices
            value = choices[0] if choices else SAMPLE
        jk[name] = value
        if value:
            original[f["key"]] = value
    if p.get("confirm"):
        jk["CONFIRM"] = original["CONFIRM"] = J.installation()
    return jk, original


def expected(p: dict, original: dict[str, str]) -> tuple[str, str]:
    """The command the pipeline should start with these fields, or why the agent will refuse them ("" for the command)."""
    try:
        return J.shown(J.argv_for(p["name"], original)), ""
    except C.Refused as exc:
        return "", str(exc)


def job_path(p: dict) -> str:
    """The pipeline's address in Jenkins: /job/<folder>/job/<name> (a folder of eax-admin has two parts)."""
    parts = (p.get("folder") or "eax").split("/") + [p.get("display") or p["name"]]
    return "".join(f"/job/{urllib.parse.quote(x, safe='')}" for x in parts)


REFUSED = "refused: "


def recorded(log_text: str, run: str) -> dict[str, str]:
    """From runs.log, each probe of this run: its id -> the command the agent recorded."""
    out: dict[str, str] = {}
    for line in log_text.splitlines():
        cols = line.split("\t")
        if len(cols) >= 5 and cols[4].startswith(f"probe={run}-"):
            if len(cols) >= 6 and cols[5].startswith("refused="):        # the agent refused it (R12.22)
                out[cols[4][len("probe="):]] = REFUSED + cols[5][len("refused="):]
                continue
            argv = cols[3].split(" ")
            out[cols[4][len("probe="):]] = J.shown(argv) if argv and argv[0] else ""
    return out


class Jenkins:
    """Jenkins' REST API on this machine, signed in with its own account (and the crumb its CSRF guard wants)."""

    def __init__(self, base: str, user: str, password: str):
        self.base = base.rstrip("/")
        self.auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.crumb: dict[str, str] = {}

    def _call(self, method: str, path: str, data: bytes | None = None) -> tuple[int, bytes]:
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Authorization": self.auth, **self.crumb})
        if data is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with self.opener.open(req, timeout=30) as r:  # noqa: S310 - Jenkins on this machine
                return r.status, r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def sign_in(self) -> None:
        """The crumb Jenkins' CSRF guard asks for, in this session; a refused account said plainly."""
        code, body = self._call("GET", "/crumbIssuer/api/json")
        if code == 401:
            raise Failure("Jenkins refused its own account (EAX_JENKINS_ADMIN and EAX_JENKINS_ADMIN_PASSWORD).")
        if code == 200:
            c = json.loads(body)
            self.crumb = {c["crumbRequestField"]: c["crumb"]}

    def fields(self, path: str) -> list[str] | None:
        """A pipeline's field names, or None when Jenkins has no such pipeline."""
        code, body = self._call("GET", f"{path}/api/json?tree=property[parameterDefinitions[name]]")
        if code != 200:
            return None
        names = []
        for prop in json.loads(body).get("property") or []:
            names += [d.get("name") for d in prop.get("parameterDefinitions") or []]
        return names

    def start(self, path: str, values: dict[str, str]) -> int:
        """A pipeline started with these fields, as its Build button would; Jenkins' answer code (201: queued)."""
        code, _ = self._call("POST", f"{path}/buildWithParameters", urllib.parse.urlencode(values).encode())
        return code


def run(argv: list[str], jenkins: Jenkins | None = None, sleep=time.sleep, wait_minutes: float = 30) -> int:
    """eax test jenkins [--only NAME,NAME]: every pipeline probed; the report in work/tests/jenkins-<time>/."""
    only = set()
    if "--only" in argv and argv.index("--only") + 1 < len(argv):
        only = {x for x in argv[argv.index("--only") + 1].split(",") if x}
    if not J.answering():
        raise Failure(f"Jenkins does not answer: {EAX} jenkins up first.")
    if not agent_knows_probes():
        raise Failure(f"The Jenkins agent does not know probes yet (an older agent would run the commands for real): "
                      f"{EAX} jenkins stop-agent, then {EAX} jenkins up.")
    jenkins = jenkins or Jenkins(f"http://127.0.0.1:{setting('EAX_JENKINS_PORT', '8088')}",
                                 setting("EAX_JENKINS_ADMIN", "jenkins-admin"), setting("EAX_JENKINS_ADMIN_PASSWORD", ""))
    jenkins.sign_in()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = uuid.uuid4().hex[:8]
    pipes = [p for p in J.pipelines() if not only or p["name"] in only]
    rows: list[dict] = []
    started: dict[str, dict] = {}
    for n, p in enumerate(pipes, 1):
        row = {"pipeline": p["name"], "folder": p.get("folder") or "eax", "expected": "", "recorded": "", "outcome": "",
               "why": ""}
        rows.append(row)
        jk, original = sample_values(p)
        row["expected"], refused = expected(p, original)
        if refused:
            row.update(outcome="skipped", why=f"a sample cannot fill its fields: {refused}")
            continue
        path = job_path(p)
        names = jenkins.fields(path)
        if names is None:
            row.update(outcome="failed", why="Jenkins has no such pipeline (eax jenkins up writes them)")
            continue
        if "EAX_PROBE" not in names:            # an older pipeline would ignore the probe and run the command
            raise Failure(f"The pipeline {p['name']} has no EAX_PROBE field yet, so a probe would run it for real: "
                          f"{EAX} jenkins up first (it writes the pipelines again). Nothing was started.")
        probe = f"{run_id}-{n:03d}"
        code = jenkins.start(path, {**{k: v for k, v in jk.items() if k in names}, "EAX_PROBE": probe})
        if code not in (200, 201):
            row.update(outcome="failed", why=f"Jenkins did not start it (HTTP {code})")
            continue
        started[probe] = row
    # Jenkins runs them a couple at a time, about 6 seconds each (the owner's first run, 22 Nov 2026: 71 in 7 minutes),
    # so the wait is said and the count shown every 30 seconds: a long quiet wait looked hung (R12.21)
    say(f"{len(started)} of {len(pipes)} pipelines started as probes; waiting for each to reach the agent "
        f"(Jenkins runs them a couple at a time: about {max(1, round(len(started) * 6 / 60))} minutes)...")
    log = WORK / "jenkins" / "runs.log"
    end = time.time() + wait_minutes * 60
    seen: dict[str, str] = {}
    loops, told, quiet = 0, -1, 0
    while started and len(seen) < len(started) and time.time() < end:
        sleep(5)
        loops += 1
        before = len(seen)
        seen = recorded(log.read_text(encoding="utf-8", errors="replace") if log.exists() else "", run_id)
        quiet = 0 if len(seen) > before else quiet + 1
        if quiet >= 36:                          # 3 minutes and none more (R12.22): the rest never will
            say(f"  none more for 3 minutes: {len(started) - len(seen)} never reached the agent")
            break
        if loops % 6 == 0 and len(seen) != told and len(seen) < len(started):
            told = len(seen)
            say(f"  {told} of {len(started)} reached the agent so far "
                f"(about {max(1, round((len(started) - told) * 6 / 60))} minutes left)")
    for probe, row in started.items():
        if probe not in seen:
            row.update(outcome="failed", why="it never reached the agent (see the pipeline's run in Jenkins)")
            continue
        if seen[probe].startswith(REFUSED):
            row.update(outcome="failed", why="the agent refused it: " + seen[probe][len(REFUSED):])
            continue
        row["recorded"] = seen[probe]
        ok = seen[probe] == row["expected"]
        row.update(outcome="passed" if ok else "failed", why="" if ok else "the agent recorded another command")
    return report(rows, WORK / "tests" / f"jenkins-{stamp}")


def agent_knows_probes() -> bool:
    """Whether the agent running now records probes instead of running them (its /health says so)."""
    req = urllib.request.Request(f"http://127.0.0.1:{setting('EAX_JENKINS_AGENT_PORT', str(J.AGENT_PORT))}/health",
                                 headers={"X-Eax-Token": setting("EAX_JENKINS_AGENT_TOKEN", "")})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310 - this machine
            return bool(json.loads(r.read()).get("probe"))
    except (OSError, ValueError):
        return False


def report(rows: list[dict], folder: Path) -> int:
    """report.json and report.md, a line per pipeline on screen; 1 when any failed."""
    folder.mkdir(parents=True, exist_ok=True)
    count = {k: sum(1 for r in rows if r["outcome"] == k) for k in ("passed", "failed", "skipped")}
    (folder / "report.json").write_text(json.dumps({"counts": count, "pipelines": rows}, indent=1), encoding="utf-8")
    md = ["# eax test jenkins", "", f"Passed {count['passed']}, failed {count['failed']}, skipped {count['skipped']} "
          f"of {len(rows)} pipelines (each started through Jenkins as a probe: checked and recorded, not run).", "",
          "| Pipeline | Outcome | Command expected | Command recorded | Why |", "|---|---|---|---|---|"]
    md += [f"| {r['folder']}/{r['pipeline']} | {r['outcome']} | `{r['expected']}` | `{r['recorded']}` | {r['why']} |"
           for r in rows]
    (folder / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for r in rows:
        if r["outcome"] != "passed":
            say(f"  {r['outcome'].upper():8} {r['pipeline']}: {r['why']}", "red" if r["outcome"] == "failed" else "yellow")
    say(f"Jenkins pipelines: {count['passed']} passed, {count['failed']} failed, {count['skipped']} skipped "
        f"(the report: {folder / 'report.md'})", "green" if not count["failed"] else "red")
    return 1 if count["failed"] else 0
