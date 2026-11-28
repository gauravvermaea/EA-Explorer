"""What eax prints: the addresses, the logins (laptop), the template hint; the local certificate (D107); following logs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .core import (
    EAX,
    ENV_REL,
    LOG_DIR,
    MAC,
    ROOT,
    STAMP,
    WINDOWS,
    Failure,
    capture,
    compose_args,
    hide_secrets,
    kind,
    log_only,
    paint,
    say,
    setting,
)
from .stack import service_on

CA_SUBJECT = "EA Explorer (self-signed)"      # the organisation in the local CA's subject (deploy/setup)
CA_NAME = "EA Explorer local CA"


def show_urls() -> None:
    """Prints the addresses of EA Explorer's pages."""
    h, p = setting("EAX_HOSTNAME", "localhost"), setting("EAX_HTTPS_PORT", "443")
    s = "" if p == "443" else f":{p}"
    say(f"Start page:  https://{h}{s}/")
    say(f"Swagger:     https://{h}{s}/api/docs")
    if service_on("reports"):
        say(f"Reports:     https://reports.{h}{s}/")
    if service_on("documents"):
        say(f"Documents:   https://docs.{h}{s}/")
    say(f"Keycloak:    https://{h}{s}/auth/admin/")
    if service_on("mcp"):
        say(f"MCP server:  https://{h}{s}/mcp")
    if setting("EAX_HTTP_API_MCP", "false") == "true":
        hp = setting("EAX_HTTP_PORT", "80")
        hs = "" if hp == "80" else f":{hp}"
        say(f"Also on plain http (this computer only): http://localhost{hs}/api/docs and http://localhost{hs}/mcp")
    trust_hint()
    templates_hint()


def templates_hint() -> None:
    """One-time admin task (phase 13, D262): the TOGAF template deliverables, kept in the library folder, never in git."""
    togaf = (ROOT / setting("EAX_LIBRARY_DIR", "./library")) / "templates" / "togaf"
    if togaf.exists() and any(f.suffix.lower() in (".docx", ".doc", ".pptx", ".xlsx") for f in togaf.rglob("*") if f.is_file()):
        return
    say("")
    say("One-time admin task: the TOGAF template deliverables (for architecture projects)", "yellow")
    say("  1. Download 'The TOGAF Standard, 10th Edition - Template Deliverables' (The Open Group publication I094):", "yellow")
    say("     https://publications.opengroup.org/i094", "yellow")
    say("  2. As a Super Admin: Administration > Project library > Upload the TOGAF zip, and choose the zip exactly", "yellow")
    say("     as you downloaded it (each template is stored unchanged, in the background).", "yellow")
    say(f"  Or unzip it into {togaf}, keeping its phase folders (git ignores the files), and press", "yellow")
    say("  Load templates from the folder there. The files are The Open Group's: never commit or share them.", "yellow")


# ---------------------------------------------------------------- the local certificate (D107)
def ca_path() -> Path:
    """The certificate authority's file, to trust."""
    d = setting("EAX_TLS_DIR", "./work/data/tls")
    if "/" not in d and "\\" not in d:
        raise Failure(f"EAX_TLS_DIR is the Docker volume '{d}', not a folder: copy ca.crt out with docker compose cp setup:/tls/ca.crt .")
    return (ROOT / d / "ca.crt").resolve()


def _ps(script: str) -> tuple[int, str]:
    """A short PowerShell script (Windows: the certificate store is reached through it)."""
    return capture(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script])


def _windows_trusted(ca: Path) -> bool:
    code, out = _ps(f"$t=(New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 '{ca}').Thumbprint; "
                    f"@(Get-ChildItem Cert:\\CurrentUser\\Root | Where-Object {{ $_.Thumbprint -eq $t }}).Count")
    return code == 0 and out.strip() not in ("", "0")


def trust_hint() -> None:
    """On Windows: says how to trust the certificate when it is not trusted yet."""
    if not WINDOWS:
        return
    try:
        ca = ca_path()
    except Failure:
        return
    if ca.exists() and not _windows_trusted(ca):
        say(f"Optional: run  {EAX} trust  once so the browser stops warning about the certificate (it survives clean-run).", "yellow")
        say("Without it, accept the warning once for localhost, reports.localhost and docs.localhost, as before.", "yellow")


