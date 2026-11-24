"""eax deploy (phase 36, D498, D500 to D506): a deployment wizard, in the console or in a local web page, with the same
questions and steps in both.

Where to deploy (D416, D457; no platform-specific code, D746: a machine in any cloud is a server reached over SSH):
  laptop        this computer, Docker Desktop
  server        a Linux server, run on the server itself or from here over SSH; Docker is installed if it is missing

The wizard asks its questions (QUESTIONS, shown only when they apply), makes the steps for the answers (steps_for) and
runs them one by one. Every step is logged (work/logs/eax-<time>-deploy.log, passwords masked). A step that fails
stops and asks: Retry, Back (to the answers, kept) or Quit. --plan prints every step and every command it would run,
and runs nothing.

Command line: eax deploy [--console|--web] [--kind K] [--answers file.json] [--set key=value ...] [--plan] [--yes]
"""

from __future__ import annotations

import json
import os
import re
import secrets as _secrets
import shlex
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import releases as R
from .core import EAX, ROOT, WINDOWS, WORK, Failure, log_only, say

KINDS = {
    "laptop": "This computer (a laptop or desktop with Docker Desktop)",
    "server": "A Linux server (one you have: this one, or one reached over SSH)",
}
INSTALL_FILE = WORK / "install.json"            # written by the installer: where this copy came from (D502)
SECRET_KEYS = ("first_admin_password",)


# ---------------------------------------------------------------- the questions
@dataclass
class Question:
    """One question of the deployment wizard, with its default, choices and help."""
    key: str
    text: str
    default: str | Callable[[dict], str] = ""
    choices: dict[str, str] | None = None
    when: Callable[[dict], bool] = lambda a: True
    help: str = ""
    secret: bool = False
    required: bool = True
    options: Callable[[dict], dict[str, str]] | None = None   # choices read when asked (the published releases, R5.6)

    def default_for(self, answers: dict) -> str:
        """The question's default for the answers so far."""
        return self.default(answers) if callable(self.default) else self.default

    def choices_for(self, answers: dict) -> dict[str, str] | None:
        """The question's choices: fixed, or read now (a drop-down)."""
        return self.options(answers) if self.options else self.choices

    def as_dict(self, answers: dict) -> dict:
        """The question for the web wizard (choices read now are filled in by the page's own service)."""
        return {"key": self.key, "text": self.text, "default": self.default_for(answers), "choices": self.choices,
                "help": self.help, "secret": self.secret, "required": self.required,
                "kind": "select" if self.options else ""}



# where files are put on the server before they go into place: a folder in the signed-in user's home only they may open
STAGE = ".eaexplorer-stage"
STAGE_SH = f'"$HOME/{STAGE}"'

