"""eax setup: the guides, guided (Release 6.6, R6.6, D750; owner, 15 Nov 2026, 21:11 to 21:14, and 17 Nov 2026, 19:42 to
19:50: "each guide is guided three ways": a Setup page in System Admin, `eax setup <guide>` here, and a Jenkins
pipeline).

  eax setup                       the guides, with what each is for
  eax setup <guide>               the guide, one step at a time: what to do, the command (run it now, skip it or stop),
                                  a check that it worked where one can be made, and the section of the written guide
  eax setup <guide> --yes         every step's command run in turn without asking (Jenkins; a step that changes
                                  everything still needs --confirm <installation name>)
  eax setup external-db --host H [--port 5432] [--admin-user eax_admin]   the customer's own database server (R6.6.2)

The written guides are docs/guides/<guide>.md in the repository (to read, print or download); GUIDES below is the
same list for the console, the Setup page (through the operations helper, which reads this file) and Jenkins.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

from .core import EAX, ENV_FILE, ROOT, Failure, say, setting

# (id, title, what it is for, steps); a step: (title, what to do and what to expect, the eax command or "", a check or "")
GUIDES: list[dict] = [
    {"id": "laptop", "title": "A laptop", "for": "EA Explorer on your own computer, to try it or to work alone",
     "steps": [("Docker runs", "Docker Desktop installed and started; at least 16 GB of memory.", "check", "docker"),
               ("The config file", "Answers laptop and password (or certificate).", "init laptop --password", "config"),
               ("Start", "The core first (a few minutes), the rest in the background.", "up", "running"),
               ("Trust the certificate", "The browser stops warning about the laptop's own certificate.", "trust", ""),
               ("Check it", "The smoke test: every role signs in, every area answers.", "test smoke", ""),
               ("Sign in", "https://localhost: the logins are printed by eax logins.", "logins", "")]},
    {"id": "server", "title": "A server", "for": "EA Explorer for a team, on a Linux server with Docker",
     "steps": [("Docker runs", "Docker Engine and the compose plugin on the server.", "check", "docker"),
               ("The config file", "Server mode: strong passwords made; certificates chosen by default; the name people open (<HOSTNAME>), with DNS records for it, reports.<HOSTNAME> and docs.<HOSTNAME>.", "init server --certificate --hostname <HOSTNAME>", "config"),
               ("The organisation's certificate", "Covering <HOSTNAME>, reports.<HOSTNAME> and docs.<HOSTNAME>, from files on this machine: checked, then used at once (or upload it on System Admin > Secrets after the start; guide: certificates).", "certs front install --cert <CERT_FILE> --key <KEY_FILE>", ""),
               ("Start", "The core, then the rest.", "up --wait-all", "running"),
               ("Backups", "The nightly backup and where it goes (guide: backups).", "backups", ""),
               ("Check it", "The full test, once.", "test full", "")]},
    {"id": "remote", "title": "Any server over SSH", "for": "EA Explorer put on another machine from this one (no cloud-specific code, D746)",
     "steps": [("The plan", "Which machine, how to reach it, laptop or server: the wizard asks.", "deploy --console --plan", ""),
               ("Deploy", "The code, the config file and the start, over SSH.", "deploy --console --yes", ""),
               ("It appears in the site picker", "Sites > the new site, green within five minutes.", "", "")]},
    {"id": "new-machine", "title": "A new machine", "for": "A machine made ready for EA Explorer: Docker, disk, folders, network",
     "steps": [("Docker", "Docker installed; at least 16 GB of memory and 100 GB of disk for a server.", "check", "docker"),
               ("Folders", "Where data, backups and logs live (EAX_DATA_DIR, EAX_BACKUP_DIR, EAX_LOGS_DIR).", "folders", ""),
               ("Network", "Port 443 open to people; nothing else needs to be.", "", ""),
               ("Then", "The laptop or server guide.", "", "")]},
    {"id": "backups", "title": "Backups", "for": "What is backed up, when, where to keep it, and checking it works",
     "steps": [("A backup now", "Every database, the files, the config file; <TAG> names it.", "backup <TAG>", ""),
               ("The list", "Newest first, with its size and whether it was checked.", "backups", ""),
               ("Check one restores", "A trial restore into scratch copies: nothing live touched.", "verify", ""),
               ("Off this machine", "A DR pack in <PACK>, to keep elsewhere (guide: DR site).", "dr-pack <PACK>", ""),
               ("The backup and restore test", "Made, backed up, removed, restored, compared.", "test backup-restore", "")]},
    {"id": "restores", "title": "Restores", "for": "A model, a project, a part or everything put back",
     "steps": [("A model", "Model Admin > the model > Backups > Restore (over itself or as a new model).", "", ""),
               ("A project", "The project's About tab > Back up and restore.", "", ""),
               ("A part", "Backups > a backup > Restore > the databases, the files or the config (<BACKUP>: a backup's name, or latest).", "restore <BACKUP> --what db", ""),
               ("Everything", "Backups > a backup > Restore > everything: EA Explorer is read only meanwhile.", "restore <BACKUP> --what full", ""),
               ("Check it", "The integrity check runs by itself after every restore (guide: database checks).", "db integrity", "")]},
    {"id": "catastrophe", "title": "A catastrophic failure", "for": "The machine or its data is lost: what to do first, who to tell, what to check",
     "steps": [("Stop and look", "What is lost: the machine, the disk, the data, or only EA Explorer.", "status", ""),
               ("Tell people", "The banner (System Admin > Banner) and the people who rely on it.", "", ""),
               ("The newest good backup", "On this machine, the share, or a DR pack kept elsewhere.", "backups", ""),
               ("A DR site?", "If there is one, switch to it (guide: switch to DR).", "", ""),
               ("Otherwise rebuild", "On a new machine from the backup (guide: rebuild).", "", "")]},
    {"id": "rebuild", "title": "Building an environment from a backup", "for": "A new machine made from a backup or a DR pack, nothing lost",
     "steps": [("The pack", "A DR pack (eax dr-pack) or a backup folder, with its env file.", "", ""),
               ("Docker on the new machine", "The new machine guide.", "check", "docker"),
               ("Build and restore", "On the new machine, from the pack in <PACK> into <INSTALL>: the code, the config, the restore, compared.", "dr:eax-dr --pack <PACK> --install <INSTALL>", ""),
               ("Check it", "The integrity check and the key items.", "db integrity", "")]},
    {"id": "dr-site", "title": "A DR site", "for": "A second site kept up to date, ready to take over",
     "steps": [("The DR site", "A server (the server guide) with the same release.", "", ""),
               ("A pairing key on the DR site", "System Admin > Site pairings > Make a key.", "", ""),
               ("Pair from the primary", "System Admin > Site pairings > Pair with a site: DR sync.", "", ""),
               ("Accept on the DR site", "It becomes read only, kept up to date every few minutes.", "", ""),
               ("Rehearse", "The restore drill, now and then.", "", "")]},
    {"id": "switch-to-dr", "title": "Switching to DR and back", "for": "The DR site takes over; later the primary comes back",
     "steps": [("Take over", "On the DR site: System Admin > Site pairings > the DR pairing > Stop and take over.", "", ""),
               ("Point people at it", "The address people open (DNS) moved to the DR site.", "", ""),
               ("Check it", "The integrity check runs by itself when it takes over.", "db integrity", ""),
               ("Fail back", "Pair the other way (the DR site sends), then switch back the same way.", "", "")]},
    {"id": "pairings", "title": "Sync and DR pairings", "for": "Content sync or DR sync between two sites",
     "steps": [("A key on the receiving site", "System Admin > Site pairings > Make a key: shown once.", "", ""),
               ("Pair from the sending site", "Its address, the key, content or DR; by hand or by itself.", "", ""),
               ("Accept", "On the receiving site: commit by hand (look first) or by itself.", "", ""),
               ("Sync now", "On the sending site; the batches show what arrived and what was committed.", "", "")]},
    {"id": "upgrades", "title": "Upgrades and rollbacks", "for": "A new release put in, and taken back out if needed",
     "steps": [("What is new", "The releases and their notes.", "update --list", ""),
               ("A backup first", "Taken by the update itself too.", "backup", ""),
               ("Update", "To the newest release of your channel, or a named one.", "update", ""),
               ("Check it", "The smoke test.", "test smoke", ""),
               ("Roll back if needed", "The release before, with its data as it was.", "rollback", "")]},
    {"id": "move", "title": "Moving to a new machine", "for": "A laptop to a server, or one server to another, nothing lost",
     "steps": [("A DR pack on the old machine", "Everything in one folder (<PACK>), checked; copy it to the new machine.", "dr-pack <PACK>", ""),
               ("The new machine", "The new machine guide.", "", ""),
               ("Build from the pack", "On the new machine, from <PACK> into <INSTALL>.", "dr:eax-dr --pack <PACK> --install <INSTALL>", ""),
               ("Point people at it", "The address moved; the old machine stopped.", "", "")]},
    {"id": "security", "title": "Security hardening", "for": "A checklist for a security review",
     "steps": [("Certificate mode", "The services sign in with certificates.", "certs", ""),
               ("Multi-factor sign-in", "System Admin > Security: admins or everyone.", "", ""),
               ("IP allow-listing", "System Admin > Security > Allowed addresses, or from the machine: <ADDRESS> let in to the site.", "allow add site <ADDRESS>", ""),
               ("Secrets", "Every password's age; rotation every 90 days.", "secrets show", ""),
               ("The front door's certificate", "The organisation's own (guide: certificates).", "", ""),
               ("The security test", "Scans and attacks.", "test security", "")]},
    {"id": "forgotten", "title": "A forgotten password or certificate", "for": "Getting back in",
     "steps": [("A person's password", "Keycloak's Forgot password, or a Keycloak Admin sets one.", "", ""),
               ("An administrator locked out", "<USER> gets a temporary password, shown once (changed at the next sign-in).", "access reset-password <USER>", ""),
               ("Keycloak is down", "The break-glass account (EAX_BREAK_GLASS_PASSWORD).", "", ""),
               ("A service's password", "eax secrets rotate <KEY> sets a new one everywhere it is used.", "secrets show", ""),
               ("A certificate", "eax certs renew --force makes them all again.", "certs renew --force", ""),
               ("Everything else", "On the machine, the database answers without a network login: eax psql.", "", "")]},
    {"id": "external-db", "title": "Your own database server", "for": "EA Explorer on a PostgreSQL server your DBA manages (R6.6.2)",
     "steps": [("Your DBA prepares the server", "deploy/external-db/prepare.sql: the databases, the logins, their rights.", "", ""),
               ("Point EA Explorer at it", "<DB_HOST>, port <DB_PORT>: tested before it is saved.", "setup external-db --host <DB_HOST> --port <DB_PORT>", "external_db"),
               ("Start", "The db container passes connections through; nothing else changes.", "restart", "running"),
               ("Backups still run", "EA Explorer's own backups, over the network; your DBA's on top.", "backup", "")]},
    {"id": "certificates", "title": "Real certificates", "for": "The front door's certificate: your organisation's, uploaded",
     "steps": [("Ask for one", "Covering <HOSTNAME>, reports.<HOSTNAME> and docs.<HOSTNAME>; with its private key (no password) and the chain.", "", ""),
               ("Put it in", "From files on this machine (or upload it on System Admin > Secrets > Front door certificate): checked, used at once, no restart, the one before kept.", "certs front install --cert <CERT_FILE> --key <KEY_FILE> --chain <CHAIN_FILE>", ""),
               ("Check it", "The names it covers, who issued it, when it ends; undo puts the one before back.", "certs front", ""),
               ("Expiry", "Alerts 30 days before and on the day.", "", ""),
               ("Laptops trust your authority", "Company laptops trust your organisation's authority already, or IT adds it.", "", "")]},
    {"id": "jenkins", "title": "Jenkins", "for": "A pipeline per eax command and DR tool, a click away (R6.6-J1)",
     "steps": [("Start it", "Its own stack, the agent on this machine, the pipelines written.", "jenkins up", ""),
               ("Sign in", "With EA Explorer (Super or IT Admin), or Jenkins' own account when Keycloak is down.", "jenkins status", ""),
               ("Run a pipeline", "eax > a command > Build with parameters; those that change everything ask for the installation's name.", "", "")]},
    {"id": "db-checks", "title": "Database checks", "for": "Integrity and recent records, weekly and after restores (R6.6.1)",
     "steps": [("Check now", "Every database: indexes, tables, constraints, sequences, the newest records.", "db integrity", ""),
               ("Safe fixes", "Made by themselves after a backup; the admins are told.", "", ""),
               ("Orphan rows", "Database maintenance > Integrity > Preview the repair (Super Admins).", "", "")]},
]
# the values a guide's commands need (the owner, 18 Nov 2026, 12:29: "put in paramters like server name location of key
# file and so on and we get the dynamic set of commands"): <KEY> in a step is filled in on the Setup page, by eax setup
# <guide> --set KEY=VALUE, and shown as it is in the written guide. key: (what it is, an example)
PARAMS: dict[str, tuple[str, str]] = {
    "HOSTNAME": ("The name people open EA Explorer at", "ea.example.org"),
    "CERT_FILE": ("The certificate file (PEM)", "C:/certs/ea.crt"),
    "KEY_FILE": ("Its private key file (PEM, no password)", "C:/certs/ea.key"),
    "CHAIN_FILE": ("The chain file (the issuers' certificates)", "C:/certs/chain.crt"),
    "TAG": ("A word to name the backup", "before-upgrade"),
    "BACKUP": ("A backup's name, or latest", "latest"),
    "PACK": ("The folder for the DR pack", "D:/dr-packs"),
    "INSTALL": ("The folder EA Explorer is put in on the new machine", "C:/EA-Explorer"),
    "ADDRESS": ("An address or range to let in", "10.20.0.0/16"),
    "USER": ("The administrator's user name", "eaadmin"),
    "DB_HOST": ("Your database server's name", "db.example.org"),
    "DB_PORT": ("Its port", "5432"),
}
OPTIONAL = {"CHAIN_FILE", "TAG"}       # left empty: the option and its value are left out of the command
_PLACE = re.compile(r"<([A-Z][A-Z_]*)>")


def params_of(g: dict) -> list[str]:
    """The values a guide needs, in the order its steps use them (pure)."""
    seen: list[str] = []
    for title, said, command, _chk in g["steps"]:
        for k in _PLACE.findall(" ".join((title, said, command))):
            if k in PARAMS and k not in seen:
                seen.append(k)
    return seen


def fill(text: str, values: dict, command: bool = False) -> str:
    """<KEY> replaced by its value where one is given; the rest left as <KEY>. In a command an optional value left empty
    takes its option with it (--chain <CHAIN_FILE> gone) (pure)."""
    if command:
        for k in OPTIONAL:
            if not str(values.get(k) or "").strip():
                text = re.sub(rf"\s+(--[a-z-]+\s+)?<{k}>", "", text)
    return _PLACE.sub(lambda m: str(values[m.group(1)]).strip() if str(values.get(m.group(1)) or "").strip() else m.group(0), text)


def unfilled(text: str) -> list[str]:
    """The values still to give (pure)."""
    return [k for k in _PLACE.findall(text) if k in PARAMS]


def shown(command: str) -> str:
    """A step's command as people type it: eax ..., or a DR tool (dr:eax-dr ...) as dr/eax-dr (pure)."""
    return f"dr/{command[3:]}" if command.startswith("dr:") else f"{EAX} {command}"


