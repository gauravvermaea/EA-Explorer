"""The attack test's scanners (R8.2, D817; owner, 17 Nov 2026, 18:18: "Lets get a docker container library or anything
that is regularly updated and can attack our platform both in blackbox and whitebox mode. We fix what we find. We check
for updates in every test"; 21 Nov 2026, 10:15: "Build what is needed for R 8.2 so that we can run it").

Run by the operations helper after the runner's attack suite (`eax test attack`), on the installation's own networks,
each scanner in its own container, removed when it ends. Every report lands in the run's folder for the runner's
`collect`, which turns each into findings for the security gate:

  black box   OWASP ZAP full scan of the front door (spider and active rules, as no one)     zap-full.json
              Schemathesis: the API's own description fuzzed, signed in as the run's Architect,
              only inside the run's own test data (attack-openapi.json, written by the runner)  schemathesis/junit.xml
              Nuclei: its community templates against every container's ports                   nuclei.jsonl
  white box   Semgrep, its maintained rule sets, on the source                                   semgrep.json
              Gitleaks, secrets in what is committed (the git history, not work/)                gitleaks.json

Always up to date: each image is pulled first and its version written to attack-tools.json; with no network the last
image pulled is used and the report says so; with none at all that scanner is left out, and said. Nothing here changes
the installation: the fuzzing writes only inside the run's test models and project, never deletes, never the admin,
operations, backup or download paths (attack_scope.py in the runner decides). A laptop or test installation only: on a
server the helper refuses unless the installation is marked a test one (EAX_ATTACK_ALLOWED=yes in the config file).

Bound to ops.py's helpers through testruns.H (the docker call, the containers)."""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import time

IMAGES = {     # always the newest (the owner: "We check for updates in every test"); each can be pinned in the config file
    "zap": os.environ.get("EAX_IMAGE_ZAP_ATTACK", "ghcr.io/zaproxy/zaproxy:stable"),
    "schemathesis": os.environ.get("EAX_IMAGE_SCHEMATHESIS", "schemathesis/schemathesis:stable"),
    "nuclei": os.environ.get("EAX_IMAGE_NUCLEI", "projectdiscovery/nuclei:latest"),
    "semgrep": os.environ.get("EAX_IMAGE_SEMGREP", "semgrep/semgrep:latest"),
    "gitleaks": os.environ.get("EAX_IMAGE_GITLEAKS", "ghcr.io/gitleaks/gitleaks:latest"),
}
TOOLS = "attack-tools.json"
SPEC, AUTH = "attack-openapi.json", "attack-auth.txt"          # written by the runner (eax/testing/attack_scope.py)
SEMGREP_RULES = ("p/python", "p/javascript", "p/react", "p/secrets", "p/dockerfile", "p/owasp-top-ten")
SKIP_DIRS = ("work", "persist", "node_modules", ".git", "dist", "__pycache__", ".venv")
NUCLEI_LEAVE_OUT = "dos,fuzz,intrusive"        # nothing that could knock a service over in the middle of the run
TIMEOUT = 3 * 3600                             # any one scanner, at most
FUZZ = ('exec schemathesis run /out/attack-openapi.json --url https://proxy -H "$EAX_FUZZ_AUTH" '
        "--tls-verify false --checks all --max-examples 25 --report junit --report-dir /out/schemathesis")
LEAKS = ("git config --global --add safe.directory '*' && exec gitleaks git /src --no-banner --redact "
         "--report-format json --report-path /out/gitleaks.json --exit-code 0")


def allowed(values: dict) -> tuple[bool, str]:
    """Whether this installation may be attacked: a laptop always; a server only when marked a test one."""
    kind = (values.get("EAX_DEPLOYMENT") or "laptop").strip().lower()
    if kind == "laptop":
        return True, "a laptop installation"
    if (values.get("EAX_ATTACK_ALLOWED") or "").strip().lower() in ("yes", "on", "true", "1"):
        return True, f"a {kind} installation marked as a test one (EAX_ATTACK_ALLOWED=yes)"
    return False, (f"This is a {kind} installation: the attack test runs only on a laptop or on a test installation "
                   "(set EAX_ATTACK_ALLOWED=yes in its config file if it is one). Nothing was run.")


