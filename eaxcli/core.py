"""The basics every command uses: the folders, this run's log, the config file, docker compose, diagnostics."""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
ENV_FILE = WORK / "eaexplorer.env"
ENV_REL = "work/eaexplorer.env"
LOG_DIR = WORK / "logs"
STAMP = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")   # local time, as the old scripts
WINDOWS = os.name == "nt"
MAC = sys.platform == "darwin"
EAX = ".\\eaxpy" if WINDOWS else "./eaxpy.sh"      # how this command is typed here (for messages)
OFF = ("off", "false", "0", "no", "disabled")


class Failure(Exception):
    """A command stops with a plain message (shown in red, written to the log)."""


# ---------------------------------------------------------------- colours and this run's log
_COLOURS = {"red": "31", "green": "32", "yellow": "33", "cyan": "36", "grey": "90"}
_log = {"file": None, "path": None}


def _colour_ok() -> bool:
    """Colour only on a terminal (R2.10): never when piped or redirected, in CI, or with --no-color / NO_COLOR set,
    so logs and scripts read the same plain text as before."""
    if os.environ.get("NO_COLOR") or os.environ.get("EAX_NO_COLOR") or os.environ.get("CI") or "--no-color" in sys.argv:
        return False
    if not sys.stdout.isatty():
        return False
    if WINDOWS:
        os.system("")     # switches on colour codes in a Windows console
    return True


_USE_COLOUR = _colour_ok()


def paint(text: str, colour: str = "") -> str:
    """Text in a colour (when the terminal shows colours)."""
    return f"\033[{_COLOURS[colour]}m{text}\033[0m" if colour and _USE_COLOUR else text


def no_colour() -> None:
    """--no-color: plain text from here on (R2.10)."""
    global _USE_COLOUR
    _USE_COLOUR = False


# the state words of a container line, as the web's start-up chip and Health page colour them (R2.10)
_RED = ("exited (1", "exited (2", "exited (125", "exited (126", "exited (127", "exited (137", "exited (139", "exited (143",
        "unhealthy", "dead", "restarting", "oomkilled")
_AMBER = ("health: starting", "starting", "created", "paused", "removing")
_GREY_ONE_SHOT = ("setup", "reports-init")


def state_colour(line: str) -> str:
    """The colour of one `docker compose ps` line: red when down or failing, amber while starting, grey for a one-shot
    set-up container that finished, green when up (and healthy)."""
    low = line.lower()
    if any(x in low for x in _GREY_ONE_SHOT) and "exited (0" in low:
        return "grey"
    if any(x in low for x in _RED) or ("exited" in low and "exited (0" not in low):
        return "red"
    if any(x in low for x in _AMBER):
        return "yellow"
    if "up " in low or "running" in low or "(healthy)" in low:
        return "green"
    if "exited (0" in low:
        return "grey"
    return ""


def say_status_lines(lines: list[str]) -> None:
    """`eax status`'s container lines, each in its state's colour (the header line plain)."""
    for i, line in enumerate(lines):
        say(line, "" if i == 0 else state_colour(line))


def ok(text: str) -> None:
    """Says something in green."""
    say(text, "green")


def warn(text: str) -> None:
    """Says something in yellow."""
    say(text, "yellow")


def heading(text: str) -> None:
    """Says something in cyan."""
    say(text, "cyan")


def say(text: str = "", colour: str = "") -> None:
    """To the console (in colour) and to this run's log."""
    print(paint(text, colour), flush=True)
    log_only(text)


def log_only(text: str) -> None:
    """Writes a line to the command's log only."""
    if _log["file"]:
        _log["file"].write(text + "\n")
        _log["file"].flush()


def start_log(name: str, rest: list[str]) -> None:
    """Starts the command's log in work/logs (two weeks of logs kept)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 14 * 86400          # keep two weeks of logs
    for f in LOG_DIR.glob("*.log"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass
    path = LOG_DIR / f"eax-{STAMP}-{name}.log"
    _log["path"] = path
    _log["file"] = open(path, "a", encoding="utf-8", newline="\n")  # noqa: SIM115 - open for the whole run
    log_only(f"=== eax {name} {' '.join(rest)}   {datetime.now().astimezone().isoformat()}")
    log_only(f"=== folder {ROOT}   Python {platform.python_version()}   {platform.platform()}   (eaxpy, D331)")
    print(paint(f"Log: {path}", "grey"), flush=True)


def stop_log() -> None:
    """Ends the command's log."""
    if _log["file"]:
        log_only(f"=== end {datetime.now().astimezone().isoformat()}")
        _log["file"].close()
        _log["file"] = None