def markdown(gid: str) -> str:
    """The written guide, docs/guides/<guide>.md, made from GUIDES (a test keeps the files the same)."""
    g = BY_ID[gid]
    lines = [f"# {g['title']}", "", f"{g['for']}.", "",
             f"On screen: System Admin > Setup > {g['title']}, where you fill in your values and get every command ready to "
             f"copy. On the machine: `eax setup {gid}`" + (" with `--set KEY=VALUE` for each value" if params_of(g) else "")
             + ". In Jenkins: the `setup` pipeline with `" + gid + "`.", ""]
    if params_of(g):
        lines += ["## Your values", "", "| Value | What it is | For example |", "|---|---|---|"]
        lines += [f"| `<{k}>` | {PARAMS[k][0]}{' (may be left out)' if k in OPTIONAL else ''} | `{PARAMS[k][1]}` |"
                  for k in params_of(g)]
        lines += [""]
    lines += ["## Steps", ""]
    for i, (title, said, command, _chk) in enumerate(g["steps"], 1):
        lines += [f"### {i}. {title}", "", _PLACE.sub(lambda m: f"`{m.group(0)}`", said), ""]
        if command:
            lines += ["Windows (PowerShell):", "", "```", windows(command), "```", "", "Linux or macOS:", "", "```",
                      unix(command), "```", ""]
    return "\n".join(lines).rstrip() + "\n"


