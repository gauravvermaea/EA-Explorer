"""eax jenkins: Jenkins beside EA Explorer, a click on a pipeline and an eax command runs (Release 6.6, R6.6-J1, D748,
D750; owner, 17 Nov 2026, 19:03 to 19:50: "We have a jeniins container we click on pipelines and things happen",
19:45: "Ensure every eax command and the dr command is executable from jenkins").

  eax jenkins up          Jenkins started in a stack of its own (<installation>-jenkins: it survives a restore drill or
                          a full restore that shuts EA Explorer down), its sign-in client made in Keycloak, the agent
                          started on this machine and the pipelines written
  eax jenkins down        Jenkins and the agent stopped (Jenkins' own data kept)
  eax jenkins status      whether Jenkins and the agent run, where to open Jenkins, how many pipelines
  eax jenkins pipelines   the pipelines written again (after an update adds a command)
  eax jenkins agent       the agent, in this window (eax jenkins up starts it in the background)

How it fits together:
  * Jenkins never owns Docker. It calls **the agent**, a small program on this machine, with a token: the agent runs
    only the eax commands of the catalogue (eaxcli/help.txt, the same checks as the Command centre, eaxcli/commands.py)
    and the DR tools (eax-dr, eax-drill, eax dr-pack), with their options checked, no shell; nothing else.
  * **Every eax command and DR tool has a pipeline**, its options as fields (a test fails when one has none). A command
    that asks questions or opens a screen runs without asking: --yes where it takes one; the menu, the full screen and
    the console run the command chosen in the pipeline; document writes its web page; restore-model takes its choices
    as fields.
  * Pipelines that change everything (a full restore, a clean restart, an update or a rollback: offline and wipe
    commands, and the DR tools) need **the installation's name typed** in the pipeline (one admin, D750); the agent
    checks it again. Every run records who clicked (Jenkins' own user, from Keycloak) in work/jenkins/runs.log and the
    run's output under work/jenkins/runs/.
  * **Sign-in**: Keycloak (Super Admins and IT Admins see the pipelines) and Jenkins' own account (EAX_JENKINS_ADMIN,
    its password in EAX_JENKINS_ADMIN_PASSWORD) as the way in when Keycloak is down.
No platform-specific code (D746): the same on any machine with Docker and eax.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets as _random
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import commands as C
from .core import EAX, ENV_FILE, ROOT, WORK, Failure, say, setting

COMPOSE = "deploy/jenkins/docker-compose.jenkins.yml"
AGENT_PORT = 8091
DR_TOOLS = {
    "eax-dr": {"summary": "A DR copy built from a DR pack or a backup (dr/eax-dr): EA Explorer installed, the backup restored",
               "params": [{"key": "--pack", "type": "flag-value", "placeholder": "folder of the DR pack"},
                          {"key": "--backup", "type": "flag-value", "placeholder": "folder of a backup (instead of a pack)"},
                          {"key": "--install", "type": "flag-value", "required": True, "placeholder": "folder to install into"},
                          {"key": "--version", "type": "flag-value", "placeholder": "release, e.g. 6.6.0"},
                          {"key": "--env", "type": "flag-value", "placeholder": "the env file to use"},
                          {"key": "--code", "type": "flag-value", "placeholder": "a copy of the code (no GitHub)"},
                          {"key": "--project", "type": "flag-value", "placeholder": "its Docker name"},
                          {"key": "--github", "type": "flag"}, {"key": "--no-smoke", "type": "flag"}]},
    "eax-drill": {"summary": "The restore drill (dr/eax-drill): backed up, shut down, a copy built and restored, compared, put back",
                  "params": [{"key": "--install", "type": "flag-value", "required": True, "placeholder": "the installation"},
                             {"key": "--dr", "type": "flag-value", "required": True, "placeholder": "folder for the DR copy"},
                             {"key": "--temp", "type": "flag-value", "required": True, "placeholder": "a temp folder"},
                             {"key": "--smoke", "type": "flag"}, {"key": "--smoke-after", "type": "flag"},
                             {"key": "--then-back", "type": "flag"}]},
}
# commands whose screens or questions are answered by the pipeline's fields (D748: "gets the flags to run without asking")
UI_COMMANDS = {"menu", "screen", "console"}       # they run the command chosen in the pipeline
EXTRA_PARAMS = {
    "restore-model": [{"key": "arg0", "type": "word", "required": True, "placeholder": "application backup run"},
                      {"key": "arg1", "type": "word", "required": True, "placeholder": "model backup file"},
                      {"key": "--new", "type": "flag-value", "placeholder": "a new model's name (or tick --over)"},
                      {"key": "--over", "type": "flag"}],
}
FIXED_ARGS = {"document": ["--web"], "deploy": ["--console"]}
# Admin tasks (the owner, 18 Nov 2026, 09:56 to 10:03): named pipelines in their own Jenkins folder, beside the one per
# command, for what is done on the machine and not inside the application ("These should be things we wont do from
# inside the application. So user management is not going to be done here"; "starting eax should be one of the
# things"). Each is one eax command (or a DR tool) with friendly fields; {"p": KEY} is a field, with "flag" when it goes
# after an option; an empty optional field is left out. Those that stop or replace things ask for the installation's name.
def _w(key: str, say: str, required: bool = True, choices: list[str] | None = None, flag: str = "") -> dict:
    return {"p": key, "say": say, "required": required, "choices": choices or [], "flag": flag}


ALLOW_PLACES = ["site", "signin", "admin", "mcp", "machine"]
ADMIN_TASKS: list[dict] = [
    # start and stop
    {"name": "start", "group": "Start and stop", "summary": "EA Explorer started, everything waited for (eax up --wait-all)",
     "argv": ["up", "--wait-all"], "confirm": False},
    {"name": "stop", "group": "Start and stop", "summary": "EA Explorer stopped; every database, document and setting kept",
     "argv": ["stop"], "confirm": True},
    {"name": "restart", "group": "Start and stop", "summary": "EA Explorer stopped and started again, everything waited for",
     "argv": ["restart", "--wait-all"], "confirm": True},
    # the environment's status and its error codes (Release 7.9, D787; owner, 18 Nov 2026, 23:29: "error code can be
    # queried from jenkins", "they give enviornment status")
    {"name": "status", "group": "Status and error codes",
     "summary": "The environment's status: every container, the disks, then every problem with its error code and what to do",
     "argv": ["status"]},
    {"name": "problems", "group": "Status and error codes",
     "summary": "Only the problems now, each with its error code (EAX-AREA-NNN) and what to do", "argv": ["status", "problems"]},
    {"name": "error-code", "group": "Status and error codes",
     "summary": "What an error code means, its usual cause and what to do (empty: every code)",
     "argv": ["errors", _w("CODE", "a code (EAX-AUTH-001), an area (BAK) or a word (backup); empty for every code", required=False)]},
    {"name": "maintenance-page-on", "group": "Get back in", "summary": "The maintenance page shown to everyone",
     "argv": ["maintenance", "on"]},
    {"name": "maintenance-page-off", "group": "Get back in", "summary": "The maintenance page taken down (and the background let run again: eax maintenance clear does both)",
     "argv": ["maintenance", "off"]},
    {"name": "maintenance-clear", "group": "Get back in",
     "summary": "What a cut-off backup, restore or drill left (the page, a restore's record, the background paused) cleared",
     "argv": ["maintenance", "clear"]},
    {"name": "change-hostname", "group": "Start and stop",
     "summary": "The name people open EA Explorer at (EAX_HOSTNAME); then restart",
     "argv": ["hostname", "set", _w("NAME", "the name, e.g. ea.example.org")], "confirm": True},
    # certificates
    {"name": "front-certificate-show", "group": "Certificates", "summary": "The certificate people's browsers see: names, issuer, end",
     "argv": ["certs", "front"]},
    {"name": "front-certificate-install", "group": "Certificates",
     "summary": "Your organisation's certificate from files on the machine: checked, the one in use kept, no restart",
     "argv": ["certs", "front", "install", _w("CERT_FILE", "the certificate file (PEM), e.g. C:/certs/ea.crt", flag="--cert"),
              _w("KEY_FILE", "its private key file (PEM, no password)", flag="--key"),
              _w("CHAIN_FILE", "the chain file, when not in the certificate file", required=False, flag="--chain")], "confirm": True},
    {"name": "front-certificate-undo", "group": "Certificates", "summary": "The certificate in use before the last one put back",
     "argv": ["certs", "front", "undo"], "confirm": True},
    {"name": "own-certificates-renew", "group": "Certificates",
     "summary": "EA Explorer's own certificates (certificate mode) made again now", "argv": ["certs", "renew", "--force"]},
    {"name": "own-certificate-revoke", "group": "Certificates", "summary": "One service's own certificate refused and a new one issued",
     "argv": ["certs", "revoke", _w("SERVICE", "the service", choices=["api", "library", "views", "keycloak", "reports", "dms"])],
     "confirm": True},
    # getting back in
    {"name": "admins", "group": "Get back in", "summary": "The administrators and whether each is enabled", "argv": ["access", "admins"]},
    {"name": "admin-reset-password", "group": "Get back in",
     "summary": "A temporary password for an administrator, shown once in the output; changed at the next sign-in",
     "argv": ["access", "reset-password", _w("USER", "the administrator's user name")], "confirm": True},
    {"name": "admin-unlock", "group": "Get back in", "summary": "An administrator's account enabled and unlocked after wrong passwords",
     "argv": ["access", "unlock", _w("USER", "the administrator's user name")]},
    {"name": "admin-mfa-off", "group": "Get back in", "summary": "An administrator's authenticator removed (a lost phone)",
     "argv": ["access", "mfa-off", _w("USER", "the administrator's user name")], "confirm": True},
    {"name": "mfa-off-for-everyone", "group": "Get back in",      # R12.20 (owner, 22 Nov 2026, 10:52)
     "summary": "Multi-factor sign-in off for everyone: the setting off, every authenticator removed, nobody asked",
     "argv": ["access", "mfa-off", "--all", "--yes"], "confirm": True},
    {"name": "allowed-addresses", "group": "Get back in", "summary": "The IP allow lists, place by place", "argv": ["allow", "show"]},
    {"name": "allow-an-address", "group": "Get back in", "summary": "An address or range let in (e.g. 10.20.0.0/16)",
     "argv": ["allow", "add", _w("PLACE", "where", choices=ALLOW_PLACES), _w("ADDRESS", "an address or range"),
              _w("NAME", "a name for it, one word", required=False)]},
    {"name": "remove-an-address", "group": "Get back in", "summary": "An address or range taken off an allow list",
     "argv": ["allow", "remove", _w("PLACE", "where", choices=ALLOW_PLACES), _w("ADDRESS", "the address or range")]},
    {"name": "allow-everyone", "group": "Get back in", "summary": "Every allow list emptied: everyone may reach EA Explorer again",
     "argv": ["allow", "clear"], "confirm": True},
    # backup and DR
    {"name": "backup-now", "group": "Backup and DR", "summary": "A backup of the whole installation now",
     "argv": ["backup", _w("TAG", "a tag, one word (e.g. before-upgrade)", required=False)]},
    {"name": "backups", "group": "Backup and DR", "summary": "The backups, newest first", "argv": ["backups"]},
    {"name": "restore-a-backup", "group": "Backup and DR", "summary": "A backup restored (everyone locked out until it is done)",
     "argv": ["restore", _w("BACKUP", "its name, or latest"), _w("WHAT", "what to restore", choices=["full", "db", "files", "app", "app+data"], flag="--what")],
     "confirm": True},
    {"name": "delete-a-backup", "group": "Backup and DR", "summary": "One backup deleted (never a pinned one)",
     "argv": ["delete-backup", _w("BACKUP", "its name")], "confirm": True},
    {"name": "dr-pack", "group": "Backup and DR", "summary": "A DR pack: everything to rebuild elsewhere, in one checked folder",
     "argv": ["dr-pack", _w("FOLDER", "where to write it, e.g. D:/dr-packs")]},
    {"name": "build-dr-copy", "group": "Backup and DR", "summary": "A DR copy built from a DR pack or a backup (dr/eax-dr)",
     "tool": "eax-dr", "confirm": True},
    {"name": "restore-drill", "group": "Backup and DR",
     "summary": "The restore drill: this installation stopped, a DR copy built, restored and left running for you", "tool": "eax-drill",
     "confirm": True},
    # settings and admin configuration (Release 6.7, D755)
    {"name": "export-settings", "group": "Settings", "summary": "The settings and admin configuration written to a file (the parts chosen)",
     "argv": ["settings", "export", _w("FILE", "the file to write, e.g. D:/eax/settings.json"),
              _w("PARTS", "the parts, e.g. system,branding (all when empty)", required=False, flag="--parts")]},
    {"name": "settings-differences", "group": "Settings", "summary": "Every difference between a settings file and this installation; nothing changed",
     "argv": ["settings", "import", _w("FILE", "the settings file"),
              _w("PARTS", "the parts, e.g. system,branding (all when empty)", required=False, flag="--parts")]},
    {"name": "import-settings", "group": "Settings",
     "summary": "A safety copy kept, then every difference in a settings file taken (the parts chosen)",
     "argv": ["settings", "import", _w("FILE", "the settings file"),
              _w("PARTS", "the parts, e.g. system,branding (all when empty)", required=False, flag="--parts"), "--yes"],
     "confirm": True},
    {"name": "settings-safety-copies", "group": "Settings", "summary": "The safety copies kept before each import", "argv": ["settings", "copies"]},
    {"name": "undo-a-settings-import", "group": "Settings", "summary": "The settings a safety copy kept put back",
     "argv": ["settings", "undo", _w("COPY", "the safety copy's id (settings-safety-copies lists them)")], "confirm": True},
    # upkeep
    {"name": "rotate-all-secrets", "group": "Upkeep",
     "summary": "Every password and key rotated behind the maintenance page, then EA Explorer restarted",
     "argv": ["secrets", "rotate", "--all", "--restart"], "confirm": True},
    {"name": "rotate-all-secrets-at", "group": "Upkeep",
     "summary": "Rotate all once, at a date and time (e.g. 2026-11-20T17:00); the same schedules as the app",
     "argv": ["secrets", "schedule", _w("AT", "when: YYYY-MM-DDTHH:MM, in the installation's time zone", flag="--at")]},
    {"name": "rotate-all-secrets-regularly", "group": "Upkeep",
     "summary": "Rotate all regularly: monthly or every three months (1st, 03:30), or off; the same schedules as the app",
     "argv": ["secrets", "schedule", _w("EVERY", "how often", choices=["monthly", "quarterly", "off", "show"])]},
    {"name": "secrets", "group": "Upkeep", "summary": "Every password and key by name: age, next due, what needs a person",
     "argv": ["secrets", "show"]},
    {"name": "database-check", "group": "Upkeep", "summary": "What needs doing in every database, in plain words", "argv": ["db", "check"]},
    {"name": "database-integrity", "group": "Upkeep", "summary": "Every database's indexes, tables, constraints and newest records checked",
     "argv": ["db", "integrity"]},
    {"name": "database-safe-fixes", "group": "Upkeep",
     "summary": "The integrity check's safe fixes made (an index rebuilt, a sequence moved on), after a backup",
     "argv": ["db", "integrity", "--fix"], "confirm": True},
    {"name": "database-tidy", "group": "Upkeep", "summary": "The nightly tidy now (nothing locked)", "argv": ["db", "tidy"]},
    {"name": "stuck-jobs-cleared", "group": "Upkeep", "summary": "Background jobs left running by a stopped service cleared",
     "argv": ["jobs", "clear-stuck"]},
    {"name": "diagnostics", "group": "Upkeep", "summary": "Every container's state and logs, in one bundle to send", "argv": ["diag"]},
    {"name": "smoke-test", "group": "Upkeep", "summary": "Every role signs in, every area answers", "argv": ["test", "smoke"]},
    {"name": "attack-test", "group": "Upkeep",                    # R8.2 (owner, 21 Nov 2026, 10:47: "Add pipeline in Jenkins to do attack")
     "summary": "The attack test: tools that try to break EA Explorer, each updated first (an hour or more)",
     "argv": ["test", "attack"]},
    {"name": "full-test", "group": "Upkeep",                      # R9.10: the full test from Jenkins, the DR drill last
     "summary": "The full test: dev check, self-test, backup and restore, SonarQube, then the DR drill (hours)",
     "argv": ["test", "full",
              _w("DEV_CHECK", "--no-dev-check to leave the dev check out", required=False, choices=["--no-dev-check"]),
              _w("ATTACK", "--no-attack to leave the attack test out", required=False, choices=["--no-attack"]),
              _w("SONAR", "--no-sonar to leave the SonarQube scan out", required=False, choices=["--no-sonar"]),
              _w("DR_DRILL", "--no-dr to leave the DR drill out", required=False, choices=["--no-dr"])],
     "confirm": True},
    {"name": "update", "group": "Upkeep", "summary": "To the newest release of your channel (a backup first)", "argv": ["update"],
     "confirm": True},
    {"name": "rollback", "group": "Upkeep", "summary": "Back to the release before, with its data as it was", "argv": ["rollback"],
     "confirm": True},
]
ADMIN_BY_NAME = {f"admin-{t['name']}": t for t in ADMIN_TASKS}   # the agent's name for each, apart from the commands' own


def _slug(group: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", group.lower()).strip("-")


def admin_argv(name: str, values: dict) -> list[str]:
    """An admin task's command line from its fields (checked again as every command is, by the caller)."""
    out: list[str] = []
    for part in ADMIN_BY_NAME[name]["argv"]:   # name: admin-<task>
        if isinstance(part, str):
            out.append(part)
            continue
        v = str(values.get(part["p"]) or "").strip().replace("\\", "/")
        if not v:
            if part["required"]:
                raise C.Refused(f"{part['p']} is needed: {part['say']}")
            continue
        if part["choices"] and v not in part["choices"]:
            raise C.Refused(f"{part['p']}: one of {', '.join(part['choices'])}")
        out += [part["flag"], v] if part["flag"] else [v]
    return out