def log_path() -> str:
    """The command's log file."""
    return str(_log["path"] or "")


# ---------------------------------------------------------------- secrets kept out of logs
_MASKS = [(re.compile(r"((?:PASSWORD|SECRET|_KEY|URLENC)[A-Z_]*\s*[:=]\s*).*$"), r"\1****"),
          (re.compile(r"(redis://:)[^@]+@"), r"\1****@"),
          (re.compile(r'("PASSWORD"\s*:\s*")[^"]*"'), r'\1****"')]


def hide_secrets(line: str) -> str:
    """A line with passwords, tokens and keys masked."""
    for rx, rep in _MASKS:
        line = rx.sub(rep, line)
    return line


# ---------------------------------------------------------------- running programs
def run_logged(args: list[str], quiet: bool = False, mask: bool = False) -> int:
    """Runs a program; every output line goes to the console (unless quiet) and to the log; returns its exit code."""
    log_only("")
    log_only("> " + " ".join(args))
    try:
        p = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
    except FileNotFoundError:
        log_only(f"< {args[0]} not found")
        if not quiet:
            say(f"{args[0]} is not installed or not on the PATH.", "red")
        return 127
    assert p.stdout is not None
    for raw in p.stdout:
        line = raw.rstrip("\n")
        if mask:
            line = hide_secrets(line)
        if not quiet:
            print(line, flush=True)
        log_only(line)
    code = p.wait()
    log_only(f"< exit {code}")
    return code


def capture(args: list[str]) -> tuple[int, str]:
    """A program's output (standard output only), not shown; (exit code, text)."""
    try:
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except FileNotFoundError:
        return 127, ""
    return r.returncode, r.stdout


def attached(args: list[str]) -> int:
    """A program with this console attached (it can ask questions and show progress); output not logged."""
    log_only("> " + " ".join(args) + "  (interactive: output in this window, not in this log)")
    try:
        return subprocess.run(args, cwd=ROOT, check=False).returncode
    except FileNotFoundError:
        say(f"{args[0]} is not installed or not on the PATH.", "red")
        return 127


# ---------------------------------------------------------------- the config file
def setting(name: str, default: str = "") -> str:
    """A value of the config file; one it holds as a reference to the key vault (R4.19), the vault's value."""
    if not ENV_FILE.exists():
        return default
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            v = line.split("=", 1)[1].strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            if v.startswith("openbao:"):
                vault_env()
                return os.environ.get(name, "") or default
            return v or default
    return default


# ---------------------------------------------------------------- the key vault (R4.19, D684)
_vault = {"done": False}
CREATING = ("up", "run", "create")           # the compose commands that make containers: they need the values


def vault_keys_file() -> Path:
    """Where the key vault's unseal keys are kept."""
    from . import vault
    persist = ""
    if ENV_FILE.exists():
        m = re.search(r"^EAX_PERSIST_DIR=(.*)$", ENV_FILE.read_text(encoding="utf-8"), re.MULTILINE)
        persist = m.group(1).strip().strip("'\"") if m else ""
    return vault.keys_path(ROOT, persist)


def vault_profile() -> None:
    """With the vault, its container is part of every compose command (profile "vault"), so down stops it too."""
    from . import vault
    if ENV_FILE.exists() and vault.where(ENV_FILE.read_text(encoding="utf-8")):
        have = [p for p in os.environ.get("COMPOSE_PROFILES", "").split(",") if p]
        if "vault" not in have:
            os.environ["COMPOSE_PROFILES"] = ",".join([*have, "vault"])