def windows(command: str) -> str:
    """The command as typed in PowerShell (pure)."""
    if command.startswith("dr:"):
        tool, *args = command[3:].split()
        return " ".join([f".\\dr\\{tool}.ps1", *[_ps_flag(a) for a in args]])
    return f".\\eax {command}"


def unix(command: str) -> str:
    """The command as typed in a Linux or macOS shell (pure)."""
    if command.startswith("dr:"):
        tool, *args = command[3:].split()
        return " ".join([f"./dr/{tool}.sh", *args])
    return f"./eax.sh {command}"


def _ps_flag(a: str) -> str:
    """--pack becomes -Pack, as the PowerShell DR tools take it (eaxcli/jenkins.py does the same)."""
    return "-" + "".join(w.capitalize() for w in a[2:].split("-")) if a.startswith("--") else a


BY_ID = {g["id"]: g for g in GUIDES}
CHANGES_EVERYTHING = ("restore ", "update", "rollback", "clean-", "cleanup")


def listing() -> list[dict]:
    """The guides with their steps and the values they need, for the Setup page and Jenkins (pure)."""
    return [{"id": g["id"], "title": g["title"], "for": g["for"], "doc": f"docs/guides/{g['id']}.md",
             "params": [{"key": k, "label": PARAMS[k][0], "example": PARAMS[k][1], "optional": k in OPTIONAL}
                        for k in params_of(g)],
             "steps": [{"title": t, "say": s, "command": c, "check": k,
                        "windows": windows(c) if c else "", "unix": unix(c) if c else ""} for t, s, c, k in g["steps"]]}
            for g in GUIDES]