def trust(options: list[str]) -> None:
    """eax trust: trusts this installation's certificate on the machine (or removes it)."""
    ca = ca_path()
    remove = "--remove" in options
    if WINDOWS:
        ours = f"Get-ChildItem Cert:\\CurrentUser\\Root | Where-Object {{ $_.Subject -like '*O={CA_SUBJECT}*' }}"
        if remove:
            code, out = _ps(f"$o=@({ours}); $o | Remove-Item; $o.Count")
            say(f"Removed {out.strip() or 0} EA Explorer certificate(s) from your trusted root certificates.")
            return
        if not ca.exists():
            raise Failure(f"No {ca} yet: run {EAX} up first (the setup service makes it).")
        if _windows_trusted(ca):
            say("Already trusted.")
        else:
            say("Adding EA Explorer's certificate to your trusted root certificates. Windows asks you to confirm: choose Yes.", "yellow")
            code, _ = _ps(f"$n=New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 '{ca}'; "
                          f"{ours} | Where-Object {{ $_.Thumbprint -ne $n.Thumbprint }} | Remove-Item; "
                          f"Import-Certificate -FilePath '{ca}' -CertStoreLocation Cert:\\CurrentUser\\Root | Out-Null")
            if code != 0:
                raise Failure("The certificate was not added (refused, or Windows did not allow it).")
            say("Trusted. Restart the browser. It may vouch only for this installation's names (localhost and EAX_HOSTNAME).")
        say(f"Firefox: set security.enterprise_roots.enabled to true in about:config, or import {ca} there.")
        say(f'MCP clients that run on Node (Claude Code, mcp-remote): setx NODE_EXTRA_CA_CERTS "{ca}"  and open a new window.')
        return
    keychain = str(Path.home() / "Library/Keychains/login.keychain-db")
    if remove:
        if MAC:
            while subprocess.run(["security", "delete-certificate", "-c", CA_NAME, keychain], capture_output=True, check=False).returncode == 0:
                pass
            say("Removed EA Explorer certificates from your login keychain.")
        else:
            say("Run: sudo rm -f /usr/local/share/ca-certificates/eaexplorer-local-ca.crt && sudo update-ca-certificates --fresh")
        return
    if not ca.exists():
        raise Failure(f"No {ca} yet: run {EAX} up first (the setup service makes it).")
    if MAC:
        while subprocess.run(["security", "delete-certificate", "-c", CA_NAME, keychain], capture_output=True, check=False).returncode == 0:
            pass
        subprocess.run(["security", "add-trusted-cert", "-r", "trustRoot", "-k", keychain, str(ca)], check=False)
        say("Trusted (macOS asks for your password). Restart the browser.")
    else:
        say(f"Run: sudo cp {ca} /usr/local/share/ca-certificates/eaexplorer-local-ca.crt && sudo update-ca-certificates")
        say(f"Chrome and Firefox on Linux keep their own lists: import {ca} there (Settings > Certificates > Authorities).")
    say(f'MCP clients that run on Node (Claude Code, mcp-remote): export NODE_EXTRA_CA_CERTS="{ca}"')