CHANGES_EVERYTHING = {"offline", "wipe", "dr"}


# ---------------------------------------------------------------- the pipelines
def kind(name: str) -> str:
    """A pipeline's kind: dr (a DR tool), or the command's kind in the Command centre."""
    return "dr" if name in DR_TOOLS else C.kind_of(name)


def pipelines() -> list[dict]:
    """Every eax command of help.txt and every DR tool as a pipeline: name, group, summary, fields, whether the
    installation's name must be typed."""
    out = []
    every = [c["name"] for g in C.catalogue()["groups"] for c in g["commands"]]
    for g in C.catalogue()["groups"]:
        for c in g["commands"]:
            params = EXTRA_PARAMS.get(c["name"]) or [p for p in c.get("params") or [] if p.get("key") != "--yes"]
            if c["name"] in UI_COMMANDS:
                params = [{"key": "COMMAND", "type": "choice", "required": True,
                           "choices": [n for n in every if n not in UI_COMMANDS]},
                          {"key": "ARGS", "type": "words", "placeholder": "its options, as typed after eax <command>"}]
            out.append({"name": c["name"], "group": g["title"] if "title" in g else g.get("name", ""), "summary": c["summary"],
                        "params": params, "kind": kind(c["name"]), "confirm": kind(c["name"]) in CHANGES_EVERYTHING})
    for a in ADMIN_TASKS:
        if a.get("tool"):
            params = DR_TOOLS[a["tool"]]["params"]
        else:
            params = [{"key": x["p"], "type": "choice" if x["choices"] else "word", "required": x["required"],
                       "choices": x["choices"], "placeholder": x["say"]} for x in a["argv"] if isinstance(x, dict)]
        out.append({"name": f"admin-{a['name']}", "display": a["name"], "folder": f"eax-admin/{_slug(a['group'])}", "group": a["group"], "summary": a["summary"],
                    "params": params, "kind": "dr" if a.get("tool") else "admin", "confirm": bool(a.get("confirm"))})
    for name, t in DR_TOOLS.items():
        out.append({"name": name, "group": "Disaster recovery", "summary": t["summary"], "params": t["params"], "kind": "dr",
                    "confirm": True})
    out.append({"name": "dr-pack", "group": "Disaster recovery", "summary": "A DR pack written to a folder (eax dr-pack)",
                "params": [{"key": "arg0", "type": "word", "required": True, "placeholder": "folder"}], "kind": "run",
                "confirm": False}) if not any(p["name"] == "dr-pack" for p in out) else None
    return out