# ---------------------------------------------------------------- checks that a step worked (on this machine)
def check(name: str) -> tuple[bool, str]:
    """A step's check: whether it worked, in words."""
    if name == "docker":
        p = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, check=False)
        return (p.returncode == 0, f"Docker {p.stdout.strip()}" if p.returncode == 0 else "Docker does not answer: start it")
    if name == "config":
        return (ENV_FILE.exists(), "the config file is there" if ENV_FILE.exists() else f"no config file: {EAX} init")
    if name == "running":
        from .core import compose_args
        p = subprocess.run(compose_args(["ps", "--status", "running", "--services"]), cwd=ROOT, capture_output=True, text=True,
                           check=False)
        up = "api" in (p.stdout or "").split()
        return up, "EA Explorer runs" if up else f"not running: {EAX} up"
    if name == "external_db":
        host = setting("EAX_EXTERNAL_DB_HOST", "")
        return (bool(host), f"pointed at {host}" if host else "not set yet")
    return True, ""


# ---------------------------------------------------------------- the customer's own database server (R6.6.2)
DB_KEYS = [("admin_pw", "EAX_DB_SUPERUSER_PASSWORD"), ("app_pw", "EAX_DB_PASSWORD"), ("report_pw", "EAX_DB_REPORT_PASSWORD"),
           ("migrator_pw", "EAX_DB_MIGRATOR_PASSWORD"), ("keycloak_pw", "EAX_KEYCLOAK_DB_PASSWORD"),
           ("superset_pw", "EAX_SUPERSET_DB_PASSWORD"), ("mayan_pw", "EAX_MAYAN_DB_PASSWORD"), ("library_pw", "EAX_LIBRARY_DB_PASSWORD"),
           ("views_pw", "EAX_VIEWS_DB_PASSWORD"), ("console_it_pw", "EAX_CONSOLE_IT_PASSWORD"),
           ("console_super_pw", "EAX_CONSOLE_SUPER_PASSWORD")]