def _installed() -> dict:
    try:
        return json.loads(INSTALL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ssh_key_default(_a: dict) -> str:
    home = Path.home() / ".ssh"
    for name in ("id_ed25519", "id_rsa", "id_ecdsa"):
        if (home / name).exists():
            return str(home / name)
    return str(home / "id_ed25519")


def _remote(a: dict) -> bool:
    """The installation is on another machine, reached over SSH."""
    return a.get("kind") == "server" and a.get("where") == "ssh"


def _server_like(a: dict) -> bool:
    return a.get("kind") == "server"


QUESTIONS: list[Question] = [
    Question("kind", "Where do you want EA Explorer?", "laptop", KINDS),
    Question("where", "Run on this server, or set up another server from here over SSH?", "here",
             {"here": "This machine is the server (Linux)", "ssh": "Another server, reached over SSH from here"},
             when=lambda a: a.get("kind") == "server"),
    # --- SSH
    Question("ssh_target", "The server to set up, as user@address", "", when=_remote,
             help="A user who may use sudo, e.g. ubuntu@203.0.113.10"),
    Question("ssh_key", "SSH private key to sign in with", _ssh_key_default, when=_remote,
             help="The key whose public half the server already has."),
    Question("ssh_port", "SSH port", "22", when=_remote),
    # --- the installation
    Question("hostname", "The address people will open (a DNS name)", lambda a: "ea.example.org", when=_server_like,
             help="https://<this>; reports.<this> and docs.<this> are used too: three DNS names pointing at the server."),
    Question("org_name", "Your organisation's name", "My organisation", when=_server_like),
    Question("admin_email", "The first EA Explorer administrator's email", lambda a: f"eaadmin@{a.get('hostname', 'example.org')}",
             when=_server_like),
    Question("tls", "Certificate", "self-signed",
             {"self-signed": "A self-signed certificate made at the first start (browsers warn until it is trusted)",
              "own": "My organisation's certificate (a folder here with tls.crt and tls.key)"}, when=_server_like),
    Question("tls_dir", "Folder (on this computer) holding tls.crt and tls.key", "", when=lambda a: _server_like(a) and a.get("tls") == "own"),
    Question("install_dir", "Installation folder on the server", "/opt/eaexplorer", when=_server_like),
    Question("data_dir", "Base folder for all the data on the server (databases, documents, logs, backups, imports, exports, certificates, reports)", "/srv/eax", when=_server_like),
    Question("repo", "Repository link (the public GitHub repository EA Explorer comes from)",
             lambda a: _installed().get("repo", "") or R.DEFAULT_REPO,
             when=_remote, help="The same link the installer used; the server downloads the release from there."),
    Question("ref", "Version to install (a published release)", "", when=_remote, options=lambda a: release_choices(a.get("repo", "")),
             help="The repository's published GitHub Releases, newest first (never the main branch)."),
    Question("move_from", "Start empty, or move an existing installation here?", "empty",
             {"empty": "Start empty", "backup": "Move an existing installation: restore one of its infrastructure backups"}),
    Question("backup_dir", "The infrastructure backup's folder on this computer (from the old installation's work/backups/infrastructure)",
             "", when=lambda a: a.get("move_from") == "backup"),
    Question("auth", "How the services sign in to each other (R6-C1)", "certificate",
             {"certificate": "Certificates (EA Explorer's own, renewed by themselves; no internal passwords)",
              "password": "Passwords (made here, rotated by themselves every 90 days)"}, when=_server_like),
]
BY_KEY = {q.key: q for q in QUESTIONS}


def release_choices(repo: str, fetcher=None) -> dict[str, str]:
    """The published releases of the repository, newest first ({tag: label}) (R5.6-U2; owner, 16 Nov 2026: releases
    come from the GitHub Releases page, never main). When GitHub cannot be reached it says so and nothing is offered."""
    try:
        rel = R.offered_releases(repo or R.DEFAULT_REPO, "prod", fetcher)
    except R.ReleaseError as exc:
        raise Failure(f"No version can be offered: {exc}") from exc
    if not rel:
        raise Failure(f"{repo or R.DEFAULT_REPO} has no published release yet: nothing can be installed.")
    return {r["tag"]: release_label(r) for r in rel}


def release_label(r: dict) -> str:
    """A release as the drop-down shows it: its version, its title and its date."""
    title = r.get("title") or ""
    return (r["version"] + (f" · {title}" if title and title not in (r["tag"], r["version"]) else "")
            + (f" ({r['date'][:10]})" if r.get("date") else ""))


def visible(answers: dict) -> list[Question]:
    """The questions that apply to these answers, in order."""
    return [q for q in QUESTIONS if q.when(answers)]


def complete(answers: dict) -> dict:
    """The answers with every applicable question filled (defaults for the unanswered); unknown choices refused."""
    out = dict(answers)
    for _ in range(3):                              # a later answer can make earlier defaults apply (kind first)
        for q in visible(out):
            if q.key not in out or out[q.key] is None:
                out[q.key] = q.default_for(out)
            if q.options and not str(out.get(q.key) or "").strip() and q.key in [x.key for x in visible(out)]:
                out[q.key] = next(iter(q.choices_for(out) or {"": ""}))    # the newest published release
    problems = []
    for q in visible(out):
        v = str(out.get(q.key, "")).strip()
        out[q.key] = v
        if q.options and v and not R.TAG.match(v):
            problems.append(f"{q.key}: a published release's tag such as v5.6.0 (not {v!r}: never a branch or a commit)")
        elif q.choices and v not in q.choices:
            problems.append(f"{q.key}: one of {', '.join(q.choices)} (not {v!r})")
        elif q.required and not v and not q.secret:
            problems.append(f"{q.key}: {q.text}")
    if problems:
        raise Failure("Answers missing or not allowed:\n  " + "\n  ".join(problems))
    return out


# ---------------------------------------------------------------- the config file for a server or a cloud machine
def password(length: int = 28) -> str:
    """A long random password of letters and digits only (no $, quotes or URL characters to escape)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(_secrets.choice(alphabet) for _ in range(length))


def server_config(answers: dict, template: Path | None = None) -> tuple[str, dict[str, str]]:
    """work/eaexplorer.env for a server from deploy/templates/eaexplorer.server.env: every change-me password
    generated, the site, the folders and the certificate folder set. Returns (text, the generated secrets)."""
    template = template or ROOT / "deploy" / "templates" / "eaexplorer.server.env"
    data = answers.get("data_dir", "/srv/eax").rstrip("/")
    sets = {
        "EAX_HOSTNAME": answers["hostname"],
        "EAX_ORG_NAME": answers.get("org_name", "My organisation"),
        "EAX_FIRST_ADMIN_EMAIL": answers.get("admin_email", f"eaadmin@{answers['hostname']}"),
        "EAX_DATA_ROOT": data,                 # one base folder, a folder per kind under it (R5.4, D687)
        "EAX_DEPLOYMENT": "server",
    }
    sets["EAX_AUTH_MODE"] = answers.get("auth", "certificate")      # R6-C1: the keys are made on the server itself
    made: dict[str, str] = {}
    lines = []
    seen = set()
    for line in template.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
        if m:
            key, value = m.groups()
            seen.add(key)
            if key in sets:
                v = sets[key]
                line = f"{key}='{v}'" if (" " in v or "$" in v) else f"{key}={v}"
            elif value.startswith("change-me"):
                base = key.removesuffix("_URLENC")
                made.setdefault(base, password(40 if "SECRET" in key or "KEY" in key else 28))
                made[key] = made[base]           # the URL-encoded copy: letters and digits need no encoding
                line = f"{key}={made[key]}"
        lines.append(line)
    for key, v in sets.items():
        if key not in seen:
            lines.append(f"{key}={v}")
    text = "\n".join(lines) + "\n"
    if re.search(r"^[A-Z0-9_]+=['\"]?change-me", text, re.MULTILINE):
        raise Failure("The config still has a change-me value (the template changed?).")
    return text, made


def secret_values(env_text: str) -> dict[str, str]:
    """The passwords and keys of a config file (core.secret_keys: every key the server template holds as change-me,
    and the few it leaves empty)."""
    from .core import secret_keys
    keys = secret_keys()
    out = {}
    for m in re.finditer(r"^([A-Z0-9_]+)=(.*)$", env_text, re.MULTILINE):
        if m.group(1) in keys:
            out[m.group(1)] = m.group(2).strip().strip("'\"")
    return out


# ---------------------------------------------------------------- where the release comes from (D417, D502)
def archive_url(repo: str, ref: str) -> str:
    """The address of a release archive (.tar.gz) of a repository at a tag, branch or commit, without git.
    GitHub and GitLab are known; anything else needs EAX_ARCHIVE_URL (e.g. https://host/{repo}/{ref}.tar.gz) or git."""
    template = os.environ.get("EAX_ARCHIVE_URL", "")
    repo = repo.strip().removesuffix("/").removesuffix(".git")
    if template:
        return template.replace("{repo}", repo).replace("{ref}", ref)
    m = re.match(r"^(?:https?://|git@)(github\.com|gitlab\.com)[/:]([^/]+)/([^/]+)$", repo)
    if not m:
        return ""
    host, owner, name = m.groups()
    if host == "github.com":
        if re.fullmatch(r"[0-9a-f]{7,40}", ref):
            return f"https://github.com/{owner}/{name}/archive/{ref}.tar.gz"
        kind = "tags" if re.match(r"^v\d", ref) else "heads"
        return f"https://github.com/{owner}/{name}/archive/refs/{kind}/{ref}.tar.gz"
    return f"https://gitlab.com/{owner}/{name}/-/archive/{ref}/{name}-{ref}.tar.gz"


def fetch_script(repo: str, ref: str, folder: str) -> str:
    """Shell lines that put the release into folder on a Linux machine: the archive with curl, or a shallow clone."""
    url = archive_url(repo, ref)
    q = shlex.quote
    if url:
        return (f"sudo mkdir -p {q(folder)} && curl -fsSL {q(url)} -o /tmp/eaexplorer.tar.gz && "
                f"sudo tar -xzf /tmp/eaexplorer.tar.gz -C {q(folder)} --strip-components=1 && rm -f /tmp/eaexplorer.tar.gz")
    return (f"(command -v git >/dev/null || (sudo apt-get update -y && sudo apt-get install -y git)) && "
            f"sudo rm -rf /tmp/eaexplorer-src && git clone --depth 1 --branch {q(ref)} {q(repo)} /tmp/eaexplorer-src && "
            f"sudo mkdir -p {q(folder)} && sudo cp -a /tmp/eaexplorer-src/. {q(folder)}/ && sudo rm -rf /tmp/eaexplorer-src")


# ---------------------------------------------------------------- running steps
class StepFailed(Exception):
    """A deployment step failed."""
    pass


@dataclass
class Ctx:
    """What a deployment's steps share: the answers, plan or real, what earlier steps found out and the secrets to mask."""
    answers: dict
    plan: bool = False
    values: dict = field(default_factory=dict)          # what earlier steps found out (an instance ID, an address)
    printed: list = field(default_factory=list)          # the plan, line by line
    mask: set = field(default_factory=set)               # values never written to the log
    env: dict = field(default_factory=dict)              # extra environment for the commands run
    out: Callable[[str], None] = print
    reveal: bool = True                                  # the first password shown once on screen (never from the page)

    def hide(self, text: str) -> str:
        """Text with the secrets masked."""
        for m in sorted(self.mask, key=len, reverse=True):
            if m and len(m) >= 4:
                text = text.replace(m, "********")
        return text

    def note(self, text: str) -> None:
        """Says a line of the deployment (kept for the plan)."""
        text = self.hide(text)
        if self.plan:
            self.printed.append(text)
        self.out(text)
        log_only(text)

    def get(self, key: str, placeholder: str = "") -> str:
        """A value an earlier step found out (a placeholder in a plan)."""
        return self.values.get(key) or placeholder or f"<{key}>"

    def run(self, argv: list[str], what: str = "", input_text: str | None = None, ok_codes: tuple = (0,),
            capture: bool = True, attach: bool = False) -> str:
        """One command here. In plan mode it is only printed."""
        shown = " ".join(shlex.quote(a) for a in argv)
        self.note(f"    $ {shown}" if not what else f"    $ {shown}    # {what}")
        if self.plan:
            return ""
        exe = shutil.which(argv[0]) or argv[0]
        env = {**os.environ, **self.env}
        if attach:
            code = subprocess.run([exe, *argv[1:]], env=env, input=input_text, text=True, check=False).returncode
            out = ""
        else:
            p = subprocess.run([exe, *argv[1:]], env=env, input=input_text, text=True, capture_output=True, check=False)
            code, out = p.returncode, (p.stdout or "")
            log_only(self.hide((p.stdout or "")[-4000:] + (p.stderr or "")[-4000:]))
            if code not in ok_codes:
                raise StepFailed(self.hide(f"{argv[0]} failed (exit {code}): {(p.stderr or p.stdout or '').strip()[-800:]}"))
        if attach and code not in ok_codes:
            raise StepFailed(f"{argv[0]} failed (exit {code})")
        return out if capture else ""

    def ssh_argv(self) -> list[str]:
        """ssh to the target machine, without asking and with a timeout."""
        a = self.answers
        target = self.values.get("ssh_target") or a.get("ssh_target") or "<user@address>"
        return ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                "-i", a.get("ssh_key", ""), "-p", str(a.get("ssh_port", "22")), target]

    def remote(self, script: str, what: str = "", input_text: str | None = None) -> str:
        """Shell lines on the server, over SSH (or here, when this machine is the server)."""
        if not _remote(self.answers):
            return self.run(["bash", "-c", script], what, input_text)
        return self.run([*self.ssh_argv(), script], what, input_text)

    def upload(self, local: Path | str, name: str, what: str = "") -> str:
        """Copies a file to the target (locally, or over SSH) into the stage folder, a folder only the signed-in user may
        open (~/.eaexplorer-stage, 700), never the shared /tmp, where another user of the server could have put a
        file or a link of the same name first (SonarQube S5443, R14); returns where it is, for the shell lines after."""
        self.remote(f"mkdir -p {STAGE_SH} && chmod 700 {STAGE_SH}", "")
        if not _remote(self.answers):
            self.run(["sudo", "cp", str(local), str(Path.home() / STAGE / name)], what)
        else:
            a = self.answers
            target = self.values.get("ssh_target") or a.get("ssh_target") or "<user@address>"
            self.run(["scp", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes", "-i", a.get("ssh_key", ""),
                      "-P", str(a.get("ssh_port", "22")), str(local), f"{target}:{STAGE}/{name}"], what)   # relative: in the home folder
        return f"{STAGE_SH}/{shlex.quote(name)}"           # one return (SonarQube S3516: the same value from two)

    def wait(self, what: str, test: Callable[[], bool], minutes: float = 10, every: float = 10) -> None:
        """Waits until a test passes (at most some minutes)."""
        self.note(f"    (wait until {what}, at most {minutes:g} minutes)")
        if self.plan:
            return
        end = time.monotonic() + minutes * 60
        while time.monotonic() < end:
            try:
                if test():
                    return
            except (StepFailed, OSError):
                pass
            time.sleep(every)
        raise StepFailed(f"Gave up waiting until {what} ({minutes:g} minutes).")


@dataclass
class Step:
    """One step of a deployment: its title and what it does."""
    title: str
    fn: Callable[[Ctx], None]


# ---------------------------------------------------------------- the steps of each kind
def steps_for(a: dict) -> list[Step]:
    """A deployment's steps by its kind (laptop, or a server here or over SSH, D746)."""
    if a["kind"] == "laptop":
        return laptop_steps(a)
    return server_steps(a)


def laptop_steps(a: dict) -> list[Step]:
    """The steps of a laptop installation."""
    from .main import run_self

    def docker(ctx: Ctx):
        ctx.run(["docker", "version", "--format", "Docker {{.Server.Version}}"], "Docker Desktop is running")

    def config(ctx: Ctx):
        env = WORK / "eaexplorer.env"
        if env.exists():
            ctx.note(f"    work/eaexplorer.env exists: kept (to start again from scratch: {EAX} clean-restart)")
            return
        ctx.note(f"    $ {EAX} init laptop")
        if not ctx.plan and run_self(["init", "laptop"]) != 0:
            raise StepFailed(f"{EAX} init laptop failed")

    def up(ctx: Ctx):
        ctx.note(f"    $ {EAX} up")
        if not ctx.plan and run_self(["up"]) != 0:
            raise StepFailed(f"{EAX} up failed: see its log in work/logs")

    def healthy(ctx: Ctx):
        ctx.wait("https://localhost/api/health answers", lambda: _http_ok("https://localhost/api/health"), minutes=10)

    def done(ctx: Ctx):
        ctx.note("    EA Explorer is at https://localhost (run trust once so the browser stops warning).")
        ctx.note(f"    $ {EAX} url")
        if not ctx.plan:
            run_self(["url"])
        for line in check_hint():
            ctx.note(line)

    steps = [Step("Check that Docker Desktop is running", docker), Step("Make the config file (laptop)", config),
             Step("Start EA Explorer", up), Step("Check that it is healthy", healthy)]
    if a.get("move_from") == "backup":
        steps.append(Step("Move the old installation here: restore its backup", restore_local))
    steps.append(Step("Show the address and the logins", done))
    return steps


def check_hint(address: str = "https://localhost") -> list[str]:
    """The three lines shown when a deployment is done (and on the first start): how to check the installation."""
    return ["    Check your installation: System admin > Self-test > Smoke test > Start (it prepares what it needs);",
            f"      or {EAX} test (smoke) or {EAX} test full there.",
            "      Results: Self-test > History (and the report). Steps: docs/deployment.md, \"Check your installation\"."]


def _http_ok(url: str) -> bool:
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(url, timeout=10, context=ctx) as r:
            return r.status == 200
    except OSError:
        return False


def restore_local(ctx: Ctx) -> None:
    """Moving an installation (D505): the old installation's infrastructure backup is put into this one's
    work/backups/infrastructure and restored: every database, then the files (documents, certificate, reports, imports,
    exports). The config file is not restored: this installation keeps its own address and passwords (the database
    logins already here are kept, D410)."""
    from .main import run_self
    src = Path(ctx.answers["backup_dir"]).expanduser()
    name = src.name
    dest = WORK / "backups" / "infrastructure" / name
    ctx.note(f"    copy {src} -> {dest}")
    if not ctx.plan:
        if not (src / "manifest.json").exists() and not any(src.glob("*.json")):
            raise StepFailed(f"{src} does not look like an infrastructure backup (no manifest).")
        shutil.copytree(src, dest, dirs_exist_ok=True)
    for what in ("db", "files"):
        ctx.note(f"    $ {EAX} restore {name} --what {what} --yes")
        if not ctx.plan and run_self(["restore", name, "--what", what, "--yes"]) != 0:
            raise StepFailed(f"{EAX} restore {name} --what {what} failed: see its log in work/logs")


DOCKER_INSTALL = ("if ! command -v docker >/dev/null 2>&1; then curl -fsSL https://get.docker.com -o /tmp/get-docker.sh "
                  "&& sudo sh /tmp/get-docker.sh && sudo systemctl enable --now docker; fi; "
                  "sudo usermod -aG docker \"$(id -un)\" || true; docker --version || sudo docker --version; "
                  "sudo docker compose version")


def server_steps(a: dict) -> list[Step]:
    """A Linux server (this one, or over SSH; a cloud machine just made): Docker, the release, the config, start,
    health, and moving an old installation here."""
    folder, data = a["install_dir"].rstrip("/"), a["data_dir"].rstrip("/")
    q = shlex.quote
    steps: list[Step] = []

    def reach(ctx: Ctx):
        if _remote(ctx.answers):
            ctx.wait("the server answers over SSH", lambda: bool(ctx.remote("echo ok", "sign in over SSH").strip()) or ctx.plan,
                     minutes=8, every=15)
        ctx.remote("uname -sm; . /etc/os-release 2>/dev/null && echo \"$PRETTY_NAME\"; free -g | awk '/Mem/{print $2\" GB memory\"}'",
                   "what the server is")

    def docker(ctx: Ctx):
        ctx.remote(DOCKER_INSTALL, "Docker and Docker Compose (installed from get.docker.com if missing)")

    def disk(ctx: Ctx):
        ctx.remote(f"sudo mkdir -p {q(data)}", "the data folder")

    def release(ctx: Ctx):
        if not _remote(ctx.answers):
            ctx.note(f"    this copy of EA Explorer ({ROOT}) is used on this server")
            ctx.values["folder"] = str(ROOT)
            return
        ctx.remote(fetch_script(a["repo"], a["ref"], folder), f"EA Explorer {a['ref']} from {a['repo']}")
        ctx.remote(f"test -f {q(folder)}/eax.sh && test -f {q(folder)}/docker-compose.yml && sudo chmod +x {q(folder)}/eax.sh "
                   f"{q(folder)}/eaxpy.sh && grep -m1 '^version' {q(folder)}/services/api/version.toml", "check the release")

    def config(ctx: Ctx):
        where = ctx.values.get("folder", folder)
        found = ctx.remote(f"test -f {q(where)}/work/eaexplorer.env && echo exists || true", "a config file there already?")
        if "exists" in found:
            ctx.note("    the server has a config file already: kept as it is (its passwords match its databases)")
            ctx.values["config_text"] = ""
            return
        text, made = server_config(ctx.answers)
        ctx.mask.update(made.values())
        ctx.values["first_admin_password"] = made.get("EAX_FIRST_ADMIN_PASSWORD", "")
        ctx.values["config_text"] = text
        ctx.note(f"    config: {len(made)} passwords and keys generated; site https://{a['hostname']}; data in {data}")
        tmp = WORK / "deploy" / "eaexplorer.env"
        if not ctx.plan:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(text, encoding="utf-8", newline="\n")
            _owner_only(tmp)
        up = ctx.upload(tmp, "eaexplorer.env", "the config file")
        ctx.remote(f"sudo mkdir -p {q(where)}/work/logs {q(where)}/work/backups {q(where)}/work/proxy && "
                   f"for d in databases documents logs backups imports exports certificates reports; do sudo mkdir -p {q(data)}/$d; done && "
                   f"sudo install -m 600 {up} {q(where)}/work/eaexplorer.env && rm -f {up}",
                   "put it in place, readable by its owner only")
        if not ctx.plan:
            tmp.unlink(missing_ok=True)

    def certificate(ctx: Ctx):
        src = Path(a.get("tls_dir", "")).expanduser()
        for f in ("tls.crt", "tls.key"):
            if not ctx.plan and not (src / f).exists():
                raise StepFailed(f"{src / f} is missing.")
            ctx.upload(src / f, f, f"your certificate's {f}")
        ctx.remote(f"sudo install -m 644 {STAGE_SH}/tls.crt {q(data)}/tls/tls.crt && sudo install -m 600 {STAGE_SH}/tls.key {q(data)}/tls/tls.key "
                   f"&& rm -f {STAGE_SH}/tls.crt {STAGE_SH}/tls.key", "into the certificate folder")

    def start(ctx: Ctx):
        where = ctx.values.get("folder", folder)
        ctx.remote(f"cd {q(where)} && sudo ./eax.sh up", "start EA Explorer (the first start builds the images: 10 to 20 minutes)")

    def healthy(ctx: Ctx):
        url = "https://localhost/api/health"
        ctx.wait("EA Explorer answers on the server",
                 lambda: "ok" in ctx.remote(f"curl -fsk -o /dev/null -w ok -H 'Host: {a['hostname']}' {url}", "health"),
                 minutes=20, every=20)

    def restore(ctx: Ctx):
        src = Path(a["backup_dir"]).expanduser()
        where = ctx.values.get("folder", folder)
        name = src.name
        if not ctx.plan and not src.is_dir():
            raise StepFailed(f"{src} is not a folder.")
        archive = WORK / "deploy" / f"{name}.tar.gz"
        ctx.note(f"    pack {src} -> {archive}")
        if not ctx.plan:
            archive.parent.mkdir(parents=True, exist_ok=True)
            import tarfile
            with tarfile.open(archive, "w:gz") as t:
                t.add(src, arcname=name)
        up = ctx.upload(archive, f"{name}.tar.gz", "the backup")
        ctx.remote(f"sudo mkdir -p {q(where)}/work/backups/infrastructure && sudo tar -xzf {up} "
                   f"-C {q(where)}/work/backups/infrastructure && rm -f {up}", "unpack it")
        for what in ("db", "files"):
            ctx.remote(f"cd {q(where)} && sudo ./eax.sh restore {q(name)} --what {what} --yes",
                       f"restore {'every database' if what == 'db' else 'the files'} (the config file stays this server's)")
        if not ctx.plan:
            archive.unlink(missing_ok=True)

    def done(ctx: Ctx):
        pw = ctx.values.get("first_admin_password", "")
        ctx.note(f"    EA Explorer is at https://{a['hostname']}  (reports: https://reports.{a['hostname']}, "
                 f"documents: https://docs.{a['hostname']})")
        ctx.note(f"    First sign-in: eaadmin, with the password in {folder}/work/eaexplorer.env (EAX_FIRST_ADMIN_PASSWORD); "
                 "Keycloak asks for a new one at the first sign-in.")
        if pw and not ctx.plan and ctx.reveal:
            ctx.out(f"    (this time only, on screen and not in the log: the first password is {pw})")
        for line in check_hint(f"https://{a['hostname']}"):
            ctx.note(line)

    steps.append(Step("Reach the server", reach))
    steps.append(Step("Docker on the server (installed if missing)", docker))
    steps.append(Step("The data folder", disk))
    steps.append(Step("Download EA Explorer onto the server" if _remote(a) else "Use this copy of EA Explorer", release))
    steps.append(Step("Make the config file: the site, the folders, every password generated", config))
    if a.get("tls") == "own":
        steps.append(Step("Your certificate", certificate))
    steps.append(Step("Start EA Explorer", start))
    steps.append(Step("Check that it is healthy", healthy))
    if a.get("move_from") == "backup":
        steps.append(Step("Move the old installation here: restore its backup", restore))
    steps.append(Step("The address and the first sign-in", done))
    return steps


def _owner_only(path: Path) -> None:
    if not WINDOWS:
        os.chmod(path, 0o600)


def all_steps(a: dict) -> list[Step]:
    """Every step of a deployment."""
    return steps_for(a)


# ---------------------------------------------------------------- running a whole deployment
RESULT_KEYS = ("ssh_target", "folder")


def run(answers: dict, plan: bool, on_fail: Callable[[Step, str], str], out: Callable[[str], None] = print,
        progress: Callable[[int, int, str, str], None] | None = None, result: dict | None = None,
        reveal: bool = True) -> str:
    """Every step in order. on_fail(step, why) answers retry, back or quit. Returns done, back or quit.
    result (when given) gets what the steps found out that may be shown (an address, a machine's ID), never secrets."""
    a = complete(answers)
    ctx = Ctx(a, plan=plan, out=out, reveal=reveal)
    if result is not None:
        result["_ctx"] = ctx
    ctx.mask.update(str(a.get(k, "")) for k in SECRET_KEYS)
    steps = all_steps(a)
    out(f"{'The plan' if plan else 'Deploying'}: {KINDS[a['kind']]} ({len(steps)} steps)")
    i = 0
    while i < len(steps):
        step = steps[i]
        out("")
        out(f"[{i + 1}/{len(steps)}] {step.title}")
        log_only(f"--- step {i + 1}: {step.title}  {datetime.now().astimezone().isoformat()}")
        if progress:
            progress(i, len(steps), step.title, "running")
        try:
            step.fn(ctx)
        except (StepFailed, Failure, OSError, subprocess.SubprocessError) as exc:
            why = ctx.hide(str(exc))
            log_only(f"FAILED: {why}")
            if progress:
                progress(i, len(steps), step.title, "failed")
            choice = "quit" if plan else on_fail(step, why)
            if choice == "retry":
                continue
            return choice
        if progress:
            progress(i, len(steps), step.title, "done")
        i += 1
    if result is not None:
        result.pop("_ctx", None)
        result.update({k: v for k, v in ctx.values.items() if k in RESULT_KEYS and v})
    out("")
    out("The plan above runs nothing; without --plan it is carried out." if plan else "Done.")
    return "done"


# ---------------------------------------------------------------- the console wizard
def ask(q: Question, answers: dict) -> str:
    """Asks one question in the terminal."""
    default = q.default_for(answers)
    if q.help:
        print(f"  ({q.help})")
    choices = q.choices_for(answers)
    if q.options and choices and default not in choices:
        default = next(iter(choices))                  # the newest release
    if choices:
        keys = list(choices)
        for i, (k, label) in enumerate(choices.items(), 1):
            print(f"  {i}  {label}{'   [default]' if k == default else ''}")
        while True:
            raw = input(f"{q.text} [{keys.index(default) + 1 if default in keys else ''}]: ").strip()
            if not raw and default in keys:
                return default
            if raw.isdigit() and 1 <= int(raw) <= len(keys):
                return keys[int(raw) - 1]
            if raw in keys:
                return raw
            print("  Choose one of the numbers.")
    if q.secret:
        import getpass
        return getpass.getpass(f"{q.text}: ").strip()
    while True:
        raw = input(f"{q.text}{f' [{default}]' if default else ''}: ").strip()
        value = raw or default
        if value or not q.required:
            return value
        print("  This one is needed.")


def console(answers: dict, plan: bool, yes: bool) -> int:
    """The deployment wizard in the terminal: the questions, the plan, then the steps."""
    say("")
    say("EA Explorer deployment (eax deploy, D498). Enter keeps the [default]; Ctrl+C stops.", "cyan")
    while True:
        for q in visible(answers):
            if q.key in answers and answers[q.key] not in (None, ""):
                continue
            answers[q.key] = ask(q, answers)
        try:
            a = complete(answers)
        except Failure as exc:
            say(str(exc), "red")
            for line in str(exc).splitlines()[1:]:
                answers.pop(line.strip().split(":")[0], None)
            continue
        say("")
        say("Your answers:", "cyan")
        for q in visible(a):
            v = a.get(q.key, "")
            say(f"  {q.key:<20} {'********' if q.secret and v else v}")
        if not yes:
            choice = input("Go ahead? (y = yes, p = show the plan first, c = change an answer, q = quit) [y]: ").strip().lower() or "y"
            if choice == "q":
                say("Nothing was changed.")
                return 0
            if choice == "c":
                key = input("Which one (its name above)? ").strip()
                if key in BY_KEY:
                    answers.pop(key, None)
                continue
            if choice == "p":
                run(a, True, lambda s, w: "quit")
                if input("Carry it out now? [y/N]: ").strip().lower() != "y":
                    continue
        if plan:
            run(a, True, lambda s, w: "quit")
            return 0

        def on_fail(step: Step, why: str) -> str:
            say(f"This step failed: {step.title}", "red")
            say(f"  {why}", "red")
            while True:
                c = input("r = retry, b = back to the answers, q = quit [r]: ").strip().lower() or "r"
                if c in ("r", "b", "q"):
                    return {"r": "retry", "b": "back", "q": "quit"}[c]
        result = run(a, False, on_fail, out=say)
        if result == "back":
            answers = dict(a)
            yes = False
            continue
        return 0 if result == "done" else 1


# ---------------------------------------------------------------- the command
def parse(options: list[str]) -> tuple[str, dict, bool, bool]:
    """eax deploy's options: the mode, answers, plan and yes."""
    mode, answers, plan, yes = "", {}, False, False
    it = iter(options)
    for o in it:
        if o in ("--console", "--web"):
            mode = o[2:]
        elif o == "--plan":
            plan = True
        elif o in ("--yes", "-y"):
            yes = True
        elif o == "--kind":
            answers["kind"] = next(it, "")
        elif o == "--answers":
            path = Path(next(it, ""))
            try:
                answers.update({k: str(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()})
            except (OSError, ValueError) as exc:
                raise Failure(f"Could not read the answers file {path}: {exc}") from exc
        elif o == "--set":
            k, _, v = next(it, "").partition("=")
            if k not in BY_KEY:
                raise Failure(f"--set {k}: no such answer. The answers: {', '.join(BY_KEY)}")
            answers[k] = v
        elif o.startswith("--") and o[2:].replace("-", "_") in BY_KEY:
            answers[o[2:].replace("-", "_")] = next(it, "")
        else:
            raise Failure(f"Unknown option {o}. Run {EAX} help deploy")
    if answers.get("kind") and answers["kind"] not in KINDS:
        raise Failure(f"--kind is one of {', '.join(KINDS)}")
    return mode, answers, plan, yes


def main(options: list[str]) -> int:
    """eax deploy: in the terminal or as a web page."""
    from .core import start_log, stop_log
    mode, answers, plan, yes = parse(options)
    if not mode:
        if yes or plan:
            mode = "console"
        else:
            raw = input("Deploy (1) here in the console, or (2) in a web page in your browser? [1/2] ").strip()
            mode = "web" if raw in ("2", "w", "web") else "console"
    start_log("deploy", [o for o in options if not any(s in o for s in ("token", "secret"))])
    try:
        if mode == "web":
            from . import deploy_web
            return deploy_web.serve(answers, plan)
        if yes:
            a = complete(answers)
            result = run(a, plan, lambda s, w: "quit", out=say)
            return 0 if result == "done" else 1
        return console(answers, plan, yes)
    except (Failure, KeyboardInterrupt) as exc:
        say(f"ERROR: {exc}" if isinstance(exc, Failure) else "Stopped.", "red")
        return 1
    finally:
        stop_log()