def write_pipelines(folder: Path | None = None) -> Path:
    """work/jenkins/pipelines.json: what Jenkins' job seed makes a pipeline of, one per command and DR tool."""
    folder = folder or WORK / "jenkins"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "pipelines.json"
    path.write_text(json.dumps({"installation": installation(), "made": datetime.now(UTC).isoformat(),
                                "pipelines": pipelines()}, indent=2), encoding="utf-8")
    return path


def installation() -> str:
    """The installation's name people type to confirm (the same as the Command centre's)."""
    return setting("EAX_INSTALLATION_NAME", "") or setting("EAX_HOSTNAME", "localhost")


# ---------------------------------------------------------------- the agent: runs what Jenkins asks, only that
def argv_for(name: str, values: dict) -> list[str]:
    """The command line for a pipeline's fields, checked as the Command centre checks it (no shell, known options only)."""
    if name in DR_TOOLS:
        out: list[str] = []
        for p in DR_TOOLS[name]["params"]:
            v = values.get(p["key"])
            if p["type"] == "flag":
                if str(v).lower() in ("true", "1", "yes", "on"):
                    out.append(p["key"])
            elif v not in (None, ""):
                tok = str(v)
                if not C.TOKEN.match(tok.replace("\\", "/").replace(" ", "_")):
                    raise C.Refused(f"{p['key']}: not an allowed value")
                out += [p["key"], tok]
            elif p.get("required"):
                raise C.Refused(f"{p['key']} is needed")
        return [name, *out]
    if name in ADMIN_BY_NAME:
        if ADMIN_BY_NAME[name].get("tool"):
            return argv_for(ADMIN_BY_NAME[name]["tool"], values)
        return C.check_argv(admin_argv(name, values))
    if name in UI_COMMANDS:
        chosen = str(values.get("COMMAND") or "")
        if not chosen or chosen in UI_COMMANDS:
            raise C.Refused("Choose the command to run")
        return C.check_argv([chosen, *[a for a in str(values.get("ARGS") or "").split() if a]])
    if name in EXTRA_PARAMS:
        argv = [name]
        for p in EXTRA_PARAMS[name]:
            v = values.get(p["key"])
            if p["type"] == "flag" and str(v).lower() in ("true", "1", "yes", "on"):
                argv.append(p["key"])
            elif p["type"] == "flag-value" and v:
                argv += [p["key"], str(v)]
            elif p["type"] == "word" and v:
                argv.append(str(v))
        return C.check_argv(argv)
    argv = C.build_argv(name, {k: v for k, v in values.items() if k not in ("CONFIRM", "BY")})
    return C.check_argv([*argv, *[a for a in FIXED_ARGS.get(name, []) if a not in argv]])