def vault_start() -> None:
    """Starts the vault's container (its profile switched on, whatever the config file says yet: eax secrets migrate runs
    before EAX_SECRETS_FROM is there); a failure to start it is said with docker compose's own words."""
    have = [p for p in os.environ.get("COMPOSE_PROFILES", "").split(",") if p]
    if "vault" not in have:
        os.environ["COMPOSE_PROFILES"] = ",".join([*have, "vault"])
    r = subprocess.run(_compose_base(["up", "-d", "--no-deps", "openbao"]), cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", check=False)
    code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    log_only(out)
    if code != 0:
        raise Failure("docker compose could not start the key vault (openbao): "
                      + " | ".join(ln.strip() for ln in out.splitlines() if ln.strip())[-600:])


def vault_log_tail(lines: int = 25) -> str:
    """The vault container's last log lines, to say why it did not answer (empty when there are none)."""
    code, out = capture(_compose_base(["logs", "--no-color", "--tail", str(lines), "openbao"]))
    out = "\n".join(ln for ln in out.splitlines() if ln.strip())
    return f"\nIts log (the last {lines} lines):\n{out}" if code == 0 and out else ""


def vault_env() -> dict[str, str]:
    """The vault's values for the config file's references, read once into this program's own environment (never a
    file): docker compose takes them from there, as values in its environment win over the config file's. Starts and
    unseals the vault when it needs to (eaxcli/vault.py)."""
    from . import vault
    if _vault["done"] or not ENV_FILE.exists():
        return {}
    text = ENV_FILE.read_text(encoding="utf-8")
    where_ = vault.where(text)
    if not where_ or not vault.references(text):
        return {}
    if not vault.ALLOWED:                        # switched off (R4.19): a config file still pointing there is said
        raise Failure(f"{ENV_REL} keeps its passwords in OpenBao (EAX_SECRETS_FROM), but {vault.OFF}")
    _vault["done"] = True
    vault_profile()

    try:
        client = vault.ready(vault_keys_file(), vault.url_for(text), where_, vault_start, say)
        values = vault.resolve(text, client, where_)
    except vault.VaultError as exc:
        _vault["done"] = False
        raise Failure(f"The key vault: {exc}{vault_log_tail()}") from exc
    os.environ.update(values)
    if not client.audited:
        log_only("The key vault's audit log is off: this OpenBao does not take audit devices through its API.")
    return values


def kind() -> str:
    """The installation's kind (laptop or server)."""
    return setting("EAX_DEPLOYMENT", "laptop")


def copy_config(why: str) -> str:
    """A dated copy of the config file before it changes (work/config-history); its name."""
    hist = WORK / "config-history"
    hist.mkdir(parents=True, exist_ok=True)
    who = re.sub(r"[^A-Za-z0-9_.-]", "-", os.environ.get("USERNAME") or os.environ.get("USER") or "eax")
    name = f"eaexplorer.env.{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.{who}.{why}"
    (hist / name).write_bytes(ENV_FILE.read_bytes())
    return name


def write_setting(name: str, value: str, drop: str = "", section: str = "") -> None:
    """Sets one value in the config file (UTF-8, LF line ends, as Compose reads it cleanly)."""
    lines = [ln for ln in ENV_FILE.read_text(encoding="utf-8").splitlines() if not (drop and re.match(rf"^\s*{drop}\s*=", ln))]
    rx = re.compile(rf"^\s*{re.escape(name)}\s*=")
    if any(rx.match(ln) for ln in lines):
        lines = [f"{name}={value}" if rx.match(ln) else ln for ln in lines]
    else:
        lines += ["", *([section] if section else []), f"{name}={value}"]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- docker compose
def build_id() -> str:
    """The build shown with the release (R2.47): EAX_BUILD as CI sets it, else the commit's short id ("-changed" when
    files differ from it), "dev" outside git."""
    if os.environ.get("EAX_BUILD"):
        return os.environ["EAX_BUILD"]
    code, c = capture(["git", "rev-parse", "--short", "HEAD"])
    if code != 0 or not c.strip():
        return "dev"
    code, changed = capture(["git", "status", "--porcelain", "--untracked-files=no"])
    return c.strip() + ("-changed" if code == 0 and changed.strip() else "")


def release() -> str:
    """The release this folder holds (services/api/version.toml)."""
    m = re.search(r'^version\s*=\s*"(.*)"', (ROOT / "services/api/version.toml").read_text(encoding="utf-8"), re.MULTILINE) \
        if (ROOT / "services/api/version.toml").exists() else None
    return m.group(1) if m else "?"


def _build_env() -> None:
    """EAX_BUILD, EAX_COMMIT and EAX_BUILT_AT for docker compose (the API shows them, R2.47); the commit's own time, so
    the API container is made again only when the commit changes."""
    os.environ["EAX_BUILD"] = build_id()
    if not os.environ.get("EAX_COMMIT"):
        code, c = capture(["git", "rev-parse", "HEAD"])
        os.environ["EAX_COMMIT"] = c.strip() if code == 0 else ""
    if not os.environ.get("EAX_BUILT_AT"):
        code, t = capture(["git", "log", "-1", "--format=%cI"])
        os.environ["EAX_BUILT_AT"] = t.strip() if code == 0 else ""


def compose_args(args: list[str]) -> list[str]:
    """docker compose with the config file, the deployment's compose files, the data folders and the profiles switched
    on."""
    if not ENV_FILE.exists():
        raise Failure(f"No {ENV_REL} yet: run {EAX} init first.")
    vault_profile()
    if args and args[0] in CREATING:
        vault_env()
        folders_env()
    return _compose_base(args)


def folders_env() -> None:
    """Where the data lives (R5.4, D687): with a base folder (EAX_DATA_ROOT), each folder made and checked and its
    value put in this process's environment for docker compose; a base folder that is missing or a folder that cannot
    be written stops the start."""
    if os.environ.get("EAX_FOLDERS_RESOLVED"):
        return
    from . import datafolders
    base, places = datafolders.resolve()
    if not base:
        return
    ok, checks = datafolders.check(base, places)
    say(datafolders.table(base, checks))
    if not ok:
        raise Failure("a data folder cannot be used (above): nothing was started.")
    for line in datafolders.env_lines(places):
        k, v = line.split("=", 1)
        os.environ[k] = v
    os.environ["EAX_FOLDERS_RESOLVED"] = "1"


def _compose_base(args: list[str]) -> list[str]:
    _build_env()
    # plain progress and no colour codes, so the log reads cleanly
    # scale-out extra files (phase 36.3, D521): EAX_COMPOSE_EXTRA=standby,shared-storage... (deploy/compose/scale)
    extra: list[str] = []
    for x in [v for v in setting("EAX_COMPOSE_EXTRA", "").replace(",", " ").split() if v]:
        f = f"deploy/compose/scale/docker-compose.{x}.yml"
        if not (ROOT / f).exists():
            raise Failure(f"EAX_COMPOSE_EXTRA names {x}, but there is no {f}.")
        extra += ["-f", f]
    return ["docker", "compose", "--ansi", "never", "--progress", "plain", "--env-file", ENV_REL,
            "-f", "docker-compose.yml", "-f", f"deploy/compose/docker-compose.{kind()}.yml", *extra, *args]


def compose(args: list[str], no_throw: bool = False, quiet: bool = False) -> int:
    """Runs docker compose (diagnostics collected when it fails)."""
    code = run_logged(compose_args(args), quiet=quiet)
    if code != 0 and not no_throw:
        say(f"docker compose failed (exit {code}). Collecting diagnostics...", "red")
        diagnostics()
        raise Failure(f"docker compose failed (exit {code}). Full log with diagnostics: {log_path()}")
    return code


def compose_out(args: list[str]) -> list[str]:
    """Lines a compose command prints (not shown, not logged); empty when it fails."""
    code, out = capture(compose_args(args))
    return [ln for ln in out.splitlines() if ln.strip()] if code == 0 else []


def docker_ok() -> bool:
    """Whether Docker's engine answers."""
    return capture(["docker", "info", "--format", "{{.ServerVersion}}"])[0] == 0


def assert_docker() -> None:
    """Stops with what to do when Docker is not running."""
    if not docker_ok():
        raise Failure("Docker is not running (or still starting). Start Docker Desktop (or the Docker service), wait until it "
                      "shows 'Engine running', check with: docker version (it must show a Server section), then run this again.")


def version() -> str:
    """The version in services/api/version.toml."""
    m = re.search(r'^version = "(.*)"', (ROOT / "services/api/version.toml").read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1) if m else ""


def diagnostics() -> None:
    """Versions, containers, images, every container's recent log and the (masked) config, into the log."""
    say("")
    say(f"==================== DIAGNOSTICS {datetime.now().astimezone().isoformat()} ====================")
    run_logged(["docker", "version"], quiet=True)
    run_logged(["docker", "compose", "version"], quiet=True)
    run_logged(["docker", "info", "--format", "CPUs {{.NCPU}}  Memory {{.MemTotal}}  Storage {{.Driver}}  OS {{.OperatingSystem}}"], quiet=True)
    run_logged(["docker", "system", "df"], quiet=True)
    if ENV_FILE.exists():
        log_only("")
        log_only(f"> settings in {ENV_REL} (images, site, deployment)")
        for ln in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if re.match(r"^EAX_(IMAGE_|DEPLOYMENT|HOSTNAME|HTTPS?_PORT|VERSION)|^COMPOSE_", ln):
                log_only(ln)
        run_logged(compose_args(["ps", "-a"]), quiet=True)
        run_logged(compose_args(["images"]), quiet=True)
        for s in compose_out(["config", "--services"]):
            run_logged(compose_args(["logs", "--no-color", "--timestamps", "--tail", "300", s]), quiet=True, mask=True)
        run_logged(compose_args(["config"]), quiet=True, mask=True)
    else:
        say(f"No {ENV_REL}: run {EAX} init first.")
    say("==================== END DIAGNOSTICS ====================")
    say(f"Diagnostics saved in {log_path()}", "yellow")