def test_connection(host: str, port: str, user: str, password: str, run=subprocess.run) -> tuple[bool, str]:
    """The customer's server reached and signed in to, from a throw-away PostgreSQL container (no client needed here)."""
    image = setting("EAX_IMAGE_POSTGRES", "postgres:17-alpine")
    p = run(["docker", "run", "--rm", "-e", "PGPASSWORD", image, "psql", "-h", host, "-p", port, "-U", user, "-d", "eaexplorer",
             "-tAc", "SELECT current_user || ' on PostgreSQL ' || current_setting('server_version')"],
            env={**os.environ, "PGPASSWORD": password}, capture_output=True, text=True, check=False)
    return (p.returncode == 0, (p.stdout or p.stderr or "").strip()[-300:])


def external_db(host: str, port: str = "5432", user: str = "eax_admin", run=subprocess.run) -> str:
    """Points EA Explorer at the customer's server: tested first, then EAX_EXTERNAL_DB_HOST/PORT, EAX_DB_ADMIN_USER and
    external-db in EAX_COMPOSE_EXTRA written (a dated copy first). The passwords stay those of the config file: the
    DBA's script takes the same ones."""
    from .secrets import dated_copy, replace_values
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host or "") or not port.isdigit():
        raise Failure("--host is the server's name or address, --port its port.")
    ok, said = test_connection(host, port, user, setting("EAX_DB_SUPERUSER_PASSWORD", ""), run=run)
    if not ok:
        raise Failure(f"{host}:{port} could not be signed in to as {user}: {said}. Has the DBA run deploy/external-db/prepare.sql "
                      "with the passwords of the config file (eax setup external-db --dba shows which)?")
    text = ENV_FILE.read_text(encoding="utf-8")
    dated_copy(text)
    extra = [x for x in setting("EAX_COMPOSE_EXTRA", "").replace(",", " ").split() if x]
    if "external-db" not in extra:
        extra.append("external-db")
    new = {"EAX_EXTERNAL_DB_HOST": host, "EAX_EXTERNAL_DB_PORT": port, "EAX_DB_ADMIN_USER": user,
           "EAX_COMPOSE_EXTRA": ",".join(extra)}
    out, _ = replace_values(text, new)
    for k, v in new.items():
        if not re.search(rf"^{k}=", out, re.MULTILINE):
            out = out.rstrip("\n") + f"\n{k}={v}\n"
    ENV_FILE.write_text(out, encoding="utf-8", newline="\n")
    return f"{said}. Saved: EA Explorer uses {host}:{port}; {EAX} restart to use it."