def command_line(argv: list[str]) -> list[str]:
    """How the agent runs it: eax commands through eaxpy (the same on every machine), the DR tools through their
    PowerShell or shell script."""
    if argv[0] in DR_TOOLS:
        ps = shutil.which("pwsh") or shutil.which("powershell")
        if os.name == "nt" and ps:
            return [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "dr" / f"{argv[0]}.ps1"),
                    *[_ps_arg(a) for a in argv[1:]]]
        return ["bash", str(ROOT / "dr" / f"{argv[0]}.sh"), *argv[1:]]
    if argv[0] in C.YES and "--yes" not in argv:
        argv = [*argv, "--yes"]
    return [sys.executable, str(ROOT / "eaxpy.py"), *argv]


def _ps_arg(a: str) -> str:
    """eax-dr.ps1 and eax-drill.ps1 take -Install, -Dr... where the shell scripts take --install, --dr..."""
    if a.startswith("--"):
        return "-" + "".join(w.capitalize() for w in a[2:].split("-")).replace("Env", "EnvFile")
    return a


CREATE_NO_WINDOW = 0x08000000


def no_window() -> dict:
    """On Windows, a run started with no console window (the owner, 18 Nov 2026, 12:18: "when i run a pipeline opens a
    command prompt on windows"): the agent has no console of its own, so each run was given a new window, which anyone
    could close, ending the run halfway. Elsewhere nothing is needed."""
    return {"creationflags": CREATE_NO_WINDOW} if os.name == "nt" else {}