# ---------------------------------------------------------------- the logins (laptop only)
TEST_USERS = [
    ("user_super_admin", "eax-super-admin", "everything, every model"),
    ("demo-super-admin", "eax-super-admin", "for demos: everything; the demo project and its models pinned"),
    ("user_it_admin", "eax-it-admin", "runs the installation; no models"),
    ("user_keycloak_admin", "eax-keycloak-admin", "Keycloak console of the realm"),
    ("user_user_admin", "eax-user-admin", "Users page, role mapping; reads no model"),
    ("user_library_admin", "eax-library-admin", "curates the model library: create, publish, promote, upload, withdraw"),
    ("user_model_creator", "eax-model-creator", "creates models; Model Admin: Karoo Re, Lean EA metamodel, Karoo Digital"),
    ("user_model_admin", "eax-user", "Model Admin: Fynbos group, Fynbos Life, Protea demo; Architect: Sample"),
    ("user_architect", "eax-user", "Architect: Sample, Fynbos Life, Protea demo; Model Sub Admin + Report Viewer: Fynbos Commercial"),
    ("user_model_sub_admin", "eax-user", "Model Sub Admin: Sample, Fynbos Life, Fynbos Commercial, Karoo Re"),
    ("user_committer", "eax-user", "Committer: Protea demo, Sample (commits what others ask to commit)"),
    ("user_history_viewer", "eax-user", "History Viewer and Report Viewer: Protea demo (sees everyone's commits)"),
    ("user_report_viewer", "eax-user", "Report Viewer: Fynbos group, Sample, Protea demo"),
    ("user_global_architect", "eax-user", "Architect on every model"),
    ("user_project_admin", "eax-user", "Project Admin of the sample architecture project (runs its setup and people)"),
    ("user_lead_architect", "eax-user", "Lead Architect of the sample architecture project"),
    ("user_stakeholder", "eax-user", "Stakeholder of the sample architecture project (reads; approves documents in 13.1)"),
]


ADMIN_ACCOUNTS = ("EA Explorer (Keycloak realm)", "Keycloak administrator", "Break-glass account", "Jenkins administrator")


def _who() -> str:
    import getpass
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return "someone"


def show_logins(admins_only: bool = False, asked: bool = False, args: list[str] | None = None) -> None:
    """The user names and passwords (D975): on the screen only, never in a log. A laptop shows them as it always has
    (after eax up and with eax logins); on a server eax logins shows them to whoever can read the config file (who can
    open it already), after YES, and the audit log keeps who looked and when. admins_only: the admin accounts only."""
    args = args or []
    server = kind() != "laptop"
    if server and not asked:
        return                                       # eax up on a server never prints them; eax logins does, when asked
    if server and "--yes" not in args:
        if not sys.stdin.isatty() or os.environ.get("EAX_NONINTERACTIVE"):
            say(f"The passwords are shown only to a person: run {EAX} logins{' --admins' if admins_only else ''} --yes, or in a window.")
            return
        print(paint("The passwords of this installation will be shown on this screen (never written to a log).", "yellow"))
        if input("Type YES to see them: ").strip() != "YES":
            say("Nothing shown.")
            return
    g = setting
    rows = [
        ("EA Explorer (Keycloak realm)", g("EAX_FIRST_ADMIN_USER", "eaadmin"), g("EAX_FIRST_ADMIN_PASSWORD"), "start page sign-in; Superset and Mayan via SSO"),
        ("Keycloak administrator", g("EAX_KC_ADMIN", "kcadmin"), g("EAX_KC_ADMIN_PASSWORD"), "/auth/admin/ (master realm)"),
        ("Superset break-glass admin", "admin", g("EAX_SUPERSET_ADMIN_PASSWORD"), "only when EAX_SUPERSET_AUTH=db"),
        ("Mayan EDMS administrator", g("EAX_MAYAN_ADMIN_USER", "admin"), g("EAX_MAYAN_ADMIN_PASSWORD"), "local Mayan account"),
        ("PostgreSQL superuser", "postgres", g("EAX_DB_SUPERUSER_PASSWORD"), "docker compose exec db psql -U postgres"),
        ("PostgreSQL EA Explorer", "eax_app", g("EAX_DB_PASSWORD"), f"database {g('EAX_DB_NAME', 'eaexplorer')}"),
        ("PostgreSQL reporting (read only)", "eax_report", g("EAX_DB_REPORT_PASSWORD"), "schema rpt"),
        ("PostgreSQL installer", "eax_migrator", g("EAX_DB_MIGRATOR_PASSWORD"), "loads reference models only"),
        ("PostgreSQL Keycloak", "keycloak", g("EAX_KEYCLOAK_DB_PASSWORD"), "database keycloak"),
        ("PostgreSQL Superset", "superset", g("EAX_SUPERSET_DB_PASSWORD"), "database superset"),
        ("PostgreSQL Mayan", "mayan", g("EAX_MAYAN_DB_PASSWORD"), "database mayan"),
        ("PostgreSQL Library", "eax_library", g("EAX_LIBRARY_DB_PASSWORD"), "database eaxlibrary"),
        ("PostgreSQL Views", "eax_views", g("EAX_VIEWS_DB_PASSWORD"), "database eaxviews"),
        ("Mayan broker (Valkey)", "(none)", g("EAX_DMS_BROKER_PASSWORD"), "password only"),
        ("MCP server (development token)", "(bearer)", g("EAX_MCP_DEV_TOKEN"), "https://localhost/mcp or http://localhost/mcp"),
        ("Keycloak client secrets", "superset/mayan", g("EAX_SUPERSET_OIDC_SECRET"), "OIDC clients"),
        ("Keycloak API client (eax-admin)", "eax-admin", g("EAX_KC_SERVICE_SECRET"), "reads people and roles"),
        ("Break-glass account", "break-glass", g("EAX_BREAK_GLASS_PASSWORD"), "when Keycloak is down: start page"),
    ]
    if g("EAX_JENKINS_ADMIN_PASSWORD"):
        rows.append(("Jenkins administrator", g("EAX_JENKINS_ADMIN_USER", "admin"), g("EAX_JENKINS_ADMIN_PASSWORD"),
                     "eax jenkins up, then its address"))
    if admins_only:
        rows = [r for r in rows if r[0] in ADMIN_ACCOUNTS]
    if not server and not admins_only:
        test_pw = g("EAX_TEST_USER_PASSWORD", "") or g("EAX_FIRST_ADMIN_PASSWORD")
        rows += [(f"Test user ({role})", user, test_pw, note) for user, role, note in TEST_USERS]
    title = ("ADMIN LOGINS" if admins_only else "LOGINS") if server else \
        ("DEVELOPMENT ADMIN LOGINS" if admins_only else "DEVELOPMENT LOGINS") + " (laptop only - never use these on a server)"
    # print, never say(): say() writes the line to this command's log too, and no password goes in a log (D975)
    print("")
    print(paint(f"================ {title} ================", "yellow"))
    print(f"{'Account':<38} {'User':<22} {'Password':<16} Notes")
    for r in rows:
        print(f"{r[0]:<38} {r[1]:<22} {r[2]:<16} {r[3]}")
    print(paint("Save the admin and break-glass passwords in your password manager. They are not written to any log.", "yellow"))
    log_only(f"{'admin ' if admins_only else ''}logins shown on the screen to {_who()} (the passwords are not written here)")
    if server:
        try:
            capture(compose_args(["exec", "-T", "api", "python", "-m", "eax.audit_cli", "installation.logins_shown", _who(),
                                  "admins only" if admins_only else "every login"]))
        except Exception:  # noqa: BLE001 - the API not running: this log says it instead
            log_only("the audit log could not be written (the api container is not running)")