def dba_command() -> str:
    """The psql command the DBA runs, with the variable names (the values are the config file's; shown, not printed)."""
    return ("psql -h <server> -U <admin> -d postgres -v ON_ERROR_STOP=1 "
            + " ".join(f"-v {v}='<{k} from work/eaexplorer.env>'" for v, k in DB_KEYS) + " -f deploy/external-db/prepare.sql")


# ---------------------------------------------------------------- the console
def _ask(prompt: str) -> str:
    if os.environ.get("EAX_NONINTERACTIVE") or not sys.stdin.isatty():
        return "y"
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "q"


def run_eax(command: str) -> int:
    """One eax command, in this window, through eaxpy (the same on every machine)."""
    return subprocess.run([sys.executable, str(ROOT / "eaxpy.py"), *command.split()], cwd=ROOT, check=False).returncode


def walk(gid: str, yes: bool = False, confirm: str = "", run=run_eax, out=say, values: dict | None = None) -> int:
    """A guide, one step at a time (see the module); values fill its <KEY>s (eax setup <guide> --set KEY=VALUE)."""
    g = BY_ID[gid]
    values = values or {}
    out(f"\n{g['title']}: {g['for']}. The written guide: docs/guides/{gid}.md\n")
    for i, (title, said, command, chk) in enumerate(g["steps"], 1):
        out(f"Step {i} of {len(g['steps'])}: {title}\n  {fill(said, values)}")
        command = fill(command, values, command=True)
        if command and (unfilled(command) or command.startswith("dr:")):
            out(f"  {shown(command)}")
            out(f"  not run here: give {', '.join(f'--set {k}=...' for k in unfilled(command))}" if unfilled(command)
                else "  not run here: on the machine it is for, as shown")
            command = ""
        elif command:
            out(f"  {EAX} {command}")
            risky = command.startswith(CHANGES_EVERYTHING)
            if yes and risky and confirm != (setting("EAX_INSTALLATION_NAME", "") or setting("EAX_HOSTNAME", "localhost")):
                out("  not run: it changes everything; give --confirm <installation name> to run it here")
            else:
                a = "y" if yes else _ask("  Run it now? [y]es, [s]kip, [q]uit: ")
                if a.startswith("q"):
                    return 1
                if a.startswith("y"):
                    code = run(command)
                    out(f"  {'done' if code == 0 else f'it ended with {code}: see above, then {EAX} setup {gid} again'}")
                    if code != 0 and yes:
                        return code
        elif not yes:
            if _ask("  Done? [y]es (go on), [q]uit: ").startswith("q"):
                return 1
        if chk:
            ok, words = check(chk)
            out(f"  check: {'ok' if ok else 'NOT YET'}{': ' + words if words else ''}")
    out(f"\n{g['title']}: every step done.")
    return 0