class Runs:
    """The agent's runs: each one's output in work/jenkins/runs/<id>.log, its end in <id>.json."""

    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def start(self, argv: list[str], by: str, run=subprocess.Popen) -> str:
        """One run started in the background: who asked in runs.log, its output in runs/<id>.log; its id."""
        rid = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + _random.token_hex(3)
        log = open(self.folder / f"{rid}.log", "w", encoding="utf-8")  # noqa: SIM115 - closed when the run ends
        env = {**os.environ, "EAX_NONINTERACTIVE": "1", "EAX_NO_BROWSER": "1", "EAX_RUN_BY": f"jenkins:{by}"}
        with open(self.folder.parent / "runs.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(UTC).isoformat()}\t{rid}\t{by}\t{' '.join(argv)}\n")
        p = run(command_line(argv), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                **no_window())

        def wait():
            code = p.wait()
            log.close()
            (self.folder / f"{rid}.json").write_text(json.dumps({"exit": code, "ended": datetime.now(UTC).isoformat()}),
                                                     encoding="utf-8")
        threading.Thread(target=wait, daemon=True).start()
        return rid

    def probe(self, argv: list[str], by: str, probe: str) -> str:
        """A probe from `eax test jenkins` (R9.13, D854): checked as a run is, recorded in runs.log with the probe's id,
        its output and end written at once; nothing is run."""
        rid = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + _random.token_hex(3)
        with self.lock, open(self.folder.parent / "runs.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(UTC).isoformat()}\t{rid}\t{by}\t{' '.join(argv)}\tprobe={probe}\n")
        (self.folder / f"{rid}.log").write_text(f"Probe {probe}: {shown(argv)} (checked, not run)\n", encoding="utf-8")
        (self.folder / f"{rid}.json").write_text(json.dumps({"exit": 0, "ended": datetime.now(UTC).isoformat(),
                                                             "probe": probe}), encoding="utf-8")
        return rid

    def read(self, rid: str, start: int = 0) -> dict:
        """A run's output from a byte onwards, and whether it ended and with what exit code."""
        if not rid.replace("-", "").replace("T", "").replace("Z", "").isalnum():
            raise C.Refused("No such run")
        log = self.folder / f"{rid}.log"
        if not log.exists():
            raise C.Refused("No such run")
        with open(log, encoding="utf-8", errors="replace") as f:
            f.seek(start)
            text = f.read()
        end = self.folder / f"{rid}.json"
        done = json.loads(end.read_text(encoding="utf-8")) if end.exists() else None
        return {"output": text, "next": start + len(text.encode("utf-8")), "done": done is not None,
                "exit": done["exit"] if done else None}