def show_part_urls(services: list[str]) -> None:
    """After starting some parts: what started and their addresses."""
    say("")
    say(f"Started: {', '.join(services)} (and what they depend on). The rest stays stopped.")
    if "api" in services:
        say(f"The API goes through nginx: start it too with  {EAX} up api proxy  (no Keycloak needed for public endpoints):")
        say("  Swagger:    https://localhost/api/docs   (laptop also http://localhost/api/docs)")
        say("  Heartbeat:  https://localhost/api/v1/heartbeat")
    say(f"Stop everything with {EAX} down")


def watch_containers(services: list[str]) -> None:
    """Every container's log into work/logs/containers-<stamp>.log (and the console) until Ctrl+C."""
    path = LOG_DIR / f"containers-{STAMP}.log"
    say("")
    say(f"Recording every container's log to {path}", "yellow")
    say("Leave this window open while you test; press Ctrl+C to stop recording (the containers keep running).", "yellow")
    with open(path, "a", encoding="utf-8", newline="\n") as w:
        p = subprocess.Popen(compose_args(["logs", "-f", "--no-color", "--timestamps", "--tail", "500", *services]), cwd=ROOT,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        assert p.stdout is not None
        try:
            for raw in p.stdout:
                line = hide_secrets(raw.rstrip("\n"))
                print(line, flush=True)
                w.write(line + "\n")
        except KeyboardInterrupt:
            p.terminate()
            say("Stopped recording; the containers keep running.")