def main(argv: list[str]) -> int:
    """eax setup [guide] [--yes] [--confirm NAME] | eax setup external-db --host H [--port P] [--admin-user U] | --dba."""
    if not argv:
        say("The guides (eax setup <guide>; the same on System Admin > Setup and in Jenkins):")
        for g in GUIDES:
            say(f"  {g['id']:<14} {g['title']}: {g['for']}")
        return 0
    gid, rest = argv[0], argv[1:]
    opt = lambda k, d="": rest[rest.index(k) + 1] if k in rest and rest.index(k) + 1 < len(rest) else d  # noqa: E731
    if gid == "external-db" and "--dba" in rest:
        say(f"Your DBA runs, on a machine that reaches the server:\n  {dba_command()}")
        return 0
    if gid == "external-db" and "--host" in rest:
        say(external_db(opt("--host"), opt("--port", "5432"), opt("--admin-user", "eax_admin")))
        return 0
    if gid not in BY_ID:
        raise Failure(f"No guide {gid}: {EAX} setup lists them.")
    values = dict(rest[i + 1].split("=", 1) for i, a in enumerate(rest) if a == "--set" and i + 1 < len(rest) and "=" in rest[i + 1])
    bad = [k for k in values if k not in PARAMS]
    if bad:
        raise Failure(f"No value called {', '.join(bad)}: {', '.join(params_of(BY_ID[gid])) or 'this guide needs none'}.")
    return walk(gid, yes="--yes" in rest, confirm=opt("--confirm"), values=values)