PROBE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def shown(argv: list[str]) -> str:
    """The command as a person reads it: eax <command> ..., or the DR tool's own name."""
    return " ".join(argv) if argv[0] in DR_TOOLS else " ".join(["eax", *argv])


def handle(body: dict, token: str, given: str, runs: Runs) -> tuple[int, dict]:
    """One request from Jenkins: the token, the pipeline, its fields, the typed name when it changes everything; then
    the run started (pure but for starting it). With a probe id (`eax test jenkins`, R9.13, D854) every check is the
    same, and the run is recorded but not started."""
    if not token or not hmac.compare_digest(given or "", token):
        return 401, {"message": "Not Jenkins: the agent's token does not match."}
    name = str(body.get("pipeline") or "")
    known = {p["name"]: p for p in pipelines()}
    if name not in known:
        return 404, {"message": f"No pipeline {name}."}
    values = {str(k): v for k, v in (body.get("values") or {}).items()}
    try:
        argv = argv_for(name, values)
    except C.Refused as exc:
        return 400, {"message": str(exc)}
    if known[name]["confirm"] or C.kind_of_argv(argv) in ("offline", "wipe"):
        if str(values.get("CONFIRM") or "").strip() != installation():
            return 403, {"message": f"This changes everything: type the installation's name ({installation()}) in CONFIRM."}
    by = str(body.get("by") or "?")[:80]
    probe = str(body.get("probe") or "")
    if probe:
        if not PROBE.match(probe):
            return 400, {"message": "A probe id is letters, digits, dots, dashes and underscores."}
        return 202, {"run": runs.probe(argv, by, probe), "command": shown(argv), "probe": probe}
    return 202, {"run": runs.start(argv, by), "command": shown(argv)}


def agent(port: int | None = None) -> int:
    """The agent, here, until stopped: POST /run {pipeline, values, by} and GET /runs/<id>?from= (the token in X-Eax-Token)."""
    token = setting("EAX_JENKINS_AGENT_TOKEN", "")
    if not token:
        raise Failure(f"No EAX_JENKINS_AGENT_TOKEN in the config file: {EAX} jenkins up makes one.")
    runs = Runs(WORK / "jenkins" / "runs")
    port = port or int(setting("EAX_JENKINS_AGENT_PORT", str(AGENT_PORT)))

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code: int, body: dict):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):  # noqa: N802
            if self.path != "/run":
                return self._send(404, {"message": "POST /run"})
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._send(400, {"message": "JSON, please"})
            code, out = handle(body, token, self.headers.get("X-Eax-Token", ""), runs)
            return self._send(code, out)

        def do_GET(self):  # noqa: N802
            if not hmac.compare_digest(self.headers.get("X-Eax-Token", ""), token):
                return self._send(401, {"message": "Not Jenkins."})
            if self.path == "/health":
                return self._send(200, {"ok": True, "installation": installation(), "probe": True})
            if self.path.startswith("/runs/"):
                rid, _, q = self.path[len("/runs/"):].partition("?from=")
                try:
                    return self._send(200, runs.read(rid, int(q or 0)))
                except (C.Refused, ValueError) as exc:
                    return self._send(404, {"message": str(exc)})
            return self._send(404, {"message": "GET /runs/<id>?from= or /health"})

    say(f"The Jenkins agent listens on port {port}: only the eax commands and DR tools of the catalogue, with the token.")
    (WORK / "jenkins").mkdir(parents=True, exist_ok=True)
    (WORK / "jenkins" / "agent.pid").write_text(str(os.getpid()), encoding="ascii")
    ThreadingHTTPServer((setting("EAX_JENKINS_AGENT_BIND", "0.0.0.0"), port), H).serve_forever()  # noqa: S104 - the token guards it
    return 0