def repo_of(work: str) -> str:
    """The installation folder (the source, on a laptop) beside work/, in the host's own spelling."""
    sep = "\\" if "\\" in work and "/" not in work else "/"
    base = re.sub(r"[\\/]work$", "", work.rstrip("\\/"))
    return base or sep


# ---------------------------------------------------------------- every test container named, labelled and removed
# (owner, 21 Nov 2026, 14:39: "when tests run they will bring down the contianer not in use"; 14:40: "This is important
# stray containers are hard on memory"). docker run --rm removes a scanner only when it ends by itself: when its time
# limit was hit only the waiting command was stopped and the scanner ran on (a ZAP full scan: 1 to 2 GB for an hour),
# and nothing named or labelled it, so eax up and down could not find it either.
LABEL = "eaexplorer.test"                       # its value: the run's folder in work/tests


def tag(args: list[str], folder: str, tool: str) -> tuple[list[str], str]:
    """A docker run given a name and the test label: (the arguments, the name)."""
    if args[:2] != ["docker", "run"] or "--name" in args:
        return args, ""
    clean = re.sub(r"[^A-Za-z0-9_.-]", "-", f"{tool}-{folder}")
    name = f"eax-test-{clean}-{secrets.token_hex(3)}"[:63]
    return [*args[:2], "--name", name, "--label", f"{LABEL}={folder or 'none'}", *args[2:]], name


def _named(args: list[str]) -> str:
    return args[args.index("--name") + 1] if "--name" in args[:-1] else ""