# ---------------------------------------------------------------- the stack
def _secrets() -> dict[str, str]:
    """Jenkins' passwords and tokens, made in the config file the first time (the tokens never printed; its own
    account's password is printed by eax jenkins up, as the way in when Keycloak is down)."""
    from .secrets import dated_copy
    want = {"EAX_JENKINS_ADMIN_PASSWORD": 24, "EAX_JENKINS_AGENT_TOKEN": 40, "EAX_JENKINS_OIDC_SECRET": 32}
    text = ENV_FILE.read_text(encoding="utf-8")
    have = {k: setting(k, "") for k in want}
    missing = {k: _random.token_urlsafe(n) for k, n in want.items() if not have[k]}
    if missing:
        dated_copy(text)
        ENV_FILE.write_text(text.rstrip("\n") + "\n# Jenkins (R6.6-J1): made by eax jenkins up\n"
                            + "".join(f"{k}={v}\n" for k, v in missing.items()), encoding="utf-8", newline="\n")
    return {**have, **missing}


def project() -> str:
    """Jenkins' own Docker name: the installation's, with -jenkins (so a restore of EA Explorer never touches it)."""
    from .drill import project as eax_project
    return f"{eax_project()}-jenkins"


def _compose(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    from .core import write_config_env
    write_config_env()
    cmd = ["docker", "compose", "-p", project(), "--env-file", str(WORK / "config.env"), "-f", COMPOSE, *args]
    return subprocess.run(cmd, cwd=ROOT, env={**os.environ, **(env or {})}, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False)


def answering() -> bool:
    """Whether Jenkins answers on this machine (its sign-in page, or a sign-in asked for)."""
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{setting('EAX_JENKINS_PORT', '8088')}/login", timeout=5) as r:  # noqa: S310
            return r.status < 500
    except urllib.error.HTTPError as exc:
        return exc.code in (401, 403)
    except OSError:
        return False


def wait_answering(minutes: int = 8, sleep=time.sleep) -> bool:
    """Until Jenkins answers (the first start installs and loads its plugins), or it stopped, or too long."""
    end = time.time() + minutes * 60
    while time.time() < end:
        if answering():
            return True
        p = _compose(["ps", "-a", "--format", "{{.State}}", "jenkins"])
        if any(s in (p.stdout or "") for s in ("exited", "dead")):
            return False
        sleep(5)
    return False


def why_not_answering() -> str:
    """Why Jenkins does not answer, from the lines of its log that say it (the owner, 18 Nov 2026, 10:11: "Jenkins is not
    up, can you check what is blocking?"); the last 300 lines kept in work/jenkins/start.log."""
    p = _compose(["logs", "--tail", "300", "jenkins"])
    return why_not_started((p.stdout or "") + (p.stderr or ""))


def why_not_started(output: str) -> str:
    """Why Jenkins did not start, in the lines that say it (pure but for keeping the whole output): a plugin that needs a
    newer Jenkins or could not be downloaded, rather than the build's last lines (the owner, 18 Nov 2026, 09:21, saw only
    "jenkins-plugin-cli ... did not complete successfully"). The whole output kept in work/jenkins/start.log."""
    try:
        (WORK / "jenkins").mkdir(parents=True, exist_ok=True)
        (WORK / "jenkins" / "start.log").write_text(output, encoding="utf-8")
    except OSError:
        pass
    keys = ("requires", "required", "depends on", "newer version", "unable to", "failed to download", "could not",
            "error:", "exception", "no such plugin", "not found", "severe", "caused by", "invalid configuration",
            "unknown attribute", "no configurator")
    hits = [ln.strip() for ln in output.splitlines() if any(k in ln.lower() for k in keys)]
    said = "; ".join(dict.fromkeys(hits))[-900:] or output.strip()[-600:]
    return f"{said} (everything it said: work/jenkins/start.log)"


def keycloak_client(secret: str) -> str:
    """Jenkins' sign-in client in EA Explorer's Keycloak (made once, its secret kept in step): kcadm inside Keycloak."""
    from .core import compose_args
    realm = setting("EAX_KEYCLOAK_REALM", "eaexplorer")
    url = jenkins_url()
    script = ('set -e; K=/opt/keycloak/bin/kcadm.sh; '
              '$K config credentials --server http://localhost:8080/auth --realm master --user "$1" '
              '--password "$(cat /run/secrets/EAX_KC_ADMIN_PASSWORD)" >/dev/null; '
              'ID=$($K get clients -r "$2" -q clientId=jenkins --fields id --format csv --noquotes); '
              'if [ -z "$ID" ]; then $K create clients -r "$2" -s clientId=jenkins -s enabled=true -s protocol=openid-connect '
              '-s publicClient=false -s standardFlowEnabled=true -s "redirectUris=[\\"$3/*\\"]" >/dev/null; '
              'ID=$($K get clients -r "$2" -q clientId=jenkins --fields id --format csv --noquotes); fi; '
              '$K update "clients/$ID" -r "$2" -s "secret=$(cat)"; echo ok')
    p = subprocess.run(compose_args(["exec", "-T", "keycloak", "bash", "-c", script, "kc", setting("EAX_KC_ADMIN", "kcadmin"),
                                     realm, url]), cwd=ROOT, input=secret, capture_output=True, text=True, check=False)
    return "made" if p.returncode == 0 else f"not made ({(p.stderr or p.stdout).strip()[-200:]}): sign in with Jenkins' own account"


def jenkins_url() -> str:
    """Where people open Jenkins."""
    return f"http://{setting('EAX_HOSTNAME', 'localhost')}:{setting('EAX_JENKINS_PORT', '8088')}"


def _agent_running() -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{setting('EAX_JENKINS_AGENT_PORT', str(AGENT_PORT))}/health",
                                     headers={"X-Eax-Token": setting("EAX_JENKINS_AGENT_TOKEN", "")})
        with urllib.request.urlopen(req, timeout=3) as r:  # noqa: S310 - this machine
            return r.status == 200
    except OSError:
        return False


def start_agent() -> None:
    """The agent in the background, on its own (it outlives this window), its output in work/logs."""
    if _agent_running():
        return
    log = open(WORK / "logs" / f"eax-{time.strftime('%Y%m%d-%H%M%S')}-jenkins-agent.log", "a", encoding="utf-8")  # noqa: SIM115
    kw: dict = {"start_new_session": True} if os.name != "nt" else {"creationflags": 0x00000008 | 0x00000200 | CREATE_NO_WINDOW}
    subprocess.Popen([sys.executable, str(ROOT / "eaxpy.py"), "jenkins", "agent"], cwd=ROOT, stdout=log,  # noqa: S603
                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)


def stop_agent(wait: float = 5.0) -> str:
    """The agent on this machine stopped (eax jenkins down, and eax cleanup before it empties work/: the owner's
    clean-restart, 18 Nov 2026, 09:49, stopped at "The process cannot access the file
    'eax-...-jenkins-agent.log' because it is being used by another process"). Only the process the pid file names, and
    only while the agent answers with this installation's token, so no other process is ever stopped."""
    pid_file = WORK / "jenkins" / "agent.pid"
    if not pid_file.exists():
        return "No agent was running."
    try:
        pid = int(pid_file.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        pid_file.unlink(missing_ok=True)
        return "No agent was running."
    said = "No agent was running."
    if _agent_running():
        try:
            os.kill(pid, 15)                          # TerminateProcess on Windows
            said = "The Jenkins agent stopped."
        except OSError as exc:
            said = f"The Jenkins agent could not be stopped: {exc}"
        end = time.time() + wait
        while time.time() < end and _agent_running():
            time.sleep(0.5)
        time.sleep(1)                                 # its log file let go
    pid_file.unlink(missing_ok=True)
    return said


def main(argv: list[str]) -> int:
    """eax jenkins up | down | status | pipelines | agent | stop-agent."""
    action = argv[0] if argv else "status"
    if action == "agent":
        return agent()
    if not ENV_FILE.exists():
        raise Failure(f"No config file yet: run {EAX} init first.")
    if action == "pipelines":
        say(f"{len(pipelines())} pipelines written to {write_pipelines()}.")
        return 0
    if action == "up":
        sec = _secrets()
        path = write_pipelines()
        say(f"Starting Jenkins ({project()}): its own stack, kept apart from EA Explorer's.")
        keycloak = setting("EAX_JENKINS_SIGNIN", "own").lower() == "keycloak"
        p = _compose(["up", "-d", "--build"], env={**sec, "EAX_JENKINS_CASC": "casc-keycloak.yaml" if keycloak else "casc.yaml"})
        if p.returncode:
            raise Failure(f"Jenkins did not start: {why_not_started((p.stdout or '') + (p.stderr or ''))}")
        if keycloak:
            say(f"  sign-in through Keycloak: {keycloak_client(sec['EAX_JENKINS_OIDC_SECRET'])}")
        start_agent()
        say("  waiting for Jenkins to answer (the first start installs its plugins: a few minutes)")
        if not wait_answering():
            raise Failure(f"Jenkins started but does not answer at {jenkins_url()}: {why_not_answering()}")
        say(f"  the agent: {'running' if _agent_running() or time.sleep(3) or _agent_running() else 'starting (eax jenkins status)'}")
        say(f"Jenkins: {jenkins_url()}  ({len(pipelines())} pipelines from {path.name}: every command in eax, the admin tasks "
            "in eax-admin)." + (" Super Admins and IT Admins sign in with EA Explorer." if keycloak else ""))
        # Jenkins' own account, printed here (the owner, 18 Nov 2026, 10:03: "Can we print jenkings break glass password
        # when we start jenkins"); it is in the config file in any case
        say(f"Jenkins' own account{' (when Keycloak is down)' if keycloak else ''}: {setting('EAX_JENKINS_ADMIN', 'jenkins-admin')}"
            f"  password: {sec.get('EAX_JENKINS_ADMIN_PASSWORD') or setting('EAX_JENKINS_ADMIN_PASSWORD', '')}", "yellow")
        return 0
    if action == "stop-agent":
        say(stop_agent())
        return 0
    if action == "down":
        p = _compose(["down"])
        stop_agent()
        say("Jenkins and the agent stopped; Jenkins' data is kept." if p.returncode == 0 else (p.stderr or p.stdout))
        return p.returncode
    if action == "status":
        p = _compose(["ps", "--status", "running", "--services"])
        up = "jenkins" in (p.stdout or "").split()
        answers = up and answering()
        say(f"Jenkins: {('answering at ' + jenkins_url()) if answers else ('started but not answering: ' + why_not_answering()) if up else 'not running (eax jenkins up)'}")
        say(f"The agent: {'running' if _agent_running() else 'not running (eax jenkins up starts it)'}")
        say(f"Pipelines: {len(pipelines())} (one per eax command and DR tool)")
        return 0
    raise Failure(f"{EAX} jenkins up|down|status|pipelines|agent|stop-agent")