def remove(name: str) -> None:
    """The container itself removed (docker rm -f), not only the command that waited for it."""
    if name:
        try:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def sweep(folder: str | None = None) -> list[str]:
    """Every test container still there (one run's with its folder, every run's without), removed; their names."""
    want = f"label={LABEL}" + (f"={folder}" if folder else "")
    try:
        p = subprocess.run(["docker", "ps", "-a", "--filter", want, "--format", "{{.Names}}"], capture_output=True,
                           text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    names = [n.strip() for n in (p.stdout or "").splitlines() if n.strip()]
    for n in names:
        remove(n)
    return names


def run_tagged(args: list[str], folder: str, tool: str, timeout: int = TIMEOUT, env: dict | None = None) -> tuple[int, str]:
    """A scanner run named and labelled; at its time limit the container is removed too."""
    return _run(tag(args, folder, tool)[0], timeout, env)


def _run(args: list[str], timeout: int = TIMEOUT, env: dict | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        remove(_named(args))                         # the scanner too, not only the command waiting for it
        return 124, f"stopped after {timeout // 60} minutes"
    except OSError as exc:
        return 127, str(exc)


def pull(image: str, run=_run) -> dict:
    """The newest image, or the last one pulled when the network is away: {image, pulled, present, digest, note}."""
    code, _out = run(["docker", "pull", "--quiet", image], 1800)
    _code, got = run(["docker", "image", "inspect", "--format", "{{index .RepoDigests 0}}|{{.Created}}", image], 60)
    present = "|" in got and not got.lower().startswith("error")
    digest, _, made = got.strip().partition("|")
    note = "the newest" if code == 0 else ("offline: the last one pulled" if present else "not there and could not be pulled")
    return {"image": image, "pulled": code == 0, "present": present, "digest": digest if present else "",
            "created": made if present else "", "note": note}


def versions(folder: str, say, run=_run) -> dict:
    """Each scanner's image brought up to date first; their versions kept in attack-tools.json for the report."""
    got = {}
    for name, image in IMAGES.items():
        say(f"attack: updating {name} ({image})")
        got[name] = pull(image, run)
        if not got[name]["present"]:
            say(f"attack: {name} is not there and could not be pulled: left out ({got[name]['note']})")
        elif not got[name]["pulled"]:
            say(f"attack: {name}: no network, the last image pulled is used")
    with open(os.path.join(folder, TOOLS), "w", encoding="utf-8") as f:
        json.dump({"at": time.time(), "tools": got}, f, indent=1)
    return got


def zap_full(hostdir: str, front: str, say, run=_run) -> None:
    """OWASP ZAP full scan of the front door: the spider, then every active rule, as someone not signed in."""
    say("attack: OWASP ZAP full scan of the front door (spider and active rules; up to an hour)")
    code, out = run(tag(["docker", "run", "--rm", *(["--network", front] if front else []), "-v", f"{hostdir}:/zap/wrk:rw",
                         "-t", IMAGES["zap"], "zap-full-scan.py", "-t", "https://proxy/", "-J", "zap-full.json", "-I",
                         "-m", "10", "-T", "60"], os.path.basename(hostdir), "zap")[0])
    if code not in (0, 1, 2, 3):
        say(f"attack: ZAP did not finish ({code}): {out.strip()[-300:]}")


def _token(here: str) -> str:
    """The run's Architect's token, read once and its file deleted at once, whatever happens."""
    path = os.path.join(here, AUTH)
    try:
        with open(path, encoding="utf-8") as f:
            token = f.read().strip()
    except OSError:
        return ""
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return token if re.fullmatch(r"[A-Za-z0-9._~+/=-]{8,8000}", token) else ""


def schemathesis(here: str, hostdir: str, front: str, say, run=_run) -> None:
    """The API fuzzed from its own description: malformed and edge-case requests to every call in the run's scope,
    signed in as the run's Architect; server errors and answers that break the description are what it looks for."""
    token = _token(here)
    if not os.path.exists(os.path.join(here, SPEC)) or not token:
        say("attack: Schemathesis: no scope or token from the runner: left out")
        return
    say("attack: Schemathesis fuzzing the API in the run's test data, as its Architect")
    env = {**os.environ, "EAX_FUZZ_AUTH": f"Authorization: Bearer {token}"}   # the value from env: not on the command line
    code, out = run(tag(["docker", "run", "--rm", *(["--network", front] if front else []), "-v", f"{hostdir}:/out:rw",
                         "-e", "EAX_FUZZ_AUTH", "--entrypoint", "sh", IMAGES["schemathesis"], "-c", FUZZ],
                        os.path.basename(hostdir), "schemathesis")[0], env=env)
    with open(os.path.join(here, "schemathesis.log"), "w", encoding="utf-8") as f:
        f.write(out.replace(token, "<token>"))
    if code not in (0, 1):
        say(f"attack: Schemathesis did not finish ({code}): see schemathesis.log")


def targets(containers: list[dict], inspect) -> dict[str, list[str]]:
    """Every running container's ports, by network: {network: ["service:port", ...]} (scanners excluded)."""
    out: dict[str, list[str]] = {}
    for c in containers:
        if c.get("state") != "running" or c.get("service") in ("testrunner", "ops"):
            continue
        try:
            info = json.loads(inspect(c["id"]))
        except (ValueError, RuntimeError, KeyError):
            continue
        ports = sorted({p.split("/")[0] for p in ((info.get("Config") or {}).get("ExposedPorts") or {})
                        if p.endswith("/tcp")}, key=lambda p: int(p) if p.isdigit() else 0)
        nets = list(((info.get("NetworkSettings") or {}).get("Networks") or {}).keys())
        if not ports or not nets:
            continue
        host = c.get("name") or c["service"]
        for net in nets:
            out.setdefault(net, []).extend(f"{host}:{p}" for p in ports)
    return {n: sorted(set(t)) for n, t in out.items()}


def nuclei(here: str, hostdir: str, nets: dict[str, list[str]], say, run=_run) -> None:
    """Nuclei's community templates (brought up to date first) against every container's ports, network by network;
    one JSON line a finding in nuclei.jsonl."""
    if not nets:
        say("attack: Nuclei: no container ports found: left out")
        return
    run(tag(["docker", "run", "--rm", "-v", "eaexplorer-nuclei:/root", IMAGES["nuclei"], "-update-templates", "-silent"],
            os.path.basename(hostdir), "nuclei-update")[0], 1800)
    for i, (net, hosts) in enumerate(sorted(nets.items())):
        name = f"nuclei-targets-{i}.txt"
        with open(os.path.join(here, name), "w", encoding="utf-8") as f:
            f.write("\n".join(hosts) + "\n")
        say(f"attack: Nuclei against {len(hosts)} ports on {net}")
        code, out = run(tag(["docker", "run", "--rm", "--network", net, "-v", "eaexplorer-nuclei:/root", "-v",
                             f"{hostdir}:/out:rw", IMAGES["nuclei"], "-l", f"/out/{name}", "-jsonl", "-o",
                             f"/out/nuclei-{i}.jsonl", "-silent", "-nc", "-duc", "-es", "info", "-etags", NUCLEI_LEAVE_OUT],
                            os.path.basename(hostdir), "nuclei")[0])
        if code not in (0, 1):
            say(f"attack: Nuclei on {net} did not finish ({code}): {out.strip()[-300:]}")
    with open(os.path.join(here, "nuclei.jsonl"), "w", encoding="utf-8") as joined:
        for i in range(len(nets)):
            try:
                with open(os.path.join(here, f"nuclei-{i}.jsonl"), encoding="utf-8") as f:
                    joined.write(f.read())
            except OSError:
                pass


def semgrep(hostdir: str, repo: str, say, run=_run) -> None:
    """Semgrep's maintained rule sets on the source (read only; work/, persist/ and the libraries left out)."""
    say(f"attack: Semgrep on the source ({', '.join(SEMGREP_RULES)})")
    args = ["docker", "run", "--rm", "-v", f"{repo}:/src:ro", "-v", f"{hostdir}:/out:rw", IMAGES["semgrep"],
            "semgrep", "scan", "--metrics", "off", "--json", "--output", "/out/semgrep.json", "--quiet"]
    for r in SEMGREP_RULES:
        args += ["--config", r]
    for d in SKIP_DIRS:
        args += ["--exclude", d]
    code, out = run(tag([*args, "/src"], os.path.basename(hostdir), "semgrep")[0])
    if code not in (0, 1):
        say(f"attack: Semgrep did not finish ({code}): {out.strip()[-300:]}")


def gitleaks(hostdir: str, repo: str, say, run=_run) -> None:
    """Gitleaks on what is committed (the git history): a secret that reached git, never the work folder's own."""
    say("attack: Gitleaks on the git history")
    code, out = run(tag(["docker", "run", "--rm", "-v", f"{repo}:/src:ro", "-v", f"{hostdir}:/out:rw", "--entrypoint", "sh",
                         IMAGES["gitleaks"], "-c", LEAKS], os.path.basename(hostdir), "gitleaks")[0])
    if code != 0:
        say(f"attack: Gitleaks did not finish ({code}): {out.strip()[-300:]}")


def run_all(H: dict, info: dict, folder: str, work: str, hostwork: str, say, run=_run) -> dict:
    """Every scanner, in turn, after the runner's attack suite. Returns what ran: {tool: ran?}."""
    here, hostdir = os.path.join(work, "tests", folder), f"{hostwork}/tests/{folder}"
    repo = repo_of(hostwork)
    got = versions(here, say, run)
    nets = list(((info.get("NetworkSettings") or {}).get("Networks") or {}).keys())
    front = next((n for n in nets if n.endswith("frontend")), "")
    ran = {}
    if got["zap"]["present"]:
        zap_full(hostdir, front, say, run)
        ran["zap"] = True
    if got["schemathesis"]["present"]:
        schemathesis(here, hostdir, front, say, run)
        ran["schemathesis"] = True
    else:
        _token(here)                                    # never left behind
    if got["nuclei"]["present"]:
        nuclei(here, hostdir, targets(H["containers"](), lambda cid: H["docker"]("inspect", "--format", "{{json .}}", cid)),
               say, run)
        ran["nuclei"] = True
    if got["semgrep"]["present"]:
        semgrep(hostdir, repo, say, run)
        ran["semgrep"] = True
    if got["gitleaks"]["present"]:
        gitleaks(hostdir, repo, say, run)
        ran["gitleaks"] = True
    left = sweep(folder)                                # nothing of this run left running (owner, 14:40)
    if left:
        say(f"attack: removed {len(left)} scanner container(s) still there: {', '.join(left)}")
    return ran
